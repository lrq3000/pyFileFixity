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

# future division is important to divide integers and get as
# a result precise floating numbers (instead of truncated int)
#from __future__ import division, absolute_import, with_statement  # unnecessary since we dropped Python 2 support, but still can be interesting if we reimplement in Cython, Cython v3 will be needed for the maths

# Include the lib folder in the python import path (so that packaged modules can be easily called, such as gooey which always call its submodules via gooey parent module)
import sys, os
thispathname = os.path.dirname(__file__)
sys.path.append(os.path.join(thispathname))

# Import necessary libraries
from lib._compat import _str, _range
from lib.aux_funcs import fullpath, recwalk, is_dir, is_file, is_dir_or_file
import argparse
import os, sys, random
import shlex # for string parsing as argv argument to main(), unnecessary otherwise
from lib.tee import Tee # Redirect print output to the terminal as well as in a log file
from tqdm import tqdm


#***********************************
#     AUXILIARY FUNCTIONS
#***********************************

def tamper_file_at(path, pos=0, replace_str=None):
    """ Tamper a file at the given position and using the given string """
    if not replace_str:
        replace_str = "\x00"
    try:
        with open(path, "r+b") as fh:
            if pos < 0: # if negative, we calculate the position backward from the end of file
                fsize = os.fstat(fh.fileno()).st_size
                pos = fsize + pos
            fh.seek(pos)
            fh.write(replace_str)
    except IOError:
        return False
    finally:
        try:
            fh.close()
        except Exception:
            pass
    return True

def tamper_file(filepath, mode='e', proba=0.03, block_proba=None, blocksize=65535, burst_length=None, header=None):
    """ Randomly tamper a file's content """
    if header and header > 0:
        blocksize = header

    tamper_count = 0 # total number of characters tampered in the file
    total_size = 0 # total buffer size, NOT necessarily the total file size (depends if you set header or not)
    with open(filepath, "r+b") as fh: # 'r+' allows to read AND overwrite characters. Else any other option won't allow both ('a+' read and append, 'w+' erases the file first then allow to read and write), and 'b' is just for binary because we can open any filetype.
        if proba >= 1: proba = 1.0/os.fstat(fh.fileno()).st_size * proba # normalizing probability if it's an integer (ie: the number of characters to flip on average)
        buf = fh.read(blocksize) # We process blocks by blocks because it's a lot faster (IO is still the slowest operation in any computing system)
        while len(buf) > 0:
            total_size += len(buf)
            if not block_proba or (random.random() < block_proba): # If block tampering is enabled, process only if this block is selected by probability
                pos2tamper = []
                burst_remain = 0 # if burst is enabled and corruption probability is triggered, then we will here store the remaining number of characters to corrupt (the length is uniformly sampled over the range specified in arguments)
                # Create the list of bits to tamper (it's a lot more efficient to precompute the list of characters to corrupt, and then modify in the file the characters all at once)
                for i in _range(len(buf)):
                    if burst_remain > 0 or (random.random() < proba): # Corruption probability: corrupt only if below the bit-flip proba
                        pos2tamper.append(i) # keep this character's position in the to-be-corrupted list
                        if burst_remain > 0: # if we're already in a burst, we minus one and continue onto the next character
                            burst_remain -= 1
                        elif burst_length: # else we're not in a burst, we create one (triggered by corruption probability: as soon as one character triggers the corruption probability, then we do a burst)
                            burst_remain = random.randint(burst_length[0], burst_length[1]) - 1 # if burst is enabled, then we randomly (uniformly) pick a random length for the burst between the range specified, and since we already tampered one character, we minus 1
                # If there's any character to tamper in the list, we tamper the string
                if pos2tamper:
                    tamper_count = tamper_count + len(pos2tamper)
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
    return [tamper_count, total_size]

def tamper_dir(inputpath, *args, **kwargs):
    """ Randomly tamper the files content in a directory tree, recursively """
    silent = kwargs.get('silent', False)
    if 'silent' in kwargs: del kwargs['silent']

    filescount = 0
    for _ in tqdm(recwalk(inputpath), desc='Precomputing', disable=silent):
        filescount += 1

    files_tampered = 0
    tamper_count = 0
    total_size = 0
    for dirname, filepath in tqdm(recwalk(inputpath), total=filescount, leave=True, desc='Tamper file n.', disable=silent):
        tcount, tsize = tamper_file(os.path.join(dirname, filepath), *args, **kwargs)
        if tcount > 0:
            tamper_count += tcount
            files_tampered += 1
        total_size += tsize
    return [files_tampered, filescount, tamper_count, total_size]


