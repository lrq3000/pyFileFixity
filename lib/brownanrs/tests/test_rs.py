from __future__ import print_function

import itertools
import hashlib

import sys
if sys.version_info < (2, 7):
    import unittest2 as unittest # to get unittest.skip() in Python < 2.7 we need to use unittest2
else:
    import unittest

from .._compat import _range, _izip
from .. import rs

class TestRSencoding(unittest.TestCase):
    def test_small_k(self):
        coder = rs.RSCoder(5, 2)
        mes = [140, 128]
        ecc_good = [182, 242, 0]
        messtr = bytearray(mes)
        if sys.version_info < (2, 7):
            messtr_md5 = hashlib.md5(str(messtr))
        else:
            messtr_md5 = hashlib.md5(messtr)
        self.assertEqual(messtr_md5.hexdigest(), "8052809d008df30342a22e7910d05600")

        mesandecc = coder.encode(messtr)
        mesandeccstr = [ord(x) for x in mesandecc]
        if mesandeccstr == [140, 54, 199, 92, 175]: print("Error in polynomial __divmod__ (probably in the stopping criterion).")
        self.assertEqual(mesandeccstr, mes + ecc_good)

    def test_fast_encode(self):
        '''Test if the fast encoding method is correct'''
        coder = rs.RSCoder(255, 180)
        mes = 'hello world'
        mesecc = coder.encode_fast(mes, k=180).lstrip("\0")
        mesecclist = [ord(x) for x in mesecc]
        # Compare to ground truth
        good_res = [104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 52, 234, 152, 75, 39, 171, 122, 196, 96, 245, 151, 167, 164, 13, 207, 148, 5, 112, 192, 124, 46, 134, 198, 32, 49, 75, 204, 217, 71, 148, 43, 66, 94, 210, 201, 128, 80, 185, 30, 219, 33, 53, 174, 183, 121, 191, 69, 203, 2, 206, 194, 109, 221, 51, 207, 4, 129, 37, 255, 237, 174, 104, 199, 28, 33, 90, 10, 74, 125, 113, 70, 59, 150, 197, 157]
        self.assertEqual(mesecclist, good_res)
        # Compare with the normal encoding method
        nmesecc = coder.encode_fast(mes, k=180).lstrip("\0")
        nmesecclist = [ord(x) for x in nmesecc]
        self.assertEqual(mesecclist, nmesecclist)

class TestRScheck(unittest.TestCase):
    def setUp(self):
        self.coder = rs.RSCoder(255,223)

    def test_check_noerror(self):
        '''Tests a codeword without errors validates'''
        code = self.coder.encode("Hello, world!")

        self.assertTrue(self.coder.check(code))
        self.assertTrue(self.coder.check_fast(code))

    def test_check_oneerror(self):
        '''Verifies that changing any single character will invalidate the
        codeword'''
        code = self.coder.encode("Hello, world! This is a test message, to be encoded,"
                " and verified.")

        for i, c in enumerate(code):
            # Change the value at position i and check that the code is not
            # valid
            # Change it to a 0, unless it's already a 0
            if ord(c) == 0:
                c = chr(1)
            else:
                c = chr(0)
            bad_code = code[:i] + c + code[i+1:]

            self.assertFalse(self.coder.check(bad_code))
            self.assertFalse(self.coder.check_fast(bad_code))

