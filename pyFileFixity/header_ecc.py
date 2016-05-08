#!/usr/bin/env python
#
# Error Correction Code for Files Headers
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
#=================================
#  Error Correction Code for Files Headers
#                by Stephen Larroque
#                       License: MIT
#              Creation date: 2015-03-12
#=================================
#
# From : http://simple.wikipedia.org/wiki/Reed-Solomon_error_correction
# The key idea behind a Reed-Solomon code is that the data encoded is first visualized as a polynomial. The code relies on a theorem from algebra that states that any k distinct points uniquely determine a polynomial of degree at most k-1.
# The sender determines a degree k-1 polynomial, over a finite field, that represents the k data points. The polynomial is then "encoded" by its evaluation at various points, and these values are what is actually sent. During transmission, some of these values may become corrupted. Therefore, more than k points are actually sent. As long as sufficient values are received correctly, the receiver can deduce what the original polynomial was, and decode the original data.
# In the same sense that one can correct a curve by interpolating past a gap, a Reed-Solomon code can bridge a series of errors in a block of data to recover the coefficients of the polynomial that drew the original curve.
# This is done automatically using a simple trick: the matrix inversion. For more infos, see this well-explained blog post by Richard Kiss: How to be Minimally Redundant (or "A Splitting Headache") http://blog.richardkiss.com/?p=264
#
# codeword_rate: rs = @(n,k) k / n
# @(n,k) (n - k) / k
#
# To get higher resilience against corruption: make the codeword bigger (decrease k and increase n = higher resilience ratio), and use smaller packets (n should be smaller). Source: Kumar, Sanjeev, and Ragini Gupta. "Bit error rate analysis of Reed-Solomon code for efficient communication system." International Journal of Computer Applications 30.12 (2011): 11-15.
# Note: in the paper, they told that their results indicate to use bigger blocks, but if you look at the Figure 4, this shows the opposite: the best performing parameters is: RS(246, 164) with code rate 0.66667 = resilience ratio 0.25
# Note2: however, logically, it's more sensible to use bigger blocks to be more resilient. Indeed, since data stream is hashed and ecc'ed per block, this means that if an error burst corrupt a block twice the size of max_block_size (or just the size of max_block_size but exactly overlapping on one block, no shift), then the block will be unrecoverable. In other words, if we have bigger blocks, we raise the required size for an error burst to permanently corrupt our data (thus we diminish the risk). Thus, it would make sense to use error correcting codes with very big blocks. However, this would probably incur a huge performance drop, at least for Reed-Solomon which is basically grounded on matrix operations (thus the complexity would be about O(max_block_size^2), a quadratic complexity).
#
#  If 2s + r < 2t (s errors, r erasures) t
#
# TODO:
# - Performance boost in Reed-Solomon libraries. A big work was done, and it's quite fast when using PyPy 2.5.0, but 10x more speedup (to attain 10MB/s encoding rate) would just be perfect! Decoding rate is sufficiently speedy as it is, no need to optimize that part.
# Use Cauchy Reed-Solomon, which significantly outperforms simple Reed-Solomon?
# or https://bitbucket.org/kmgreen2/pyeclib with jerasure
# or http://www.bth.se/fou/cuppsats.nsf/all/bcb2fd16e55a96c2c1257c5e00666323/$file/BTH2013KARLSSON.pdf
# or https://www.usenix.org/legacy/events/fast09/tech/full_papers/plank/plank_html/
# - Also backup folders meta-data? (to reconstruct the tree in case a folder is truncated by bit rot)
#

from __future__ import with_statement

from ._infos import __version__

# Include the lib folder in the python import path (so that packaged modules can be easily called, such as gooey which always call its submodules via gooey parent module)
import sys, os
thispathname = os.path.dirname(__file__)
sys.path.append(os.path.join(thispathname))

# Import necessary libraries
from lib._compat import _str, _range, b, _izip
from lib.aux_funcs import get_next_entry, is_dir, is_dir_or_file, fullpath, recwalk, sizeof_fmt, path2unix
import lib.argparse as argparse
import datetime, time
import lib.tqdm as tqdm
import itertools
import math
#import operator # to get the max out of a dict
import csv # to process the errors_file from rfigc.py
import shlex # for string parsing as argv argument to main(), unnecessary otherwise
from lib.tee import Tee # Redirect print output to the terminal as well as in a log file
import struct # to support indexes backup file
#import pprint # Unnecessary, used only for debugging purposes

# ECC and hashing facade libraries
from lib.eccman import ECCMan, compute_ecc_params
from lib.hasher import Hasher
from lib.reedsolomon.reedsolo import ReedSolomonError
from lib.brownanrs.rs import RSCodecError



#***********************************
#     AUXILIARY FUNCTIONS
#***********************************

def entry_fields(entry, field_delim="\xFF"):
    '''From a raw ecc entry (a string), extract the metadata fields (filename, filesize, ecc for both), and the rest being blocks of hash and ecc per blocks of the original file's header'''
    entry = entry.lstrip(field_delim) # if there was some slight adjustment error (example: the last ecc block of the last file was the field_delim, then we will start with a field_delim, and thus we need to remove the trailing field_delim which is useless and will make the field detection buggy). This is not really a big problem for the previous file's ecc block: the missing ecc characters (which were mistaken for a field_delim), will just be missing (so we will lose a bit of resiliency for the last block of the previous file, but that's not a huge issue, the correction can still rely on the other characters).

    # Find metadata fields delimiters positions
    # TODO: automate this part, just give in argument the number of field_delim to find, and the func will find the x field_delims (the number needs to be specified in argument because the field_delim can maybe be found wrongly inside the ecc stream, which we don't want)
    first = entry.find(field_delim)
    second = entry.find(field_delim, first+len(field_delim))
    third = entry.find(field_delim, second+len(field_delim))
    fourth = entry.find(field_delim, third+len(field_delim))
    # Note: we do not try to find all the field delimiters because we optimize here: we just walk the string to find the exact number of field_delim we are looking for, and after we stop, no need to walk through the whole string.

    # Extract the content of the fields
    # Metadata fields
    relfilepath = entry[:first]
    filesize = entry[first+len(field_delim):second]
    relfilepath_ecc = entry[second+len(field_delim):third]
    filesize_ecc = entry[third+len(field_delim):fourth]
    # Ecc stream field (aka ecc blocks)
    ecc_field = entry[fourth+len(field_delim):]

    # Try to convert to an int, an error may happen
    try:
        filesize = int(filesize)
    except Exception as e:
        print("Exception when trying to detect the filesize in ecc field (it may be corrupted), skipping: ")
        print(e)
        #filesize = 0 # avoid setting to 0, we keep as an int so that we can try to fix using intra-ecc

    # entries = [ {"message":, "ecc":, "hash":}, etc.]
    #print(entry)
    #print(len(entry))
    return {"relfilepath": relfilepath, "relfilepath_ecc": relfilepath_ecc, "filesize": filesize, "filesize_ecc": filesize_ecc, "ecc_field": ecc_field}

