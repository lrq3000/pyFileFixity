# Copyright (c) 2010 Andrew Brown <brownan@cs.duke.edu, brownan@gmail.com>
# Copyright (c) 2015 Stephen Larroque <LRQ3000@gmail.com>
# See LICENSE.txt for license terms

from cStringIO import StringIO
from itertools import izip

import numpy as np

# Exponent table for 3, a generator for GF(256)
GF256int_exptable = np.array( [1, 3, 5, 15, 17, 51, 85, 255, 26, 46, 114, 150, 161, 248, 19,
        53, 95, 225, 56, 72, 216, 115, 149, 164, 247, 2, 6, 10, 30, 34,
        102, 170, 229, 52, 92, 228, 55, 89, 235, 38, 106, 190, 217, 112,
        144, 171, 230, 49, 83, 245, 4, 12, 20, 60, 68, 204, 79, 209, 104,
        184, 211, 110, 178, 205, 76, 212, 103, 169, 224, 59, 77, 215, 98,
        166, 241, 8, 24, 40, 120, 136, 131, 158, 185, 208, 107, 189, 220,
        127, 129, 152, 179, 206, 73, 219, 118, 154, 181, 196, 87, 249, 16,
        48, 80, 240, 11, 29, 39, 105, 187, 214, 97, 163, 254, 25, 43, 125,
        135, 146, 173, 236, 47, 113, 147, 174, 233, 32, 96, 160, 251, 22,
        58, 78, 210, 109, 183, 194, 93, 231, 50, 86, 250, 21, 63, 65, 195,
        94, 226, 61, 71, 201, 64, 192, 91, 237, 44, 116, 156, 191, 218,
        117, 159, 186, 213, 100, 172, 239, 42, 126, 130, 157, 188, 223,
        122, 142, 137, 128, 155, 182, 193, 88, 232, 35, 101, 175, 234, 37,
        111, 177, 200, 67, 197, 84, 252, 31, 33, 99, 165, 244, 7, 9, 27,
        45, 119, 153, 176, 203, 70, 202, 69, 207, 74, 222, 121, 139, 134,
        145, 168, 227, 62, 66, 198, 81, 243, 14, 18, 54, 90, 238, 41, 123,
        141, 140, 143, 138, 133, 148, 167, 242, 13, 23, 57, 75, 221, 124,
        132, 151, 162, 253, 28, 36, 108, 180, 199, 82, 246, 1], dtype=int )

# Logarithm table, base 3
GF256int_logtable = np.array([-1, 0, 25, 1, 50, 2, 26, 198, 75, 199, 27, 104, 51, 238, 223,
        3, 100, 4, 224, 14, 52, 141, 129, 239, 76, 113, 8, 200, 248, 105,
        28, 193, 125, 194, 29, 181, 249, 185, 39, 106, 77, 228, 166, 114,
        154, 201, 9, 120, 101, 47, 138, 5, 33, 15, 225, 36, 18, 240, 130,
        69, 53, 147, 218, 142, 150, 143, 219, 189, 54, 208, 206, 148, 19,
        92, 210, 241, 64, 70, 131, 56, 102, 221, 253, 48, 191, 6, 139, 98,
        179, 37, 226, 152, 34, 136, 145, 16, 126, 110, 72, 195, 163, 182,
        30, 66, 58, 107, 40, 84, 250, 133, 61, 186, 43, 121, 10, 21, 155,
        159, 94, 202, 78, 212, 172, 229, 243, 115, 167, 87, 175, 88, 168,
        80, 244, 234, 214, 116, 79, 174, 233, 213, 231, 230, 173, 232, 44,
        215, 117, 122, 235, 22, 11, 245, 89, 203, 95, 176, 156, 169, 81,
        160, 127, 12, 246, 111, 23, 196, 73, 236, 216, 67, 31, 45, 164,
        118, 123, 183, 204, 187, 62, 90, 251, 96, 177, 134, 59, 82, 161,
        108, 170, 85, 41, 157, 151, 178, 135, 144, 97, 190, 220, 252, 188,
        149, 207, 205, 55, 63, 91, 209, 83, 57, 132, 60, 65, 162, 109, 71,
        20, 42, 158, 93, 86, 242, 211, 171, 68, 17, 146, 217, 35, 32, 46,
        137, 180, 124, 184, 38, 119, 153, 227, 165, 103, 74, 237, 222, 197,
        49, 254, 24, 13, 99, 140, 128, 192, 247, 112, 7], dtype=int )