class TestRSdecoding(unittest.TestCase):
    def setUp(self):
        self.coder = rs.RSCoder(255,223)
        self.string = "Hello, world! This is a long string"

        codestr = self.coder.encode(self.string)

        self.code = codestr

    def test_strip(self):
        '''Tests that the nostrip feature works'''
        otherstr = self.string.rjust(223, "\0")
        codestr = self.coder.encode(otherstr)

        self.assertEqual(255, len(codestr))

        # Decode with default behavior: stripping of leading null bytes
        decode, _ = self.coder.decode(codestr)
        decode2, _ = self.coder.decode(codestr[:5] + "\x50" + codestr[6:])

        self.assertEqual(self.string, decode)
        self.assertEqual(self.string, decode2)

        # Decode with nostrip
        decode, _ = self.coder.decode(codestr, nostrip=True)
        decode2, _ = self.coder.decode(codestr[:5] + "\x50" + codestr[6:], nostrip=True)

        self.assertEqual(otherstr, decode)
        self.assertEqual(otherstr, decode2)

    def test_noerr(self):
        '''Make sure a codeword with no errors decodes'''
        decode, _ = self.coder.decode(self.code)
        self.assertEqual(self.string, decode)

    def test_oneerr(self):
        '''Change just one byte and make sure it decodes (and try that by changing one byte for any possible position)'''
        for i, c in enumerate(self.code):
            newch = chr( (ord(c)+50) % 256 )
            r = self.code[:i] + newch + self.code[i+1:]

            decode, _ = self.coder.decode(r)

            self.assertEqual(self.string, decode)

    @unittest.skip("testing skipping")
    def disabled_test_twoerr(self):
        '''Test that changing every combination of 2 bytes still decodes.
        This test is long and probably unnecessary (if it decodes with 1 byte error in any position, it should also work with 2 in any position).'''
        # Test disabled, it takes too long
        for i1, i2 in itertools.combinations(range(len(self.code)), 2):
            r = list(ord(x) for x in self.code)

            # increment the byte by 50
            r[i1] = (r[i1] + 50) % 256
            r[i2] = (r[i2] + 50) % 256

            r = "".join(chr(x) for x in r)
            decode, _ = self.coder.decode(r)
            self.assertEqual(self.string, decode)

    def test_16err(self):
        '''Tests if 16 byte errors still decodes'''
        errors = [5, 6, 12, 13, 38, 40, 42, 47, 50, 57, 58, 59, 60, 61, 62, 65]
        r = list(ord(x) for x in self.code)

        for e in errors:
            r[e] = (r[e] + 50) % 256

        r = "".join(chr(x) for x in r)
        decode, _ = self.coder.decode(r)
        self.assertEqual(self.string, decode)

    def test_16err_fast(self):
        '''Tests if 16 byte errors still decodes with the fast method'''
        errors = [5, 6, 12, 13, 38, 40, 42, 47, 50, 57, 58, 59, 60, 61, 62, 65]
        r = list(ord(x) for x in self.code)

        for e in errors:
            r[e] = (r[e] + 50) % 256

        r = "".join(chr(x) for x in r)
        decode, _ = self.coder.decode_fast(r)
        self.assertEqual(self.string, decode)

    def test_17err(self):
        '''Kinda pointless, checks that 17 errors doesn't decode.
        Actually, this could still decode by coincidence on some inputs,
        so this test shouldn't be here at all.'''
        errors = [5, 6, 12, 13, 22, 38, 40, 42, 47, 50, 57, 58, 59, 60, 61, 62,
                65]
        r = list(ord(x) for x in self.code)

        for e in errors:
            r[e] = (r[e] + 50) % 256

        r = "".join(chr(x) for x in r)
        with self.assertRaises(rs.RSCodecError) as cm:
            decode, _ = self.coder.decode(r)
        #self.assertNotEqual(self.string, decode)