def entry_assemble(entry_fields, ecc_params, header_size, filepath, fileheader=None):
    '''From an entry with its parameters (filename, filesize), assemble a list of each block from the original file along with the relative hash and ecc for easy processing later.'''
    # Extract the header from the file
    if fileheader is None:
        with open(filepath, 'rb') as file: # filepath is the absolute path to the original file (the one with maybe corruptions, NOT the output repaired file!)
            # Compute the size of the buffer to read: either header_size if possible, but if the file is smaller than that then we will read the whole file.
            if isinstance(entry_fields["filesize"], int) and entry_fields["filesize"] > 0 and entry_fields["filesize"] < header_size:
                fileheader = file.read(entry_fields["filesize"])
            else:
                fileheader = file.read(header_size)

    # Cut the header and the ecc entry into blocks, and then assemble them so that we can easily process block by block
    entry_asm = []
    for i, j in _izip(_range(0, len(fileheader), ecc_params["message_size"]), _range(0, len(entry_fields["ecc_field"]), ecc_params["hash_size"] + ecc_params["ecc_size"])):
        # Extract each fields from each block
        mes = fileheader[i:i+ecc_params["message_size"]]
        hash = entry_fields["ecc_field"][j:j+ecc_params["hash_size"]]
        ecc = entry_fields["ecc_field"][j+ecc_params["hash_size"]:j+ecc_params["hash_size"]+ecc_params["ecc_size"]]
        entry_asm.append({"message": mes, "hash": hash, "ecc": ecc})

    # Return a list of fields for each block
    return entry_asm

def compute_ecc_hash(ecc_manager, hasher, buf, max_block_size, rate, message_size=None, as_string=False):
    '''Split a string in blocks given max_block_size and compute the hash and ecc for each block, and then return a nice list with both for easy processing.'''
    result = []
    # If required parameters were not provided, we compute them
    if not message_size:
        ecc_params = compute_ecc_params(max_block_size, rate, hasher)
        message_size = ecc_params["message_size"]
    # Split the buffer string in blocks (necessary for Reed-Solomon encoding because it's limited to 255 characters max)
    for i in _range(0, len(buf), message_size):
        # Compute the message block
        mes = buf[i:i+message_size]
        # Compute the ecc
        ecc = ecc_manager.encode(mes)
        # Compute the hash
        hash = hasher.hash(mes)
        #crc = zlib.crc32(mes) # DEPRECATED: CRC is not resilient enough
        #print("mes %i (%i) - ecc %i (%i) - hash %i (%i)" % (len(mes), message_size, len(ecc), ecc_params["ecc_size"], len(hash), ecc_params["hash_size"])) # DEBUGLINE

        # Return the result (either in string for easy writing into a file, or in a list for easy post-processing)
        if as_string:
            result.append(b(hash)+b(ecc))
        else:
            result.append([b(hash), b(ecc)])
    return result

def ecc_correct_intra(ecc_manager_intra, ecc_params_intra, field, ecc, entry_pos, enable_erasures=False, erasures_char="\x00", only_erasures=False):
    """ Correct an intra-field with its corresponding intra-ecc if necessary """
    fentry_fields = {"ecc_field": ecc}
    field_correct = [] # will store each block of the corrected (or already correct) filepath
    fcorrupted = False # check if field was corrupted
    fcorrected = True # check if field was corrected (if it was corrupted)
    errmsg = ''
    # Decode each block of the filepath
    for e in entry_assemble(fentry_fields, ecc_params_intra, len(field), '', field):
        # Check if this block of the filepath is OK, if yes then we just copy it over
        if ecc_manager_intra.check(e["message"], e["ecc"]):
            field_correct.append(e["message"])
        else: # Else this block is corrupted, we will try to fix it using the ecc
            fcorrupted = True
            # Repair the message block and the ecc
            try:
                repaired_block, repaired_ecc = ecc_manager_intra.decode(e["message"], e["ecc"], enable_erasures=enable_erasures, erasures_char=erasures_char, only_erasures=only_erasures)
            except (ReedSolomonError, RSCodecError) as exc: # the reedsolo lib may raise an exception when it can't decode. We ensure that we can still continue to decode the rest of the file, and the other files.
                repaired_block = None
                repaired_ecc = None
                errmsg += "- Error: unrecoverable corrupted metadata field at offset %i: %s\n" % (entry_pos[0], exc)
            # Check if the block was successfully repaired: if yes then we copy the repaired block...
            if repaired_block is not None and ecc_manager_intra.check(repaired_block, repaired_ecc):
                field_correct.append(repaired_block)
            else: # ... else it failed, then we copy the original corrupted block and report an error later
                field_correct.append(e["message"])
                fcorrected = False
    # Join all the blocks into one string to build the final filepath
    field_correct = [b(x) for x in field_correct] # workaround when using --ecc_algo 3 or 4, because we get a list of bytearrays instead of str
    field = b''.join(field_correct)
    # Report errors
    return (field, fcorrupted, fcorrected, errmsg)



#***********************************
#        GUI AUX FUNCTIONS
#***********************************

