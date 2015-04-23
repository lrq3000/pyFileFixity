import unittest
import itertools
import hashlib

import rs

class TestRSencoding(unittest.TestCase):
    def test_small_k(self):
        coder = rs.RSCoder(5, 2)
        mes = [140, 128]
        ecc_good = [182, 242, 0]
        messtr = "".join(chr(x) for x in mes)
        self.assertEqual(hashlib.md5(messtr).hexdigest(), "8052809d008df30342a22e7910d05600")

        mesandecc = coder.encode(messtr)
        mesandeccstr = [ord(x) for x in mesandecc]
        if mesandeccstr == [140, 54, 199, 92, 175]: print("Error in polynomial __divmod__ (probably in the stopping criterion).")
        self.assertEqual(mesandeccstr, mes + ecc_good)

    def test_fast_encode(self):
        coder = rs.RSCoder(255, 180)
        mes = 'hello world'
        mesecc = coder.encode_fast(mes, k=180).lstrip("\0")
        mesecclist = [ord(x) for x in mesecc]
        good_res = [104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 52, 234, 152, 75, 39, 171, 122, 196, 96, 245, 151, 167, 164, 13, 207, 148, 5, 112, 192, 124, 46, 134, 198, 32, 49, 75, 204, 217, 71, 148, 43, 66, 94, 210, 201, 128, 80, 185, 30, 219, 33, 53, 174, 183, 121, 191, 69, 203, 2, 206, 194, 109, 221, 51, 207, 4, 129, 37, 255, 237, 174, 104, 199, 28, 33, 90, 10, 74, 125, 113, 70, 59, 150, 197, 157]
        self.assertEqual(mesecclist, good_res)

class TestRSverify(unittest.TestCase):
    def setUp(self):
        self.coder = rs.RSCoder(255,223)

    def test_one(self):
        """Tests a codeword without errors validates"""
        code = self.coder.encode("Hello, world!")

        self.assertTrue(self.coder.verify(code))

    def test_two(self):
        """Verifies that changing any single character will invalidate the
        codeword"""
        code = self.coder.encode("Hello, world! This is a test message, to be encoded,"
                " and verified.")

        for i, c in enumerate(code):
            # Change the value at position i and verify that the code is not
            # valid
            # Change it to a 0, unless it's already a 0
            if ord(c) == 0:
                c = chr(1)
            else:
                c = chr(0)
            bad_code = code[:i] + c + code[i+1:]

            self.assertFalse(self.coder.verify(bad_code))

