# Copyright (c) 2010 Andrew Brown <brownan@cs.duke.edu, brownan@gmail.com>
# See LICENSE.txt for license terms

from StringIO import StringIO

class Polynomial(object):
    """Completely general polynomial class.
    
    Polynomial objects are immutable.
    
    Implementation note: while this class is mostly agnostic to the type of
    coefficients used (as long as they support the usual mathematical
    operations), the Polynomial class still assumes the additive identity and
    multiplicative identity are 0 and 1 respectively. If you're doing math over
    some strange field or using non-numbers as coefficients, this class will
    need to be modified."""
    def __init__(self, coefficients=(), **sparse):
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
        if coefficients and sparse:
            raise TypeError("Specify coefficients list /or/ keyword terms, not"
                    " both")
        if coefficients:
            # Polynomial((1, 2, 3, ...))
            c = list(coefficients)
            # Expunge any leading 0 coefficients
            while c and c[0] == 0:
                c.pop(0)
            if not c:
                c.append(0)

            self.coefficients = tuple(c)
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

            self.coefficients = tuple(coefficients)
        else:
            # Polynomial()
            self.coefficients = (0,)

    def __len__(self):
        """Returns the number of terms in the polynomial"""
        return len(self.coefficients)
    def degree(self):
        """Returns the degree of the polynomial"""
        return len(self.coefficients) - 1

    def __add__(self, other):
        diff = len(self) - len(other)
        if diff > 0:
            t1 = self.coefficients
            t2 = (0,) * diff + other.coefficients
        else:
            t1 = (0,) * (-diff) + self.coefficients
            t2 = other.coefficients

        return self.__class__(x+y for x,y in zip(t1, t2))

    def __neg__(self):
        return self.__class__(-x for x in self.coefficients)
    def __sub__(self, other):
        return self + -other
            
    def __mul__(self, other):
        terms = [0] * (len(self) + len(other))

        for i1, c1 in enumerate(reversed(self.coefficients)):
            if c1 == 0:
                # Optimization
                continue
            for i2, c2 in enumerate(reversed(other.coefficients)):
                terms[i1+i2] += c1*c2

        return self.__class__(reversed(terms))

    def __floordiv__(self, other):
        return divmod(self, other)[0]
    def __mod__(self, other):
        return divmod(self, other)[1]

    def __divmod__(dividend, divisor):
        """Implements polynomial long-division recursively. I know this is
        horribly inefficient, no need to rub it in. I know it can even throw
        recursion depth errors on some versions of Python.

        However, not being a math person myself, I implemented this from my
        memory of how polynomial long division works. It's straightforward and
        doesn't do anything fancy. There's no magic here.
        """
        class_ = dividend.__class__

        # See how many times the highest order term
        # of the divisor can go into the highest order term of the dividend

        dividend_power = dividend.degree()
        dividend_coefficient = dividend.coefficients[0]

        divisor_power = divisor.degree()
        divisor_coefficient = divisor.coefficients[0]

        quotient_power = dividend_power - divisor_power
        if quotient_power < 0:
            # Doesn't divide at all, return 0 for the quotient and the entire
            # dividend as the remainder
            return class_((0,)), dividend

        # Compute how many times the highest order term in the divisor goes
        # into the dividend
        quotient_coefficient = dividend_coefficient / divisor_coefficient
        quotient = class_( (quotient_coefficient,) + (0,) * quotient_power )

        remander = dividend - quotient * divisor

        if remander.coefficients == (0,):
            # Goes in evenly with no remainder, we're done
            return quotient, remander

        # There was a remainder, see how many times the remainder goes into the
        # divisor
        morequotient, remander = divmod(remander, divisor)
        return quotient + morequotient, remander

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

        for term in reversed(self.coefficients):
            c = c + term * p

            p = p * x

        return c

    def get_coefficient(self, degree):
        """Returns the coefficient of the specified term"""
        if degree > self.degree():
            return 0
        else:
            return self.coefficients[-(degree+1)]
