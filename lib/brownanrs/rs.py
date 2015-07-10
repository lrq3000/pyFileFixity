#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2010 Andrew Brown <brownan@cs.duke.edu, brownan@gmail.com>
# Copyright (c) 2015 Stephen Larroque <LRQ3000@gmail.com>
# See LICENSE.txt for license terms

try: # Cython implementation import. This should be a bit faster than using PyPy with the pure-python implementation.
    from cff import GF2int, init_lut
    from cpolynomial import Polynomial
except ImportError: # Else, we import the pure-python implementation (the reference, this should always work albeit more slowly).
    from ff import GF2int, init_lut
    from polynomial import Polynomial

from operator import mul
#import copy
#import array # avoid because PyPy has troubles! https://bitbucket.org/pypy/pypy/issue/1989/arrayarray-creation-5x-slower-than-cpython

class RSCodecError(Exception):
    pass

'''This module implements a universal errors-and-erasures Reed-Solomon Encoding and Decoding.
It supports arbitrary configurations for n and k, the codeword length and
message length. This can be used to adjust the error correcting power of the
code.

It also supports any configurations for the generator, the prime polynomial, the
first consecutive root and the Galois Field's characteristic (ie, you are not limited
to GF(2^8)). This allows this module to interface with any other RS codec
(ie, you can decode the codeword output of any other RS codec if you provide
the correct parameters here).

Warning: Because of the way I've implemented things, leading null bytes in a
message are dropped. Be careful if encoding binary data, pad the data yourself
to k bytes per block to avoid problems. Also see the nostrip option to
decode().

When called as a script, this file encodes data from standard in and outputs it
to standard out, using the standard RS code 255,223. This is suitable for
encoding text and trying it out, but don't try to encode binary data with it!

When encoding, it outputs blocks of 255 bytes, 223 of them are data (padded
with leading null bytes if necessary) and then 32 bytes of parity data.

Use the -d flag to decode data on standard in to standard out. This reads in
blocks of 255 bytes, and outputs the decoded data from them. If there are less
than 16 errors per block, your data will be recovered.
'''

class RSCoder(object):
    def __init__(self, n, k, generator=3, prim=0x11b, fcr=1, c_exp=8):
        '''Creates a new Reed-Solomon Encoder/Decoder object configured with
        the given n and k values.
        n is the length of a codeword, must be less than 2^c_exp
        k is the length of the message, must be less than n
        
        The other parameters are optional (but allows compatibility with all RS encoders/decoders):
        - generator is the generator number (the "increment" that will be used to walk through the field by multiplication, this must be a prime number)
        - prim is the prime/primitive (binary) polynomial and must be irreducible (it can't represented as the product of two smaller polynomials). It's a polynomial in the binary sense: each bit is a coefficient, but in fact it's an integer between 2^p and (2^p)*2, and not a list of gf values.
        - fcr is the first consecutive root
        - c_exp is the exponent of the Galois Field's characteristic: GF(2^c_exp). This both define the maximum possible value for one symbol, and the maximum length of a message+ecc (n == 2^c_exp). Note that for different c_exp, you must use a different prime polynomial (prim).

        The code can correct up to 2*e + v <= (n-k) where e is the number of errors and v the number of erasures.

        The typical RSCoder is RSCoder(255, 223)
        '''
        self.gf2_charac = int(2**c_exp - 1)
        self.gf2_c_exp = int(c_exp)
        if n < 0 or k < 0:
            raise ValueError("n and k must be positive")
        if n > self.gf2_charac:
            raise ValueError("n must be at most %i" % self.gf2_charac)
        if not k < n:
            raise ValueError("Codeword length n must be greater than message"
                    " length k")
        self.n = n
        self.k = k

        self.generator = generator # Generator number (must be prime)
        self.prim = prim # irreducible primitive polynomial (which is in fact an integer)
        self.fcr = fcr

        self.g = {} # Generator (irreducible) polynomial for decoding
        #self.h = {}

        # Initialize the look-up tables for logarithm and anti-log
        init_lut(generator=generator, prim=prim, c_exp=self.gf2_c_exp)

        # Generate the generator polynomial for RS codes
        # g(x) = (x-α^1)(x-α^2)...(x-α^(n-k))
        # α is 3, a generator for GF(2^8)
        g = Polynomial([GF2int(1)])
        for i in xrange(0, 2): self.g[i] = g
        for i in xrange(0,n):
            p = Polynomial([GF2int(1), GF2int(self.generator)**(i+fcr)])
            g = g * p
            self.g[n-(i+1)] = g # copy.deepcopy(g)

        # h(x) = (x-α^(n-k+1))...(x-α^n)
        #h = Polynomial([GF2int(1)])
        #for i in xrange(n-1, n+1): self.h[i] = h
        #for i in xrange(n, 0, -1):
        #    p = Polynomial([GF2int(1), GF2int(self.generator)**(i+fcr)])
        #    h = h * p
        #    self.h[n-i+1] = h

        # g*h is used in verification, and is always x^n-1

        # TODO: The following line gtimesh is hardcoded for (255,223)
        # But it doesn't matter since my verify method doesn't use it
        #self.gtimesh = Polynomial(x255=GF2int(1), x0=GF2int(1))

    def encode(self, message, poly=False, k=None):
        '''Encode a given string with reed-solomon encoding. Returns a byte
        string with the k message bytes and n-k parity bytes at the end.
        
        If a message is < k bytes long, it is assumed to be padded at the front
        with null bytes.

        The sequence returned is always n bytes long.

        If poly is not False, returns the encoded Polynomial object instead of
        the polynomial translated back to a string (useful for debugging)
        '''
        n = self.n
        if not k: k = self.k

        if len(message)>k:
            raise ValueError("Message length is max %d. Message was %d" % (k,
                len(message)))

        # Encode message as a polynomial:
        if isinstance(message, basestring):
            m = Polynomial([GF2int(ord(x)) for x in message])
            #m = Polynomial(map(GF2int, map(ord,message)))
            #m = Polynomial([GF2int(x) for x in array.array('b', message).tolist()]) # equivalent to: Polynomial([GF2int(ord(x)) for x in message])
        else:
            m = Polynomial([GF2int(x) for x in message])

        # Shift polynomial up by n-k by multiplying by x^(n-k) to reserve the first n-k coefficients for the ecc. This effectively pad the message with \0 bytes for the lower coefficients (where the ecc will be placed).
        mprime = m * Polynomial([GF2int(1)] + [GF2int(0)]*(n-k))

        # mprime = q*g + b for some q
        # so let's find b, the code word (ecc block):
        b = mprime % self.g[k]

        # Subtract out b, so now c = q*g, which is a way of xoring mprime and code word b, which is a way of just saying that we append the polynomial ecc code to the original message (we replace the padded 0 bytes of mprime with the code word)
        c = mprime - b
        # Since c is a multiple of g, it has (at least) n-k roots: α^1 through
        # α^(n-k)

        if not poly:
            # Turn the polynomial c back into a string
            return ''.join([chr(x) for x in c.coefficients]).rjust(n, "\0") # rjust is useful for the nostrip feature
            #return ''.join(map(chr,c.coefficients)).rjust(self.gf2_charac, "\0") # faster but doesn't validate unittest...
            #return array.array('B', c).tostring().rjust(n, "\0") # faster than but equivalent to: "".join(chr(x) for x in c).rjust(n, "\0") # see: https://www.python.org/doc/essays/list2str/
        else: return c

    def encode_fast(self, message, poly=False, k=None):
        '''Fast encoding of a message, using synthetic division and other tricks to minimize the number of operations on Polynomials.'''
        n = self.n
        if not k: k = self.k

        if len(message)>k:
            raise ValueError("Message length is max %d. Message was %d" % (k,
                len(message)))

        # Encode message as a polynomial:
        if isinstance(message, basestring):
            m = Polynomial([GF2int(ord(x)) for x in message])
        else:
            m = Polynomial([GF2int(x) for x in message])

        # Encode message as a polynomial and shift polynomial up by n-k to reserve the first n-k coefficients for the ecc (without multiplication, this is an optimization). This effectively pad the message with \0 bytes for the lower coefficients (where the ecc will be placed).
        mprime = Polynomial(m.coefficients + [GF2int(0)]*(n-k))

        # mprime = q*g + b for some q
        # so let's find b:
        #b = m % self.g[k]
        # note that mprime is the same as m, it's just padded with 0 coeffs, so we can exchange m and mprime if we want to
        b = mprime._gffastmod(self.g[k]) # equivalent to the more generic (works with any polynomial, not just GF(2^p)) but less optimized: b = mprime._fastmod(self.g[k])

        # Append the polynomial ecc code to the original message
        c = mprime.coefficients[:-len(b.coefficients)] + b.coefficients # equivalent to c = mprime - b

        if not poly:
            # Turn the polynomial c back into a byte string
            return ''.join([chr(x) for x in c]).rjust(n, "\0") # rjust is useful for the nostrip feature
            #return bytearray(c).rjust(n, "\0") # based on %timeit, bytearray is 4x faster than list comprehension for this job, but PyPy does a better job at speeding up list comprehensions than bytearray, so better keep the list comprehension.
        else: return Polynomial(c)

    def check(self, code, k=None):
        '''Verifies the code is valid by testing that the code (message+ecc) as a polynomial code divides g
        returns True/False
        '''
        n = self.n
        if not k: k = self.k
        #h = self.h[k]
        g = self.g[k]

        if isinstance(code, basestring):
            c = Polynomial([GF2int(ord(x)) for x in code])
        else:
            c = Polynomial([GF2int(x) for x in code])

        # This works too, but takes longer. Both checks are just as valid.
        #return (c*h)%gtimesh == Polynomial(x0=0)

        # Since all codewords are multiples of g, checking that code divides g
        # suffices for validating a codeword.
        return c % g == Polynomial(x0=0) # TODO: for faster computation replace by c._fastmod(g, self.n-k) ?

    def check_fast(self, r, k=None):
        '''Fast check if there's any error in a message+ecc. Can be used before decoding, in addition to hashes to detect if the message was tampered, or after decoding to check that the message was fully recovered.
        returns True/False
        '''
        n = self.n
        if not k: k = self.k
        #h = self.h[k]
        g = self.g[k]

        # Turn r into a polynomial
        if isinstance(r, basestring):
            r = Polynomial([GF2int(ord(x)) for x in r])
        else:
            r = Polynomial([GF2int(x) for x in r])

        # Compute the syndromes:
        sz = self._syndromes(r, k=k)

        # Checking that the syndrome is all 0 is sufficient to check if there are no more any errors in the decoded message
        #return all(int(x) == 0 for x in sz)
        return sz.coefficients.count(GF2int(0)) == len(sz) # Faster than all()

    def decode(self, r, nostrip=False, k=None, erasures_pos=None, only_erasures=False):
        '''Given a received string or byte array r, attempts to decode it. If
        it's a valid codeword, or if there are no more than (n-k)/2 errors, the
        message is returned.

        A message always has k bytes, if a message contained less it is left
        padded with null bytes. When decoded, these leading null bytes are
        stripped, but that can cause problems if decoding binary data. When
        nostrip is True, messages returned are always k bytes long. This is
        useful to make sure no data is lost when decoding binary data.
        
        Theoretically, we have R(x) = C(x) + E(x) + V(x), where R is the received message, C is the correct message without errors nor erasures, E are the errors and V the erasures. Thus the goal is to compute E and V from R, so that we can compute: C(x) = R(x) - E(x) - V(x), and then we have our original message! The main problem of decoding is to solve the so-called Key Equation, here we use Berlekamp-Massey.
        
        When stated in the language of spectral estimation, consists of a Fourier transform (syndrome computer), followed by a spectral analysis (Berlekamp-Massey or Euclidian algorithm), followed by an inverse Fourier transform (Chien search).
        (see Blahut, "Algebraic Codes for Data Transmission", 2003, chapter 7.6 Decoding in Time Domain).
        '''
        n = self.n
        if not k: k = self.k

        # Deprecated check: we do it below in a faster way (we always compute the syndrome only once and it allows to check or to correct without recomputing anythome more