# Try to import Gooey for GUI display, but manage exception so that we replace the Gooey decorator by a dummy function that will just return the main function as-is, thus keeping the compatibility with command-line usage
try:  # pragma: no cover
    import lib.gooey as gooey
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

#@conditional_decorator(check_gui_arg(), gooey.Gooey) # alternative to AutoGooey which also correctly works
@AutoGooey
def main(argv=None):
    if argv is None: # if argv is empty, fetch from the commandline
        argv = sys.argv[1:]
    elif isinstance(argv, _str): # else if argv is supplied but it's a simple string, we need to parse it to a list of arguments before handing to argparse or any other argument parser
        argv = shlex.split(argv) # Parse string just like argv using shlex

    #==== COMMANDLINE PARSER ====

    #== Commandline description
    desc = '''Error Correction Code for Files Headers
Description: Given a directory, generate or check/correct the headers (defined by a constant number of bits in arguments) for every files recursively. Using Reed-Solomon for the ECC management.
Headers are the most sensible part of any file: this is where the format definition and parameters are specified, and in addition for compression formats, the beginning of the file (just after the header) is usually where the most important strings of data are stored and compressed. Thus, having a high redundancy specifically for the headers means that you ensure that you will be able to at least open the file (file format will be recognized), and for compressed files that the most important symbols will be restituted.
The concept is to use this script in addition to more common parity files like PAR2 so that you get an additional protection at low cost (because headers are just in the first KB of the file, thus it won't cost much in storage and processing time to add more redundancy to such a small stream of data).
Note: Folders meta-data is NOT accounted, only the files! Use DVDisaster or a similar tool to also cover folders meta-data.
    '''
    ep = '''Use --gui as the first argument to use with a GUI (via Gooey).

Note1: this is a pure-python implementation (except for MD5 hash but a pure-python alternative is provided in lib/md5py.py), thus it may be VERY slow to generate an ecc file. To speed-up things considerably, you can use PyPy v2.5.0 or above, there will be a speed-up of at least 100x from our experiments (you can expect an encoding rate of more than 1MB/s). Feel free to profile using easy_profiler.py and try to optimize the encoding parts of the reed-solomon libraries.

Note2: that Reed-Solomon can correct up to 2*resilience_rate erasures (eg, null bytes, you know where they are) or resilience_rate errors (an error is a corrupted character but you don't know its position) and amount to an additional storage of 2*resilience_rate storage compared to the original total files size.
'''

    #== Commandline arguments
    #-- Constructing the parser
    # Use GooeyParser if we want the GUI because it will provide better widgets
    if len(argv) > 0 and (argv[0] == '--gui' and not '--ignore-gooey' in argv):  # pragma: no cover
        # Initialize the Gooey parser
        main_parser = gooey.GooeyParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter)
        # Define Gooey widget types explicitly (because type auto-detection doesn't work quite well)
        widget_dir = {"widget": "DirChooser"}
        widget_filesave = {"widget": "FileSaver"}
        widget_file = {"widget": "FileChooser"}
        widget_text = {"widget": "TextField"}
    else: # Else in command-line usage, use the standard argparse
        # Delete the special argument to avoid unrecognized argument error in argparse
        if '--ignore-gooey' in argv[0]: argv.remove('--ignore-gooey') # this argument is automatically fed by Gooey when the user clicks on Start
        # Initialize the normal argparse parser
        main_parser = argparse.ArgumentParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter)
        # Define dummy dict to keep compatibile with command-line usage
        widget_dir = {}
        widget_filesave = {}
        widget_file = {}
        widget_text = {}
    # Required arguments
    main_parser.add_argument('-i', '--input', metavar='/path/to/root/folder', type=is_dir_or_file, nargs=1, required=True,
                        help='Path to the root folder (or a single file) from where the scanning will occur.', **widget_dir)
    main_parser.add_argument('-d', '--database', metavar='/some/folder/ecc.txt', type=str, nargs=1, required=True, #type=argparse.FileType('rt')
                        help='Path to the file containing the ECC informations.', **widget_filesave)
                        

    # Optional general arguments
    main_parser.add_argument('--ecc_algo', type=int, default=1, required=False,
                        help='What algorithm use to generate and verify the ECC? Values possible: 1-4. 1 is the formal, fully verified Reed-Solomon in base 3 ; 2 is a faster implementation but still based on the formal base 3 ; 3 is an even faster implementation but based on another library which may not be correct ; 4 is the fastest implementation supporting US FAA ADSB UAT RS FEC standard but is totally incompatible with the other three (a text encoded with any of 1-3 modes will be decodable with any one of them).', **widget_text)
    main_parser.add_argument('--max_block_size', type=int, default=255, required=False,
                        help='Reed-Solomon max block size (maximum = 255). It is advised to keep it at the maximum for more resilience (see comments at the top of the script for more info).', **widget_text)
    main_parser.add_argument('-s', '--size', type=int, default=1024, required=False,
                        help='Headers block size to protect with ecc (eg: 1024 meants that the first 1k of each file will be protected).', **widget_text)
    main_parser.add_argument('-r', '--resilience_rate', type=float, default=0.3, required=False,
                        help='Resilience rate for files headers (eg: 0.3 = 30%% of errors can be recovered but size of codeword will be 60%% of the data block, thus the ecc file will be about 60%% the size of your data).', **widget_text)
    main_parser.add_argument('-ri', '--resilience_rate_intra', type=float, default=0.5, required=False,
                        help='Resilience rate for intra-ecc (ecc on meta-data, such as filepath, thus this defines the ecc for the critical spots!).', **widget_text)
    main_parser.add_argument('-l', '--log', metavar='/some/folder/filename.log', type=str, nargs=1, required=False,
                        help='Path to the log file. (Output will be piped to both the stdout and the log file)', **widget_filesave)
    main_parser.add_argument('--stats_only', action='store_true', required=False, default=False,
                        help='Only show the predicted total size of the ECC file given the parameters.')
    main_parser.add_argument('--hash', metavar='md5;shortmd5;shortsha256...', type=str, required=False,
                        help='Hash algorithm to use. Choose between: md5, shortmd5, shortsha256, minimd5, minisha256.', **widget_text)
    main_parser.add_argument('-v', '--verbose', action='store_true', required=False, default=False,
                        help='Verbose mode (show more output).')
    main_parser.add_argument('--silent', action='store_true', required=False, default=False,
                        help='No console output (but if --log specified, the log will still be saved in the specified file).')

    # Correction mode arguments
    main_parser.add_argument('-c', '--correct', action='store_true', required=False, default=False,
                        help='Check/Correct the files?')
    main_parser.add_argument('-o', '--output', metavar='/path/to/output/folder', type=is_dir, nargs=1, required=False,
                        help='Path of the folder where the repaired files will be copied (only repaired corrupted files will be copied there, files that weren\'t corrupted at all won\'t be copied so you have to copy them by yourself afterwards).', **widget_dir)
    main_parser.add_argument('-e', '--errors_file', metavar='/some/folder/errorsfile.csv', type=str, nargs=1, required=False, #type=argparse.FileType('rt')
                        help='Path to the error file generated by RFIGC.py (this specify in csv format the list of files to check, and only those files will be checked and repaired). Do not specify this argument if you want to check and repair all files.', **widget_file)
    main_parser.add_argument('--ignore_size', action='store_true', required=False, default=False,
                        help='On correction, if the file size differs from when the ecc file was generated, ignore and try to correct anyway (this may work with file where data was appended without changing the rest. For compressed formats like zip, this will probably fail).')
    main_parser.add_argument('--no_fast_check', action='store_true', required=False, default=False,
                        help='On correction, block corruption is only checked with the hash (the ecc will still be checked after correction, but not before). If no_fast_check is enabled, then ecc will also be checked before. This allows to find blocks corrupted by malicious intent (the block is corrupted but the hash has been corrupted as well to match the corrupted block, because it\'s almost impossible that following a hardware or logical fault, the hash match the corrupted block).')
    main_parser.add_argument('--skip_missing', action='store_true', required=False, default=False,
                        help='Skip missing files (no warning).')
    main_parser.add_argument('--enable_erasures', action='store_true', required=False, default=False,
                        help='Enable errors-and-erasures correction. Reed-Solomon can correct twice more erasures than errors (eg, if resilience rate is 0.3, then you can correct 30%% errors and 60%% erasures and any combination of errors and erasures between 30%%-60%% corruption). An erasure is a corrupted symbol where we know the position, while errors are not known at all. To find erasures, we will find any symbol that is equal to --erasure_symbol and flag it as an erasure. This is particularly useful if the software you use (eg, a disk scraper) can mark bad sectors with a constant character (eg, null byte). Misdetected erasures will just eat one ecc symbol, and won\'t change the decoded message.')
    main_parser.add_argument('--only_erasures', action='store_true', required=False, default=False,
                        help='Enable only erasures correction (no errors). Use this only if you are sure that all corrupted symbols have the same value (eg, if your disk scraper replace bad sectors by null bytes). This will ensure that you can correct up to 2*resilience_rate corrupted symbols.')
    main_parser.add_argument('--erasure_symbol', type=int, default=0, required=False,
                        help='Symbol that will be flagged as an erasure. Default: null byte 0. (value must be an integer)', **widget_text)

    # Generate mode arguments
    main_parser.add_argument('-g', '--generate', action='store_true', required=False, default=False,
                        help='Generate the ecc file?')
    main_parser.add_argument('-f', '--force', action='store_true', required=False, default=False,
                        help='Force overwriting the ecc file even if it already exists (if --generate).')
    main_parser.add_argument('--skip_size_below', type=int, default=None, required=False,
                        help='Skip files below the specified size (in bytes).', **widget_text)
    main_parser.add_argument('--always_include_ext', metavar='txt|jpg|png', type=str, default=None, required=False,
                        help='Always include files with the specified extensions, useful in combination with --skip_size_below to keep files of certain types even if they are below the size. Format: extensions separated by |.', **widget_text)

    #== Parsing the arguments
    args = main_parser.parse_args(argv) # Storing all arguments to args

    #-- Set hard-coded variables
    entrymarker = "\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF" # marker that will signal the beginning of an ecc entry - use an alternating pattern of several characters, this avoids confusion (eg: if you use "AAA" as a pattern, if the ecc block of the previous file ends with "EGA" for example, then the full string for example will be "EGAAAAC:\yourfolder\filea.jpg" and then the entry reader will detect the first "AAA" occurrence as the entry start - this should not make the next entry bug because there is an automatic trim - but the previous ecc block will miss one character that could be used to repair the block because it will be "EG" instead of "EGA"!)
    field_delim = "\xFA\xFF\xFA\xFF\xFA" # delimiter between fields (filepath, filesize, hash+ecc blocks) inside an ecc entry

    #-- Set variables from arguments
    inputpath = fullpath(args.input[0]) # path to the files to protect (either a folder or a single file)
    rootfolderpath = inputpath # path to the root folder (to compute relative paths)
    database = fullpath(args.database[0])
    generate = args.generate
    correct = args.correct
    force = args.force
    stats_only = args.stats_only
    max_block_size = args.max_block_size
    header_size = args.size
    resilience_rate = args.resilience_rate
    resilience_rate_intra = args.resilience_rate_intra
    enable_erasures = args.enable_erasures
    only_erasures = args.only_erasures
    erasure_symbol = args.erasure_symbol
    ignore_size = args.ignore_size
    skip_missing = args.skip_missing
    skip_size_below = args.skip_size_below
    always_include_ext = args.always_include_ext
    if always_include_ext: always_include_ext = tuple(['.'+ext for ext in always_include_ext.split('|')]) # prepare a tuple of extensions (prepending with a dot) so that str.endswith() works (it doesn't with a list, only a tuple)
    hash_algo = args.hash
    if not hash_algo: hash_algo = "md5"
    ecc_algo = args.ecc_algo
    fast_check = not args.no_fast_check
    verbose = args.verbose
    silent = args.silent

    if os.path.isfile(inputpath): # if inputpath is a single file (instead of a folder), then define the rootfolderpath as the parent directory (for correct relative path generation, else it will also truncate the filename!)
        rootfolderpath = os.path.dirname(inputpath)

    if correct:
        if not args.output:
            raise NameError('Output path is necessary when in correction mode!')
        outputpath = fullpath(args.output[0])

    errors_file = None
    if args.errors_file: errors_file = os.path.basename(fullpath(args.errors_file[0]))

    # -- Checking arguments
    if not stats_only and not generate and not os.path.isfile(database):
        raise NameError('Specified database ecc file %s does not exist!' % database)
    elif generate and os.path.isfile(database) and not force:
        raise NameError('Specified database ecc file %s already exists! Use --force if you want to overwrite.' % database)

    if resilience_rate <= 0 or resilience_rate_intra <= 0:
        raise ValueError('Resilience rate cannot be negative nor zero and it must be a float number.');

    if max_block_size < 2 or max_block_size > 255:
        raise ValueError('RS max block size must be between 2 and 255.')

    if header_size < 1:
        raise ValueError('Header size cannot be negative.')

    # -- Configure the log file if enabled (ptee.write() will write to both stdout/console and to the log file)
    if args.log:
        ptee = Tee(args.log[0], 'a', nostdout=silent)
        #sys.stdout = Tee(args.log[0], 'a')
        sys.stderr = Tee(args.log[0], 'a', nostdout=silent)
    else:
        ptee = Tee(nostdout=silent)


    # == PROCESSING BRANCHING == #

    # Precompute some parameters and load up ecc manager objects (big optimization as g_exp and g_log tables calculation is done only once)
    ptee.write("Initializing the ECC codecs, please wait...")
    hasher = Hasher(hash_algo)
    hasher_intra = Hasher('none') # for intra_ecc we don't use any hash
    ecc_params = compute_ecc_params(max_block_size, resilience_rate, hasher)
    ecc_manager = ECCMan(max_block_size, ecc_params["message_size"], algo=ecc_algo)
    ecc_params_intra = compute_ecc_params(max_block_size, resilience_rate_intra, hasher_intra)
    ecc_manager_intra = ECCMan(max_block_size, ecc_params_intra["message_size"], algo=ecc_algo)
    ecc_params_idx = compute_ecc_params(27, 1, hasher_intra)
    ecc_manager_idx = ECCMan(27, ecc_params_idx["message_size"], algo=ecc_algo)

    # == Precomputation of ecc file size
    # Precomputing is important so that the user can know what size to expect before starting (and how much time it will take...).
    filescount = 0
    sizetotal = 0
    sizeheaders = 0
    ptee.write("Precomputing list of files and predicted statistics...")
    for (dirpath, filename) in tqdm.tqdm(recwalk(inputpath), file=ptee):
        filescount = filescount + 1 # counting the total number of files we will process (so that we can show a progress bar with ETA)
        # Get full absolute filepath
        filepath = os.path.join(dirpath, filename)
        relfilepath = path2unix(os.path.relpath(filepath, rootfolderpath)) # File relative path from the root (we truncate the rootfolderpath so that we can easily check the files later even if the absolute path is different)
        # Get the current file's size
        size = os.stat(filepath).st_size
        # Check if we must skip this file because size is too small, and then if we still keep it because it's extension is always to be included
        if skip_size_below and size < skip_size_below and (not always_include_ext or not relfilepath.lower().endswith(always_include_ext)): continue

        # Compute total size of all files
        sizetotal = sizetotal + size
        # Compute predicted size of their headers
        if size >= header_size: # for big files, we limit the size to the header size
            header_size_add = header_size
        else: # else for size smaller than the defined header size, it will just be the size of the file
            header_size_add = size
        # Size of the ecc entry for this file will be: entrymarker-bytes + field_delim-bytes*occurrence + length-filepath-string + length-size-string + length-filepath-ecc + size of the ecc per block for all blocks in file header + size of the hash per block for all blocks in file header.
        sizeheaders = sizeheaders + (len(entrymarker) + len(field_delim)*3 + len(relfilepath) + len(str(size)) + int(float(len(relfilepath))*resilience_rate_intra) + (int(math.ceil(float(header_size_add) / ecc_params["message_size"])) * (ecc_params["ecc_size"]+ecc_params["hash_size"])) ) # Compute the total number of bytes we will add with ecc + hash (accounting for the padding of the remaining characters at the end of the sequence in case it doesn't fit with the message_size, by using ceil() )
    ptee.write("Precomputing done.")
    if generate: # show statistics only if generating an ecc file
        # TODO: add the size of the ecc format header? (arguments string + PYHEADERECC identifier)
        total_pred_percentage = sizeheaders * 100 / sizetotal
        ptee.write("Total ECC size estimation: %s = %g%% of total files size %s." % (sizeof_fmt(sizeheaders), total_pred_percentage, sizeof_fmt(sizetotal)))
        ptee.write("Details: resiliency of %i%%: For the header (first %i characters) of each file: each block of %i chars will get an ecc of %i chars (%i errors or %i erasures)." % (resilience_rate*100, header_size, ecc_params["message_size"], ecc_params["ecc_size"], int(ecc_params["ecc_size"] / 2), ecc_params["ecc_size"]))

    if stats_only:
        ptee.close()
        return 0

    # == Generation mode
    # Generate an ecc file, containing ecc entries for every files recursively in the specified root folder.
    # The file header will be split by blocks depending on max_block_size and resilience_rate, and each of those blocks will be hashed and a Reed-Solomon code will be produced.
    if generate:
        ptee.write("====================================")
        ptee.write("Header ECC generation, started on %s" % datetime.datetime.now().isoformat())
        ptee.write("====================================")

        with open(database, 'wb') as db, open(database+".idx", 'wb') as dbidx:
            # Write ECC file header identifier (unique string + version)
            db.write( b("**PYHEADERECCv%s**\n" % (''.join([x * 3 for x in __version__]))) ) # each character in the version will be repeated 3 times, so that in case of tampering, a majority vote can try to disambiguate
            # Write the parameters (they are NOT reloaded automatically, you have to specify them at commandline! It's the user role to memorize those parameters (using any means: own brain memory, keep a copy on paper, on email, etc.), so that the parameters are NEVER tampered. The parameters MUST be ultra reliable so that errors in the ECC file can be more efficiently recovered.
            for i in _range(3): db.write( ("** Parameters: "+" ".join(argv) + "\n").encode() ) # copy them 3 times just to be redundant in case of ecc file corruption
            db.write( b("** Generated under %s\n" % ecc_manager.description()) )
            # NOTE: there's NO HEADER for the ecc file! Ecc entries are all independent of each others, you just need to supply the decoding arguments at commandline, and the ecc entries can be decoded. This is done on purpose to be remove the risk of critical spots in ecc file.

            # Processing ecc on files
            files_done = 0
            files_skipped = 0
            for (dirpath, filename) in tqdm.tqdm(recwalk(inputpath), file=ptee, total=filescount, leave=True, unit="files"):
                # Get full absolute filepath
                filepath = os.path.join(dirpath, filename)
                # Get database relative path (from scanning root folder)
                relfilepath = path2unix(os.path.relpath(filepath, rootfolderpath)) # File relative path from the root (we truncate the rootfolderpath so that we can easily check the files later even if the absolute path is different)
                # Get file size
                filesize = os.stat(filepath).st_size
                # If skip size is enabled and size is below the skip size, we skip UNLESS the file extension is in the always include list
                if skip_size_below and filesize < skip_size_below and (not always_include_ext or not relfilepath.lower().endswith(always_include_ext)):
                    files_skipped += 1
                    continue

                # Opening the input file's to read its header and compute the ecc/hash blocks
                if verbose: ptee.write("\n- Processing file %s" % relfilepath)
                with open(os.path.join(rootfolderpath, filepath), 'rb') as file:
                    # -- Intra-ecc generation: Compute an ecc for the filepath and filesize, to avoid a critical spot here (so that we don't care that the filepath gets corrupted, we have an ecc to fix it!)
                    relfilepath_ecc = b''.join(compute_ecc_hash(ecc_manager_intra, hasher_intra, relfilepath, max_block_size, resilience_rate_intra, ecc_params_intra["message_size"], True))
                    filesize_ecc = b''.join(compute_ecc_hash(ecc_manager_intra, hasher_intra, str(filesize), max_block_size, resilience_rate_intra, ecc_params_intra["message_size"], True))
                    # -- Hash/Ecc encoding of file's content (everything is managed inside compute_ecc_hash)
                    buf = file.read(header_size) # read the file's header
                    ecc_stream = compute_ecc_hash(ecc_manager, hasher, buf, max_block_size, resilience_rate, ecc_params["message_size"], True) # then compute the ecc/hash entry for this file's header (this will be a chain of multiple ecc/hash fields per block of data, because Reed-Solomon is limited to a maximum of 255 bytes, including the original_message+ecc!)
                    # -- Build the ecc entry
                    # First put the ecc metadata
                    ecc_entry = b''.join([b(entrymarker), b(relfilepath), b(field_delim), b(str(filesize)), b(field_delim), b(relfilepath_ecc), b(field_delim), b(filesize_ecc), b(field_delim)]) # first save the file's metadata (filename, filesize, filepath ecc, ...)
                    # Then put the ecc stream (the ecc blocks for the file's data)
                    for es in ecc_stream:
                        ecc_entry += es
                    # -- Commit the ecc entry into the database
                    entrymarker_pos = db.tell() # backup the position of the start of this ecc entry
                    # -- Committing the hash/ecc encoding of the file's content
                    db.write(b(ecc_entry)) # commit to the ecc file, and replicate the number of times required
                    # -- External indexes backup: calculate the position of the entrymarker and of each field delimiter, and compute their ecc, and save into the index backup file. This will allow later to retrieve the position of each marker in the ecc file, and repair them if necessary, while just incurring a very cheap storage cost.
                    # Also, the index backup file is fixed delimited fields sizes, which means that each field has a very specifically delimited size, so that we don't need any marker: we can just compute the total size for each entry, and thus find all entries independently even if one or several are corrupted beyond repair, so that this won't affect other index entries.
                    markers_pos = [entrymarker_pos,
                                                entrymarker_pos+len(entrymarker)+len(relfilepath),
                                                entrymarker_pos+len(entrymarker)+len(relfilepath)+len(field_delim)+len(str(filesize)),
                                                entrymarker_pos+len(entrymarker)+len(relfilepath)+len(field_delim)+len(str(filesize))+len(field_delim)+len(relfilepath_ecc),
                                                entrymarker_pos+len(entrymarker)+len(relfilepath)+len(field_delim)+len(str(filesize))+len(field_delim)+len(relfilepath_ecc)+len(field_delim)+len(filesize_ecc),
                                                ] # Make the list of all markers positions for this ecc entry. The first and last indexes are the most important (first is the entrymarker, the last is the field_delim just before the ecc track start)
                    markers_pos = [struct.pack('>Q', x) for x in markers_pos] # Convert to a binary representation in 8 bytes using unsigned long long (up to 16 EB, this should be more than sufficient)
                    markers_types = [b'1', b'2', b'2', b'2', b'2']
                    markers_pos_ecc = [ecc_manager_idx.encode(x+y) for x,y in _izip(markers_types,markers_pos)] # compute the ecc for each number
                    # Couple each marker's position with its type and with its ecc, and write them all consecutively into the index backup file
                    for items in _izip(markers_types,markers_pos,markers_pos_ecc):
                        for item in items:
                            dbidx.write(b(item))
                files_done += 1
        ptee.write("All done! Total number of files processed: %i, skipped: %i" % (files_done, files_skipped))
        ptee.close()
        return 0

    # == Error Correction (and checking by hash) mode
    # For each file, check their headers by block by checking each block against a hash, and if the hash does not match, try to correct with Reed-Solomon and then check the hash again to see if we correctly repaired the block (else the ecc entry might have been corrupted, whether it's the hash or the ecc field, in both cases it's highly unlikely that a wrong repair will match the hash after this wrong repair)
    elif correct:
        ptee.write("====================================")
        ptee.write("Header ECC verification and correction, started on %s" % datetime.datetime.now().isoformat())
        ptee.write("====================================")

        # Prepare the list of files with errors to reduce the scan (only if provided)
        errors_filelist = []
        if errors_file:
            with open(errors_file, 'rb') as efile:
                for row in csv.DictReader(efile, lineterminator='\n', delimiter='|', quotechar='"', fieldnames=['filepath', 'error']): # need to specify the fieldnames, else the first row in the csv file will be skipped (it will be used as the columns names)
                    errors_filelist.append(row['filepath'])

        # Read the ecc file
        dbsize = os.stat(database).st_size # must get db file size before opening it in order not to move the cursor
        with open(database, 'rb') as db:
            # Counters
            files_count = 0
            files_corrupted = 0
            files_repaired_partially = 0
            files_repaired_completely = 0
            files_skipped = 0

            # Main loop: process each ecc entry
            entry = 1 # to start the while loop
            bardisp = tqdm.tqdm(total=dbsize, file=ptee, leave=True, desc='DBREAD', unit='B', unit_scale=True) # display progress bar based on reading the database file (since we don't know how many files we will process beforehand nor how many total entries we have)
            while entry:

                # -- Read the next ecc entry (extract the raw string from the ecc file)
                #if replication_rate == 1:
                entry = get_next_entry(db, entrymarker, False)
                if entry: bardisp.update(len(entry)) # update progress bar

                # No entry? Then we finished because this is the end of file (stop condition)
                if not entry: break

                # -- Get position of current entry (for debugging purposes)
                entry_pos = [db.tell(), db.tell()-len(entry)]

                # -- Extract the fields from the ecc entry
                entry_p = entry_fields(entry, b(field_delim))

                # -- Get file path, check its correctness and correct it by using intra-ecc if necessary
                relfilepath = entry_p["relfilepath"] # Relative file path
                relfilepath, fpcorrupted, fpcorrected, fperrmsg = ecc_correct_intra(ecc_manager_intra, ecc_params_intra, relfilepath, entry_p["relfilepath_ecc"], entry_pos, enable_erasures=enable_erasures, erasures_char=erasure_symbol, only_erasures=only_erasures)

                # Report errors
                if fpcorrupted:
                    if fpcorrected: ptee.write("\n- Fixed error in metadata field at offset %i filepath %s." % (db.tell()-len(entry), relfilepath))
                    else: ptee.write("\n- Error in filepath, could not correct completely metadata field at offset %i with value: %s. Please fix manually by editing the ecc file or set the corrupted characters to null bytes and --enable_erasures." % (entry_pos[0], relfilepath))
                ptee.write(fperrmsg)

                # Convert to str (so that we can use os.path funcs)
                relfilepath = relfilepath.decode('latin-1')
                # Update entry_p
                entry_p["relfilepath"] = relfilepath
                # -- End of intra-ecc on filepath

                # -- Get file size, check its correctness and correct it by using intra-ecc if necessary
                filesize = str(entry_p["filesize"])
                filesize, fscorrupted, fscorrected, fserrmsg = ecc_correct_intra(ecc_manager_intra, ecc_params_intra, filesize, entry_p["filesize_ecc"], entry_pos, enable_erasures=enable_erasures, erasures_char=erasure_symbol, only_erasures=only_erasures)

                # Report errors
                if fscorrupted:
                    if fscorrected: ptee.write("\n- Fixed error in metadata field at offset %i filesize %s." % (db.tell()-len(entry), filesize))
                    else: ptee.write("\n- Error in filesize, could not correct completely metadata field at offset %i with value: %s. Please fix manually by editing the ecc file or set the corrupted characters to null bytes and --enable_erasures." % (entry_pos[0], filesize))
                ptee.write(fserrmsg)

                # Convert filesize intra-field into an int
                filesize = int(filesize)

                # Update entry_p
                entry_p["filesize"] = filesize # need to update entry_p because various funcs will directly access filesize this way...
                # -- End of intra-ecc on filesize

                # Build the absolute file path
                filepath = os.path.join(rootfolderpath, relfilepath) # Get full absolute filepath from given input folder (because the files may be specified in any folder, in the ecc file the paths are relative, so that the files can be moved around or burnt on optical discs)
                if errors_filelist and relfilepath not in errors_filelist: continue # if a list of files with errors was supplied (for example by rfigc.py), then we will check only those files and skip the others

                if verbose: ptee.write("\n- Processing file %s" % relfilepath)

                # -- Check filepath
                # Check that the filepath isn't corrupted (if a silent error erase a character (not only flip a bit), then it will also be detected this way)
                if relfilepath.find("\x00") >= 0:
                    ptee.write("Error: ecc entry corrupted on filepath field, please try to manually repair the filepath (filepath: %s - missing/corrupted character at %i)." % (filepath, relfilepath.find("\x00")))
                    files_skipped += 1
                    continue
                # Check that file still exists before checking it
                if not os.path.isfile(filepath):
                    if not skip_missing: ptee.write("Error: file %s could not be found: either file was moved or the ecc entry was corrupted. You may try to fix manually the entry." % filepath)
                    files_skipped += 1
                    continue

                # -- Checking file size: if the size has changed, the blocks may not match anymore!
                real_filesize = os.stat(filepath).st_size
                if filesize != real_filesize:
                    if ignore_size:
                        ptee.write("Warning: file %s has a different size: %s (before: %s). Will still try to correct it (but the blocks may not match!)." % (relfilepath, real_filesize, filesize))
                    else:
                        ptee.write("Error: file %s has a different size: %s (before: %s). Skipping the file correction because blocks may not match (you can set --ignore_size to still correct even if size is different, maybe just the entry was corrupted)." % (relfilepath, real_filesize, filesize))
                        files_skipped += 1
                        continue

                files_count += 1
                # -- Check blocks and repair if necessary
                entry_asm = entry_assemble(entry_p, ecc_params, header_size, filepath) # Extract and assemble each message block from the original file with its corresponding ecc and hash
                corrupted = False # flag to signal that the file was corrupted and we need to reconstruct it afterwards
                repaired_partially = False # flag to signal if a file was repaired only partially
                err_consecutive = True # flag to check if the ecc track is misaligned/misdetected (we only encounter corrupted blocks that we can't fix)
                # For each message block, check the message with hash and repair with ecc if necessary
                for i, e in enumerate(entry_asm):
                    # If the message block has a different hash, it was corrupted (or the hash is corrupted, or both)
                    if hasher.hash(e["message"]) != e["hash"] or (not fast_check and not ecc_manager.check(e["message"], e["ecc"])):
                        corrupted = True
                        # Try to repair the block using ECC
                        ptee.write("File %s: corruption in block %i. Trying to fix it." % (relfilepath, i))
                        try:
                            repaired_block, repaired_ecc = ecc_manager.decode(e["message"], e["ecc"], enable_erasures=enable_erasures, erasures_char=erasure_symbol, only_erasures=only_erasures)
                        except (ReedSolomonError, RSCodecError) as exc: # the reedsolo lib may raise an exception when it can't decode. We ensure that we can still continue to decode the rest of the file, and the other files.
                            repaired_block = None
                            repaired_ecc = None
                            print("Error: file %s: block %i: %s" % (relfilepath, i, exc))
                        # Check if the repair was successful.
                        hash_ok = None
                        ecc_ok = None
                        if repaired_block is not None:
                            hash_ok = (hasher.hash(repaired_block) == e["hash"])
                            ecc_ok = ecc_manager.check(repaired_block, repaired_ecc)
                        if repaired_block is not None and (hash_ok or ecc_ok): # If either the hash or the ecc check now match the repaired message block, we commit the new block
                            entry_asm[i]["message_repaired"] = repaired_block # save the repaired block
                            # Show a precise report about the repair
                            if hash_ok and ecc_ok: ptee.write("File %s: block %i repaired!" % (relfilepath, i))
                            elif not hash_ok: ptee.write("File %s: block %i probably repaired with matching ecc check but with a hash error (assume the hash was corrupted)." % (relfilepath, i))
                            elif not ecc_ok: ptee.write("File %s: block %i probably repaired with matching hash but with ecc check error (assume the ecc was partially corrupted)." % (relfilepath, i))
                            err_consecutive = False
                        else: # Else the hash and the ecc check do not match: the repair failed (either because the ecc is too much tampered, or because the hash is corrupted. Either way, we don't commit).
                            ptee.write("Error: file %s could not repair block %i (both hash and ecc check mismatch)." % (relfilepath, i)) # you need to code yourself to use bit-recover, it's in perl but it should work given the hash computed by this script and the corresponding message block.
                            repaired_partially = True
                            # Detect if the ecc track is misaligned/misdetected (we encounter only errors that we can't fix)
                            if err_consecutive and i >= 10: # threshold is ten consecutive uncorrectable errors
                                ptee.write("Failure: Too many consecutive uncorrectable errors for %s. Most likely, the ecc track was misdetected (try to repair the entrymarkers and field delimiters). Skipping this track/file." % relfilepath)
                                break
                    else:
                        err_consecutive = False
                # -- Reconstruct/Copying the repaired file
                # If this file had a corruption in one of its header blocks, then we will reconstruct the file header and then append the rest of the file (which can then be further repaired by other tools such as PAR2).
                if corrupted:
                    # Counters...
                    files_corrupted += 1
                    if repaired_partially:
                        files_repaired_partially += 1
                    else:
                        files_repaired_completely += 1
                    # Reconstructing the file
                    outfilepath = os.path.join(outputpath, relfilepath) # get the full path to the output file
                    outfiledir = os.path.dirname(outfilepath)
                    if not os.path.isdir(outfiledir): os.makedirs(outfiledir) # if the target directory does not exist, create it (and create recursively all parent directories too)
                    with open(outfilepath, 'wb') as out:
                        # Reconstruct the header using repaired blocks (and the other non corrupted blocks)
                        for e in entry_asm:
                            if "message_repaired" in e:
                                out.write(e["message_repaired"])
                            else:
                                out.write(e["message"])
                        # Append the rest of the file by copying from the original
                        with open(filepath, 'rb') as originalfile:
                            blocksize = 65535
                            originalfile.seek(header_size)
                            buf = originalfile.read(blocksize)
                            while buf:
                                out.write(buf)
                                buf = originalfile.read(blocksize)
                    # Copying the last access time and last modification time from the original file TODO: a more reliable way would be to use the db computed by rfigc.py, because if a software maliciously tampered the data, then the modification date may also have changed (but not if it's a silent error, in that case we're ok).
                    filestats = os.stat(filepath)
                    os.utime(outfilepath, (filestats.st_atime, filestats.st_mtime))
        # All ecc entries processed for checking and potentally repairing, we're done correcting!
        bardisp.close() # at the end, the bar may not be 100% because of the headers that are skipped by get_next_entry() and are not accounted in bardisp.
        ptee.write("All done! Stats:\n- Total files processed: %i\n- Total files corrupted: %i\n- Total files repaired completely: %i\n- Total files repaired partially: %i\n- Total files corrupted but not repaired at all: %i\n- Total files skipped: %i" % (files_count, files_corrupted, files_repaired_completely, files_repaired_partially, files_corrupted - (files_repaired_partially + files_repaired_completely), files_skipped) )
        ptee.close()
        if files_corrupted == 0 or files_repaired_completely == files_corrupted:
            return 0
        else:
            return 1

# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":  # pragma: no cover
    global __package__
    if __package__ is None:
        #sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        print('HOHO')
        __package__ = 'pyFileFixity.header_ecc'
    sys.exit(main())
