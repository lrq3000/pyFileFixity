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

# Compatibility with Python 3
from _compat import _str, _range, b, _bytes

from .distance.distance import hamming

# ECC libraries
try: # Try to automatically load Cython implementations if compiled
    from .brownanrs import rs as brownanrs
    from .reedsolomon import creedsolo as reedsolo
    #from .brownanrs import crs as brownanrs
except ImportError:
    from .brownanrs import rs as brownanrs # Pure python implementation of Reed-Solomon with configurable max_block_size and automatic error detection (you don't have to specify where they are). This is a base 3 implementation that is formally correct and with unit tests.
    from .reedsolomon import reedsolo as reedsolo # Faster pure python implementation of Reed-Solomon, with a base 3 compatible encoder (but not yet decoder! But you can use brownanrs to decode).

rs_encode_msg = reedsolo.rs_encode_msg # local reference for small speed boost
#rs_encode_msg_precomp = reedsolo.rs_encode_msg_precomp


### Auxiliary ECC functions ###


def compute_ecc_params(max_block_size, rate, hasher):
    '''Compute the ecc parameters (size of the message, size of the hash, size of the ecc). This is an helper function to easily compute the parameters from a resilience rate to instanciate an ECCMan object.'''
    #message_size = max_block_size - int(round(max_block_size * rate * 2, 0)) # old way to compute, wasn't really correct because we applied the rate on the total message+ecc size, when we should apply the rate to the message size only (that is not known beforehand, but we want the ecc size (k) = 2*rate*message_size or in other words that k + k * 2 * rate = n)
    message_size = int(round(float(max_block_size) / (1 + 2*rate), 0))
    ecc_size = max_block_size - message_size
    hash_size = len(hasher) # 32 when we use MD5
    return {"message_size": message_size, "ecc_size": ecc_size, "hash_size": hash_size}

def detect_reedsolomon_parameters(message, mesecc_orig, gen_list=[2, 3, 5], c_exp=8):
    '''Use an exhaustive search to automatically find the correct parameters for the ReedSolomon codec from a sample message and its encoded RS code.
    Arguments: message is the sample message, eg, "hello world" ; mesecc_orig is the message variable encoded with RS block appended at the end.
    '''
    # Description: this is basically an exhaustive search where we will try every possible RS parameter, then try to encode the sample message, and see if the resulting RS code is close to the supplied code.
    # All variables except the Galois Field's exponent are automatically generated and searched.
    # To compare with the supplied RS code, we compute the Hamming distance, so that even if the RS code is tampered, we can still find the closest set of RS parameters to decode this message.
    # The goal is to provide users a function so that they can use the "hello world" sample string in generated ECC files to recover their RS parameters in case they forget them. But users can use any sample message: for example, if they have an untampered file and its relative ecc track, they can use the ecc track as the mesecc_orig and their original file as the sample message.

    from .reedsolomon import reedsolo as reedsolop # need to import another time the reedsolo library for detect_reedsolomon_parameters to work (because we need to reinit all the tables, and they are declared module-wide, so this would conflict with decoding)

    # Init the variables
    n = len(mesecc_orig)
    k = len(message)
    field_charac = int((2**c_exp) - 1)
    maxval1 = max([ord(x) if isinstance(x, _str) else x for x in message ])
    maxval2 = max([ord(x) if isinstance(x, _str) else x for x in mesecc_orig])
    maxval = max([maxval1, maxval2])
    if (maxval > field_charac):
        raise ValueError("The specified field's exponent is wrong, the message contains values (%i) above the field's cardinality (%i)!" % (maxval, field_charac))

    # Prepare the variable that will store the result
    best_match = {"hscore": -1, "params": [{"gen_nb": 0, "prim": 0, "fcr": 0}]}

    if isinstance(message, _str):
        message = b(message)

    # Exhaustively search by generating every combination of values for the RS parameters and test the Hamming distance
    for gen_nb in gen_list:
        prim_list = reedsolop.find_prime_polys(generator=gen_nb, c_exp=c_exp, fast_primes=False, single=False)
        for prim in prim_list:
            reedsolop.init_tables(prim)
            for fcr in _range(field_charac):
                #g = reedsolop.rs_generator_poly_all(n, fcr=fcr, generator=gen_nb)
                # Generate a RS code from the sample message using the current combination of RS parameters
                mesecc = reedsolop.rs_encode_msg(message, n-k, fcr=fcr)
                # Compute the Hamming distance
                h = hamming(mesecc, mesecc_orig)
                # If the Hamming distance is lower than the previous best match (or if it's the first try), save this set of parameters
                if best_match["hscore"] == -1 or h <= best_match["hscore"]:
                    # If the distance is strictly lower than for the previous match, then we replace the previous match with the current one
                    if best_match["hscore"] == -1 or h < best_match["hscore"]:
                        best_match["hscore"] = h
                        best_match["params"] = [{"gen_nb": gen_nb, "prim": prim, "fcr": fcr}]
                    # Else there is an ambiguity: the Hamming distance is the same as for the previous best match, so we keep the previous set of parameters but we append the current set
                    elif h == best_match["hscore"]:
                        best_match["params"].append({"gen_nb": gen_nb, "prim": prim, "fcr": fcr})
                    # If Hamming distance is 0, then we have found a perfect match (the current set of parameters allow to generate the exact same RS code from the sample message), so we stop here
                    if h == 0: break

    # Printing the results to the user
    if best_match["hscore"] >= 0 and best_match["hscore"] < len(mesecc_orig):
        perfect_match_str = " (0=perfect match)" if best_match["hscore"]==0 else ""
        result = ''
        result += "Found closest set of parameters, with Hamming distance %i%s:\n" % (best_match["hscore"], perfect_match_str)
        for param in best_match["params"]:
            result += "gen_nb=%s prim=%s(%s) fcr=%s\n" % (param["gen_nb"], param["prim"], hex(param["prim"]), param["fcr"])
        return result
    else:
        return "Parameters could not be automatically detected..."


