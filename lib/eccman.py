#!/usr/bin/env python
#
# ECC manager facade api
# Allows to easily use different kinds of ECC algorithms and libraries under one single class.
# Copyright (C) 2015 Larroque Stephen
#
# Licensed under the MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# ECC libraries
import lib.brownanrs.rs as brownanrs # Pure python implementation of Reed-Solomon with configurable max_block_size and automatic error detection (you don't have to specify where they are). This is a base 3 implementation that is formally correct and with unit tests.
import lib.reedsolomon.reedsolo as reedsolo # Faster pure python implementation of Reed-Solomon, with a base 3 compatible encoder (but not yet decoder! But you can use brownanrs to decode).

def compute_ecc_params(max_block_size, rate, hasher):
    '''Compute the ecc parameters (size of the message, size of the hash, size of the ecc). This is an helper function to easily compute the parameters from a resilience rate to instanciate an ECCMan object.'''
    #message_size = max_block_size - int(round(max_block_size * rate * 2, 0)) # old way to compute, wasn't really correct because we applied the rate on the total message+ecc size, when we should apply the rate to the message size only (that is not known beforehand, but we want the ecc size (k) = 2*rate*message_size or in other words that k + k * 2 * rate = n)
    message_size = int(round(float(max_block_size) / (1 + 2*rate), 0))
    ecc_size = max_block_size - message_size
    hash_size = len(hasher) # 32 when we use MD5
    return {"message_size": message_size, "ecc_size": ecc_size, "hash_size": hash_size}

class ECCMan(object):
    '''Error correction code manager, which provides a facade API to use different kinds of ecc algorithms or libraries.'''

    def __init__(self, n, k, algo=1):
        if algo == 1 or algo == 2: # brownanrs library implementations: fully correct base 3 implementation, and mode 2 is for fast encoding
            self.ecc_manager = brownanrs.RSCoder(n, k)
        elif algo == 3: # reedsolo fast implementation, compatible with brownanrs in base 3
            reedsolo.init_tables_base3()
            self.g = reedsolo.rs_generator_poly_base3(n)
            self.ecc_manager = brownanrs.RSCoder(n, k) # used for decoding
        elif algo == 4: # reedsolo fast implementation, incompatible with any other implementation
            reedsolo.init_tables(0x187) # parameters for US FAA ADSB UAT RS FEC
            self.prim = 0x187
            self.fcr = 120

        self.algo = algo
        self.n = n
        self.k = k

    def encode(self, message, k=None):
        '''Encode one message block (up to 255) into an ecc'''
        if not k: k = self.k
        message, _ = self.pad(message, k=k)
        if self.algo == 1:
            mesecc = self.ecc_manager.encode(message, k=k)
        elif self.algo == 2:
            mesecc = self.ecc_manager.encode_fast(message, k=k)
        elif self.algo == 3:
            mesecc = reedsolo.rs_encode_msg(message, self.n-k, gen=self.g[k])
        elif self.algo == 4:
            mesecc = reedsolo.rs_encode_msg(message, self.n-k, fcr=self.fcr)

        ecc = mesecc[len(message):]
        return ecc

    def decode(self, message, ecc, k=None):
        '''Repair a message and its ecc also, given the message and its ecc (both can be corrupted, we will still try to fix both of them)'''
        if not k: k = self.k
        message, pad = self.pad(message, k=k)
        ecc, _ = self.rpad(ecc, k=k) # fill ecc with null bytes if too small (maybe the field delimiters were misdetected and this truncated the ecc? But we maybe still can correct if the truncation is less than the resilience rate)
        if self.algo == 1 or self.algo == 2 or self.algo == 3:
            res, ecc_repaired = self.ecc_manager.decode(message + ecc, nostrip=True, k=k) # Avoid automatic stripping because we are working with binary streams, thus we should manually strip padding only when we know we padded
        elif self.algo == 4:
            res, ecc_repaired = reedsolo.rs_correct_msg(bytearray(message + ecc), self.n-k, fcr=self.fcr)
            res = bytearray(res)
            ecc_repaired = bytearray(ecc_repaired)

        if pad: # Strip the null bytes if we padded the message before decoding
            res = res[len(pad):len(res)]
        return res, ecc_repaired

    def pad(self, message, k=None):
        '''Automatically left pad with null bytes a message if too small, or leave unchanged if not necessary. This allows to keep track of padding and strip the null bytes after decoding reliably with binary data.'''
        if not k: k = self.k
        pad = None
        if len(message) < k:
            pad = "\x00" * (k-len(message))
            message = pad + message
        return [message, pad]

    def rpad(self, ecc, k=None):
        '''Automatically right pad with null bytes an ecc to fill for missing bytes if too small, or leave unchanged if not necessary. This can be used as a workaround for field delimiter misdetection.'''
        if not k: k = self.k
        pad = None
        if len(ecc) < self.n-k:
            print("Warning: the ecc field may have been truncated (entrymarker or field_delim misdetection?).")
            pad = "\x00" * (self.n-k-len(ecc))
            ecc = ecc + pad
        return [ecc, pad]

    def verify(self, message, ecc, k=None):
        '''Verify that a message+ecc is a correct RS code (essentially it's the same purpose as check, the only difference is the methodology)'''
        if not k: k = self.k
        message, _ = self.pad(message, k=k)
        ecc, _ = self.rpad(ecc, k=k)
        if self.algo == 1 or self.algo == 2:
            return self.ecc_manager.verify(message + ecc, k=k)

    def check(self, message, ecc, k=None):
        '''Check if there's any error in a message+ecc. Can be used before decoding, in addition to hashes to detect if the message was tampered, or after decoding to check that the message was fully recovered.'''
        if not k: k = self.k
        message, _ = self.pad(message, k=k)
        ecc, _ = self.rpad(ecc, k=k)
        if self.algo == 1 or self.algo == 2:
            return self.ecc_manager.check(message + ecc, k=k)
        elif self.algo == 3:
            return reedsolo.rs_check_base3(bytearray(message + ecc), self.n-k)
        elif self.algo == 4:
            return reedsolo.rs_check(bytearray(message + ecc), self.n-k, fcr=self.fcr)

    def description(self):
        '''Provide a description for each algorithm available, useful to print in ecc file'''
        if self.algo <= 3:
            return "Reed-Solomon with polynomials in Galois field 256 (2^8) of base 3."
        elif self.algo == 4:
            return "Reed-Solomon with polynomials in Galois field 256 (2^8) under US FAA ADSB UAT RS FEC standard with prim=%s and fcr=%s." % (self.prim, self.fcr)
        else:
            return "No description for this ECC algorithm."