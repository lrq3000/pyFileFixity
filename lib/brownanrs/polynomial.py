# Copyright (c) 2010 Andrew Brown <brownan@cs.duke.edu, brownan@gmail.com>
# Copyright (c) 2015 Stephen Larroque <LRQ3000@gmail.com>
# See LICENSE.txt for license terms

# TODO: use set instead of list? or bytearray?

from cStringIO import StringIO
from itertools import izip

class Polynomial(object):
    """Completely general polynomial class.
    
    Polynomial objects are immutable.
    
    Implementation note: while this class is mostly agnostic to the type of
    coefficients used (as long as they support the usual mathematical
    operations), the Polynomial class still assumes the additive identity and
    multiplicative identity are 0 and 1 respectively. If you're doing math over
    some strange field or using non-numbers as coefficients, this class will
    need to be modified."""
    def __init__(self, coefficients=None, **sparse):
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
            #if isinstance(coefficients, tuple): coefficients = list(coefficients)
            # Expunge any leading 0 coefficients
            while len(coefficients) > 0 and coefficients[0] == 0:
                coefficients.pop(0)
            if not coefficients:
                coefficients.append(0)

            self.coefficients = coefficients
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

            self.coefficients = coefficients
        else:
            # Polynomial()
            self.coefficients = [0]
        # In any case, compute the degree of the polynomial (=the maximum degree)
        self.degree = len(self.coefficients)-1

    def __len__(self):
        """Returns the number of terms in the polynomial"""
        return self.degree+1
        # return len(self.coefficients)

    def get_degree(self, poly=None):
        """Returns the degree of the polynomial"""
        if not poly:
            return self.degree
            #return len(self.coefficients) - 1
        elif poly and hasattr("coefficients", poly):
            return len(poly.coefficients) - 1
        else:
            while poly and poly[-1] == 0:
                poly.pop()   # normalize
            return len(poly)-1

    def __add__(self, other):
        diff = len(self) - len(other)
        t1 = [0] * (-diff) + self.coefficients
        t2 = [0] * diff + other.coefficients
        return self.__class__([x+y for x,y in izip(t1, t2)])

    def __neg__(self):
        if self[0].__class__.__name__ == "GF256int": # optimization: -GF256int(x) == GF256int(x), so it's useless to do a loop in this case
            return self
        else:
            return self.__class__([-x for x in self.coefficients])

    def __sub__(self, other):
        return self + -other

    def __mul__(self, other):
        terms = [0] * (len(self) + len(other))

        l1 = self.degree
        l2 = other.degree
        for i1, c1 in enumerate(self.coefficients):
            if c1 == 0:
                # Optimization
                continue
            for i2, c2 in enumerate(other.coefficients):
                if c2 == 0:
                    continue
                else:
                    terms[-((l1-i1)+(l2-i2))-1] += c1*c2
        return self.__class__(terms)

    def __floordiv__(self, other):
        return divmod(self, other)[0]
    def __mod__(self, other):
        return divmod(self, other)[1]
    
    def _fastmod(dividend, divisor, nsym):
        '''Fast polynomial division by using Synthetic division (Horner's method)? Returns only the quotient (no remainder). Transposed from the reedsolomon library: https://github.com/tomerfiliba/reedsolomon'''
        msg_out = [0] * (len(dividend) + nsym)
        msg_out[:len(dividend)] = dividend
        for i in range(0, len(dividend)):
            coef = msg_out[i]
            if coef != 0: # optimization, avoid computing something useless
                for j in range(0, len(divisor)):
                    if divisor[j] != 0: msg_out[i + j] += divisor[j] * coef
        return Polynomial(msg_out[len(dividend):])

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
            quotient = class_()
            remainder = dividend
        else: # dividend_power >= divisor_power
            quotient = class_() # init the quotient array
            # init the remainder to the dividend, and we will divide it sucessively by the quotient major coefficient
            remainder = dividend
            remainder_power = dividend_power
            remainder_coefficient = dividend_coefficient
            quotient_power = remainder_power - divisor_power # need to set at least 1 just to start the loop. Warning if set to remainder_power - divisor_power: because it may skip the loop altogether (and we want to at least do one iteration to set the quotient)

            # Compute how many times the highest order term in the divisor goes into the dividend
            while quotient_power >= 0 and remainder.coefficients != [0]: # Until there's no remainder left (or the remainder cannot be divided anymore by the divisor)
                quotient_coefficient = remainder_coefficient / divisor_coefficient
                q = class_( [quotient_coefficient] + [0] * quotient_power ) # construct an array with only the quotient major coefficient (we divide the remainder only with the major coeff)
                quotient = quotient + q # add the coeff to the full quotient
                remainder = remainder - q * divisor # divide the remainder with the major coeff quotient multiplied by the divisor, this gives us the new remainder
                remainder_power = remainder.degree # compute the new remainder degree
                remainder_coefficient = remainder[0] # Compute the new remainder coefficient
                quotient_power = remainder_power - divisor_power
        return quotient, remainder

    # def __olddivmod__(dividend, divisor):
        # """Implements polynomial long-division recursively. I know this is
        # horribly inefficient, no need to rub it in. I know it can even throw
        # recursion depth errors on some versions of Python.

        # However, not being a math person myself, I implemented this from my
        # memory of how polynomial long division works. It's straightforward and
        # doesn't do anything fancy. There's no magic here.
        # """
        # class_ = dividend.__class__

        # # See how many times the highest order term
        # # of the divisor can go into the highest order term of the dividend

        # dividend_power = dividend.degree
        # dividend_coefficient = dividend.coefficients[0]

        # divisor_power = divisor.degree
        # divisor_coefficient = divisor.coefficients[0]

        # quotient_power = dividend_power - divisor_power
        # if quotient_power < 0:
            # # Doesn't divide at all, return 0 for the quotient and the entire
            # # dividend as the remainder
            # return class_([0]), dividend

        # # Compute how many times the highest order term in the divisor goes
        # # into the dividend
        # quotient_coefficient = dividend_coefficient / divisor_coefficient
        # quotient = class_( [quotient_coefficient] + [0] * quotient_power )

        # remainder = dividend - quotient * divisor

        # if remainder.coefficients == [0]:
            # # Goes in evenly with no remainder, we're done
            # return quotient, remainder

        # # There was a remainder, see how many times the remainder goes into the
        # # divisor
        # morequotient, remainder = divmod(remainder, divisor)
        # return quotient + morequotient, remainder

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
        '''Evaluate this polynomial at value x, returning the result.'''
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
        '''Returns the coefficient of the specified term'''
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
