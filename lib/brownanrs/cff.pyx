# -*- coding: utf-8 -*-

# Copyright (c) 2010 Andrew Brown <brownan@cs.duke.edu, brownan@gmail.com>
# Copyright (c) 2015 Stephen Larroque <LRQ3000@gmail.com>
# See LICENSE.txt for license terms

# For fast software computation in Finite Fields, see the excellent paper: Huang, Cheng, and Lihao Xu. "Fast software implementation of finite field operations." Washington University in St. Louis, Tech. Rep (2003).
# to understand the basic mathematical notions behind finite fields, see the excellent tutorial: http://research.swtch.com/field

import cython
cimport cython

from ._compat import _range

from cpython cimport array

# Galois Field's characteristic, by default, it's GF(2^8) == GF(256)
# Note that it's -1 (thus for GF(2^8) it's really 255 and not 256) because this is historically tied to the definition of Reed-Solomon codes: since the 0 and 256 values are impossible, we effectively have only 255 possible values. But later were defined (singly) extended Reed-Solomon codes, which include the 0 and thus 256 values, and then doubly extended Reed-Solomon codes which include the 0 and 256 == infinity.
cdef int GF2_charac = int(2**8 - 1)
cdef int GF2_c_exp = 8

# Exponent table for generator=3 and prim=0x11b in GF(2^8)
cdef array.array GF2int_exptable_a = array.array('i', [1, 3, 5, 15, 17, 51, 85, 255, 26, 46, 114, 150, 161, 248, 19,
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
            132, 151, 162, 253, 28, 36, 108, 180, 199, 82, 246, 1])
cdef int[::1] GF2int_exptable = GF2int_exptable_a

# Logarithm table for the same GF parameters
# Note: do NOT use cdef int* GF2int_logtable = [...], it will be faster but return wrong results!
cdef array.array GF2int_logtable_a = array.array('i', [-1, 0, 25, 1, 50, 2, 26, 198, 75, 199, 27, 104, 51, 238, 223, # None was replaced by -1, because Cython doesn't support None nor NULL in arrays
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
            49, 254, 24, 13, 99, 140, 128, 192, 247, 112, 7])
cdef int[::1] GF2int_logtable = GF2int_logtable_a

def rwh_primes1(n):
    # http://stackoverflow.com/questions/2068372/fastest-way-to-list-all-primes-below-n-in-python/3035188#3035188
    ''' Returns  a list of primes < n '''
    sieve = [True] * (n/2)
    for i in _range(3,int(n**0.5)+1,2):
        if sieve[i/2]:
            sieve[i*i/2::i] = [False] * ((n-i*i-1)/(2*i)+1)
    return [2] + [2*i+1 for i in _range(1,n/2) if sieve[i]]

