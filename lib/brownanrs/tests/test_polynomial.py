import unittest

from polynomial import Polynomial
from ff import GF2int, init_lut

def map_GF2int(L):
    return list(map(GF2int, L))

class TestGFPoly(unittest.TestCase):
    """Tests that the Polynomial class works when given GF2int objects
    instead of regular integers
    """
    def setUp(self):
        # (Re) initialize the GF tables to avoid conflicts with previously ran tests
        init_lut(generator=3, prim=0x11b, c_exp=8)

    def test_add(self):
        one = Polynomial(map_GF2int([8,3,5,1]))
        two = Polynomial(map_GF2int([5,3,1,1,6,8]))

        r = one + two

        self.assertEqual(list(r.coefficients), [5,3,9,2,3,9])

    def test_sub(self):
        one = Polynomial(map_GF2int([8,3,5,1]))
        two = Polynomial(map_GF2int([5,3,1,1,6,8]))
        r = one - two
        self.assertEqual(list(r.coefficients), [5,3,9,2,3,9])

    def test_mul(self):
        one = Polynomial(map_GF2int([8,3,5,1]))
        two = Polynomial(map_GF2int([5,3,1,1,6,8]))
        r = one * two
        self.assertEqual(list(r.coefficients), [40,23,28,1,53,78,7,46,8])

    def test_mul_at(self):
        one = Polynomial(map_GF2int([2,4,7,3]))
        two = Polynomial(map_GF2int([5,2,4,2]))
        k = 3

        r1 = one * two
        r2 = one.mul_at(two, k)

        self.assertEqual(r1.get_coefficient(k), r2)

    def test_scale(self):
        one = Polynomial(map_GF2int([2,14,7,3]))
        scalar = 12

        r = one.scale(12)

        self.assertEqual(list(r.coefficients), [24, 72, 36, 20])

    def test_div(self):
        one = Polynomial(map_GF2int([8,3,5,1]))
        two = Polynomial(map_GF2int([5,3,1,1,6,8]))
        q, r = divmod(two,one)
        self.assertEqual(list(q.coefficients), [101, 152, 11])
        self.assertEqual(list(r.coefficients), [183, 185, 3])

        # Make sure they multiply back out okay
        self.assertEqual(q*one + r, two)

    def test_div_fast(self):
        one = Polynomial(map_GF2int([8,3,5,1]))
        two = Polynomial(map_GF2int([5,3,1,1,6,8]))

        q, r = two._fastdivmod(one)
        self.assertEqual(list(q.coefficients), [101, 152, 11])
        self.assertEqual(list(r.coefficients), [183, 185, 3])

        # Make sure they multiply back out okay
        self.assertEqual(q*one + r, two)

    def test_div_gffast(self):
        one = Polynomial(map_GF2int([1,3,5,1])) # must be monic! (because the function is optimized for monic divisor polynomial)
        two = Polynomial(map_GF2int([5,3,1,1,6,8]))
        
        q, r = two._gffastdivmod(one) # optimized for monic divisor polynomial

        q2, r2 = two._fastdivmod(one)
        self.assertEqual(q, q2)
        self.assertEqual(r, r2)

        self.assertEqual(list(q.coefficients), [5, 12, 4])
        self.assertEqual(list(r.coefficients), [52, 30, 12])

        # Make sure they multiply back out okay
        self.assertEqual(q*one + r, two)

    def test_div_scalar(self):
        """Tests division by a scalar"""
        numbers = map_GF2int([5,20,50,100,134,158,0,148,233,254,4,5,2])
        scalar = GF2int(17)

        poly = Polynomial(list(numbers))
        scalarpoly = Polynomial(x0=scalar)

        self.assertEqual(
                list((poly // scalarpoly).coefficients),
                [x / scalar for x in numbers]
                )

    def test_div_scalar2(self):
        """Test that dividing by a scalar is the same as multiplying by the
        scalar's inverse"""
        a = Polynomial(map_GF2int([5,3,1,1,6,8]))

        scalar = GF2int(50)

        self.assertEqual(
                a * Polynomial(x0=scalar),
                a // Polynomial(x0=scalar.inverse())
                )

    def test_evaluate(self):
        a = Polynomial(map_GF2int([5,3,1,1,6,8]))
        e = a.evaluate(3)
        self.assertEqual(e, 196)

    def test_evaluate_array(self):
        a = Polynomial(map_GF2int([5,3,1,1,6,8]))
        arr, sum = a.evaluate_array(3)
        self.assertEqual(sum, 196)
        self.assertEqual(list(arr), [255, 51, 15, 5, 10, 8])

    def test_derive(self):
        a = Polynomial(map_GF2int([5,3,1,1,6,8]))
        r = a.derive()
        self.assertEqual(list(r), [17, 12, 3, 2, 6])



class TestPolynomial(unittest.TestCase):
    def test_add_1(self):
        one = Polynomial([2,4,7,3])
        two = Polynomial([5,2,4,2])

        r = one + two

        self.assertEqual(list(r.coefficients), [7, 6, 11, 5])

    def test_add_2(self):
        one = Polynomial([2,4,7,3,5,2])
        two = Polynomial([5,2,4,2])

        r = one + two

        self.assertEqual(list(r.coefficients), [2,4,12,5,9,4])

    def test_add_3(self):
        one = Polynomial([7,3,5,2])
        two = Polynomial([6,8,5,2,4,2])

        r = one + two

        self.assertEqual(list(r.coefficients), [6,8,12,5,9,4])

    def test_mul_1(self):
        one = Polynomial([2,4,7,3])
        two = Polynomial([5,2,4,2])

        r = one * two

        self.assertEqual(list(r.coefficients),
                [10,24,51,49,42,26,6])

    def test_mul_at_1(self):
        one = Polynomial([2,4,7,3])
        two = Polynomial([5,2,4,2])
        k = 3

        r1 = one * two
        r2 = one.mul_at(two, k)

        self.assertEqual(r1.get_coefficient(k), r2)

    def test_scale_1(self):
        one = Polynomial([2,4,7,3])
        scalar = 12

        r = one.scale(12)

        self.assertEqual(list(r.coefficients), [24, 48, 84, 36])

    def test_div_1(self):
        one = Polynomial([1,4,0,3])
        two = Polynomial([1,0,1])

        q, r = divmod(one, two)
        self.assertEqual(q, one // two)
        self.assertEqual(r, one % two)

        self.assertEqual(list(q.coefficients), [1,4])
        self.assertEqual(list(r.coefficients), [-1,-1])

    def test_div_2(self):
        one = Polynomial([1,0,0,2,2,0,1,2,1])
        two = Polynomial([1,0,-1])

        q, r = divmod(one, two)
        self.assertEqual(q, one // two)
        self.assertEqual(r, one % two)

        self.assertEqual(list(q.coefficients), [1,0,1,2,3,2,4])
        self.assertEqual(list(r.coefficients), [4,5])

    def test_div_3(self):
        # 0 quotient
        one = Polynomial([1,0,-1])
        two = Polynomial([1,1,0,0,-1])

        q, r = divmod(one, two)
        self.assertEqual(q, one // two)
        self.assertEqual(r, one % two)

        self.assertEqual(list(q.coefficients), [0])
        self.assertEqual(list(r.coefficients), [1,0,-1])

    def test_div_4(self):
        # no remander
        one = Polynomial([1,0,0,2,2,0,1,-2,-4])
        two = Polynomial([1,0,-1])

        q, r = divmod(one, two)
        self.assertEqual(q, one // two)
        self.assertEqual(r, one % two)

        self.assertEqual(list(q.coefficients), [1,0,1,2,3,2,4])
        self.assertEqual(list(r.coefficients), [0])

    def test_div_fast_1(self):
        # no remander
        one = Polynomial([1,0,0,2,2,0,1,-2,-4])
        two = Polynomial([1,0,-1])

        q, r = one._fastdivmod(two)
        self.assertEqual(q, one._fastfloordiv(two))
        self.assertEqual(r, one._fastmod(two))

        self.assertEqual(list(q.coefficients), [1,0,1,2,3,2,4])
        self.assertEqual(list(r.coefficients), [0])

    def test_getcoeff(self):
        p = Polynomial([9,3,3,2,2,3,1,-2,-4])
        self.assertEqual(p.get_coefficient(0), -4)
        self.assertEqual(p.get_coefficient(2), 1)
        self.assertEqual(p.get_coefficient(8), 9)
        self.assertEqual(p.get_coefficient(9), 0) # try to get a higher coefficient than the length of the polynomial, it should return 0 (non significant high coefficients are removed)

    def test_evaluate(self):
        a = Polynomial([5,3,1,1,6,8])
        e = a.evaluate(3)
        self.assertEqual(e, 1520)

    def test_evaluate_array(self):
        a = Polynomial([5,3,1,1,6,8])
        arr, sum = a.evaluate_array(3)
        self.assertEqual(sum, 1520)
        self.assertEqual(list(arr), [1215, 243, 27, 9, 18, 8])

    def test_derive(self):
        a = Polynomial([5,3,1,1,6,8])
        r = a.derive()
        self.assertEqual(list(r), [25, 12, 3, 2, 6])

if __name__ == "__main__":
    unittest.main()