class TestRSdecodinginside(unittest.TestCase):
    '''Check the various local methods that are necessary for decoding'''
    
    def test_bm(self):
        '''Test Berlekamp-Massey decoding and also the analytical equations to calculate directly the erasure/errata locator and evaluator
        The trick here is that the errata locator should always be the same, whether it's solely computed from erasures using the analytical equation, or using Berlekamp-Massey, it doesn't matter.
        '''
        
        orig_mes = bytearray(b"hello world")
        n = len(orig_mes)*2
        k = len(orig_mes)

        fcr=1
        prim=0x11b
        generator=3
        c_exponent=8

        erasenb = 4

        ############################

        # Encode the message and tamper it
        rsman = rs.RSCoder(n, k, fcr=fcr, prim=prim, generator=generator, c_exp=c_exponent)
        rmesecc = bytearray([ord(x) for x in rsman.encode_fast(orig_mes, k=k)])
        rmesecc_orig = rmesecc[:] # make a copy to check later against the original message (only objective way to check if the message was successfully decoded)
        rmesecc[:erasenb] = [0] * erasenb

        # Prepare the erasures positions
        erasures_pos = [x for x in _range(len(rmesecc)) if rmesecc[x] == 0]

        ####

        # Start of decoding
        rp = rsman._list2gfpoly(rmesecc)
        sz = rsman._syndromes(rp, k=k)
        self.assertEqual( list(sz) , [206, 253, 1, 78, 232, 253, 96, 190, 77, 125, 20, 0] )
        coeff_pos = [len(rmesecc)-1-x for x in erasures_pos]
        erasures_count = len(erasures_pos)

        # Compute the erasure locator polynomial
        erasures_loc = rsman._find_erasures_locator(coeff_pos)
        # Compute the erasure evaluator polynomial
        erasures_eval = rsman._find_error_evaluator(sz, erasures_loc, k=k)

        # Compute error locator polynomial without providing the erasures
        sigma, omega = rsman._berlekamp_massey(sz, k=k)
        self.assertEqual( erasures_loc , sigma )
        # same but provide the erasures (so normally BM should not modify the locator polynomial, the output should be equal to the erasures_loc in input)
        sigma, omega = rsman._berlekamp_massey(sz, k=k, erasures_loc=erasures_loc, erasures_eval=erasures_eval, erasures_count=erasures_count)
        self.assertEqual( erasures_loc , sigma )
        # same but with fast BM
        sigma, omega = rsman._berlekamp_massey_fast(sz, k=k)
        self.assertEqual( erasures_loc , sigma )
        sigma, omega = rsman._berlekamp_massey_fast(sz, k=k, erasures_loc=erasures_loc, erasures_eval=erasures_eval, erasures_count=erasures_count)
        self.assertEqual( erasures_loc , sigma )

        # Finally, check against ground truth
        sigma_groundtruth = [120, 210, 102, 219, 1]
        self.assertEqual( list(sigma) , sigma_groundtruth )

        # Bonus: check that the evaluator polynomial is the same, whether:
        self.assertEqual( erasures_eval , omega ) # ... it's computed only from the erasures vs computed from the output of BM simultaneously computed with the errata locator polynomial
        omega2 = rsman._find_error_evaluator(sz, sigma, k=k) # analytical calculation from BM's final errata_locator sigma
        self.assertEqual( omega , omega2 ) # ... it's computed simultaneously in BM vs analytically calculated from BM's final errata_locator sigma

    def test_synd_shift(self):
        '''Test if syndrome computation do not trim automatically the 0 coefficients. This is an edge case (that sometimes the syndromes generate leading 0 coefficients), but it's very important that we don't trim them (at least for the syndromes polynomial) because we need to know the full length of the syndromes polynomial to calculate the correct syndrome shift in Berlekamp-Massey'''
        orig_mes = bytearray(b"hello world")
        n = len(orig_mes)*2
        k = len(orig_mes)

        fcr=1
        prim=0xfd
        generator=3
        c_exponent=7

        erasenb = 5

        rsman = rs.RSCoder(n, k, fcr=fcr, prim=prim, generator=generator, c_exp=c_exponent)
        rmesecc = bytearray([ord(x) for x in rsman.encode(orig_mes, k=k)])
        rmesecc[-erasenb:] = [0] * erasenb
        rmesecc_poly = rsman._list2gfpoly(rmesecc)

        # Compute the syndromes and check that 0 coefficients aren't removed
        synd = rsman._syndromes(rmesecc_poly, k=k)
        self.assertEqual( [int(x) for x in synd] , [0, 75, 112, 28, 95, 77, 73, 113, 22, 29, 100, 0] ) # ground truth comparison
        self.assertEqual( len(synd) , 12 ) # the syndrome's length should be 12, if it's less (because it was trimmed of the leading non significant 0 coefficient), then can't calculate the syndrome shift in BM
        

