#!/usr/bin/env python
#
# ECC Speed Tester
# Copyright (C) 2015-2023 Larroque Stephen
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
from lib._compat import _range, _bytes, _str
from lib.aux_funcs import sizeof_fmt
from lib.eccman import ECCMan, compute_ecc_params
from lib.hasher import Hasher
from reedsolo import ReedSolomonError

# Import necessary libraries
import argparse
import math, random
import datetime, time

# Import progress bar
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

def main(argv=None, command=None):
    if argv is None: # if argv is empty, fetch from the commandline
        argv = sys.argv[1:]
    elif isinstance(argv, _str): # else if argv is supplied but it's a simple string, we need to parse it to a list of arguments before handing to argparse or any other argument parser
        argv = shlex.split(argv) # Parse string just like argv using shlex

    #==== COMMANDLINE PARSER ====

    #== Commandline description
    desc = '''ECC Speedtest
Description: Tests encoding and/or decoding speed of error correction codes using the specified configuration and ecc algorithms.
    '''
    ep = ''' '''

    #-- Constructing the parser
    # Only command-line usage, use the standard argparse
    # Delete the special argument to avoid unrecognized argument error in argparse
    # Initialize the normal argparse parser
    # Note that prog allows to change the shown calling script, it is necessary to manually set it when it is called as a subcommand (of pff.py). If None, prog will default to sys.argv[0] but with the absolute path removed.
    main_parser = argparse.ArgumentParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter, prog=command)
    # Define dummy dict to keep compatibile with command-line usage
    widget_dir = {}
    widget_filesave = {}
    widget_file = {}
    widget_text = {}

    # Required arguments

    # Optional arguments
    main_parser.add_argument('--ecc_algo', type=int, default=3, required=False,
                        help='What algorithm use to generate and verify the ECC? Values possible: 1-4. 1 is the formal, fully verified Reed-Solomon in base 3 ; 2 is a faster implementation but still based on the formal base 3 ; 3 is an even faster implementation but based on another library which may not be correct ; 4 is the fastest implementation supporting US FAA ADSB UAT RS FEC standard but is totally incompatible with the other three (a text encoded with any of 1-3 modes will be decodable with any one of them).', **widget_text)
    main_parser.add_argument('--max_block_size', type=int, default=255, required=False,
                        help='Max block size, cannot exceed 255.', **widget_text)
    main_parser.add_argument('--resilience_rate', type=float, default=0.2, required=False,
                        help='Number of ecc symbols to compute per block, as a percent of the whole message size.', **widget_text)
    main_parser.add_argument('--tamper_rate', type=float, default=0.4, required=False,
                        help='How much we tamper each message before decoding. Note that tamper rate is relative to the number of ecc bytes, not the whole message (unlike --resilience_rate).', **widget_text)
    main_parser.add_argument('--tamper_mode', type=str, default='noise', required=False,
                        help='How do we tamper each message before decoding, can be "noise" or "erasure" (tamper_rate can be 2x as much with erasure than with noise). Noise means that characters that get tampered are considered errors, their positions will not be given to the decoder. Hence, with erasure mode, only erasures are done as the positions of tampered characters are provided to the decoder, so that the Reed-Solomon algorithm works slightly differently and may be much faster since it does not have to search for where errors are located.', **widget_text)
    main_parser.add_argument('--msg_nb', type=int, default=1000000, required=False,
                        help='Total number of messages/blocks to test.', **widget_text)
    main_parser.add_argument('--decoding_mode', type=int, required=False, default=1,
                        help='0 for only encoding, 1 for both encoding then decoding, 2 for only decoding (which includes an encoding step).')
    main_parser.add_argument('--subchunking', action='store_true', required=False, default=False,
                        help='Subchunk directly in the speedtest, instead of letting the Reed-Solomon library do it.')
    main_parser.add_argument('--subchunking_size', type=int, required=False, default=50,
                        help='Size of subchunks, if enabled.')

    #== Parsing the arguments
    args = main_parser.parse_args(argv) # Storing all arguments to args

    # Setup configuration variables. Change here if you want to.
    max_block_size = args.max_block_size
    resilience_rate = args.resilience_rate
    ecc_algo = args.ecc_algo
    msg_nb = args.msg_nb
    tamper_rate = args.tamper_rate
    tamper_mode = args.tamper_mode
    decoding_mode = args.decoding_mode
    subchunking = args.subchunking
    subchunk_size = args.subchunking_size

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
    print("%s." % ("Only encoding test" if decoding_mode == 0 else ("Encoding and decoding test" if decoding_mode == 1 else "Decoding test only (including an encoding step)")))

    # -- Encoding test
    # IMPORTANT: we do NOT check the correctness of encoding, only the speed! It's up to you to verify that you are computing the ecc correctly.
    if not decoding_mode == 2:
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
    if decoding_mode in [1, 2]:
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