class TestRSdecoding(unittest.TestCase):
    def setUp(self):
        self.coder = rs.RSCoder(255,223)
        self.string = "Hello, world! This is a long string"

        codestr = self.coder.encode(self.string)

        self.code = codestr

    def test_strip(self):
        """Tests that the nostrip feature works"""
        otherstr = self.string.rjust(223, "\0")
        codestr = self.coder.encode(otherstr)

        self.assertEqual(255, len(codestr))

        # Decode with default behavior: stripping of leading null bytes
        decode = self.coder.decode(codestr)
        decode2 = self.coder.decode(codestr[:5] + "\x50" + codestr[6:])

        self.assertEqual(self.string, decode)
        self.assertEqual(self.string, decode2)

        # Decode with nostrip
        decode = self.coder.decode(codestr, nostrip=True)
        decode2 = self.coder.decode(codestr[:5] + "\x50" + codestr[6:], nostrip=True)

        self.assertEqual(otherstr, decode)
        self.assertEqual(otherstr, decode2)

    def test_noerr(self):
        """Make sure a codeword with no errors decodes"""
        decode = self.coder.decode(self.code)
        self.assertEqual(self.string, decode)

    def test_oneerr(self):
        """Change just one byte and make sure it decodes"""
        for i, c in enumerate(self.code):
            newch = chr( (ord(c)+50) % 256 )
            r = self.code[:i] + newch + self.code[i+1:]

            decode = self.coder.decode(r)

            self.assertEqual(self.string, decode)

    def disabled_test_twoerr(self):
        """Test that changing every combination of 2 bytes still decodes.
        This test is long and probably unnecessary."""
        # Test disabled, it takes too long
        for i1, i2 in itertools.combinations(range(len(self.code)), 2):
            r = list(ord(x) for x in self.code)

            # increment the byte by 50
            r[i1] = (r[i1] + 50) % 256
            r[i2] = (r[i2] + 50) % 256

            r = "".join(chr(x) for x in r)
            decode = self.coder.decode(r)
            self.assertEqual(self.string, decode)

    def test_16err(self):
        """Tests if 16 byte errors still decodes"""
        errors = [5, 6, 12, 13, 38, 40, 42, 47, 50, 57, 58, 59, 60, 61, 62, 65]
        r = list(ord(x) for x in self.code)

        for e in errors:
            r[e] = (r[e] + 50) % 256

        r = "".join(chr(x) for x in r)
        decode = self.coder.decode(r)
        self.assertEqual(self.string, decode)

    def test_17err(self):
        """Kinda pointless, checks that 17 errors doesn't decode.
        Actually, this could still decode by coincidence on some inputs,
        so this test shouldn't be here at all."""
        errors = [5, 6, 12, 13, 22, 38, 40, 42, 47, 50, 57, 58, 59, 60, 61, 62,
                65]
        r = list(ord(x) for x in self.code)

        for e in errors:
            r[e] = (r[e] + 50) % 256

        r = "".join(chr(x) for x in r)
        decode = self.coder.decode(r)
        self.assertNotEqual(self.string, decode)

class TestOtherConfig(unittest.TestCase):
    """Tests a configuration of the coder other than RS(255,223)"""

    def test255_13(self):
        coder = rs.RSCoder(255,13)
        m = "Hello, world!"
        code = coder.encode(m)

        self.assertTrue( coder.verify(code) )
        self.assertEqual(m, coder.decode(code) )

        self.assertEqual(255, len(code))

        # Change 121 bytes. This code should tolerate up to 121 bytes changed
        changes = [1, 4, 5, 6, 9, 10, 14, 15, 19, 20, 21, 24, 26, 30, 32, 34,
                38, 39, 40, 42, 43, 44, 45, 47, 49, 50, 53, 59, 60, 62, 65, 67,
                68, 69, 71, 73, 74, 79, 80, 81, 85, 89, 90, 93, 94, 95, 100,
                101, 105, 106, 107, 110, 112, 117, 120, 121, 123, 126, 127,
                132, 133, 135, 136, 138, 143, 149, 150, 152, 154, 158, 159,
                161, 162, 163, 165, 166, 168, 169, 170, 174, 176, 177, 178,
                179, 182, 186, 191, 192, 193, 196, 197, 198, 200, 203, 206,
                208, 209, 210, 211, 212, 216, 219, 222, 224, 225, 226, 228,
                230, 232, 234, 235, 237, 238, 240, 242, 244, 245, 248, 249,
                250, 253]
        c = list(ord(x) for x in code)
        for pos in changes:
            c[pos] = (c[pos] + 50) % 255

        c = "".join(chr(x) for x in c)
        decode = coder.decode(c)
        self.assertEqual(m, decode)

    def test30_10(self):
        """Tests the RS(30,10) code"""
        coder = rs.RSCoder(30,10)
        m = "Hello, wor"
        code = coder.encode(m)

        self.assertTrue( coder.verify(code) )
        self.assertEqual(m, coder.decode(code) )
        self.assertEqual(30, len(code))

        # Change 10 bytes. This code should tolerate up to 10 bytes changed
        changes = [0, 1, 2, 4, 7,
                10, 14, 18, 22, 27]
        c = list(ord(x) for x in code)
        for pos in changes:
            c[pos] = (c[pos] + 50) % 255

        c = "".join(chr(x) for x in c)
        decode = coder.decode(c)
        self.assertEqual(m, decode)


if __name__ == "__main__":
    unittest.main()