class TestOtherConfig(unittest.TestCase):
    '''Tests a configuration of the coder other than RS(255,223)'''

    def test255_13(self):
        coder = rs.RSCoder(255,13)
        m = "Hello, world!"
        code = coder.encode(m)

        self.assertTrue( coder.check(code) )
        self.assertEqual(m, coder.decode(code)[0] )

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
        decode, _ = coder.decode(c)
        self.assertEqual(m, decode)

    def test30_10(self):
        '''Tests the RS(30,10) code'''
        coder = rs.RSCoder(30,10)
        m = "Hello, wor"
        code = coder.encode(m)

        self.assertTrue( coder.check(code) )
        self.assertEqual(m, coder.decode(code)[0] )
        self.assertEqual(30, len(code))

        # Change 10 bytes. This code should tolerate up to 10 bytes changed
        changes = [0, 1, 2, 4, 7,
                10, 14, 18, 22, 27]
        c = list(ord(x) for x in code)
        for pos in changes:
            c[pos] = (c[pos] + 50) % 255

        c = "".join(chr(x) for x in c)
        decode, _ = coder.decode(c)
        self.assertEqual(m, decode)

class TestRSCodecUniversalCrossValidation(unittest.TestCase):
    '''Ultimate set of tests of a full set of different parameters for encoding and decoding. If this passes, the codec is universal and can correctly interface with any other RS codec!'''

    def test_main(self):
        def cartesian_product_dict_items(dicts):
            return (dict(_izip(dicts, x)) for x in itertools.product(*dicts.values()))

        debugg = False # if one or more tests don't pass, you can enable this flag to True to get verbose output to debug

        orig_mes = bytearray(b"hello world")
        n = len(orig_mes)*2
        k = len(orig_mes)
        nsym = n-k
        istart = 0

        params = {"count": 5,
                  "fcr": [120, 0, 1, 1, 1],
                  "prim": [0x187, 0x11d, 0x11b, 0xfd, 0xfd],
                  "generator": [2, 2, 3, 3, 2],
                  "c_exponent": [8, 8, 8, 7, 7],
                 }
        cases = {
                 "errmode": [1, 2, 3, 4],
                 "erratasnb_errorsnb_onlyeras": [[8, 3, False], [6, 5, False], [5, 5, False], [11, 0, True], [11, 0, False], [0,0, False]], # errata number (errors+erasures), erasures number and only_erasures: the last item is the value for only_erasures (True/False)
                 }

        ############################$

        results_br = []
        results_rs = []

        it = 0
        for p in _range(params["count"]):
            fcr = params["fcr"][p]
            prim = params["prim"][p]
            generator = params["generator"][p]
            c_exponent = params["c_exponent"][p]

            for case in cartesian_product_dict_items(cases):
                errmode = case["errmode"]
                erratanb = case["erratasnb_errorsnb_onlyeras"][0]
                errnb = case["erratasnb_errorsnb_onlyeras"][1]
                only_erasures = case["erratasnb_errorsnb_onlyeras"][2]
                
                it += 1
                if debugg:
                    print("it ", it)
                    print("param", p)
                    print(case)

                # BROWNANRS
                # Init the RS codec
                rsman = rs.RSCoder(n, k, fcr=fcr, prim=prim, generator=generator, c_exp=c_exponent)
                # Encode the message
                rmesecc = rsman.encode(orig_mes, k=k)
                rmesecc_orig = rmesecc[:] # make a copy of the original message to check later if fully corrected (because the syndrome may be wrong sometimes)
                # Tamper the message
                if erratanb > 0:
                    if errmode == 1:
                        sl = slice(istart, istart+erratanb)
                    elif errmode == 2:
                        sl = slice(-istart-erratanb-(n-k), -(n-k))
                    elif errmode == 3:
                        sl = slice(-istart-erratanb-1, -1)
                    elif errmode == 4:
                        sl = slice(-istart-erratanb, None)
                    if debugg:
                        print("Removed slice:", list(rmesecc[sl]), rmesecc[sl])
                    rmesecc = bytearray([ord(x) for x in rmesecc]) # convert to bytearray (mutable string)
                    rmesecc[sl] = [0] * erratanb # erase some symbols
                    #rmesecc = ''.join(chr(x) for x in rmesecc) # convert back to str
                # Generate the erasures positions (if any)
                erase_pos = [x for x in _range(len(rmesecc)) if rmesecc[x] == 0]
                if errnb > 0: erase_pos = erase_pos[:-errnb] # remove the errors positions (must not be known by definition)
                if debugg:
                    print("erase_pos", erase_pos)
                    print("coef_pos", [len(rmesecc) - 1 - pos for pos in erase_pos])
                    print("Errata total: ", erratanb-errnb + errnb*2, " -- Correctable? ", (erratanb-errnb + errnb*2 <= nsym))
                # Decoding the corrupted codeword
                # -- fast method
                try:
                    rmes, recc = rsman.decode_fast(rmesecc, k=k, erasures_pos=erase_pos, only_erasures=only_erasures)
                    results_br.append( rsman.check(rmes + recc, k=k) ) # check if correct by syndrome analysis (can be wrong)
                    results_br.append( rmesecc_orig == (rmes+recc) ) # check if correct by comparing to the original message (always correct)
                    if debugg and not rsman.check(rmes + recc, k=k) or not (rmesecc_orig == (rmes+recc)): raise rs.RSCodecError("False!!!!!")
                except rs.RSCodecError as exc:
                    results_br.append(False)
                    results_br.append(False)
                    if debugg:
                        print("====")
                        print("ERROR! Details:")
                        print("param", p)
                        print(case)
                        print(erase_pos)
                        print("original_msg", rmesecc_orig)
                        print("tampered_msg", rmesecc)
                        try:
                            print("decoded_msg", rmes+recc)
                            print("checks: ", rsman.check(rmes + recc, k=k), rmesecc_orig == (rmes+recc))
                        except Exception:
                            pass
                        print("====")
                        raise exc
                # -- normal method
                try:
                    rmes, recc = rsman.decode(rmesecc, k=k, erasures_pos=erase_pos, only_erasures=only_erasures)
                    results_br.append( rsman.check(rmes + recc, k=k) )
                    results_br.append( rmesecc_orig == (rmes+recc) )
                except rs.RSCodecError as exc:
                    results_br.append(False)
                    results_br.append(False)

                if debugg: print("-----")

        self.assertTrue(results_br.count(True) == len(results_br))