### Main ECCMan Class to manage ECC codecs ###


class ECCMan(object):
    '''Error correction code manager, which provides a facade API to use different kinds of ecc algorithms or libraries/codecs.'''

    def __init__(self, n, k, algo=1):
        self.c_exp = 8 # we stay in GF(2^8) for this software
        self.field_charac = int((2**self.c_exp) - 1)

        if algo == 1 or algo == 2: # brownanrs library implementations: fully correct base 3 implementation, and mode 2 is for fast encoding
            self.gen_nb = 3
            self.prim = 0x11b
            self.fcr = 1

            self.ecc_manager = brownanrs.RSCoder(n, k, generator=self.gen_nb, prim=self.prim, fcr=self.fcr)
        elif algo == 3: # reedsolo fast implementation, compatible with brownanrs in base 3
            self.gen_nb = 3
            self.prim = 0x11b
            self.fcr = 1

            reedsolo.init_tables(generator=self.gen_nb, prim=self.prim)
            self.g = reedsolo.rs_generator_poly_all(n, fcr=self.fcr, generator=self.gen_nb)
            #self.gf_mul_arr, self.gf_add_arr = reedsolo.gf_precomp_tables()
        elif algo == 4: # reedsolo fast implementation, incompatible with any other implementation
            self.gen_nb = 2
            self.prim = 0x187
            self.fcr = 120

            reedsolo.init_tables(self.prim) # parameters for US FAA ADSB UAT RS FEC
            self.g = reedsolo.rs_generator_poly_all(n, fcr=self.fcr, generator=self.gen_nb)
        else:
            raise Exception("Specified algorithm %i is not supported!" % algo)

        self.algo = algo
        self.n = n
        self.k = k

    def encode(self, message, k=None):
        '''Encode one message block (up to 255) into an ecc'''
        if not k: k = self.k
        message, _ = self.pad(b(message), k=k)
        if self.algo == 1:
            mesecc = self.ecc_manager.encode(message, k=k)
        elif self.algo == 2:
            mesecc = self.ecc_manager.encode_fast(message, k=k)
        elif self.algo == 3 or self.algo == 4:
            mesecc = rs_encode_msg(message, self.n-k, fcr=self.fcr, gen=self.g[self.n-k])
            #mesecc = rs_encode_msg_precomp(message, self.n-k, fcr=self.fcr, gen=self.g[self.n-k])

        ecc = mesecc[len(message):]
        return _bytes(ecc)

    def decode(self, message, ecc, k=None, enable_erasures=False, erasures_char="\x00", only_erasures=False):
        '''Repair a message and its ecc also, given the message and its ecc (both can be corrupted, we will still try to fix both of them)'''
        if not k: k = self.k

        # Optimization, use bytearray
        if isinstance(message, _str):
            message = bytearray([ord(x) for x in message])
        if isinstance(ecc, _str):
            ecc = bytearray([ord(x) for x in ecc])

        # Detect erasures positions and replace with null bytes (replacing erasures with null bytes is necessary for correct syndrome computation)
        # Note that this must be done before padding, else we risk counting the padded null bytes as erasures!
        erasures_pos = None
        if enable_erasures:
            # Concatenate to find erasures in the whole codeword
            mesecc = message + ecc
            # Convert char to a int (because we use a bytearray)
            if isinstance(erasures_char, _str): erasures_char = ord(erasures_char)
            # Find the positions of the erased characters
            erasures_pos = [i for i in _range(len(mesecc)) if mesecc[i] == erasures_char]
            # Failing case: no erasures could be found and we want to only correct erasures, then we return the message as-is
            if only_erasures and not erasures_pos: return message, ecc

        # Pad with null bytes if necessary
        message, pad = self.pad(message, k=k)
        ecc, _ = self.rpad(ecc, k=k) # fill ecc with null bytes if too small (maybe the field delimiters were misdetected and this truncated the ecc? But we maybe still can correct if the truncation is less than the resilience rate)

        # If the message was left padded, then we need to update the positions of the erasures
        if erasures_pos and pad:
            len_pad = len(pad)
            erasures_pos = [x+len_pad for x in erasures_pos]

        # Decoding
        if self.algo == 1:
            msg_repaired, ecc_repaired = self.ecc_manager.decode(message + ecc, nostrip=True, k=k, erasures_pos=erasures_pos, only_erasures=only_erasures) # Avoid automatic stripping because we are working with binary streams, thus we should manually strip padding only when we know we padded
        elif self.algo == 2:
            msg_repaired, ecc_repaired = self.ecc_manager.decode_fast(message + ecc, nostrip=True, k=k, erasures_pos=erasures_pos, only_erasures=only_erasures)
        elif self.algo == 3:
            #msg_repaired, ecc_repaired = self.ecc_manager.decode_fast(message + ecc, nostrip=True, k=k, erasures_pos=erasures_pos, only_erasures=only_erasures)
            msg_repaired, ecc_repaired = reedsolo.rs_correct_msg_nofsynd(bytearray(message + ecc), self.n-k, fcr=self.fcr, generator=self.gen_nb, erase_pos=erasures_pos, only_erasures=only_erasures)
            msg_repaired = bytearray(msg_repaired)
            ecc_repaired = bytearray(ecc_repaired)
        elif self.algo == 4:
            msg_repaired, ecc_repaired = reedsolo.rs_correct_msg(bytearray(message + ecc), self.n-k, fcr=self.fcr, generator=self.gen_nb, erase_pos=erasures_pos, only_erasures=only_erasures)
            msg_repaired = bytearray(msg_repaired)
            ecc_repaired = bytearray(ecc_repaired)

        if pad: # Strip the null bytes if we padded the message before decoding
            msg_repaired = msg_repaired[len(pad):len(msg_repaired)]
        return _bytes(msg_repaired), _bytes(ecc_repaired)

    def pad(self, message, k=None):
        '''Automatically left pad with null bytes a message if too small, or leave unchanged if not necessary. This allows to keep track of padding and strip the null bytes after decoding reliably with binary data. Equivalent to shortening (shortened reed-solomon code).'''
        if not k: k = self.k
        pad = None
        if len(message) < k:
            #pad = "\x00" * (k-len(message))
            pad = bytearray(k-len(message))
            message = pad + bytearray(b(message))
        return [message, pad]

    def rpad(self, ecc, k=None):
        '''Automatically right pad with null bytes an ecc to fill for missing bytes if too small, or leave unchanged if not necessary. This can be used as a workaround for field delimiter misdetection. Equivalent to puncturing (punctured reed-solomon code).'''
        if not k: k = self.k
        pad = None
        if len(ecc) < self.n-k:
            print("Warning: the ecc field may have been truncated (entrymarker or field_delim misdetection?).")
            #pad = "\x00" * (self.n-k-len(ecc))
            pad = bytearray(self.n-k-len(ecc))
            ecc = bytearray(ecc) + pad
        return [ecc, pad]

    def check(self, message, ecc, k=None):
        '''Check if there's any error in a message+ecc. Can be used before decoding, in addition to hashes to detect if the message was tampered, or after decoding to check that the message was fully recovered.'''
        if not k: k = self.k
        message, _ = self.pad(message, k=k)
        ecc, _ = self.rpad(ecc, k=k)
        if self.algo == 1 or self.algo == 2:
            return self.ecc_manager.check_fast(message + ecc, k=k)
        elif self.algo == 3 or self.algo == 4:
            return reedsolo.rs_check(bytearray(message + ecc), self.n-k, fcr=self.fcr, generator=self.gen_nb)

    def description(self):
        '''Provide a description for each algorithm available, useful to print in ecc file'''
        if 0 < self.algo <= 3:
            return "Reed-Solomon with polynomials in Galois field of characteristic %i (2^%i) with generator=%s, prime poly=%s and first consecutive root=%s." % (self.field_charac, self.c_exp, self.gen_nb, hex(self.prim), self.fcr)
        elif self.algo == 4:
            return "Reed-Solomon with polynomials in Galois field of characteristic %i (2^%i) under US FAA ADSB UAT RS FEC standard with generator=%s, prime poly=%s and first consecutive root=%s." % (self.field_charac, self.c_exp, self.gen_nb, hex(self.prim), self.fcr)
        else:
            return "No description for this ECC algorithm."