def find_prime_polynomials(generator=2, c_exp=8, fast_primes=False, single=False):
    '''Compute the list of prime polynomials for the given generator and galois field characteristic exponent.'''
    # fast_primes will output less results but will be significantly faster.
    # single will output the first prime polynomial found, so if all you want is to just find one prime polynomial to generate the LUT for Reed-Solomon to work, then just use that.

    # A prime polynomial (necessarily irreducible) is necessary to reduce the multiplications in the Galois Field, so as to avoid overflows.
    # Why do we need a "prime polynomial"? Can't we just reduce modulo 255 (for GF(2^8) for example)? Because we need the values to be unique.
    # For example: if the generator (alpha) = 2 and c_exp = 8 (GF(2^8) == GF(256)), then the generated Galois Field (0, 1, α, α^1, α^2, ..., α^(p-1)) will be galois field it becomes 0, 1, 2, 4, 8, 16, etc. However, upon reaching 128, the next value will be doubled (ie, next power of 2), which will give 256. Then we must reduce, because we have overflowed above the maximum value of 255. But, if we modulo 255, this will generate 256 == 1. Then 2, 4, 8, 16, etc. giving us a repeating pattern of numbers. This is very bad, as it's then not anymore a bijection (ie, a non-zero value doesn't have a unique index). That's why we can't just modulo 255, but we need another number above 255, which is called the prime polynomial.
    # Why so much hassle? Because we are using precomputed look-up tables for multiplication: instead of multiplying a*b, we precompute alpha^a, alpha^b and alpha^(a+b), so that we can just use our lookup table at alpha^(a+b) and get our result. But just like in our original field we had 0,1,2,...,p-1 distinct unique values, in our "LUT" field using alpha we must have unique distinct values (we don't care that they are different from the original field as long as they are unique and distinct). That's why we need to avoid duplicated values, and to avoid duplicated values we need to use a prime irreducible polynomial.

    # Here is implemented a bruteforce approach to find all these prime polynomials, by generating every possible prime polynomials (ie, every integers between field_charac+1 and field_charac*2), and then we build the whole Galois Field, and we reject the candidate prime polynomial if it duplicates even one value or if it generates a value above field_charac (ie, cause an overflow).
    # Note that this algorithm is slow if the field is too big (above 12), because it's an exhaustive search algorithm. There are probabilistic approaches, and almost surely prime approaches, but there is no determistic polynomial time algorithm to find irreducible monic polynomials. More info can be found at: http://people.mpi-inf.mpg.de/~csaha/lectures/lec9.pdf
    # Another faster algorithm may be found at Adleman, Leonard M., and Hendrik W. Lenstra. "Finding irreducible polynomials over finite fields." Proceedings of the eighteenth annual ACM symposium on Theory of computing. ACM, 1986.

    # Prepare the finite field characteristic (2^p - 1), this also represent the maximum possible value in this field
    root_charac = 2 # we're in GF(2)
    field_charac = int(root_charac**c_exp - 1)
    field_charac_next = int(root_charac**(c_exp+1) - 1)

    prim_candidates = []
    if fast_primes:
        prim_candidates = rwh_primes1(field_charac_next) # generate maybe prime polynomials and check later if they really are irreducible
        prim_candidates = [x for x in prim_candidates if x > field_charac] # filter out too small primes
    else:
        prim_candidates = _range(field_charac+2, field_charac_next, root_charac) # try each possible prime polynomial, but skip even numbers (because divisible by 2 so necessarily not irreducible)

    # Start of the main loop
    correct_primes = []
    for prim in prim_candidates: # try potential candidates primitive irreducible polys
        seen = bytearray(field_charac+1) # memory variable to indicate if a value was already generated in the field (value at index x is set to 1) or not (set to 0 by default)
        conflict = False # flag to know if there was at least one conflict

        # Second loop, build the whole Galois Field
        x = GF2int(1)
        for i in _range(field_charac):
            # Compute the next value in the field (ie, the next power of alpha/generator)
            x = x.multiply(generator, prim, field_charac+1)

            # Rejection criterion: if the value overflowed (above field_charac) or is a duplicate of a previously generated power of alpha, then we reject this polynomial (not prime)
            if x > field_charac or seen[x] == 1:
                conflict = True
                break
            # Else we flag this value as seen (to maybe detect future duplicates), and we continue onto the next power of alpha
            else:
                seen[x] = 1

        # End of the second loop: if there's no conflict (no overflow nor duplicated value), this is a prime polynomial!
        if not conflict: 
            correct_primes.append(prim)
            if single: return prim

    # Return the list of all prime polynomials
    return correct_primes # you can use the following to print the hexadecimal representation of each prime polynomial: print [hex(i) for i in correct_primes]