#***********************************
#        GUI AUX FUNCTIONS
#***********************************

# Try to import Gooey for GUI display, but manage exception so that we replace the Gooey decorator by a dummy function that will just return the main function as-is, thus keeping the compatibility with command-line usage
try:  # pragma: no cover
    import gooey
except ImportError as exc:
    # Define a dummy replacement function for Gooey to stay compatible with command-line usage
    class gooey(object):  # pragma: no cover
        def Gooey(func):
            return func
    # If --gui was specified, then there's a problem
    if len(sys.argv) > 1 and sys.argv[1] == '--gui':  # pragma: no cover
        print('ERROR: --gui specified but an error happened with lib/gooey, cannot load the GUI (however you can still use this script in commandline). Check that lib/gooey exists and that you have wxpython installed. Here is the error: ')
        raise(exc)

def conditional_decorator(flag, dec):  # pragma: no cover
    def decorate(fn):
        if flag:
            return dec(fn)
        else:
            return fn
    return decorate

def check_gui_arg():  # pragma: no cover
    '''Check that the --gui argument was passed, and if true, we remove the --gui option and replace by --gui_launched so that Gooey does not loop infinitely'''
    if len(sys.argv) > 1 and sys.argv[1] == '--gui':
        # DEPRECATED since Gooey automatically supply a --ignore-gooey argument when calling back the script for processing
        #sys.argv[1] = '--gui_launched' # CRITICAL: need to remove/replace the --gui argument, else it will stay in memory and when Gooey will call the script again, it will be stuck in an infinite loop calling back and forth between this script and Gooey. Thus, we need to remove this argument, but we also need to be aware that Gooey was called so that we can call gooey.GooeyParser() instead of argparse.ArgumentParser() (for better fields management like checkboxes for boolean arguments). To solve both issues, we replace the argument --gui by another internal argument --gui_launched.
        return True
    else:
        return False

def AutoGooey(fn):  # pragma: no cover
    '''Automatically show a Gooey GUI if --gui is passed as the first argument, else it will just run the function as normal'''
    if check_gui_arg():
        return gooey.Gooey(fn)
    else:
        return fn


#***********************************
#                       MAIN
#***********************************