#        if self.verify(r): # the code is already valid, there's nothing to do
#            # The last n-k bytes are parity
#            if nostrip:
#                return r[:-(n-k)], r[-(n-k):]
#            else:
#                return r[:-(n-k)].lstrip("\0"), r[-(n-k):]

        # Turn r into a polynomial
        if isinstance(r, basestring):
            rp = Polynomial([GF2int(ord(x)) for x in r])
        else:
            rp = Polynomial([GF2int(x) for x in r])

        if erasures_pos:
            # Convert string positions to coefficients positions for the algebra to work (see _find_erasures_locator(), ecc characters represent the first coefficients while the message is put last, so it's exactly the reverse of the string positions where the message is first and the ecc is last, thus it's just like if you read the message+ecc string in reverse)
            erasures_pos = [len(r)-1-x for x in erasures_pos]
            # Set erasures characters to null bytes
            # Note that you can just leave the original characters as they are, you don't need to set erased characters to null bytes for the decoding to work, but note that it won't help either (ie, fake erasures, meaning characters that were detected as erasures but actually aren't, will still "consume" one ecc symbol, even if you don't set them to null byte, this is because the syndrome is limited to n-k and thus you can't decode above this bound without a clever trick).
            # Example string containing a fake erasure: "hello sam" -> "ooooo sam" with erasures_pos = [0, 1, 2, 3, 4]. Here in fact the last erasure is fake because the original character also was "o" so if we detect "o" as an erasure, we will end up with one fake erasure. But setting it to null byte or not, it will still use up one ecc symbol, it will always be counted as a real erasure. If you're below the n-k bound, then the doceding will be ok. If you're above, then you can't do anything, the decoding won't work. Maybe todo: try to find a clever list decoding algorithm to account for fake erasures....
            # Note: commented out so that the resulting omega (error evaluator polynomial) is the same as the erasure evaluator polynomial when decoding the same number of errors or erasures (ie, decoding 3 erasures only will give the same result as 3 errors only, with of course the errors/erasures on the same characters).
            #for erasure in erasures_pos:
                #rp[erasure] = GF2int(0)

        # Compute the syndromes:
        sz = self._syndromes(rp, k=k)

        if sz.coefficients.count(GF2int(0)) == len(sz): # the code is already valid, there's nothing to do
            # The last n-k bytes are parity
            if nostrip:
                return r[:-(n-k)], r[-(n-k):]
            else:
                return r[:-(n-k)].lstrip("\0"), r[-(n-k):]

        # Erasures locator polynomial computation
        erasures_loc = None
        erasures_eval = None
        erasures_count = 0
        if erasures_pos:
            erasures_count = len(erasures_pos)
            # Compute the erasure locator polynomial
            erasures_loc = self._find_erasures_locator(erasures_pos)
            # Compute the erasure evaluator polynomial
            erasures_eval = self._find_error_evaluator(sz, erasures_loc, k=k)

        if only_erasures:
            sigma = erasures_loc
            omega = erasures_eval
        else:
            # Find the error locator polynomial and error evaluator polynomial
            # using the Berlekamp-Massey algorithm
            # if erasures were supplied, BM will generate the errata (errors-and-erasures) locator and evaluator polynomials
            sigma, omega = self._berlekamp_massey(sz, k=k, erasures_loc=erasures_loc, erasures_eval=erasures_eval, erasures_count=erasures_count)
            omega = self._find_error_evaluator(sz, sigma, k=k) # we want to make sure that omega is correct (we know that sigma is always correct, but omega not really)

        # Now use Chien's procedure to find the error locations
        # j is an array of integers representing the positions of the errors, 0
        # being the rightmost byte
        # X is a corresponding array of GF(2^8) values where X_i = alpha^(j_i)
        X, j = self._chien_search(sigma)

        # Sanity check: Cannot guarantee correct decoding of more than n-k errata (Singleton Bound, n-k being the minimum distance), and we cannot even check if it's correct (the syndrome will always be all 0 if we try to decode above the bound), thus it's better to just return the input as-is.
        if len(j) > n-k:
            if nostrip:
                return r[:-(n-k)], r[-(n-k):]
            else:
                return r[:-(n-k)].lstrip("\0"), r[-(n-k):]

        # And finally, find the error magnitudes with Forney's Formula
        # Y is an array of GF(2^8) values corresponding to the error magnitude
        # at the position given by the j array
        Y = self._forney(omega, X)

        # Put the error and locations together to form the error polynomial
        # Note that an alternative would be to compute the error-spectrum polynomial E(x) which satisfies E(x)*Sigma(x) = 0 (mod x^n - 1) = Omega(x)(x^n - 1) -- see Blahut, Algebraic codes for data transmission
        Elist = [GF2int(0)] * self.gf2_charac
        if len(Y) >= len(j): # failsafe: if the number of erratas is higher than the number of coefficients in the magnitude polynomial, we failed!
            for i in xrange(self.gf2_charac): # FIXME? is this really necessary to go to self.gf2_charac? len(rp) wouldn't be just enough? (since the goal is anyway to substract E to rp)
                if i in j:
                    Elist[i] = Y[j.index(i)]
            E = Polynomial( Elist[::-1] ) # reverse the list because we used the coefficient degrees (j) instead of the error positions
        else:
            E = Polynomial()

        # And we get our real codeword!
        c = rp - E # Remember what we wrote above: R(x) = C(x) + E(x), so here to get back the original codeword C(x) = R(x) - E(x) ! (V(x) the erasures are here is included inside E(x))

        if len(c) > len(r): c = rp # failsafe: in case the correction went totally wrong (we repaired padded null bytes instead of the message! thus we end up with a longer message than what we should have), then we just return the uncorrected message. Note: we compare the length of c with r on purpose, that's not an error: if we compare with rp, if the first few characters were erased (null bytes) in r, then in rp the Polynomial will automatically skip them, thus the length will always be smaller in that case.

        # Form it back into a string and return all but the last n-k bytes
        ret = ''.join(chr(x) for x in c.coefficients[:-(n-k)])
        ecc = ''.join(chr(x) for x in c.coefficients[-(n-k):]) # also return the corrected ecc, so that user can check()

        if nostrip:
            # Polynomial objects don't store leading 0 coefficients, so we
            # actually need to pad this to k bytes
            return ret.rjust(k, "\0"), ecc
        else:
            return ret, ecc

    def decode_fast(self, r, nostrip=False, k=None, erasures_pos=None, only_erasures=False):
        '''Faster decoding of a message with ecc bytes, using optimized algorithms (use PyPy to get really fast!).

        Given a received string or byte array r, attempts to decode it. If
        it's a valid codeword, or if there are no more than (n-k)/2 errors, the
        message is returned.

        A message always has k bytes, if a message contained less it is left
        padded with null bytes. When decoded, these leading null bytes are
        stripped, but that can cause problems if decoding binary data. When
        nostrip is True, messages returned are always k bytes long. This is
        useful to make sure no data is lost when decoding binary data.

        Theoretically, we have R(x) = C(x) + E(x) + V(x), where R is the received message, C is the correct message without errors nor erasures, E are the errors and V the erasures. Thus the goal is to compute E and V from R, so that we can compute: C(x) = R(x) - E(x) - V(x), and then we have our original message! The main problem of decoding is to solve the so-called Key Equation, here we use Berlekamp-Massey.
        '''
        n = self.n
        if not k: k = self.k

        # Deprecated check: we do it below in a faster way (we always compute the syndrome only once and it allows to check or to correct without recomputing anythome more