def init_lut(generator=3, prim=0x11b, c_exp=8):
    '''Precompute the logarithm and anti-log (look-up) tables for faster computation later, using the provided primitive polynomial.
    These tables are used for multiplication/division since addition/substraction are simple XOR operations inside GF of characteristic 2.
    The basic idea is quite simple: since b**(log_b(x), log_b(y)) == x * y given any number b (the base or generator of the logarithm), then we can use any number b to precompute logarithm and anti-log (exponentiation) tables to use for multiplying two numbers x and y.
    That's why when we use a different base/generator number, the log and anti-log tables are drastically different, but the resulting computations are the same given any such tables.
    For more infos, see https://en.wikipedia.org/wiki/Finite_field_arithmetic#Implementation_tricks
    '''
    # generator is the generator number (the "increment" that will be used to walk through the field by multiplication, this must be a prime number). This is basically the base of the logarithm/anti-log tables. Also often noted "alpha" in academic books.
    # prim is the primitive/prime (binary) polynomial and must be irreducible (it can't represented as the product of two smaller polynomials). It's a polynomial in the binary sense: each bit is a coefficient, but in fact it's an integer between 0 and 255, and not a list of gf values. For more infos: http://research.swtch.com/field
    # note that the choice of generator or prime polynomial doesn't matter very much: any two finite fields of size p^n have identical structure, even if they give the individual elements different names (ie, the coefficients of the codeword will be different, but the final result will be the same: you can always correct as many errors/erasures with any choice for those parameters). That's why it makes sense to refer to all the finite fields, and all decoders based on Reed-Solomon, of size p^n as one concept: GF(p^n). It can however impact sensibly the speed (because some parameters will generate sparser tables).

    global GF2int_exptable, GF2int_logtable, GF2_charac, GF2_c_exp
    GF2_charac = int(2**c_exp - 1)
    GF2_c_exp = int(c_exp)
    exptable = [-1] * (GF2_charac+1) # anti-log (exponential) table. The first two elements will always be [GF2int(1), generator]
    logtable = [-1] * (GF2_charac+1) # log table, log[0] is impossible and thus unused

    # Construct the anti-log table
    # It's basically the cumulative product of 1 by the generator number, on and on and on until you have walked through the whole field.
    # That's why exptable is always dense (all entries are filled), but logtable may be sparse (lots of empty values, because multiple logtable's entries point to the same exptable's entry).
    g = GF2int(1)
    for i in range(GF2_charac+1): # note that the last item of exptable will always be equal to the first item in the table, because g^p==g^0 because of the modulo p (we're in a finite field!).
        exptable[i] = g # compute anti-log for this value and store it in a table
        #logtable[g] = i # compute logtable at the same time as exptable (but log[1] will always be equal to g^255, which may be weird when compared to lists of logtables online but this is equivalent)
        g = g.multiply(generator, prim, GF2_charac+1) # equivalent to: g = generator**(i+1)

    # Construct the log table
    # Ignore the last element of the field because fields wrap back around.
    # The log of 1 can have two values: either g^0 (the exact value change depending on parameters) or it could be 255 (g^255=1) because of the wraparound
    for i, x in enumerate(exptable[:-1]):
        logtable[x] = i

    # Optimization: convert to integer arrays (and use contiguous memory views)
    GF2int_exptable = array.array('i', exptable)
    GF2int_logtable = array.array('i', logtable)
    return GF2int_exptable, GF2int_logtable



