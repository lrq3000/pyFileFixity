#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2010 Andrew Brown <brownan@cs.duke.edu, brownan@gmail.com>
# Copyright (c) 2015 Stephen Larroque <LRQ3000@gmail.com>
# See LICENSE.txt for license terms

# TODO: use set instead of list? or bytearray?

from cStringIO import StringIO
from itertools import izip

class Polynomial(object):
    '''Completely general polynomial class.
    
    Polynomial objects are immutable.
    
    Implementation note: while this class is mostly agnostic to the type of
    coefficients used (as long as they support the usual mathematical
    operations), the Polynomial class still assumes the additive identity and
    multiplicative identity are 0 and 1 respectively. If you're doing math over
    some strange field or using non-numbers as coefficients, this class will
    need to be modified.'''

    __slots__ = ['length', 'coefficients', 'degree'] # define all properties to save memory (can't add new properties at runtime)

    def __init__(self, coefficients=None, keep_zero=False, **sparse):
        '''
        There are three ways to initialize a Polynomial object.
        1) With a list, tuple, or other iterable, creates a polynomial using
        the items as coefficients in order of decreasing power

        2) With keyword arguments such as for example x3=5, sets the
        coefficient of x^3 to be 5

        3) With no arguments, creates an empty polynomial, equivalent to
        Polynomial([0])

        >>> print Polynomial([5, 0, 0, 0, 0, 0])
        5x^5

        >>> print Polynomial(x32=5, x64=8)
        8x^64 + 5x^32

        >>> print Polynomial(x5=5, x9=4, x0=2) 
        4x^9 + 5x^5 + 2
        '''
        if coefficients is not None and sparse:
            raise TypeError("Specify coefficients list /or/ keyword terms, not"
                    " both")
        if coefficients is not None:
            # Polynomial( [1, 2, 3, ...] )
            #if isinstance(coefficients, tuple): coefficients = list(coefficients)
            # Expunge any leading (unsignificant) 0 coefficients
            if not keep_zero: # for some polynomials we may want to keep all zeros, even the higher insignificant zeros (eg, for the syndrome polynomial, we need to keep all coefficients because the length is a precious info)
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
        self.length = len(self.coefficients)
        self.degree = self.length-1

    def __len__(self):
        '''Returns the number of terms in the polynomial'''
        return self.length
        # return len(self.coefficients)

    def get_degree(self, poly=None):
        '''Returns the degree of the polynomial'''
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
        if self[0].__class__.__name__ == "GF2int": # optimization: -GF2int(x) == GF2int(x), so it's useless to do a loop in this case
            return self
        else:
            return self.__class__([-x for x in self.coefficients])

    def __sub__(self, other):
        return self + -other

    def __mul__(self, other):
        '''Multiply two polynomials (also works over Galois Fields, but it's a general approach). Algebraically, multiplying polynomials over a Galois field is equivalent to convolving vectors containing the polynomials' coefficients, where the convolution operation uses arithmetic over the same Galois field (see Matlab's gfconv()).'''
        terms = [0] * (len(self) + len(other))

        #l1 = self.degree
        #l2 = other.degree
        l1l2 = self.degree + other.degree
        for i1, c1 in enumerate(self.coefficients):
            if c1 == 0: # log(0) is undefined, skip (and in addition it's a nice optimization)
                continue
            for i2, c2 in enumerate(other.coefficients):
                if c2 == 0: # log(0) is undefined, skip (and in addition it's a nice optimization)
                    continue
                else:
                    #terms[-((l1-i1)+(l2-i2))-1] += c1*c2 # old way, but not optimized because we recompute l1+l2 everytime
                    terms[ -(l1l2-(i1+i2)+1) ] += c1*c2
        return self.__class__(terms)

    def mul_at(self, other, k):
        '''Compute the multiplication between two polynomials only at the specified coefficient (this is a lot cheaper than doing the full polynomial multiplication and then extract only the required coefficient)'''
        if k > (self.degree + other.degree) or k > self.degree: return 0 # optimization: if the required coefficient is above the maximum coefficient of the resulting polynomial, we can already predict that and just return 0

        term = 0

        for i in xrange(min(len(self), len(other))):
            coef1 = self.coefficients[-(k-i+1)]
            coef2 = other.coefficients[-(i+1)]
            if coef1 == 0 or coef2 == 0: continue # log(0) is undefined, skip (and in addition it's a nice optimization)
            term += coef1 * coef2
        return term

    def scale(self, scalar):
        '''Multiply a polynomial with a scalar'''
        return self.__class__([self.coefficients[i] * scalar for i in xrange(len(self))])

    def __floordiv__(self, other):
        return divmod(self, other)[0]
    def __mod__(self, other):
        return divmod(self, other)[1]
    def _fastfloordiv(self, other):
        return self._fastdivmod(other)[0]
    def _fastmod(self, other):
        return self._fastdivmod(other)[1]
    def _gffastfloordiv(self, other):
        return self._gffastdivmod(other)[0]
    def _gffastmod(self, other):
        return self._gffastdivmod(other)[1]

    def _fastdivmod(dividend, divisor):
        '''Fast polynomial division by using Extended Synthetic Division (aka Horner's method). Also works with non-monic polynomials.
        A nearly exact same code is explained greatly here: http://research.swtch.com/field and you can also check the Wikipedia article and the Khan Academy video.'''
        # Note: for RS encoding, you should supply divisor = mprime (not m, you need the padded message)
        msg_out = list(dividend) # Copy the dividend
        normalizer = divisor[0] # precomputing for performance
        for i in xrange(len(dividend)-(len(divisor)-1)):
            msg_out[i] /= normalizer # for general polynomial division (when polynomials are non-monic), the usual way of using synthetic division is to divide the divisor g(x) with its leading coefficient (call it a). In this implementation, this means:we need to compute: coef = msg_out[i] / gen[0]. For more infos, see http://en.wikipedia.org/wiki/Synthetic_division
            coef = msg_out[i] # precaching
            if coef != 0: # log(0) is undefined, so we need to avoid that case explicitly (and it's also a good optimization)
                for j in xrange(1, len(divisor)): # in synthetic division, we always skip the first coefficient of the divisior, because it's only used to normalize the dividend coefficient
                    if divisor[j] != 0: # log(0) is undefined so we need to avoid that case
                        msg_out[i + j] += -divisor[j] * coef

        # The resulting msg_out contains both the quotient and the remainder, the remainder being the size of the divisor (the remainder has necessarily the same degree as the divisor -- not length but degree == length-1 -- since it's what we couldn't divide from the dividend), so we compute the index where this separation is, and return the quotient and remainder.
        separator = -(len(divisor)-1)
        return Polynomial(msg_out[:separator]), Polynomial(msg_out[separator:]) # return quotient, remainder.

    def _gffastdivmod(dividend, divisor):
        '''Fast polynomial division by using Extended Synthetic Division and optimized for GF(2^p) computations (so it is not generic, must be used with GF2int).
        Transposed from the reedsolomon library: https://github.com/tomerfiliba/reedsolomon
        BEWARE: it works only for monic divisor polynomial! (which is always the case with Reed-Solomon's generator polynomials)'''

        msg_out = list(dividend) # Copy the dividend list and pad with 0 where the ecc bytes will be computed
        for i in xrange(len(dividend)-(len(divisor)-1)):
            coef = msg_out[i] # precaching
            if coef != 0: # log(0) is undefined, so we need to avoid that case explicitly (and it's also a good optimization)
                for j in xrange(1, len(divisor)): # in synthetic division, we always skip the first coefficient of the divisior, because it's only used to normalize the dividend coefficient (which is here useless since the divisor, the generator polynomial, is always monic)
                    #if divisor[j] != 0: # log(0) is undefined so we need to check that, but it slow things down in fact and it's useless in our case (reed-solomon encoding) since we know that all coefficients in the generator are not 0
                    msg_out[i + j] ^= divisor[j] * coef # equivalent to the more mathematically correct (but xoring directly is faster): msg_out[i + j] += -divisor[j] * coef
                    # Note: we could speed things up a bit if we could inline the table lookups, but the Polynomial class is generic, it doesn't know anything about the underlying fields and their operators. Good OOP design, bad for performances in Python because of function calls and the optimizations we can't do (such as precomputing gf_exp[divisor]). That's what is done in reedsolo lib, this is one of the reasons it is faster.

        # The resulting msg_out contains both the quotient and the remainder, the remainder being the size of the divisor (the remainder has necessarily the same degree as the divisor -- not length but degree == length-1 -- since it's what we couldn't divide from the dividend), so we compute the index where this separation is, and return the quotient and remainder.
        separator = -(len(divisor)-1)
        return Polynomial(msg_out[:separator]), Polynomial(msg_out[separator:]) # return quotient, remainder.

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
        elif dividend_power < divisor_power: # Incorrect addendum: or (dividend_power == divisor_power and divisor_coefficient > dividend_coefficient):
            # Doesn't divide at all (divisor is too big), return 0 for the quotient and the entire
            # dividend as the remainder
            quotient = class_()
            remainder = dividend
        else: # dividend_power > divisor_power: # Incorrect addendum: or (dividend_power == divisor_power and divisor_coefficient <= dividend_coefficient) , the divisor is small enough and can divide the dividend
            quotient = class_() # init the quotient array
            # init the remainder to the dividend, and we will divide it sucessively by the quotient major coefficient
            remainder = dividend
            remainder_power = dividend_power
            remainder_coefficient = dividend_coefficient
            quotient_power = remainder_power - divisor_power

            # Compute how many times the highest order term in the divisor goes into the dividend
            while quotient_power >= 0 and remainder.coefficients != [0]: # Until there's no remainder left (or the remainder cannot be divided anymore by the divisor)
                quotient_coefficient = remainder_coefficient / divisor_coefficient # in GF256, the division here can be interchanged with multiplication, it doesn't change the result.
                q = class_( [quotient_coefficient] + [0] * quotient_power ) # construct an array with only the quotient major coefficient (we divide the remainder only with the major coeff)
                quotient[quotient_power] = quotient_coefficient # add the coeff to the full quotient. Equivalent to: quotient = quotient + q
                remainder = remainder - q*divisor # divide the remainder with the major coeff quotient multiplied by the divisor, this gives us the new remainder
                remainder_power = remainder.degree # compute the new remainder degree
                remainder_coefficient = remainder[0] # Compute the new remainder coefficient
                quotient_power = remainder_power - divisor_power
        return quotient, remainder

    # def __olddivmod__(dividend, divisor):
        # '''Implements polynomial long-division recursively. I know this is
        # horribly inefficient, no need to rub it in. I know it can even throw
        # recursion depth errors on some versions of Python.

        # However, not being a math person myself, I implemented this from my
        # memory of how polynomial long division works. It's straightforward and
        # doesn't do anything fancy. There's no magic here.
        # '''
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
        '''Evaluate this polynomial at value x, returning the result (which is the sum of all evaluations at each term).'''
        # Holds the sum over each term in the polynomial
        #c = 0

        # Holds the current power of x. This is multiplied by x after each term
        # in the polynomial is added up. Initialized to x^0 = 1
        #p = 1

        #for term in self.coefficients[::-1]:
        #    c = c + term * p
        #    p = p * x
        #return c

        # Faster alternative using Horner's Scheme
        y = self[0]
        for i in xrange(1, len(self)):
            y = y * x + self.coefficients[i]
        return y

    def evaluate_array(self, x):
        '''Simple way of evaluating a polynomial at value x, but here we return both the full array (evaluated at each polynomial position) and the sum'''
        x_gf = self.coefficients[0].__class__(x)
        arr = [self.coefficients[-i]*x_gf**(i-1) for i in xrange(len(self), 0, -1)]
        # if x == 1: arr = sum(self.coefficients)
        return arr, sum(arr)

    def derive(self):
        '''Compute the formal derivative of the polynomial: sum(i*coeff[i] x^(i-1))'''
        #res = [0] * (len(self)-1) # pre-allocate the list, it will be one item shorter because the constant coefficient (x^0) will be removed
        #for i in xrange(2, len(self)+1): # start at 2 to skip the first coeff which is useless since it's a constant (x^0) so we +1, and because we work in reverse (lower coefficients are on the right) so +1 again
            #res[-(i-1)] = (i-1) * self[-i] # self[-i] == coeff[i] and i-1 is the x exponent (eg: x^1, x^2, x^3, etc.)
        #return Polynomial(res)

        # One liner way to do it (also a bit faster too)
        #return Polynomial( [(i-1) * self[-i] for i in xrange(2, len(self)+1)][::-1] )
        # Another faster version
        L = len(self)-1
        return Polynomial( [(L-i) * self[i] for i in xrange(0, len(self)-1)] )

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
        return self.coefficients[slice] # TODO: should return 0 for coefficients higher than the degree (but debugging would be harder...)

    def __setitem__(self, key, item):
        '''Set or create a coefficient value, the key being the coefficient order (not the internal list index)'''
        if key < self.length:
            self.coefficients[-key-1] = item
        else:
            self.coefficients = [item] + [0]*(key-self.length) + list(self.coefficients)
            self.length = len(self.coefficients)
            self.degree = self.length-1
