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

# Import necessary libraries
import argparse
import os, sys, random

# Relative path to absolute
def fullpath(relpath):
    if (type(relpath) is object or type(relpath) is file):
        relpath = relpath.name
    return os.path.abspath(os.path.expanduser(relpath))


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    #==== COMMANDLINE PARSER ====

    #== Commandline description
    desc = '''Random file characters tamperer in Python
Description: Randomly tampers characters in a file in order to test for integrity after.
    '''
    ep = ''' '''

    #== Commandline arguments
    #-- Constructing the parser
    main_parser = argparse.ArgumentParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter)
    # Required arguments
    main_parser.add_argument('-i', '--input', metavar='filetotamper.ext', type=str, nargs=1, required=True,
                        help='Path to the file to tamper.')
    main_parser.add_argument('-m', '--mode', metavar='e, erasure, n, noise', type=str, nargs=1, required=True,
                        help='Tampering mode: erasure or noise?')
    main_parser.add_argument('-p', '--probability', type=float, nargs=1, required=True,
                        help='Probability of tampering (float between 0.0 and 1.0)')

    #== Parsing the arguments
    args = main_parser.parse_args(argv) # Storing all arguments to args

    #-- Set variables from arguments
    filepath = fullpath(args.input[0])
    mode = args.mode[0]
    proba = float(args.probability[0])
    blocksize = 65536

    print('Tampering the file %s, please wait...' % os.path.basename(filepath))
    if os.path.isfile(filepath):
        count = 0
        count2 = 0
        with open(filepath, "r+b") as fh:
            buf = fh.read(blocksize)
            while len(buf) > 0:
                pos2tamper = []
                for i in xrange(len(buf)):
                    if (random.random() < proba):
                        pos2tamper.append(i)
                if pos2tamper:
                    count = count + len(pos2tamper)
                    #print("Before: %s" % buf)
                    buf = bytearray(buf)
                    for pos in pos2tamper:
                        if mode == 'e' or mode == 'erasure':
                            buf[pos] = 0
                        elif mode == 'n' or mode == 'noise':
                            buf[pos] = random.randint(0,255)
                    #print("After: %s" % buf)
                    prevpos = fh.tell()
                    fh.seek(fh.tell()-len(buf))
                    fh.write(buf)
                    fh.seek(prevpos) # need to store and place back the seek cursor because after the write, if it's the end of the file, the next read may be buggy (getting characters that are not part of the file)
                # Load the next characters from file
                buf = fh.read(blocksize)
    print("Tampering done: %i characters tampered." % count)


# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":
    sys.exit(main())