@cython.nonecheck(False) # Turn off nonecheck locally for the function
@cython.boundscheck(False) # turn off boundscheck for this function
cdef class GF2int(object): # with (int) it works, else it doesn't... # DO NOT try to inherit from int, else it will cause a MemoryError if you generate too many GF2int (because they aren't freed, they stay in memory. This is an issue with the current Cython v0.22).
    '''Instances of this object are elements of the field GF(2^p)
    Instances are integers in the range 0 to p-1
    This field is defined using the irreducable polynomial
    x^8 + x^4 + x^3 + x + 1
    and using 3 as the generator for the exponent table and log table.
    '''

    cdef int value # where we will store the int value, this is not necessary when inheriting from int

    # Maps integers to GF2int instances
    #cache = {}

    # def __new__(cls, value): # Note: works but commented out because on computers, we'd rather use less CPU than use less memory.
        # # Check cache
        # # Caching sacrifices a bit of speed for less memory usage. This way,
        # # there are only a max of 256 instances of this class at any time.
        # try:
            # return GF2int.cache[value]
        # except KeyError:
            # if value > GF2_charac or value < 0:
                # raise ValueError("Field elements of GF(2^p) are between 0 and %i. Cannot be %s" % (GF2_charac, value))

            # newval = int.__new__(cls, value)
            # GF2int.cache[int(value)] = newval
            # return newval

    #cdef object __weakref__ # explicitly enable weakref for this extension type, will self-destruct when it is no longer strongly referenced.

    # store the int value, this is not necessary when inheriting from int
    def __init__(GF2int self, value): # CAUTION: do not use __cinit__ because it will make the Python interpreter crash on decoding (but on encoding it's ok, dunno why).
        self.value = value

    def __add__(int a, int b):
        "Addition in GF(2^8) is the xor of the two"
        return GF2int(a ^ b) # Do NOT do int(a).__xor__(int(b)), even if it is indeed safer, it sacrifices speed too much (/3 slowdown!)
    def __sub__(a, b): return a + b
    def __radd__(a, b): return a + b
    def __rsub__(a, b): return a + b
    def __xor__(int a, int b): return GF2int(a ^ b) # important to define directly the xoring on casted ints, as to avoid infinite recursion

    def __neg__(GF2int self):
        return self

    def __mul__(int a, int b):
        "Multiplication in GF(2^8)"
        if a == 0 or b == 0:
            return GF2int(0)
        cdef int x = GF2int_logtable[a]
        cdef int y = GF2int_logtable[b]
        cdef int z = (x + y) % GF2_charac
        return GF2int(GF2int_exptable[z])
    def __rmul__(a, b): return a * b

    def __pow__(int self, int power, modulo):
        #if isinstance(power, GF2int): # no need anymore because int power types correctly power so that it's always a regular integer.
            #raise TypeError("Raising a Field element to another Field element is not defined. power must be a regular integer")
        cdef int x = GF2int_logtable[self]
        cdef int z = (x * power) % GF2_charac
        return GF2int(GF2int_exptable[z])

    cpdef inverse(GF2int self):
        cdef int e = GF2int_logtable[<int>self]
        return GF2int(GF2int_exptable[GF2_charac - e])

    def __truediv__(int self, int other): # for Python 3.x
        #return self * GF2int(other).inverse() # self / other = self * inv(other) . This is equivalent to what is below, but 2x slower.
        if self == 0 or other == 0:
            return GF2int(0)
        cdef int x = GF2int_logtable[self]
        cdef int y = GF2int_logtable[other]
        cdef int z = (x - y) % GF2_charac # in logarithms, substraction = division after exponentiation
        return GF2int(GF2int_exptable[z])
    def __floordiv__(self, other): return self.__truediv__(other)
    def __div__(int self, int other): # for Python 2.x
        if self == 0 or other == 0:
            return GF2int(0)
        cdef int x = GF2int_logtable[self]
        cdef int y = GF2int_logtable[other]
        cdef int z = (x - y) % GF2_charac # in logarithms, substraction = division after exponentiation
        return GF2int(GF2int_exptable[z])

    def __rtruediv__(int self, int other):
        #return self.inverse() * other
        return GF2int.__truediv__(other, self)
    def __rfloordiv__(self, other): return GF2int.__truediv__(other, self)
    def __rdiv__(self, other): return GF2int.__truediv__(other, self) # for Python 2.x

    def __repr__(GF2int self):
        n = self.__class__.__name__
        return "%s(%r)" % (n, int(self))

    def __str__(GF2int self):
        return "%i" % int(self)

    cpdef _to_binpoly(GF2int x):
        '''Convert a Galois Field's number into a nice polynomial'''
        if x <= 0: return "0"
        b = 1 # init to 2^0 = 1
        c = [] # stores the degrees of each term of the polynomials
        i = 0 # counter for b = 2^i
        while x > 0:
            b = (1 << i) # generate a number power of 2: 2^0, 2^1, 2^2, ..., 2^i. Equivalent to b = 2^i
            if x & b : # then check if x is divisible by the power of 2. Equivalent to x % 2^i == 0
                # If yes, then...
                c.append(i) # append this power (i, the exponent, gives us the coefficient)
                x ^= b # and compute the remainder of x / b
            i = i+1 # increment to compute the next power of 2
        return " + ".join(["x^%i" % y for y in c[::-1]]) # print a nice binary polynomial

    cpdef multiply(GF2int x, int y, int prim=0x11b, int field_charac_full=256, int carryless=True):
        '''A slow multiply method. This method gives the same results as the
        other __mul__ method but without needing precomputed tables,
        thus it can be used to generate those tables.

        If prim is set to 0 and carryless=False, the function produces the result of a standard multiplication of integers (outside of a finite field, ie, no modular reduction and no carry-less operations).

        This procedure is called Russian Peasant Multiplication algorithm, which is just a general algorithm to multiply two integers together.
        The only two differences that you need to account for when doing multiplication in a finite field (as opposed to just integers) are:
        1- carry-less addition and substraction (XOR in GF(2^p))
        2- modular reduction (to avoid duplicate values in the field) using a prime polynomial
        '''

        r = 0
        a = int(x)
        b = int(y)
        while b: # while b is not 0
            if b & 1: r = r ^ a if carryless else r + a # b is odd, then add the corresponding a to r (the sum of all a's corresponding to odd b's will give the final product). Note that since we're in GF(2), the addition is in fact an XOR (very important because in GF(2) the multiplication and additions are carry-less, thus it changes the result!).
            b = b >> 1 # equivalent to b // 2
            a = a << 1 # equivalent to a*2
            if prim > 0 and a & field_charac_full: a = a ^ prim # GF modulo: if a >= 256 then apply modular reduction using the primitive polynomial (we just substract, but since the primitive number can be above 256 then we directly XOR).

        return GF2int(r)

    def multiply_slow(x, y, prim=0x11b):
        '''Another equivalent (but even slower) way to compute multiplication in Galois Fields without using a precomputed look-up table.
        This is the form you will most often see in academic literature, by using the standard carry-less multiplication + modular reduction using an irreducible prime polynomial.'''

        ### Define bitwise carry-less operations as inner functions ###
        def cl_mult(x, y):
            '''Bitwise carry-less multiplication on integers'''
            z = 0
            i = 0
            while (y>>i) > 0:
                if y & (1<<i):
                    z ^= x<<i
                i += 1
            return z

        def bit_length(n):
            '''Compute the position of the most significant bit (1) of an integer. Equivalent to int.bit_length()'''
            bits = 0
            while n >> bits: bits += 1
            return bits

        def cl_div(dividend, divisor=None):
            '''Bitwise carry-less long division on integers and returns the remainder'''
            # Compute the position of the most significant bit for each integers
            dl1 = bit_length(dividend)
            dl2 = bit_length(divisor)
            # If the dividend is smaller than the divisor, just exit
            if dl1 < dl2:
                return dividend
            # Else, align the most significant 1 of the divisor to the most significant 1 of the dividend (by shifting the divisor)
            for i in _range(dl1-dl2,-1,-1):
                # Check that the dividend is divisible (useless for the first iteration but important for the next ones)
                if dividend & (1 << i+dl2-1):
                    # If divisible, then shift the divisor to align the most significant bits and XOR (carry-less substraction)
                    dividend ^= divisor << i
            return dividend

        ### Main GF multiplication routine ###

        a = int(x)
        b = int(y)
        # Multiply the gf numbers
        result = cl_mult(a,b)
        # Then do a modular reduction (ie, remainder from the division) with an irreducible primitive polynomial so that it stays inside GF bounds
        if prim > 0:
            result = cl_div(result, prim)

        return result



############ INT AND INDEX REIMPLEMENTATION ###########
# The following magic methods definitions are only necessary  because we do not inherit from int. When Cython will fix the issue with Extension Types inheriting from ints, these methods can be removed.

    def __index__(GF2int self):
        return self.value
    
    def __hash__(GF2int self): # used for quick key comparison in dicts
        return self.value

    def __int__(GF2int self):
        return self.value
    
    def __nonzero__(GF2int self): # eg, when using "not a"
        return self.value != 0

    def __richcmp__(GF2int self, other, int op): # it's necessary to implement explicitly the behavior when comparing because we do not inherit from int...
        # 0: <
        # 2: ==
        # 4: >
        # 1: <=
        # 3: !=
        # 5: >=
        if op == 0:
            return int(self) < int(other)
        elif op == 1:
            return int(self) <= int(other)
        elif op == 2:
            return int(self) == int(other)
        elif op == 3:
            return int(self) != int(other)
        elif op == 4:
            return int(self) > int(other)
        elif op == 5:
            return int(self) >= int(other)