class TestRSFIXME(unittest.TestCase):
    '''Tests that should not pass (they only pass because of a bug somewhere or a maybe normal limitation of the RS codec)'''

    def test_decode_above_bound(self):
        '''Particular case where a message with too many errors is wrongly decoded (as expected), but the check methods won't report that the decoding failed!
        Maybe we cannot do anything about it (because the decoded message is formally correct and thus it's one of the peculiar cases where RS can't know it even failed)
        or maybe we can implement other checking methods like the ones described in the works of Dilip Sarwate:
        http://www.dsprelated.com/showthread/comp.dsp/15148-1.php
        http://www.ifp.uiuc.edu/~sarwate/malfunction.ps and
        http://www.ifp.uiuc.edu/~sarwate/pubs/Sarwate90Decoder.pdf
        '''
        mes = bytearray(b'hello world')
        n = len(mes)*2
        k = len(mes)
        erase_char = "\x00"

        erasenb = 12 # total number of erratas
        errnb = 1 # total number of errors
        istart = 0
        self.assertTrue( erasenb-errnb + errnb*2 > (n-k) ) # check if we are outside of the bound (too many errors), this should be true in this case because we have 2e+v=2+11=13 > n-k = 11.

        # init the codec
        rsman = rs.RSCoder(n, k) # every set of parameters for generator/prim/fcr will give the same issue (even if the output is different, but in the end, the message won't be decoded correctly but check won't detect the error)
        # encode the message
        rmesecc = bytearray([ord(x) for x in rsman.encode(mes, k=k)])
        rmesecc_orig = rmesecc[:] # copy the original untampered message for later checking
        # tamper the message
        rmesecc[istart:istart+erasenb] = [ord(erase_char)] * erasenb # introduce erratas
        erase_pos = [x for x in _range(len(rmesecc)) if rmesecc[x] == ord(erase_char)] # compute erasures positions
        if errnb > 0: erase_pos = erase_pos[:-errnb] # remove the errors positions (so we only have erasures)
        # decode the message
        rmes, recc = rsman.decode(rmesecc, k=k, erasures_pos=erase_pos)
        # This check, comparing the original message with the decoded message, clearly shows that the decoding failed
        self.assertFalse( (rmes+recc) == rmesecc )
        # But the check methods won't see any problem!
        self.assertTrue( rsman.check(rmes + recc, k=k) )
        self.assertTrue( rsman.check_fast(rmes + recc, k=k) )


if __name__ == "__main__":
    unittest.main()
