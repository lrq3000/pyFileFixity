import unittest
import itertools

from ff import GF256int

class TestGF256int(unittest.TestCase):
    def test_arithmetic(self):
        a = GF256int(3)
        b = GF256int(9)

        self.assertEqual(a + b, 10)
        self.assertEqual(b + a, 10)
        self.assertEqual(3 + b, 10)
        self.assertEqual(a + 9, 10)

        self.assertEqual(a - b, 10)
        self.assertEqual(b - a, 10)
        self.assertEqual(3 - b, 10)
        self.assertEqual(a - 9, 10)

        self.assertEqual(a * b, 27)
        self.assertEqual(b * a, 27)
        self.assertEqual(3 * b, 27)
        self.assertEqual(a * 9, 27)

        self.assertEqual(b * b.inverse(), 1)
        self.assertEqual(b / b, 1)

        self.assertEqual(b / a, 7)
        self.assertEqual(9 / a, 7)
        self.assertEqual(b / 3, 7)

        self.assertRaises(Exception, lambda: b**a)
        self.assertEqual(b**3, 127)
        self.assertRaises(Exception, lambda: a**b)
        self.assertEqual(a**9, 46)

        self.assertEqual(b.inverse(), 79)
        self.assertEqual(b * 79, 1)

    def test_fermats_theorem(self):
        for x in range(1,256):
            self.assertEqual(GF256int(x)**255, 1)

    def test_other_multiply(self):

        a = GF256int(3)
        b = GF256int(9)

        self.assertEqual(a * b, a.multiply(b))


if __name__ == "__main__":
    unittest.main()
