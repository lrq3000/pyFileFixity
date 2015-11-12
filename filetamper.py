#!/usr/bin/env python
#
# Random file characters tamperer
# Randomly tampers characters in a file in order to test for integrity after.
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
#------------------------------
#
# This script is similar to what has been done in a paper, albeit in a dumbed down version (since they could automatically check for corruption measures based on file format): Heydegger, Volker. "Analysing the impact of file formats on data integrity." Archiving Conference. Vol. 2008. No. 1. Society for Imaging Science and Technology, 2008.
# And another interesting paper by the same author: Heydegger, Volker. "Just one bit in a million: On the effects of data corruption in files." Research and Advanced Technology for Digital Libraries. Springer Berlin Heidelberg, 2009. 315-326.
# Errors are not evenly spread but rather block level (thus concentrated). Addis, Matthew, et al. "Reliable Audiovisual Archiving Using Unreliable Storage Technology and Services." (2009).
#

# Import necessary libraries
from lib.aux_funcs import fullpath
import lib.argparse as argparse
import os, sys, random
import shlex # for string parsing as argv argument to main(), unnecessary otherwise


def main(argv=None):
    if argv is None: # if argv is empty, fetch from the commandline
        argv = sys.argv[1:]
    elif isinstance(argv, basestring): # else if argv is supplied but it's a simple string, we need to parse it to a list of arguments before handing to argparse or any other argument parser
        argv = shlex.split(argv) # Parse string just like argv using shlex

    #==== COMMANDLINE PARSER ====

    #== Commandline description
    desc = '''Random file characters tamperer in Python
Description: Randomly tampers characters in a file in order to test for integrity after.
    '''
    ep = '''NOTE: this script tampers at the character (byte) level, not the bits! Thus the measures you will get here may be different from those you will find in papers (you must divide your probability by 8).'''

    #== Commandline arguments
    #-- Constructing the parser
    main_parser = argparse.ArgumentParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter)
    # Required arguments
    main_parser.add_argument('-i', '--input', metavar='filetotamper.ext', type=str, nargs=1, required=True,
                        help='Path to the file to tamper.')
    main_parser.add_argument('-m', '--mode', metavar='e, erasure, n, noise', type=str, nargs=1, required=True,
                        help='Tampering mode: erasure or noise?')
    main_parser.add_argument('-p', '--probability', type=float, nargs=1, required=True,
                        help='Probability of corruption (float between 0.0 and 1.0)')
    # Optional arguments
    main_parser.add_argument('--block_probability', type=float, nargs=1, required=False,
                        help='Probability of block tampering (between 0.0 and 1.0, do not set it if you want to spread errors evenly, but researchs have shown that errors are rather at block level and not evenly distributed)')
    main_parser.add_argument('-b', '--burst_length', metavar="startint|endint", type=str, required=False,
                        help='If specified, this will define the number of consecutive characters that will be corrupted when the corruption probability (--probability) is triggered. Specify a range startint|endint, the burst length will be uniformly sampled over this range.')
    main_parser.add_argument('--header', type=int, required=False,
                        help='Only tamper the header of the file')

    #== Parsing the arguments
    args = main_parser.parse_args(argv) # Storing all arguments to args

    #-- Set variables from arguments
    filepath = fullpath(args.input[0])
    mode = args.mode[0]
    proba = float(args.probability[0])
    burst_length = args.burst_length
    if burst_length: burst_length = [int(r) for r in burst_length.split('|')] # split range and convert to int

    block_proba = None
    if args.block_probability:
        block_proba = float(args.block_probability[0])

    blocksize = 65536
    header = args.header
    if header and header > 0:
        blocksize = header

    print('Tampering the file %s, please wait...' % os.path.basename(filepath))
    if not os.path.isfile(filepath):
        print("File does not exist: %s" % filepath)
    else:
        count = 0
        with open(filepath, "r+b") as fh: # 'r+' allows to read AND overwrite characters. Else any other option won't allow both ('a+' read and append, 'w+' erases the file first then allow to read and write), and 'b' is just for binary because we can open any filetype.
            if proba >= 1: proba = 1.0/os.fstat(fh.fileno()).st_size * proba # normalizing probability if it's an integer (ie: the number of characters to flip on average)
            buf = fh.read(blocksize) # We process blocks by blocks because it's a lot faster (IO is still the slowest operation in any computing system)
            while len(buf) > 0:
                if not block_proba or (random.random() < block_proba): # If block tampering is enabled, process only if this block is selected by probability
                    pos2tamper = []
                    burst_remain = 0 # if burst is enabled and corruption probability is triggered, then we will here store the remaining number of characters to corrupt (the length is uniformly sampled over the range specified in arguments)
                    # Create the list of bits to tamper (it's a lot more efficient to precompute the list of characters to corrupt, and then modify in the file the characters all at once)
                    for i in xrange(len(buf)):
                        if burst_remain > 0 or (random.random() < proba): # Corruption probability: corrupt only if below the bit-flip proba
                            pos2tamper.append(i) # keep this character's position in the to-be-corrupted list
                            if burst_remain > 0: # if we're already in a burst, we minus one and continue onto the next character
                                burst_remain -= 1
                            elif burst_length: # else we're not in a burst, we create one (triggered by corruption probability: as soon as one character triggers the corruption probability, then we do a burst)
                                burst_remain = random.randint(burst_length[0], burst_length[1]) - 1 # if burst is enabled, then we randomly (uniformly) pick a random length for the burst between the range specified, and since we already tampered one character, we minus 1
                    # If there's any character to tamper in the list, we tamper the string
                    if pos2tamper:
                        count = count + len(pos2tamper)
                        #print("Before: %s" % buf)
                        buf = bytearray(buf) # Strings in Python are immutable, thus we need to convert to a bytearray
                        for pos in pos2tamper:
                            if mode == 'e' or mode == 'erasure': # Erase the character (set a null byte)
                                buf[pos] = 0
                            elif mode == 'n' or mode == 'noise': # Noising the character (set a random ASCII character)
                                buf[pos] = random.randint(0,255)
                        #print("After: %s" % buf)
                        # Overwriting the string into the file
                        prevpos = fh.tell() # need to store and place back the seek cursor because after the write, if it's the end of the file, the next read may be buggy (getting characters that are not part of the file)
                        fh.seek(fh.tell()-len(buf)) # Move the cursor at the beginning of the string we just read
                        fh.write(buf) # Overwrite it
                        fh.seek(prevpos) # Restore the previous position after the string
                # If we only tamper the header, we stop here by setting the buffer to an empty string
                if header and header > 0:
                    buf = ''
                # Else we continue to the next data block
                else:
                    # Load the next characters from file
                    buf = fh.read(blocksize)
        print("Tampering done: %i characters tampered." % count)


# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":
    sys.exit(main())