class nPolynomial(object):
    """Polynomial for GF256int class with numpy implementation.
    This class implements vectorized operations on GF256int, thus the type is "defined" implitly in the operations involving GF256int_logtable and GF256int_exptable.

    Polynomial objects are immutable.

    Implementation note: this class is NOT type agnostic, contrariwise to polynomial.py and cpolynomial.py."""
    def __init__(self, coefficients=[], **sparse):
        """
        There are three ways to initialize a Polynomial object.
        1) With a list, tuple, or other iterable, creates a polynomial using
        the items as coefficients in order of decreasing power

        2) With keyword arguments such as for example x3=5, sets the
        coefficient of x^3 to be 5

        3) With no arguments, creates an empty polynomial, equivalent to
        Polynomial((0,))

        >>> print Polynomial((5, 0, 0, 0, 0, 0))
        5x^5

        >>> print Polynomial(x32=5, x64=8)
        8x^64 + 5x^32

        >>> print Polynomial(x5=5, x9=4, x0=2) 
        4x^9 + 5x^5 + 2
        """
        if coefficients is not None and sparse:
            raise TypeError("Specify coefficients list /or/ keyword terms, not"
                    " both")
        if coefficients is not None:
            # Polynomial( [1, 2, 3, ...] )
            #c = coefficients
            #if isinstance(coefficients, tuple): c = list(coefficients)
            # Expunge any leading 0 coefficients
            while len(coefficients) > 0 and coefficients[0] == 0:
                if isinstance(coefficients, np.ndarray):
                    coefficients = np.delete(coefficients, 0)
                else:
                    coefficients.pop(0)
            if len(coefficients) == 0:
                coefficients.append(0)

            self.coefficients = np.array(coefficients, dtype=int)
        elif sparse:
            # Polynomial(x32=...)
            powers = sparse.keys()
            powers.sort(reverse=1)
            # Not catching possible exceptions from the following line, let
            # them bubble up.
            highest = int(powers[0][1:])
            coefficients = [0] * (highest+1)

            for power, coeff in sparse.iteritems():
                power = int(power[1:])
                coefficients[highest - power] = coeff

            self.coefficients = np.array(coefficients, dtype=int)
        else:
            # Polynomial()
            self.coefficients = np.zeros(1, dtype=int)
        self.degree = len(self.coefficients)

    def __len__(self):
        """Returns the number of terms in the polynomial"""
        return self.degree

    def degree(self, poly=None):
        """Returns the degree of the polynomial"""
        if not poly:
            return self.degree - 1
        elif poly and hasattr("coefficients", poly):
            return len(poly.coefficients) - 1
        else:
            while poly and poly[-1] == 0:
                poly.pop()   # normalize
            return len(poly)-1

    def __add__(self, other):
        diff = self.degree - other.degree

        # Warning: value must be absolute, there's no negative value accepted here! (in fact they will be accepted but the result will be meaningless! and divmod will be in infinite loop)
        t1 = np.pad(np.absolute(self.coefficients), (np.max([0, -diff]),0), mode='constant')
        t2 = np.pad(np.absolute(other.coefficients), (np.max([0, diff]),0), mode='constant')

        return self.__class__(np.bitwise_xor(t1,t2))

    def __neg__(self):
        return self.__class__(np.absolute(self.coefficients))
    def __sub__(self, other):
        return self + -other

    def __mul__(self, other):
        result = np.zeros(self.coefficients.size + other.coefficients.size - 1, dtype=int)
        self_coefficients_trimmed = np.trim_zeros(self.coefficients)
        other_coefficients_trimmed = np.trim_zeros(other.coefficients)
        result_tmp = GF256int_exptable[(GF256int_logtable[self_coefficients_trimmed][:, np.newaxis] + GF256int_logtable[other_coefficients_trimmed]) % 255]
        result_tmp[np.where(self_coefficients_trimmed == 0), :] = 0 # VERY important: if az[i] == 0 or bz[i] == 0, then it's not a valid value in GF256, we need to skip it!
        result_tmp[:, np.where(other_coefficients_trimmed == 0)] = 0 # do not np.delete() the rows, else it will offset the n coefficients in x^n!
        for i in np.arange(len(self_coefficients_trimmed)):
            #print i, other.coefficients.size+i, len(result_tmp[i,:]),
            #if not az[i]: print 'Pass'
            #else: print
            #if not az[i]: continue # useless because we already do that in a vectorized way above, using np.where to set whole lines and whole columns to 0
            result[i:other_coefficients_trimmed.size+i] = np.bitwise_xor( result[i:other_coefficients_trimmed.size+i], result_tmp[i,:] )
        return self.__class__(result)

    def _mul_standard(self, other):
        result = np.zeros(self.coefficients.size + other.coefficients.size - 1, dtype=int)
        result_tmp = self.coefficients[:, np.newaxis] * other.coefficients # standard convolution/numpy.polymul
        for i in np.arange(self.degree):
            #print i, other.coefficients.size+i, len(result_tmp[i,:])
            result[i:other.coefficients.size+i] += result_tmp[i,:] # standard convolution/numpy.polymul
        return self.__class__(result)

    def __floordiv__(self, other):
        return divmod(self, other)[0]
    def __mod__(self, other):
        return divmod(self, other)[1]

    def __divmod__(dividend, divisor):
        '''Implementation of the Polynomial Long Division, without recursion. Polynomial Long Division is very similar to a simple division of integers, see purplemath.com. Implementation inspired by the pseudo-code from Rosettacode.org'''
        '''Pseudocode:
        degree(P):
          return the index of the last non-zero element of P;
                 if all elements are 0, return -inf

        polynomial_long_division(N, D) returns (q, r):
          // N, D, q, r are vectors
          if degree(D) < 0 then error
          if degree(N) >= degree(D) then
            q = 0
            while degree(N) >= degree(D)
              d = D shifted right by (degree(N) - degree(D))
              q[degree(N) - degree(D)] = N(degree(N)) / d(degree(d))
              // by construction, degree(d) = degree(N) of course
              d = d * q[degree(N) - degree(D)]
              N = N - d
            endwhile
            r = N
          else
            q = 0
            r = N
          endif
          return (q, r)
          '''
        class_ = dividend.__class__

        # See how many times the highest order term
        # of the divisor can go into the highest order term of the dividend

        dividend_power = dividend.degree
        dividend_coefficient = dividend[0]

        divisor_power = divisor.degree
        divisor_coefficient = divisor[0]

        if divisor_power < 0:
            raise ZeroDivisionError
        elif dividend_power < divisor_power:
            # Doesn't divide at all, return 0 for the quotient and the entire
            # dividend as the remainder
            quotient = class_([0])
            remainder = dividend
        else: # dividend_power >= divisor_power
            quotient = class_([0] * dividend_power) # init the quotient array
            # init the remainder to the dividend, and we will divide it sucessively by the quotient major coefficient
            remainder = dividend
            remainder_power = dividend_power
            remainder_coefficient = dividend_coefficient
            while remainder_power >= divisor_power: # Until there's no remainder left (or the remainder cannot be divided anymore by the divisor)
                quotient_power = remainder_power - divisor_power
                quotient_coefficient = remainder_coefficient / divisor_coefficient
                q = class_( np.pad([quotient_coefficient], (0,quotient_power), mode='constant') ) # construct an array with only the quotient major coefficient (we divide the remainder only with the major coeff)
                quotient = quotient + q # add the coeff to the full quotient
                remainder = remainder - q * divisor # divide the remainder with the major coeff quotient multiplied by the divisor, this gives us the new remainder
                remainder_power = remainder.degree # compute the new remainder degree
                remainder_coefficient = remainder[0] # Compute the new remainder coefficient
                #print "quotient: %s remainder: %s" % (quotient, remainder)
        return quotient, remainder

    def __eq__(self, other):
        return self.coefficients == other.coefficients
    def __ne__(self, other):
        return self.coefficients != other.coefficients
    def __hash__(self):
        return hash(self.coefficients)

    def __repr__(self):
        n = self.__class__.__name__
        return "%s(%r)" % (n, self.coefficients)
    def __str__(self):
        buf = StringIO()
        l = len(self) - 1
        for i, c in enumerate(self.coefficients):
            if not c and i > 0:
                continue
            power = l - i
            if c == 1 and power != 0:
                c = ""
            if power > 1:
                buf.write("%sx^%s" % (c, power))
            elif power == 1:
                buf.write("%sx" % c)
            else:
                buf.write("%s" % c)
            buf.write(" + ")
        return buf.getvalue()[:-3]

    def evaluate(self, x):
        "Evaluate this polynomial at value x, returning the result."
        # Holds the sum over each term in the polynomial
        c = 0

        # Holds the current power of x. This is multiplied by x after each term
        # in the polynomial is added up. Initialized to x^0 = 1
        p = 1

        for term in self.coefficients[::-1]:
            c = c + term * p
            p = p * x

        return c

    def get_coefficient(self, degree):
        """Returns the coefficient of the specified term"""
        if degree > self.degree:
            return 0
        else:
            return self.coefficients[-(degree+1)]

    def __iter__(self):
        return iter(self.coefficients)
        #for item in self.coefficients:
            #yield item

    def  __getitem__(self, slice):
        return self.coefficients[slice]