#!/usr/bin/env python
#
# ECC Speed Tester
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
#
#

# Include the lib folder in the python import path (so that packaged modules can be easily called, such as gooey which always call its submodules via gooey parent module)
import sys, os
thispathname = os.path.dirname(__file__)
sys.path.append(os.path.join(thispathname))

# ECC and hashing facade libraries
from lib._compat import _range, _bytes
from lib.aux_funcs import sizeof_fmt
from lib.eccman import ECCMan, compute_ecc_params
from lib.hasher import Hasher
from reedsolo import ReedSolomonError

# Import necessary libraries
import random, math
import time, datetime
import tqdm


def gen_random_string(n, size):
    '''Generate very fastly a random hexadecimal string. Kudos to jcdryer http://stackoverflow.com/users/131084/jcdyer'''
    # The main insight is that we can just compute a big int of the total message size and then convert it to a string

    # Init length of string (this will be used to convert the bigint to a string)
    hexstr = '%0'+str(size)+'x'

    for _ in _range(n):
        # Generate a random string
        yield hexstr % random.randrange(16**size) # Generate a random bigint of the size we require, and convert to a string

def format_sizeof(num, suffix='bytes'):
    return sizeof_fmt(num, suffix, 1000)


#***********************************
#                       MAIN
#***********************************

def main(argv=None):
    # Setup configuration variables. Change here if you want to.
    max_block_size = 255
    resilience_rate = 0.2
    ecc_algo = 3
    msg_nb = 1000000
    tamper_rate = 0.4 # tamper rate is relative to the number of ecc bytes, not the whole message (not like the resilience_rate)
    tamper_mode = 'noise' # noise or erasure
    no_decoding = False  # True for only encoding, False for both encoding then decoding, 3 for only decoding (which includes an encoding step)
    subchunking = False
    subchunk_size = 50

    # Precompute some parameters and load up ecc manager objects (big optimization as g_exp and g_log tables calculation is done only once)
    hasher_none = Hasher('none') # for index ecc we don't use any hash
    ecc_params = compute_ecc_params(max_block_size, resilience_rate, hasher_none)
    ecc_params_subchunk = compute_ecc_params(subchunk_size, resilience_rate, hasher_none)
    ecc_manager = ECCMan(max_block_size, ecc_params["message_size"], algo=ecc_algo)
    ecc_manager_subchunk = ECCMan(subchunk_size, ecc_params_subchunk["message_size"], algo=ecc_algo)

    # == Main loop
    print("====================================")
    print("ECC Speed Test, started on %s" % datetime.datetime.now().isoformat())
    print("====================================")
    print("ECC algorithm: %i." % ecc_algo)
    print("%s." % ("Only encoding test" if no_decoding is True else ("Encoding and decoding test" if no_decoding is False else "Decoding test only (including an encoding step)")))

    # -- Encoding test
    # IMPORTANT: we do NOT check the correctness of encoding, only the speed! It's up to you to verify that you are computing the ecc correctly.
    if not no_decoding == 3:
        total_time = 0
        total_size = msg_nb*max_block_size
        bardisp = tqdm.tqdm(total=total_size, leave=True, desc='ENC', unit='B', unit_scale=True, ncols=79, mininterval=0.5) # display progress bar based on the number of bytes encoded
        k = ecc_params["message_size"]
        # Generate a random string and encode it
        for msg in gen_random_string(msg_nb, k):
            start = time.process_time()  # time.clock() was dropped in Py3.8, use time.perf_counter() instead to time performance including sleep, or time.process_time() without sleep periods.
            if subchunking:
                for i in xrange(0, len(msg), subchunk_size):
                    ecc_manager_subchunk.encode(msg[i:i+subchunk_size])
            else:
                ecc_manager.encode(msg)
            total_time += time.process_time() - start
            bardisp.update(max_block_size)
        bardisp.close()
        print("Encoding: total time elapsed: %f sec for %s of data. Real Speed (only encoding, no other computation): %s." % (total_time, format_sizeof(total_size, 'B'), format_sizeof(total_size/total_time, 'B/sec') ))
    
    # -- Decoding test
    if not no_decoding or no_decoding == 3:
        total_time = 0
        total_size = msg_nb*max_block_size
        bardisp = tqdm.tqdm(total=total_size*2, leave=True, desc='DEC', unit='B', unit_scale=True) # display progress bar based on the number of bytes encoded
        # Generate a random string and encode it
        for msg in gen_random_string(msg_nb, ecc_params["message_size"]):
            # Make it into a bytearray first
            msg = bytearray(msg, 'utf-8')
            # Computing the ecc first
            ecc = ecc_manager.encode(msg)

            # Then tamper it randomly
            # First generate a list of random indices where we will tamper
            tamper_idx = random.sample(_range(ecc_params["message_size"]), int(math.floor(ecc_params["ecc_size"] * tamper_rate)))
            # Convert to bytearray to easily modify characters in the message
            msg_tampered = bytearray(msg)
            # Tamper the characters
            for pos in tamper_idx:
                if tamper_mode == 'n' or tamper_mode == 'noise': # Noising the character (set a random ASCII character)
                    msg_tampered[pos] = random.randint(0,255)
                elif tamper_mode == 'e' or tamper_mode == 'erasure': # Erase the character (set a null byte)
                    msg_tampered[pos] = 0
            # Convert back to a string
            msg_tampered = _bytes(msg_tampered)
            ecc = _bytes(ecc)

            # Decode the tampered message with ecc
            start = time.process_time()
            try:
                msg_repaired, ecc_repaired = ecc_manager.decode(msg_tampered, ecc)
                # Check if the decoding was successful, else there's a problem, the decoding may be buggy
                if not ecc_manager.check(msg_repaired, ecc_repaired): raise ReedSolomonError
            except ReedSolomonError:
                print("Warning, there was an error while decoding. Please check your parameters (tamper_rate not too high) or the decoding procedure.")
                pass
            total_time += time.process_time() - start
            bardisp.update(max_block_size*2)  # update x2 because we encode AND decode
        bardisp.close()
        print("Decoding: total time elapsed: %f sec for %s of data. Real Speed (only decoding, no other computation): %s." % (total_time, format_sizeof(total_size, 'B'), format_sizeof(total_size/total_time, 'B/sec') ))

    return 0

# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":
    sys.exit(main())