@AutoGooey
def main(argv=None, command=None):
    if argv is None: # if argv is empty, fetch from the commandline
        argv = sys.argv[1:]
    elif isinstance(argv, _str): # else if argv is supplied but it's a simple string, we need to parse it to a list of arguments before handing to argparse or any other argument parser
        argv = shlex.split(argv) # Parse string just like argv using shlex

    #==== COMMANDLINE PARSER ====

    #== Commandline description
    desc = '''Random file/directory characters tamperer in Python
Description: Randomly tampers characters in a file or in a directory tree recursively (useful to test for integrity/repair after).
WARNING: this will tamper the file you specify. Please ensure you keep a copy of the original!
    '''
    ep = '''NOTE: this script tampers at the character (byte) level, not the bits! Thus the measures you will get here may be different from those you will find in papers (you must divide your probability by 8).'''

    #-- Constructing the parser
    # Use GooeyParser if we want the GUI because it will provide better widgets
    if len(argv) > 0 and (argv[0] == '--gui' and not '--ignore-gooey' in argv):  # pragma: no cover
        # Initialize the Gooey parser
        main_parser = gooey.GooeyParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter, prog=command)
        # Define Gooey widget types explicitly (because type auto-detection doesn't work quite well)
        widget_dir = {"widget": "DirChooser"}
        widget_filesave = {"widget": "FileSaver"}
        widget_file = {"widget": "FileChooser"}
        widget_text = {"widget": "TextField"}
    else: # Else in command-line usage, use the standard argparse
        # Delete the special argument to avoid unrecognized argument error in argparse
        if '--ignore-gooey' in argv: argv.remove('--ignore-gooey') # this argument is automatically fed by Gooey when the user clicks on Start
        # Initialize the normal argparse parser
        # Note that prog allows to change the shown calling script, it is necessary to manually set it when it is called as a subcommand (of pff.py). If None, prog will default to sys.argv[0] but with the absolute path removed.
        main_parser = argparse.ArgumentParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter, prog=command)
        # Define dummy dict to keep compatibile with command-line usage
        widget_dir = {}
        widget_filesave = {}
        widget_file = {}
        widget_text = {}
    # Required arguments
    main_parser.add_argument('-i', '--input', metavar='filetotamper.ext', type=is_dir_or_file, nargs=1, required=True,
                        help='Path to the file (or directory tree) to tamper.', **widget_dir)
    main_parser.add_argument('-m', '--mode', metavar='e, erasure, n, noise', type=str, nargs=1, required=True,
                        help='Tampering mode: erasure or noise?', **widget_text)
    main_parser.add_argument('-p', '--probability', type=float, nargs=1, required=True,
                        help='Probability of corruption (float between 0.0 and 1.0)', **widget_text)
    # Optional arguments
    main_parser.add_argument('--block_probability', type=float, nargs=1, required=False,
                        help='Probability of block tampering (between 0.0 and 1.0, do not set it if you want to spread errors evenly, but researchs have shown that errors are rather at block level and not evenly distributed)', **widget_text)
    main_parser.add_argument('-b', '--burst_length', metavar="startint|endint", type=str, required=False,
                        help='If specified, this will define the number of consecutive characters that will be corrupted when the corruption probability (--probability) is triggered. Specify a range startint|endint, the burst length will be uniformly sampled over this range.')
    main_parser.add_argument('--header', type=int, required=False,
                        help='Only tamper the header of the file')

    main_parser.add_argument('-l', '--log', metavar='/some/folder/filename.log', type=str, nargs=1, required=False,
                        help='Path to the log file. (Output will be piped to both the stdout and the log file)', **widget_filesave)
    main_parser.add_argument('-v', '--verbose', action='store_true', required=False, default=False,
                        help='Verbose mode (show more output).')
    main_parser.add_argument('--silent', action='store_true', required=False, default=False,
                        help='No console output (but if --log specified, the log will still be saved in the specified file).')

    #== Parsing the arguments
    args = main_parser.parse_args(argv) # Storing all arguments to args

    #-- Set variables from arguments
    filepath = fullpath(args.input[0])
    mode = args.mode[0]
    proba = float(args.probability[0])
    verbose = args.verbose
    silent = args.silent

    burst_length = args.burst_length
    if burst_length: burst_length = [int(r) for r in burst_length.split('|')] # split range and convert to int

    block_proba = None
    if args.block_probability:
        block_proba = float(args.block_probability[0])

    blocksize = 65536
    header = args.header

    # -- Configure the log file if enabled (ptee.write() will write to both stdout/console and to the log file)
    if args.log:
        ptee = Tee(args.log[0], 'a', nostdout=silent)
        #sys.stdout = Tee(args.log[0], 'a')
        sys.stderr = Tee(args.log[0], 'a', nostdout=silent)
    else:
        ptee = Tee(nostdout=silent)

    # == PROCESSING BRANCHING == #
    # Sanity check
    if not os.path.exists(filepath):
        raise RuntimeError("Path does not exist: %s" % filepath)
    else:
        # -- Tampering a file
        if os.path.isfile(filepath):
            ptee.write('Tampering the file %s, please wait...' % os.path.basename(filepath))
            tcount, tsize = tamper_file(filepath, mode=mode, proba=proba, block_proba=block_proba, blocksize=blocksize, burst_length=burst_length, header=header, silent=silent)
            ptee.write("Tampering done: %i/%i (%.2f%%) characters tampered." % (tcount, tsize, tcount / max(1, tsize) * 100))
        # -- Tampering a directory tree recursively
        elif os.path.isdir(filepath):
            ptee.write('Tampering all files in directory %s, please wait...' % filepath)
            files_tampered, filescount, tcount, tsize = tamper_dir(filepath, mode=mode, proba=proba, block_proba=block_proba, blocksize=blocksize, burst_length=burst_length, header=header, silent=silent)
            ptee.write("Tampering done: %i/%i files tampered and overall %i/%i (%.2f%%) characters were tampered." % (files_tampered, filescount, tcount, tsize, tcount / max(1, tsize) * 100))

    ptee.close()
    return 0


# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":
    sys.exit(main())