#        if self.verify(r): # the code is already valid, there's nothing to do
#            # The last n-k bytes are parity
#            if nostrip:
#                return r[:-(n-k)], r[-(n-k):]
#            else:
#                return r[:-(n-k)].lstrip("\0"), r[-(n-k):]

        # Turn r into a polynomial
        if isinstance(r, basestring):
            rp = Polynomial([GF2int(ord(x)) for x in r])
        else:
            rp = Polynomial([GF2int(x) for x in r])

        if erasures_pos:
            # Convert string positions to coefficients positions for the algebra to work (see _find_erasures_locator(), ecc characters represent the first coefficients while the message is put last, so it's exactly the reverse of the string positions where the message is first and the ecc is last, thus it's just like if you read the message+ecc string in reverse)
            erasures_pos = [len(r)-1-x for x in erasures_pos]
            # Note: no need to set the erased characters to null bytes, and keeping values has the advantage of helping in debugging

        # Compute the syndromes:
        sz = self._syndromes(rp, k=k)

        if sz.coefficients.count(GF2int(0)) == len(sz): # the code is already valid, there's nothing to do
            # The last n-k bytes are parity
            if nostrip:
                return r[:-(n-k)], r[-(n-k):]
            else:
                return r[:-(n-k)].lstrip("\0"), r[-(n-k):]

        # Erasures locator polynomial computation
        erasures_loc = None
        erasures_eval = None
        erasures_count = 0
        if erasures_pos:
            erasures_count = len(erasures_pos)
            # Compute the erasure locator polynomial
            erasures_loc = self._find_erasures_locator(erasures_pos)
            # Compute the erasure evaluator polynomial
            erasures_eval = self._find_error_evaluator_fast(sz, erasures_loc, k=k)

        if only_erasures:
            sigma = erasures_loc
            omega = erasures_eval
        else:
            # Find the error locator polynomial and error evaluator polynomial
            # using the Berlekamp-Massey algorithm
            sigma, omega = self._berlekamp_massey_fast(sz, k=k, erasures_loc=erasures_loc, erasures_eval=erasures_eval, erasures_count=erasures_count)
            omega = self._find_error_evaluator_fast(sz, sigma, k=k) # make sure it's correct, because the high order terms trim hack may not be enough (sometimes, omega has a smaller degree than sigma)

        # Now use Chien's procedure to find the error locations
        # j is an array of integers representing the positions of the errors, 0
        # being the rightmost byte
        # X is a corresponding array of GF(2^8) values where X_i = alpha^(j_i)
        X, j = self._chien_search_faster(sigma)

        # Sanity check: Cannot guarantee correct decoding of more than n-k errata (Singleton Bound, n-k being the minimum distance), and we cannot even check if it's correct (the syndrome will always be all 0 if we try to decode above the bound), thus it's better to just return the input as-is.
        if len(j) > n-k:
            if nostrip:
                return r[:-(n-k)], r[-(n-k):]
            else:
                return r[:-(n-k)].lstrip("\0"), r[-(n-k):]

        # And finally, find the error magnitudes with Forney's Formula
        # Y is an array of GF(2^8) values corresponding to the error magnitude
        # at the position given by the j array
        Y = self._forney(omega, X)

        # Put the error and locations together to form the error polynomial
        # Note that an alternative would be to compute the error-spectrum polynomial E(x) which satisfies E(x)*Sigma(x) = 0 (mod x^n - 1) = Omega(x)(x^n - 1) -- see Blahut, Algebraic codes for data transmission
        Elist = [GF2int(0)] * self.gf2_charac
        for i in xrange(self.gf2_charac):
            if i in j:
                Elist[i] = Y[j.index(i)]
        E = Polynomial( Elist[::-1] )

        # And we get our real codeword!
        c = rp - E

        if len(c) > len(r): c = rp # failsafe: in case the correction went totally wrong (we repaired padded null bytes instead of the message! thus we end up with a longer message than what we should have), then we just return the uncorrected message. Note: we compare the length of c with r on purpose, that's not an error: if we compare with rp, if the first few characters were erased (null bytes) in r, then in rp the Polynomial will automatically skip them, thus the length will always be smaller in that case.

        # Form it back into a string and return all but the last n-k bytes
        ret = ''.join(chr(x) for x in c.coefficients[:-(n-k)])
        ecc = ''.join(chr(x) for x in c.coefficients[-(n-k):]) # also return the corrected ecc, so that user can check()

        if nostrip:
            # Polynomial objects don't store leading 0 coefficients, so we
            # actually need to pad this to k bytes
            return ret.rjust(k, "\0"), ecc
        else:
            return ret, ecc


    def _list2gfpoly(self, L):
        return Polynomial([GF2int(x) for x in L])

    def _syndromes(self, r, k=None):
        '''Given the received codeword r in the form of a Polynomial object,
        computes the syndromes and returns the syndrome polynomial.
        Mathematically, it's essentially equivalent to a Fourrier Transform (Chien search being the inverse).
        '''
        n = self.n
        if not k: k = self.k
        # Note the + [GF2int(0)] : we add a 0 coefficient for the lowest degree (the constant). This effectively shifts the syndrome, and will shift every computations depending on the syndromes (such as the errors locator polynomial, errors evaluator polynomial, etc. but not the errors positions).
        # This is not necessary as anyway syndromes are defined such as there are only non-zero coefficients (the only 0 is the shift of the constant here) and subsequent computations will/must account for the shift by skipping the first iteration (eg, the often seen range(1, n-k+1)), but you can also avoid prepending the 0 coeff and adapt every subsequent computations to start from 0 instead of 1.
        return Polynomial( [r.evaluate( GF2int(self.generator)**(l+self.fcr) ) for l in xrange(n-k-1, -1, -1)] + [GF2int(0)], keep_zero=True ) # IMPORTANT: for the syndrome, we want to keep all terms, even null ones! This is because the length of the syndrome gives us a precious information to compute the syndrome shift in Berlekamp-Massey and other places.

        # s[l] is the received codeword evaluated at α^l for 1 <= l <= s
        # α in this implementation is 3
        #s = [0] * (n-k+1)
        #s[-1] = GF2int(0) # s[0] is 0 (coefficient of z^0)
        #for l in xrange(1, n-k+1):
        #    s[-(l+1)] = r.evaluate( GF2int(self.generator)**l )

        # Now build a polynomial out of all our s[l] values
        # s(z) = sum(s_i * z^i, i=1..inf)
        #sz = Polynomial( s )

        #return sz

    # UNUSED
    def _forney_syndromes(self, synd, erasures_loc):
        # Compute he modified syndromes, may be used as an alternative to compute the errata locator polynomial without providing Berlekamp-Massey the erasure locator polynomial (but just the error locator polynomial with the modified Forney syndromes), from Blahut's book and Forney, G. (1965). On decoding BCH codes. IEEE Transactions on Information Theory, 11(4), 549-557.
        # The modified Forney syndromes is a syndrome where only errors are included, erasures have been trimmed out, so that BM can be used just like if no erasure is known (the erasures positions are then later added to the result of BM+Chien Search and feed to Forney Algorithm)
        # See Shao, H. M., Truong, T. K., Deutsch, L. J., & Reed, I. S. (1986, April). A single chip VLSI Reed-Solomon decoder. In Acoustics, Speech, and Signal Processing, IEEE International Conference on ICASSP'86. (Vol. 11, pp. 2151-2154). IEEE.ISO 690
        # TODO: does not seem to work correctly, do not use! But it should, theoretically it's correct (and in the reedsolo lib it works flawlessly). Maybe we should trim the first always 0 coefficient from sz?
        return (erasures_loc * sz) % Polynomial([1] + [0] * (n-k-1))

    def _find_erasures_locator(self, erasures_pos):
        '''Compute the erasures locator polynomial from the erasures positions (the positions must be relative to the x coefficient, eg: "hello worldxxxxxxxxx" is tampered to "h_ll_ worldxxxxxxxxx" with xxxxxxxxx being the ecc of length n-k=9, here the string positions are [1, 4], but the coefficients are reversed since the ecc characters are placed as the first coefficients of the polynomial, thus the coefficients of the erased characters are n-1 - [1, 4] = [18, 15] = erasures_loc to be specified as an argument.'''
        # See: http://ocw.usu.edu/Electrical_and_Computer_Engineering/Error_Control_Coding/lecture7.pdf and Blahut, Richard E. "Transform techniques for error control codes." IBM Journal of Research and development 23.3 (1979): 299-315. http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.92.600&rep=rep1&type=pdf and also a MatLab implementation here: http://www.mathworks.com/matlabcentral/fileexchange/23567-reed-solomon-errors-and-erasures-decoder/content//RS_E_E_DEC.m
        erasures_loc = Polynomial([GF2int(1)]) # just to init because we will multiply, so it must be 1 so that the multiplication starts correctly without nulling any term
        # erasures_loc is very simple to compute: erasures_loc = prod(1 - x*alpha[j]**i) for i in erasures_pos and where alpha is the alpha chosen to evaluate polynomials (here in this library it's gf(3)). To generate c*x where c is a constant, we simply generate a Polynomial([c, 0]) where 0 is the constant and c is positionned to be the coefficient for x^1. See https://en.wikipedia.org/wiki/Forney_algorithm#Erasures
        for i in erasures_pos:
            erasures_loc = erasures_loc * (Polynomial([GF2int(1)]) - Polynomial([GF2int(self.generator)**i, 0]))
        return erasures_loc

    def _berlekamp_massey(self, s, k=None, erasures_loc=None, erasures_eval=None, erasures_count=0):
        '''Computes and returns the errata (errors+erasures) locator polynomial (sigma) and the
        error evaluator polynomial (omega) at the same time.
        If the erasures locator is specified, we will return an errors-and-erasures locator polynomial and an errors-and-erasures evaluator polynomial, else it will compute only errors. With erasures in addition to errors, it can simultaneously decode up to v+2e <= (n-k) where v is the number of erasures and e the number of errors.
        Mathematically speaking, this is equivalent to a spectral analysis (see Blahut, "Algebraic Codes for Data Transmission", 2003, chapter 7.6 Decoding in Time Domain).
        The parameter s is the syndrome polynomial (syndromes encoded in a
        generator function) as returned by _syndromes.

        Notes:
        The error polynomial:
        E(x) = E_0 + E_1 x + ... + E_(n-1) x^(n-1)

        j_1, j_2, ..., j_s are the error positions. (There are at most s
        errors)

        Error location X_i is defined: X_i = α^(j_i)
        that is, the power of α (alpha) corresponding to the error location

        Error magnitude Y_i is defined: E_(j_i)
        that is, the coefficient in the error polynomial at position j_i

        Error locator polynomial:
        sigma(z) = Product( 1 - X_i * z, i=1..s )
        roots are the reciprocals of the error locations
        ( 1/X_1, 1/X_2, ...)

        Error evaluator polynomial omega(z) is here computed at the same time as sigma, but it can also be constructed afterwards using the syndrome and sigma (see _find_error_evaluator() method).

        It can be seen that the algorithm tries to iteratively solve for the error locator polynomial by
        solving one equation after another and updating the error locator polynomial. If it turns out that it
        cannot solve the equation at some step, then it computes the error and weights it by the last
        non-zero discriminant found, and delays the weighted result to increase the polynomial degree
        by 1. Ref: "Reed Solomon Decoder: TMS320C64x Implementation" by Jagadeesh Sankaran, December 2000, Application Report SPRA686

        The best paper I found describing the BM algorithm for errata (errors-and-erasures) evaluator computation is in "Algebraic Codes for Data Transmission", Richard E. Blahut, 2003.
        '''
        # For errors-and-erasures decoding, see: "Algebraic Codes for Data Transmission", Richard E. Blahut, 2003 and (but it's less complete): Blahut, Richard E. "Transform techniques for error control codes." IBM Journal of Research and development 23.3 (1979): 299-315. http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.92.600&rep=rep1&type=pdf and also a MatLab implementation here: http://www.mathworks.com/matlabcentral/fileexchange/23567-reed-solomon-errors-and-erasures-decoder/content//RS_E_E_DEC.m
        # also see: Blahut, Richard E. "A universal Reed-Solomon decoder." IBM Journal of Research and Development 28.2 (1984): 150-158. http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.84.2084&rep=rep1&type=pdf
        # and another good alternative book with concrete programming examples: Jiang, Yuan. A practical guide to error-control coding using Matlab. Artech House, 2010.
        n = self.n
        if not k: k = self.k

        # Initialize, depending on if we include erasures or not:
        if erasures_loc:
            sigma = [ Polynomial(erasures_loc.coefficients) ] # copy erasures_loc by creating a new Polynomial, so that we initialize the errata locator polynomial with the erasures locator polynomial.
            B = [ Polynomial(erasures_loc.coefficients) ]
            omega = [ Polynomial(erasures_eval.coefficients) ] # to compute omega (the evaluator polynomial) at the same time, we also need to initialize it with the partial erasures evaluator polynomial
            A = [ Polynomial(erasures_eval.coefficients) ] # TODO: fix the initial value of the evaluator support polynomial, because currently the final omega is not correct (it contains higher order terms that should be removed by the end of BM)
        else:
            sigma = [ Polynomial([GF2int(1)]) ] # error locator polynomial. Also called Lambda in other notations.
            B = [ Polynomial([GF2int(1)]) ] # this is the error locator support/secondary polynomial, which is a funky way to say that it's just a temporary variable that will help us construct sigma, the error locator polynomial
            omega = [ Polynomial([GF2int(1)]) ] # error evaluator polynomial. We don't need to initialize it with erasures_loc, it will still work, because Delta is computed using sigma, which itself is correctly initialized with erasures if needed.
            A = [ Polynomial([GF2int(0)]) ] # this is the error evaluator support/secondary polynomial, to help us construct omega
        L = [ 0 ] # update flag: necessary variable to check when updating is necessary and to check bounds (to avoid wrongly eliminating the higher order terms). For more infos, see https://www.cs.duke.edu/courses/spring11/cps296.3/decoding_rs.pdf
        M = [ 0 ] # optional variable to check bounds (so that we do not mistakenly overwrite the higher order terms). This is not necessary, it's only an additional safe check. For more infos, see the presentation decoding_rs.pdf by Andrew Brown in the doc folder.

        # Fix the syndrome shifting: when computing the syndrome, some implementations may prepend a 0 coefficient for the lowest degree term (the constant). This is a case of syndrome shifting, thus the syndrome will be bigger than the number of ecc symbols (I don't know what purpose serves this shifting). If that's the case, then we need to account for the syndrome shifting when we use the syndrome such as inside BM, by skipping those prepended coefficients.
        # Another way to detect the shifting is to detect the 0 coefficients: by definition, a syndrome does not contain any 0 coefficient (except if there are no errors/erasures, in this case they are all 0). This however doesn't work with the modified Forney syndrome (that we do not use in this lib but it may be implemented in the future), which set to 0 the coefficients corresponding to erasures, leaving only the coefficients corresponding to errors.
        synd_shift = 0
        if len(s) > (n-k): synd_shift = len(s) - (n-k)

        # Polynomial constants:
        ONE = Polynomial(z0=GF2int(1))
        ZERO = Polynomial(z0=GF2int(0))
        Z = Polynomial(z1=GF2int(1)) # used to shift polynomials, simply multiply your poly * Z to shift

        # Precaching
        s2 = ONE + s

        # Iteratively compute the polynomials n-k-erasures_count times. The last ones will be correct (since the algorithm refines the error/errata locator polynomial iteratively depending on the discrepancy, which is kind of a difference-from-correctness measure).
        for l in xrange(0, n-k-erasures_count): # skip the first erasures_count iterations because we already computed the partial errata locator polynomial (by initializing with the erasures locator polynomial)
            K = erasures_count+l+synd_shift # skip the FIRST erasures_count iterations (not the last iterations, that's very important!)

            # Goal for each iteration: Compute sigma[l+1] and omega[l+1] such that
            # (1 + s)*sigma[l] == omega[l] in mod z^(K)

            # For this particular loop iteration, we have sigma[l] and omega[l],
            # and are computing sigma[l+1] and omega[l+1]

            # First find Delta, the non-zero coefficient of z^(K) in
            # (1 + s) * sigma[l]
            # Note that adding 1 to the syndrome s is not really necessary, you can do as well without.
            # This delta is valid for l (this iteration) only
            Delta = ( s2 * sigma[l] ).get_coefficient(K) # Delta is also known as the Discrepancy, and is always a scalar (not a polynomial).
            # Make it a polynomial of degree 0, just for ease of computation with polynomials sigma and omega.
            Delta = Polynomial(x0=Delta)

            # Can now compute sigma[l+1] and omega[l+1] from
            # sigma[l], omega[l], B[l], A[l], and Delta
            sigma.append( sigma[l] - Delta * Z * B[l] )
            omega.append( omega[l] - Delta * Z * A[l] )

            # Now compute the next support polynomials B and A
            # There are two ways to do this
            # This is based on a messy case analysis on the degrees of the four polynomials sigma, omega, A and B in order to minimize the degrees of A and B. For more infos, see https://www.cs.duke.edu/courses/spring10/cps296.3/decoding_rs_scribe.pdf
            # In fact it ensures that the degree of the final polynomials aren't too large.
            if Delta == ZERO or 2*L[l] > K+erasures_count \
                or (2*L[l] == K+erasures_count and M[l] == 0):
            #if Delta == ZERO or len(sigma[l+1]) <= len(sigma[l]): # another way to compute when to update, and it doesn't require to maintain the update flag L
                # Rule A
                B.append( Z * B[l] )
                A.append( Z * A[l] )
                L.append( L[l] )
                M.append( M[l] )

            elif (Delta != ZERO and 2*L[l] < K+erasures_count) \
                or (2*L[l] == K+erasures_count and M[l] != 0):
            # elif Delta != ZERO and len(sigma[l+1]) > len(sigma[l]): # another way to compute when to update, and it doesn't require to maintain the update flag L
                # Rule B
                B.append( sigma[l] // Delta )
                A.append( omega[l] // Delta )
                L.append( K - L[l] ) # the update flag L is tricky: in Blahut's schema, it's mandatory to use `L = K - L - erasures_count` (and indeed in a previous draft of this function, if you forgot to do `- erasures_count` it would lead to correcting only 2*(errors+erasures) <= (n-k) instead of 2*errors+erasures <= (n-k)), but in this latest draft, this will lead to a wrong decoding in some cases where it should correctly decode! Thus you should try with and without `- erasures_count` to update L on your own implementation and see which one works OK without producing wrong decoding failures.
                M.append( 1 - M[l] )

            else:
                raise Exception("Code shouldn't have gotten here")

        # Hack to fix the simultaneous computation of omega, the errata evaluator polynomial: because A (the errata evaluator support polynomial) is not correctly initialized (I could not find any info in academic papers). So at the end, we get the correct errata evaluator polynomial omega + some higher order terms that should not be present, but since we know that sigma is always correct and the maximum degree should be the same as omega, we can fix omega by truncating too high order terms.
        if omega[-1].degree > sigma[-1].degree: omega[-1] = Polynomial(omega[-1].coefficients[-(sigma[-1].degree+1):])

        # Debuglines, uncomment to show the result of every iterations
        #print "SIGMA BM"
        #for i,x in enumerate(sigma):
            #print i, ":", x

        # Return the last result of the iterations (since BM compute iteratively, the last iteration being correct - it may already be before, but we're not sure)
        return sigma[-1], omega[-1]

    def _berlekamp_massey_fast(self, s, k=None, erasures_loc=None, erasures_eval=None, erasures_count=0):
        '''Faster implementation of errata (errors-and-erasures) Berlekamp-Massey.
        Returns the error locator polynomial (sigma) and the
        error evaluator polynomial (omega) with a faster implementation.
        '''
        n = self.n
        if not k: k = self.k

        # Initialize, depending on if we include erasures or not:
        if erasures_loc:
            sigma = Polynomial(erasures_loc.coefficients) # copy erasures_loc by creating a new Polynomial, so that we initialize the errata locator polynomial with the erasures locator polynomial.
            sigmaprev = Polynomial(sigma.coefficients)
            B = Polynomial(sigma.coefficients)
            omega = Polynomial(erasures_eval.coefficients) # to compute omega (the evaluator polynomial) at the same time, we also need to initialize it with the partial erasures evaluator polynomial
            omegaprev = Polynomial(omega.coefficients)
            A = Polynomial(omega.coefficients) # TODO: fix the initial value of the evaluator support polynomial, because currently the final omega is not correct (it contains higher order terms that should be removed by the end of BM)
        else:
            sigma = sigmaprev = Polynomial([GF2int(1)]) # error locator polynomial. Also called Lambda in other notations.
            sigmaprev = Polynomial([GF2int(1)]) # we need the previous iteration to compute the next value of the support polynomials
            B = Polynomial([GF2int(1)]) # this is the error locator support/secondary polynomial, which is a funky way to say that it's just a temporary variable that will help us construct sigma, the error locator polynomial
            omega = omegaprev = Polynomial([GF2int(1)]) # error evaluator polynomial. We don't need to initialize it with erasures_loc, it will still work, because Delta is computed using sigma, which itself is correctly initialized with erasures if needed.
            omegaprev = Polynomial([GF2int(1)])
            A = Polynomial([GF2int(0)]) # this is the error evaluator support/secondary polynomial, to help us construct omega
        L = 0 # update flag: necessary variable to check when updating is necessary and to check bounds (to avoid wrongly eliminating the higher order terms). For more infos, see https://www.cs.duke.edu/courses/spring11/cps296.3/decoding_rs.pdf
        #M = 0 # optional variable to check bounds (so that we do not mistakenly overwrite the higher order terms). This is not necessary, it's only an additional safe check. For more infos, see the presentation decoding_rs.pdf by Andrew Brown in the doc folder.

        # Fix the syndrome shifting: when computing the syndrome, some implementations may prepend a 0 coefficient for the lowest degree term (the constant). This is a case of syndrome shifting, thus the syndrome will be bigger than the number of ecc symbols (I don't know what purpose serves this shifting). If that's the case, then we need to account for the syndrome shifting when we use the syndrome such as inside BM, by skipping those prepended coefficients.
        # Another way to detect the shifting is to detect the 0 coefficients: by definition, a syndrome does not contain any 0 coefficient (except if there are no errors/erasures, in this case they are all 0). This however doesn't work with the modified Forney syndrome (that we do not use in this lib but it may be implemented in the future), which set to 0 the coefficients corresponding to erasures, leaving only the coefficients corresponding to errors.
        synd_shift = 0
        if len(s) > (n-k): synd_shift = len(s) - (n-k)

        # Polynomial constants:
        ONE = Polynomial([GF2int(1)])
        ZERO = GF2int(0)
        Z = Polynomial([GF2int(1), GF2int(0)]) # used to shift polynomials, simply multiply your poly * Z to shift

        # Precaching
        s2 = ONE+s

        # Iteratively compute the polynomials n-k-erasures_count times. The last ones will be correct (since the algorithm refines the error/errata locator polynomial iteratively depending on the discrepancy, which is kind of a difference-from-correctness measure).
        for l in xrange(n-k-erasures_count): # skip the first erasures_count iterations because we already computed the partial errata locator polynomial (by initializing with the erasures locator polynomial)
            K = erasures_count+l+synd_shift # skip the FIRST erasures_count iterations (not the last iterations, that's very important!)

            # Goal for each iteration: Compute sigma[l+1] and omega[l+1] such that
            # (1 + s)*sigma[l] == omega[l] in mod z^(K)

            # For this particular loop iteration, we have sigma[l] and omega[l],
            # and are computing sigma[l+1] and omega[l+1]

            # First find Delta, the non-zero coefficient of z^(K) in
            # (1 + s) * sigma[l]
            # Note that adding 1 to the syndrome s is not really necessary, you can do as well without.
            # This delta is valid for l (this iteration) only
            Delta = s2.mul_at(sigma, K) # Delta is also known as the Discrepancy, and is always a scalar (not a polynomial). We just need one coefficient at a specific degree, so we can optimize by computing only the polynomial multiplication at this term, and skip the others.

            # Can now compute sigma[l+1] and omega[l+1] from
            # sigma[l], omega[l], B[l], A[l], and Delta
            sigmaprev = sigma
            omegaprev = omega
            sigma = sigma - (Z * B).scale(Delta)
            omega = omega - (Z * A).scale(Delta)

            # Now compute the next support polynomials B and A
            # There are two ways to do this
            # This is based on a messy case analysis on the degrees of the four polynomials sigma, omega, A and B in order to minimize the degrees of A and B. For more infos, see https://www.cs.duke.edu/courses/spring10/cps296.3/decoding_rs_scribe.pdf
            # In fact it ensures that the degree of the final polynomials aren't too large.
            if Delta == ZERO or 2*L > K+erasures_count:
                #or (2*L == K+erasures_count and M == 0):
            #if Delta == ZERO or len(sigma) <= len(sigmaprev): # another way to compute when to update, and it doesn't require to maintain the update flag L
                # Rule A
                B = Z * B
                A = Z * A
                #L = L
                #M = M

            else:
            #elif (Delta != ZERO and 2*L < K+erasures_count) \
            #    or (2*L == K+erasures_count and M != 0):
            # elif Delta != ZERO and len(sigma) > len(sigmaprev): # another way to compute when to update, and it doesn't require to maintain the update flag L
                # Rule B
                B = sigmaprev.scale(Delta.inverse())
                A = omegaprev.scale(Delta.inverse())
                L = K - L # the update flag L is tricky: in Blahut's schema, it's mandatory to use `L = K - L - erasures_count` (and indeed in a previous draft of this function, if you forgot to do `- erasures_count` it would lead to correcting only 2*(errors+erasures) <= (n-k) instead of 2*errors+erasures <= (n-k)), but in this latest draft, this will lead to a wrong decoding in some cases where it should correctly decode! Thus you should try with and without `- erasures_count` to update L on your own implementation and see which one works OK without producing wrong decoding failures.
                #M = 1 - M

            #else:
            #    raise Exception("Code shouldn't have gotten here")

        # Hack to fix the simultaneous computation of omega, the errata evaluator polynomial: because A (the errata evaluator support polynomial) is not correctly initialized (I could not find any info in academic papers). So at the end, we get the correct errata evaluator polynomial omega + some higher order terms that should not be present, but since we know that sigma is always correct and the maximum degree should be the same as omega, we can fix omega by truncating too high order terms.
        if omega.degree > sigma.degree: omega = Polynomial(omega.coefficients[-(sigma.degree+1):])

        # Return the last result of the iterations (since BM compute iteratively, the last iteration being correct - it may already be before, but we're not sure)
        return sigma, omega

    def _find_error_evaluator(self, synd, sigma, k=None):
        '''Compute the error (or erasures if you supply sigma=erasures locator polynomial) evaluator polynomial Omega from the syndrome and the error/erasures/errata locator Sigma. Omega is already computed at the same time as Sigma inside the Berlekamp-Massey implemented above, but in case you modify Sigma, you can recompute Omega afterwards using this method, or just ensure that Omega computed by BM is correct given Sigma (as long as syndrome and sigma are correct, omega will be correct).'''
        n = self.n
        if not k: k = self.k

        # Omega(x) = [ (1 + Synd(x)) * Error_loc(x) ] mod x^(n-k+1)
        # NOTE: I don't know why we do 1+Synd(x) here, from docs it seems just Synd(x) is enough (and in practice if you remove the "ONE +" it will still decode correcty) as advised by Blahut in Algebraic Codes for Data Transmission, but it seems it's an implementation detail here.
        #ONE = Polynomial([GF2int(1)])
        #return ((ONE + synd) * sigma) % Polynomial([GF2int(1)] + [GF2int(0)] * (n-k+1)) # NOT CORRECT: in practice it works flawlessly with this implementation (primitive polynomial = 3), but if you use another primitive like in reedsolo lib, it doesn't work! Thus, I guess that adding ONE is not correct for the general case.
        return (synd * sigma) % Polynomial([GF2int(1)] + [GF2int(0)] * (n-k+1)) # Note that you should NOT do (1+Synd(x)) as can be seen in some books because this won't work with all primitive generators.

    def _find_error_evaluator_fast(self, synd, sigma, k=None):
        '''Compute the error (or erasures if you supply sigma=erasures locator polynomial) evaluator polynomial Omega from the syndrome and the error/erasures/errata locator Sigma. Omega is already computed at the same time as Sigma inside the Berlekamp-Massey implemented above, but in case you modify Sigma, you can recompute Omega afterwards using this method, or just ensure that Omega computed by BM is correct given Sigma (as long as syndrome and sigma are correct, omega will be correct).'''
        n = self.n
        if not k: k = self.k

        # Omega(x) = [ Synd(x) * Error_loc(x) ] mod x^(n-k+1) -- From Blahut, Algebraic codes for data transmission, 2003
        return (synd * sigma)._gffastmod(Polynomial([GF2int(1)] + [GF2int(0)] * (n-k+1))) # Note that you should NOT do (1+Synd(x)) as can be seen in some books because this won't work with all primitive generators.

    def _chien_search(self, sigma):
        '''Recall the definition of sigma, it has s roots. To find them, this
        function evaluates sigma at all 2^(c_exp-1) (ie: 255 for GF(2^8)) non-zero points to find the roots
        The inverse of the roots are X_i, the error locations

        Returns a list X of error locations, and a corresponding list j of
        error positions (the discrete log of the corresponding X value) The
        lists are up to s elements large.
        
        This is essentially an inverse Fourrier transform.

        Important technical math note: This implementation is not actually
        Chien's search. Chien's search is a way to evaluate the polynomial
        such that each evaluation only takes constant time. This here simply
        does 255 evaluations straight up, which is much less efficient.
        Said differently, we simply do a bruteforce search by trial substitution to find the zeros of this polynomial, which identifies the error locations.
        '''
        # TODO: find a more efficient algorithm, this is the slowest part of the whole decoding process (~2.5 ms, while any other part is only ~400microsec). Could try the Pruned FFT from "Simple Algorithms for BCH Decoding", by Jonathan Hong and Martin Vetterli, IEEE Transactions on Communications, Vol.43, No.8, August 1995
        X = []
        j = []
        p = GF2int(self.generator)
        # Try for each possible location
        for l in xrange(1, self.gf2_charac+1): # range 1:256 is important: if you use range 0:255, if the last byte of the ecc symbols is corrupted, it won't be correctable! You need to use the range 1,256 to include this last byte.
            #l = (i+self.fcr)
            # These evaluations could be more efficient, but oh well
            if sigma.evaluate( p**l ) == 0: # If it's 0, then bingo! It's an error location
                # Compute the error location polynomial X (will be directly used to compute the errors magnitudes inside the Forney algorithm)
                X.append( p**(-l) )
                # Compute the coefficient position (not the error position, it's actually the reverse: we compute the degree of the term where the error is located. To get the error position, just compute n-1-j).
                # This is different than the notes, I think the notes were in error
                # Notes said j values were just l, when it's actually 255-l
                j.append(self.gf2_charac - l)

        # Sanity check: the number of errors/errata positions found should be exactly the same as the length of the errata locator polynomial
        errs_nb = len(sigma) - 1 # compute the exact number of errors/errata that this error locator should find
        if len(j) != errs_nb:
            raise RSCodecError("Too many (or few) errors found by Chien Search for the errata locator polynomial!")

        return X, j

    def _chien_search_fast(self, sigma):
        '''Real chien search, we reuse the previous polynomial evaluation and just multiply by a constant polynomial. This should be faster, but it seems it's just the same speed as the other bruteforce version. However, it should easily be parallelizable.'''
        # TODO: doesn't work when fcr is different than 1 (X values are incorrectly "shifted"...)
        # TODO: try to mix this approach with the optimized walk on only interesting values, implemented in _chien_search_faster()
        X = []
        j = []
        p = GF2int(self.generator)
        if not hasattr(self, 'const_poly'): self.const_poly = [GF2int(self.generator)**(i+self.fcr) for i in xrange(self.gf2_charac, -1, -1)] # constant polynomial that will allow us to update the previous polynomial evaluation to get the next one
        const_poly = self.const_poly # caching for more efficiency since it never changes
        ev_poly, ev = sigma.evaluate_array( p**1 ) # compute the first polynomial evaluation
        # Try for each possible location
        for l in xrange(1, self.gf2_charac+1): # range 1:256 is important: if you use range 0:255, if the last byte of the ecc symbols is corrupted, it won't be correctable! You need to use the range 1,256 to include this last byte.
            #l = (i+self.fcr)

            # Check if it's a root for the polynomial
            if ev == 0: # If it's 0, then bingo! It's an error location
                # Compute the error location polynomial X (will be directly used to compute the errors magnitudes inside the Forney algorithm)
                X.append( p**(-l) )
                # Compute the coefficient position (not the error position, it's actually the reverse: we compute the degree of the term where the error is located. To get the error position, just compute n-1-j).
                # This is different than the notes, I think the notes were in error
                # Notes said j values were just l, when it's actually 255-l
                j.append(self.gf2_charac - l)

            # Update the polynomial evaluation for the next iteration
            # we simply multiply each term[k] with alpha^k (where here alpha = p = GF2int(generator)).
            # For more info, see the presentation by Andrew Brown, or this one: http://web.ntpu.edu.tw/~yshan/BCH_decoding.pdf
            # TODO: parallelize this loop
            for i in xrange(1, len(ev_poly)+1): # TODO: maybe the fcr != 1 fix should be put here?
                ev_poly[-i] *= const_poly[-i]
            # Compute the new evaluation by just summing
            ev = sum(ev_poly)

        return X, j

    def _chien_search_faster(self, sigma):
        '''Faster chien search, processing only useful coefficients (the ones in the messages) instead of the whole 2^8 range.
        Besides the speed boost, this also allows to fix a number of issue: correctly decoding when the last ecc byte is corrupted, and accepting messages of length n > 2^8.'''
        n = self.n
        X = []
        j = []
        p = GF2int(self.generator)
        # Normally we should try all 2^8 possible values, but here we optimize to just check the interesting symbols
        # This also allows to accept messages where n > 2^8.
        for l in xrange(n):
            #l = (i+self.fcr)
            # These evaluations could be more efficient, but oh well
            if sigma.evaluate( p**(-l) ) == 0: # If it's 0, then bingo! It's an error location
                # Compute the error location polynomial X (will be directly used to compute the errors magnitudes inside the Forney algorithm)
                X.append( p**l )
                # Compute the coefficient position (not the error position, it's actually the reverse: we compute the degree of the term where the error is located. To get the error position, just compute n-1-j).
                # This is different than the notes, I think the notes were in error
                # Notes said j values were just l, when it's actually 255-l
                j.append(l)

        # Sanity check: the number of errors/errata positions found should be exactly the same as the length of the errata locator polynomial
        errs_nb = len(sigma) - 1 # compute the exact number of errors/errata that this error locator should find
        if len(j) != errs_nb:
            # Note: decoding messages+ecc with length n > self.gf2_charac does work partially, but it's wrong, because you will get duplicated values, and then Chien Search cannot discriminate which root is correct and which is not. The duplication of values is normally prevented by the prime polynomial reduction when generating the field (see init_lut() in ff.py), but if you overflow the field, you have no guarantee anymore. We may try to use a bruteforce approach: the correct positions ARE in the final array j, but the problem is because we are above the Galois Field's range, there is a wraparound because of overflow so that for example if j should be [0, 1, 2, 3], we will also get [255, 256, 257, 258] (because 258 % 255 == 3, same for the other values), so we can't discriminate. The issue with that bruteforce approach is that fixing any errs_nb errors among those will always give a correct output message (in the sense that the syndrome will be all 0), so we may not even be able to check if that's correct or not, so there's clearly no way to decode a message of greater length than the field.
            raise RSCodecError("Too many (or few) errors found by Chien Search for the errata locator polynomial!")

        return X, j

    def _old_forney(self, omega, X, k=None):
        '''Computes the error magnitudes (only works with errors or erasures under t = floor((n-k)/2), not with erasures above (n-k)//2)'''
        # XXX Is floor division okay here? Should this be ceiling?
        if not k: k = self.k
        t = (self.n - k) // 2

        Y = []

        for l, Xl in enumerate(X):

            # Compute the sequence product and multiply its inverse in
            prod = GF2int(1) # just to init the product (1 is the neutral term for multiplication)
            Xl_inv = Xl.inverse()
            for ji in xrange(t): # do not change to xrange(len(X)) as can be seen in some papers, it won't give the correct result! (sometimes yes, but not always)
                if ji == l:
                    continue
                if ji < len(X):
                    Xj = X[ji]
                else: # if above the maximum degree of the polynomial, then all coefficients above are just 0 (that's logical...)
                    Xj = GF2int(0)
                prod = prod * (Xl - Xj)
                #if (ji != l):
                #    prod = prod * (GF2int(1) - X[ji]*(Xl.inverse()))

            # Compute Yl
            Yl = Xl**t * omega.evaluate(Xl_inv) * Xl_inv * prod.inverse()

            Y.append(Yl)
        return Y

    def _forney(self, omega, X):
        '''Computes the error magnitudes. Works also with erasures and errors+erasures beyond the (n-k)//2 bound, here the bound is 2*e+v <= (n-k-1) with e the number of errors and v the number of erasures.'''
        # XXX Is floor division okay here? Should this be ceiling?

        Y = [] # the final result, the error/erasures polynomial (contain the values that we should minus on the received message to get the repaired message)
        Xlength = len(X)
        for l, Xl in enumerate(X):

            Xl_inv = Xl.inverse()

            # Compute the formal derivative of the error locator polynomial (see Blahut, Algebraic codes for data transmission, pp 196-197).
            # the formal derivative of the errata locator is used as the denominator of the Forney Algorithm, which simply says that the ith error value is given by error_evaluator(gf_inverse(Xi)) / error_locator_derivative(gf_inverse(Xi)). See Blahut, Algebraic codes for data transmission, pp 196-197.
            sigma_prime = [1 - Xl_inv * X[j] for j in xrange(Xlength) if j != l] # TODO? maybe a faster way would be to precompute sigma_prime = sigma[len(sigma) & 1:len(sigma):2] and then just do sigma_prime.evaluate(X[j]) ? (like in reedsolo.py)
            sigma_prime = reduce(mul, sigma_prime, 1) # compute the product

            # Compute Yl
            # This is a more faithful translation of the theoretical equation contrary to the old forney method. Here it is exactly copy/pasted from the included presentation decoding_rs.pdf: Yl = omega(Xl.inverse()) / prod(1 - Xj*Xl.inverse()) for j in len(X) (in the paper it's for j in s, but it's useless when len(X) < s because we compute neutral terms 1 for nothing, and wrong when correcting more than s erasures or erasures+errors since it prevents computing all required terms).
            # Thus here this method works with erasures too because firstly we fixed the equation to be like the theoretical one (don't know why it was modified in _old_forney(), if it's an optimization, it doesn't enhance anything), and secondly because we removed the product bound on s, which prevented computing errors and erasures above the s=(n-k)//2 bound.
            # The best resource I have found for the correct equation is https://en.wikipedia.org/wiki/Forney_algorithm -- note that in the article, fcr is defined as c.
            Yl = - (Xl**(1-self.fcr)  * omega.evaluate(Xl_inv) / sigma_prime) # sigma_prime is the denominator of the Forney algorithm

            Y.append(Yl)
        return Y

# Not implemented here (because it must be implemented by the interface that will use this library) are the 6 techniques of modifying ecc codes. Here is a brief summary:
# defining a message by its length n, its dimension k, and its redundancy r = n−k, we can modify it by :
# (i) Augmenting. Fix n; increase k; decrease r.
# (ii) Expurgating. Fix n; decrease k; increase r.
# (iii) Extending. Fix k; increase n; increase r.
# (iv) Puncturing. Fix k; decrease n; decrease r.
# (v) Lengthening. Fix r; increase n; increase k.
# (vi) Shortening. Fix r; decrease n; decrease k.
# In practice, for example, puncturing is the removal of parity symbols from a codeword, and shortening is the removal of message symbols from a codeword and padding with 0.
# Here's a great intro: http://users.math.msu.edu/users/jhall/classes/codenotes/Mod.pdf

if __name__ == "__main__":
    import sys
    coder = RSCoder(255,223)
    if "-d" in sys.argv:
        method = coder.decode
        blocksize = 255
    else:
        method = coder.encode
        blocksize = 223

    while True:
        block = sys.stdin.read(blocksize)
        if not block: break
        code = method(block)
        sys.stdout.write(code)


