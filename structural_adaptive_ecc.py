#!/usr/bin/env python
#
# Structural Adaptive Error Correction Code
# !!!!!!!!!!!!!!!!!!!!!!!!! DO NOT USE THIS SCRIPT FOR PRODUCTION, IT DOESN'T WORK (encoding yes, not decoding) !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
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
#  Structural Adaptive Error Correction Code generator and checker
#                by Stephen Larroque
#                       License: MIT
#                 Runs on Python 2.7.6
#              Creation date: 2015-03-10
#          Last modification: 2015-03-18
#                     version: 0.0.1
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
# - Use zfec (https://pypi.python.org/pypi/zfec) for more speed. PROBLEM: the philosophy is different, it splits the file in parts. The goal is to be able to reassemble the file from any k parts (from n total). Maybe then try to optimize using numba or numpy or Cython?
# Or use Cauchy Reed-Solomon, which significantly outperforms simple Reed-Solomon?
# or https://bitbucket.org/kmgreen2/pyeclib with jerasure
# or http://www.bth.se/fou/cuppsats.nsf/all/bcb2fd16e55a96c2c1257c5e00666323/$file/BTH2013KARLSSON.pdf
# or https://www.usenix.org/legacy/events/fast09/tech/full_papers/plank/plank_html/
# Note: Pypy v2.5.0 speeds the script without any modification!
# - Also backup folders meta-data? (to reconstruct the tree in case a folder is truncated by bit rot)
# - add a Reed-solomon on hashes, so that we are sure that if error correction is not tampered but the hash is, we can still repair the block? (because the repair is in fact ok, it's just that the hash is corrupted and won't match, but we should prevent this scenario. An ecc on the hash may fix the issue). Currently, replication_rate >= 3 will prevent a bit this scenario using majority vote.
# - replace tqdm with https://github.com/WoLpH/python-progressbar for a finer progress bar and ETA? (currently ETA is computed on the number of files processed, but it should really be on the total number of characters processed over the total size) - BUT requirement is that it doesn't require an external library only available on Linux (such as ncurses)
# or this: https://github.com/lericson/fish
# - --gui option using https://github.com/chriskiehl/Gooey
# - intra-ecc on: filepath, and on hash of every blocks? (this should use a lot less storage space than replication for the same efficiency, but the problem is how to delimit fields since we won't know the size of the ecc. For the ecc of hashes, yes we can know because hash is fixed length and so will be the ecc of the hash, but for the ecc of the filepath it will be proportional to the filepath. And an ecc can contain any character such as \x00, thus it will make our fields detection buggy).
#

__version__ = "0.0.1"

# Include the lib folder in the python import path (so that packaged modules can be easily called, such as gooey which always call its submodules via gooey parent module)
import sys, os
thispathname = os.path.dirname(sys.argv[0])
sys.path.append(os.path.join(thispathname, 'lib'))

# Import necessary libraries
import lib.argparse as argparse
import datetime, time
import hashlib, zlib
import lib.tqdm as tqdm
import itertools
import math
#import operator # to get the max out of a dict
import csv # to process the errors_file from rfigc.py
import shlex # for string parsing as argv argument to main(), unnecessary otherwise
from lib.tee import Tee # Redirect print output to the terminal as well as in a log file
#import pprint # Unnecessary, used only for debugging purposes

import lib.brownanrs.rs as brownanrs # Pure python implementation of Reed-Solomon with configurable max_block_size and automatic error detection (you don't have to specify where they are).
rsmode = 1 # to allow different implementations (possibly more efficient) of Reed-Solomon in the future

# try:
    # import lib.brownanrs.rs as brownanrs
    # rsmode = 1
# except ImportError:
        # import lib.reedsolomon.reedsolo as reedsolo
        # rsmode = 2

#***********************************
#     AUXILIARY FUNCTIONS
#***********************************

# Check that an argument is a real directory
def is_dir(dirname):
    '''Checks if a path is an actual directory'''
    if not os.path.isdir(dirname):
        msg = "{0} is not a directory".format(dirname)
        raise argparse.ArgumentTypeError(msg)
    else:
        return dirname

# Relative path to absolute
def fullpath(relpath):
    if (type(relpath) is object or type(relpath) is file):
        relpath = relpath.name
    return os.path.abspath(os.path.expanduser(relpath))

def recwalk(folderpath):
    '''Recursively walk through a folder. This provides a mean to flatten out the files restitution (necessary to show a progress bar). This is a generator.'''
    for dirpath, dirs, files in os.walk(folderpath):	
        for filename in files:
            yield (dirpath, filename)

def sizeof_fmt(num, suffix='B'):
    '''Readable size format, courtesy of Sridhar Ratnakumar'''
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)

def feature_scaling(x, xmin, xmax, a=0, b=1):
    '''Generalized feature scaling (unused, only useful for variable error correction rate in the future)'''
    return a + float(x - xmin) * (b - a) / (xmax - xmin)

class Hasher(object):
    '''Class to provide a hasher object with various hashing algorithms. What's important is to provide the __len__ so that we can easily compute the block size of ecc entries. Must only use fixed size hashers for the rest of the script to work properly.'''
    def __init__(self, algo="md5"):
        self.algo = algo.lower()

    def hash(self, mes):
        if self.algo == "md5":
            return hashlib.md5(mes).hexdigest()

    def __len__(self):
        if self.algo == "md5":
            return 32

class ECC(object):
    '''ECC manager, which provide a modular way to use different kinds of ecc algorithms.'''
    def __init__(self, n, k):
        self.ecc_manager = brownanrs.RSCoder(n, k)
        self.n = n
        self.k = k

    def encode(self, message):
        message, _ = self.pad(message)
        if rsmode == 1:
            mesecc = self.ecc_manager.encode(message)
            ecc = mesecc[len(message):]
            return ecc

    def decode(self, message, ecc):
        message, pad = self.pad(message)
        if rsmode == 1:
            res = self.ecc_manager.decode(message + ecc, nostrip=True) # Avoid automatic stripping because we are working with binary streams, thus we should manually strip padding only when we know we padded
            if pad: # Strip the null bytes if we padded the message before decoding
                res = res[len(pad):len(res)]
            return res
    
    def pad(self, message):
        '''Automatically pad with null bytes a message if too small, or leave unchanged if not necessary. This allows to keep track of padding and strip the null bytes after decoding reliably with binary data.'''
        pad = None
        if len(message) < self.k:
            pad = "\x00" * (self.k-len(message))
            message = pad + message
        return [message, pad]

    def check(self, message, ecc):
        message = self.pad(message)
        if rsmode == 1:
            return self.ecc_manager.verify(message, ecc)

def read_next_entry(file, entrymarker="\xFF\xFF\xFF\xFF"):
    '''Read the next ecc entry (string) in the ecc file. This will read any string length between two entrymarkers. The reading is very tolerant, so it will always return any valid entry (but also scrambled entries if any, but the decoding will ensure everything's ok).'''
    blocksize = 65535
    found = False
    start = None
    buf = 1
    # Continue the search as long as we did not find at least one starting marker and one ending marker (or end of file)
    while (not found and buf):
        # Read a long block at once, we will readjust the file cursor after
        buf = file.read(blocksize)
        # Find the start marker (if not found already)
        if not start or start == -1:
            start = buf.find(entrymarker); # relative position of the starting marker in the currently read string
            if start >= 0:
                startcursor = file.tell() - len(buf) + start # absolute position of the starting marker in the file
        # If we have a starting marker, we try to find a subsequent marker which will be the ending of our entry (if the entry is corrupted we don't care: it won't pass the entry_to_dict() decoding or subsequent steps of decoding and we will just pass to the next ecc entry). This allows to process any valid entry, no matter if previous ones were scrambled.
        if start >= 0:
            end = buf.find(entrymarker, start + len(entrymarker))
            if end < 0 and len(buf) < blocksize: # Special case: we didn't find any ending marker but we reached the end of file, then we are probably in fact just reading the last entry (thus there's no ending marker for this entry)
                end = len(buf) # It's ok, we have our entry, the ending marker is just the end of file
            # If we found an ending marker (or if end of file is reached), then we compute the absolute cursor value and put the file reading cursor back in position, just before the next entry (where the ending marker is if any)
            if end >= 0:
                endcursor = file.tell() - len(buf) + end
                file.seek(endcursor)
                found = True
    entry = None # return None if there's no new entry to read
    if found: # if an entry was found, we seek to the beginning of the entry and read the entry from file
        file.seek(startcursor + len(entrymarker))
        entry = file.read(endcursor - startcursor - len(entrymarker))
    # Detect from first marker to the next
    return entry

def entry_fields(entry, field_delim="\xFF"):
    '''From a raw ecc entry (a string), extract the filename, filesize, and the rest being blocks of hash and ecc per blocks of the original file's header'''
    first = entry.find(field_delim)
    second = entry.find(field_delim, first+len(field_delim))
    relfilepath = entry[:first]
    filesize = entry[first+len(field_delim):second]
    ecc_field = entry[second+len(field_delim):]
    # entries = [ {"message":, "ecc":, "hash":}, etc.]
    return {"relfilepath": relfilepath, "filesize": int(filesize), "ecc_field": ecc_field}

def entry_assemble(entry_fields, ecc_params, header_size, filepath):
    '''From an entry with its parameters (filename, filesize), assemble a list of each block from the original file along with the relative hash and ecc for easy processing later.'''
    # Extract the header from the file
    with open(filepath, 'rb') as file: # filepath is the absolute path to the original file (the one with maybe corruptions, NOT the output repaired file!)
        if entry_fields["filesize"] < header_size:
            fileheader = file.read(entry_fields["filesize"])
        else:
            fileheader = file.read(header_size)
    # Cut the header and the ecc entry into blocks, and then assemble them so that we can easily process block by block
    entry_asm = []
    for i, j in itertools.izip(xrange(0, len(fileheader), ecc_params["message_size"]), xrange(0, len(entry_fields["ecc_field"]), ecc_params["hash_size"] + ecc_params["ecc_size"])):
        mes = fileheader[i:i+ecc_params["message_size"]]
        hash = entry_fields["ecc_field"][j:j+ecc_params["hash_size"]]
        ecc = entry_fields["ecc_field"][j+ecc_params["hash_size"]:j+ecc_params["hash_size"]+ecc_params["ecc_size"]]
        entry_asm.append({"message": mes, "hash": hash, "ecc": ecc})
    return entry_asm

def entries_disambiguate(entries, field_delim="\xFF", ptee=None): # field_delim is only useful if there are errors
    '''Takes a list of ecc entries in string format (not yet assembled) representing the same data (replicated over several entries), and disambiguate by majority vote: for position in string, if the character is not the same accross all entries, we keep the major one. If none, it will be replaced by a null byte (because we can't know if any of the entries are correct about this character).'''
    # The idea of replication combined with ECC was a bit inspired by this paper: Friedman, Roy, Yoav Kantor, and Amir Kantor. "Combining Erasure-Code and Replication Redundancy Schemes for Increased Storage and Repair Efficiency in P2P Storage Systems.", 2013, Technion, Computer Science Department, Technical Report CS-2013-03

    if not entries[0]: return None # if entries is empty (we have reached end of file), just return None

    final_entry = []
    errors = []
    if len(entries) == 1:
        final_entry = entries[0]
    else:
        # Walk along each column (imagine the strings being rows in a matrix, then we pick one column at each iteration = all characters at position i of each string), so that we can compare these characters easily
        for i in xrange(len(entries[0])):
            hist = {} # kind of histogram, we just memorize how many times a character is presented at the position i in each string
            # Extract the character at position i of each string and compute the histogram at the same time (number of time this character appear among all strings at this position i)
            for e in entries:
                key = str(ord(e[i])) # convert to the ascii value to avoid any funky problem with encoding in dict keys
                hist[key] = hist.get(key, 0) + 1
            # If there's only one character (it's the same accross all strings at position i), then it's an exact match, we just save the character and we can skip to the next iteration
            if len(hist) == 1:
                final_entry.append(chr(int(hist.iterkeys().next())))
                continue
            # Else, the character is different among different entries, we will pick the major one (mode)
            elif len(hist) > 1:
                # Sort the dict by value (and reverse because we want the most frequent first)
                skeys = sorted(hist, key=hist.get, reverse=True)
                # If each entries present a different character (thus the major has only an occurrence of 1), then it's too ambiguous and we just set a null byte to signal that
                if hist[skeys[0]] == 1:
                    final_entry.append("\x00")
                    errors.append(i) # Print an error indicating the characters that failed
                # Else if there is a tie (at least two characters appear with the same frequency), then we just pick one of them
                elif hist[skeys[0]] == hist[skeys[1]]:
                    final_entry.append(chr(int(skeys[0]))) # TODO: find a way to account for both characters. Maybe return two different strings that will both have to be tested? (eg: maybe one has a tampered hash, both will be tested and if one correction pass the hash then it's ok we found the correct one)
                # Else we have a clear major character that appear in more entries than any other character, then we keep this one
                else:
                    final_entry.append(chr(int(skeys[0]))) # alternative one-liner: max(hist.iteritems(), key=operator.itemgetter(1))[0]
                continue
        # Concatenate to a string (this is faster than using a string from the start and concatenating at each iteration because Python strings are immutable so Python has to copy over the whole string, it's in O(n^2)
        final_entry = ''.join(final_entry)
        # Errors signaling
        if errors:
            #entry_p = entry_fields(final_entry, field_delim) # get the filename
            if ptee:
                ptee.write("Unrecoverable corruptions in a ecc entry on characters: %s. Ecc entry:\n%s" % (errors, final_entry)) # Signal to user that this file has unrecoverable corruptions (he may try to fix the bits manually or with his own script)
            else:
                print("Unrecoverable corruptions in a ecc entry on characters: %s. Ecc entry:\n%s" % (errors, final_entry))
            # After printing the error, return None so that we won't try to decode a corrupted ecc entry
            #final_entry = None
    return final_entry

def compute_ecc_params(max_block_size, rate, hasher):
    '''Compute the ecc parameters (size of the message, size of the hash, size of the ecc)'''
    message_size = max_block_size - int(round(max_block_size * rate * 2, 0))
    ecc_size = max_block_size - message_size
    hash_size = len(hasher) # 32 when we use MD5
    return {"message_size": message_size, "ecc_size": ecc_size, "hash_size": hash_size}

def compute_ecc_hash(ecc_manager, hasher, buf, max_block_size, rate, message_size=None, as_string=False):
    '''Split a string in blocks given max_block_size and compute the hash and ecc for each block, and then return a nice list with both for easy processing.'''
    result = []
    # If required parameters were not provided, we compute them
    if not message_size:
        ecc_params = compute_ecc_params(max_block_size, rate, hasher)
        message_size = ecc_params["message_size"]
    # Split the buffer string in blocks (necessary for Reed-Solomon encoding because it's limited to 255 characters max)
    for i in xrange(0, len(buf), message_size):
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
            result.append("%s%s" % (str(hash),str(ecc)))
        else:
            result.append([hash, ecc])
    return result



#***********************************
#        GUI AUX FUNCTIONS
#***********************************

# Try to import Gooey for GUI display, but manage exception so that we replace the Gooey decorator by a dummy function that will just return the main function as-is, thus keeping the compatibility with command-line usage
try:
    import lib.gooey as gooey
except:
    # Define a dummy replacement function for Gooey to stay compatible with command-line usage
    class gooey(object):
        def Gooey(func):
            return func
    # If --gui was specified, then there's a problem
    if len(sys.argv) > 1 and sys.argv[1] == '--gui': raise ImportError('--gui specified but lib/gooey could not be found, cannot load the GUI (however you can still use in commandline).')

def conditional_decorator(flag, dec):
    def decorate(fn):
        if flag:
            return dec(fn)
        else:
            return fn
    return decorate

def check_gui_arg():
    '''Check that the --gui argument was passed, and if true, we remove the --gui option and replace by --gui_launched so that Gooey does not loop infinitely'''
    if len(sys.argv) > 1 and sys.argv[1] == '--gui':
        #del sys.argv[1]
        sys.argv[1] = '--gui_launched' # CRITICAL: need to remove/replace the --gui argument, else it will stay in memory and when Gooey will call the script again, it will be stuck in an infinite loop calling back and forth between this script and Gooey. Thus, we need to remove this argument, but we also need to be aware that Gooey was called so that we can call gooey.GooeyParser() instead of argparse.ArgumentParser() (for better fields management like checkboxes for boolean arguments). To solve both issues, we replace the argument --gui by another internal argument --gui_launched.
        return True
    else:
        return False

def AutoGooey(fn):
    '''Automatically show a Gooey GUI if --gui is passed as the first argument, else it will just run the function as normal'''
    if check_gui_arg():
        return gooey.Gooey(fn)
    else:
        return fn



#***********************************
#                       MAIN
#***********************************

@AutoGooey
def main(argv=None):
    if argv is None: # if argv is empty, fetch from the commandline
        argv = sys.argv[1:]
    elif isinstance(argv, basestring): # else if argv is supplied but it's a simple string, we need to parse it to a list of arguments before handing to argparse or any other argument parser
        argv = shlex.split(argv) # Parse string just like argv using shlex

    #==== COMMANDLINE PARSER ====

    #== Commandline description
    desc = '''Structural Adaptive Error Correction Code generator and checker
Description: Given a directory, this application will generate error correcting codes or correct corrupt files, using a structural adaptive approach (the headers will be protected by more ecc bits than subsequent parts, progressively decreasing in the resilience).
Note: Folders meta-data is NOT accounted, only the files! Use DVDisaster or a similar tool to also cover folders meta-data.
    '''
        ep = '''
Note1: this is a pure-python implementation (except for MD5 hash but a pure-python alternative is provided in lib/md5py.py), thus it may be VERY slow to generate an ecc file. To speed-up things considerably, you can use PyPy v2.5.0 or above, there will be a speed-up of at least 5x from our experiments. Feel free to profile using easy_profiler.py and try to optimize the reed-solomon library.

Note2: that Reed-Solomon can correct up to 2*resilience_rate erasures (null bytes), resilience_rate errors (bit-flips, thus a character that changes but not necessarily a null byte) and amount to an additional storage of 2*resilience_rate storage compared to the original files size.'''

    #== Commandline arguments
    #-- Constructing the parser
    if len(sys.argv) > 1 and sys.argv[1] == '--gui_launched': # Use GooeyParser if we want the GUI because it will provide better widgets
        main_parser = gooey.GooeyParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter)
        # Define Gooey widget types explicitly (because type auto-detection doesn't work quite well)
        widget_dir = {"widget": "DirChooser"}
        widget_filesave = {"widget": "FileSaver"}
        widget_file = {"widget": "FileChooser"}
        widget_text = {"widget": "TextField"}
    else: # Else in command-line usage, use the standard argparse
        main_parser = argparse.ArgumentParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter)
        # Define dummy dict to keep compatibile with command-line usage
        widget_dir = {}
        widget_filesave = {}
        widget_file = {}
        widget_text = {}
    # Required arguments
    main_parser.add_argument('-i', '--input', metavar='/path/to/root/folder', type=is_dir, nargs=1, required=True,
                        help='Path to the root folder from where the scanning will occur.', **widget_dir)
    main_parser.add_argument('-d', '--database', metavar='/some/folder/ecc.txt', type=str, nargs=1, required=True, #type=argparse.FileType('rt')
                        help='Path to the file containing the ECC informations.', **widget_filesave)

    # Optional general arguments
    main_parser.add_argument('--max_block_size', type=int, default=255, required=False,
                        help='Reed-Solomon max block size (maximum = 255). It is advised to keep it at the maximum for more resilience (see comments at the top of the script for more info).', **widget_text)
    main_parser.add_argument('-s', '--size', type=int, default=1024, required=False,
                        help='Headers block size to protect with resilience rate stage 1 (eg: 1024 meants that the first 1k of each file will be protected by stage 1).', **widget_text)
    main_parser.add_argument('-r1', '--resilience_rate_stage1', type=float, default=0.3, required=False,
                        help='Resilience rate for files headers (eg: 0.3 = 30% of errors can be recovered but size of codeword will be 60% of the data block).', **widget_text)
    main_parser.add_argument('-r2', '--resilience_rate_stage2', type=float, default=0.2, required=False,
                        help='Resilience rate for stage 2 (after headers, this is the starting rate applied to the rest of the file, which will be gradually lessened towards the end of the file to the stage 3 rate).', **widget_text)
    main_parser.add_argument('-r3', '--resilience_rate_stage3', type=float, default=0.1, required=False,
                        help='Resilience rate for stage 3 (rate that will be applied towards the end of the files).', **widget_text)
    main_parser.add_argument('--replication_rate', type=int, default=1, required=False,
                        help='Replication rate, if you want to duplicate each ecc entry.', **widget_text)
    main_parser.add_argument('-l', '--log', metavar='/some/folder/filename.log', type=str, nargs=1, required=False,
                        help='Path to the log file. (Output will be piped to both the stdout and the log file)', **widget_filesave)
    main_parser.add_argument('--stats_only', action='store_true', required=False, default=False,
                        help='Only show the predicted total size of the ECC file given the parameters.')
    main_parser.add_argument('--max_memory', type=int, default=65535, required=False,
                        help='Maximum memory used to process files (more memory will help process faster as there will be less IO). This also defines when variable encoding will reevaluate the variable resilience rate (eg: 1024 means that every 1024 blocks the resilience rate will be reevaluated).', **widget_text)

    # Correction mode arguments
    main_parser.add_argument('-c', '--correct', action='store_true', required=False, default=False,
                        help='Check/Correct the files')
    main_parser.add_argument('-o', '--output', metavar='/path/to/output/folder', type=is_dir, nargs=1, required=False,
                        help='Path of the folder where the corrected files will be copied (only corrupted files will be copied there).', **widget_dir)
    main_parser.add_argument('-e', '--errors_file', metavar='/some/folder/errorsfile.csv', type=str, nargs=1, required=False, #type=argparse.FileType('rt')
                        help='Path to the error file generated by RFIGC.py. The software will automatically correct those files and only those files.', **widget_file)
    main_parser.add_argument('--ignore_size', action='store_true', required=False, default=False,
                        help='On correction, if the file size differs from when the ecc file was generated, ignore and try to correct anyway (this may work with file where data was appended without changing the rest. For compressed formats like zip, this will probably fail).')

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
    entrymarker = "\xFF\xFF\xFF\xFF" # marker that will signal the beginning of an ecc entry
    field_delim = "\xFF" # delimiter between fields (filepath, filesize, hash+ecc blocks) inside an ecc entry

    #-- Set variables from arguments
    folderpath = fullpath(args.input[0])
    database = fullpath(args.database[0])
    generate = args.generate
    correct = args.correct
    force = args.force
    stats_only = args.stats_only
    max_block_size = args.max_block_size
    header_size = args.size
    resilience_rate_s1 = args.resilience_rate_stage1
    resilience_rate_s2 = args.resilience_rate_stage2
    resilience_rate_s3 = args.resilience_rate_stage3
    replication_rate = args.replication_rate
    ignore_size = args.ignore_size
    skip_size_below = args.skip_size_below
    always_include_ext = args.always_include_ext
    if always_include_ext: always_include_ext = tuple(['.'+ext for ext in always_include_ext.split('|')]) # prepare a tuple of extensions (prepending with a dot) so that str.endswith() works (it doesn't with a list, only a tuple)

    if correct:
        if not args.output:
            raise NameError('Output path is necessary when in correction mode!')
        outputpath = fullpath(args.output[0])

    max_memory = 65535
    if args.max_memory and args.max_memory > 0: max_memory = args.max_memory

    errors_file = None
    if args.errors_file: errors_file = os.path.basename(fullpath(args.errors_file[0]))

    # -- Checking arguments
    if not stats_only and not generate and not os.path.isfile(database):
        raise NameError('Specified database ecc file %s does not exist!' % database)
    elif generate and os.path.isfile(database) and not force:
        raise NameError('Specified database ecc file %s already exists! Use --force if you want to overwrite.' % database)

    if resilience_rate_s1 <= 0 or resilience_rate_s2 <= 0 or resilience_rate_s3 <= 0:
        raise ValueError('Resilience rates cannot be negative and they must be floating numbers.');

    if max_block_size < 2 or max_block_size > 255:
        raise ValueError('RS max block size must be between 2 and 255.')

    if header_size < 1:
        raise ValueError('Header size cannot be negative.')

    if replication_rate < 0 or replication_rate == 2:
        raise ValueError('Replication rate must either be 1 (no replication) or above 3 to be useful (cannot disambiguate with only 2 replications).')

    # -- Configure the log file if enabled (ptee.write() will write to both stdout/console and to the log file)
    if args.log:
        ptee = Tee(args.log[0], 'a')
        #sys.stdout = Tee(args.log[0], 'a')
        sys.stderr = Tee(args.log[0], 'a')
    else:
        ptee = Tee()


    # == PROCESSING BRANCHING == #

    # Precompute some parameters
    hasher = Hasher("md5")
    ecc_params_header = compute_ecc_params(max_block_size, resilience_rate_s1, hasher) # TODO: not static anymore since it's a variable encoding rate, so we have to recompute it on-the-fly for each block relatively to total file size.
    ecc_manager_header = ECC(max_block_size, ecc_params_header["message_size"])
    ecc_params_variable_average = compute_ecc_params(max_block_size, resilience_rate_s2 + resilience_rate_s3, hasher) # compute the average variable rate

    # == Precomputation of ecc file size
    # Precomputing is important so that the user can know what size to expect before starting (and how much time it will take...).
    filescount = 0
    sizetotal = 0
    sizeecc = 0
    ptee.write("Precomputing list of files and predicted statistics...")
    for (dirpath, filename) in tqdm.tqdm(recwalk(folderpath)):
        filescount = filescount + 1 # counting the total number of files we will process (so that we can show a progress bar with ETA)
        # Get full absolute filepath
        filepath = os.path.join(dirpath,filename)
        relfilepath = os.path.relpath(filepath, folderpath) # File relative path from the root (so that we can easily check the files later even if the absolute path is different)
        # Get the current file's size
        size = os.stat(filepath).st_size
        # Check if we must skip this file because size is too small, and then if we still keep it because it's extension is always to be included
        if skip_size_below and size < skip_size_below and (not always_include_ext or not relfilepath.lower().endswith(always_include_ext)): continue

        # Compute total size of all files
        sizetotal = sizetotal + size
        # Compute predicted size of their headers
        if size >= header_size: # for big files, we limit the size to the header size
            filesize_header = header_size
            filesize_content = size - header_size
        else: # else for size smaller than the defined header size, it will just be the size of the file
            filesize_header = size
            filesize_content = 0
        # Size of the ecc entry for this file will be: marker-bytes (\xFF bytes) + length-filepath-string + length-size-string + size of the ecc per block for all blocks in file header + size of the hash per block for all blocks in file header.
        sizeecc = sizeecc + replication_rate * (len(entrymarker) + len(field_delim)*2 + len(relfilepath) + len(str(size)) + (int(math.ceil(float(filesize_header) / ecc_params_header["message_size"])) * (ecc_params_header["ecc_size"]+ecc_params_header["hash_size"])) + (int(math.ceil(float(filesize_content) / ecc_params_variable_average["message_size"])) * (ecc_params_variable_average["ecc_size"]+ecc_params_variable_average["hash_size"])) ) # Compute the total number of bytes we will add with ecc + hash (accounting for the padding of the remaining characters at the end of the sequence in case it doesn't fit with the message_size, by using ceil() )
    ptee.write("Precomputing done.")
    # TODO: add the size of the ecc format header? (arguments string + PYHEADERECC identifier)
    total_pred_percentage = sizeecc * 100 / sizetotal
    ptee.write("Total ECC size estimation: %s = %g%% of total files size %s." % (sizeof_fmt(sizeecc), total_pred_percentage, sizeof_fmt(sizetotal)))

    if stats_only: return True

    # == Generation mode
    # Generate an ecc file, containing ecc entries for every files recursively in the specified root folder.
    # The file header will be split by blocks depending on max_block_size and resilience_rate, and each of those blocks will be hashed and a Reed-Solomon code will be produced.
    if generate:
        ptee.write("====================================")
        ptee.write("Structural adaptive ECC generation, started on %s" % datetime.datetime.now().isoformat())
        ptee.write("====================================")
        
        with open(database, 'wb') as db:
            # Write ECC file header identifier (unique string + version)
            db.write("**PYSTRUCTADAPTECCv%s**\n" % (''.join([x * 3 for x in __version__]))) # each character in the version will be repeated 3 times, so that in case of tampering, a majority vote can try to disambiguate)
            # Write the parameters (they are NOT reloaded automatically, you have to specify them at commandline! It's the user role to memorize those parameters (using any means: own brain memory, keep a copy on paper, on email, etc.), so that the parameters are NEVER tampered. The parameters MUST be ultra reliable so that errors in the ECC file can be more efficiently recovered.
            for i in xrange(3): db.write("** Parameters: "+" ".join(sys.argv[1:]) + "\n") # copy them 3 times just to be redundant in case of ecc file corruption
            # NOTE: there's NO HEADER for the ecc file! Ecc entries are all independent of each others, you just need to supply the decoding arguments at commandline, and the ecc entries can be decoded. This is done on purpose to be remove the risk of critical spots in ecc file (there is still a critical spot in the filepath and on hashes, see intra-ecc in todo).

            # Compile the list of files to put in the header
            #filesheader = [':'.join([str(i), str(item[0]), str(item[1])]) for i, item in enumerate(itertools.izip(fileslist, filessizes))]
            #for i in xrange(4): # replicate the headers several times as a safeguard for corruption
                #db.write("**" + '|'.join(filesheader) + "**\n")

            # Processing ecc on files
            files_done = 0
            files_skipped = 0
            for (dirpath, filename) in tqdm.tqdm(recwalk(folderpath), total=filescount, leave=True):
                # Get full absolute filepath
                filepath = os.path.join(dirpath,filename)
                # Get database relative path (from scanning root folder)
                relfilepath = os.path.relpath(filepath, folderpath) # File relative path from the root (so that we can easily check the files later even if the absolute path is different)
                # Get file size
                filesize = os.stat(filepath).st_size
                # If skip size is enabled and size is below the skip size, we skip UNLESS the file extension is in the always include list
                if skip_size_below and filesize < skip_size_below and (not always_include_ext or not relfilepath.lower().endswith(always_include_ext)):
                    files_skipped += 1
                    continue

                # Opening the input file's to read its header and compute the ecc/hash blocks
                #print("Processing file %s\n" % filepath) # DEBUGLINE
                for i in xrange(replication_rate): # TODO: that's a shame because we recompute several times the whole ecc entry. Try to put the ecc entry in a temporary file at first, and then streamline copy to the ecc file.
                    with open(os.path.join(folderpath,filepath), 'rb') as file:
                        db.write((entrymarker+"%s"+field_delim+"%s"+field_delim) % (relfilepath, filesize)) # first save the file's metadata (filename, filesize, ...)
                        # -- Header constant ecc encoding
                        buf = file.read(header_size) # read the file's header
                        db.write(''.join(compute_ecc_hash(ecc_manager_header, hasher, buf, max_block_size, resilience_rate_s1, ecc_params_header["message_size"], as_string=True))) # then compute the ecc/hash entry for this file's header (this will be a chain of multiple ecc/hash fields per block of data, because Reed-Solomon is limited to a maximum of 255 bytes, including the original_message+ecc!)
                        # -- Variable content encoding
                        buf = file.read(max_memory)
                        while len(buf) > 0:
                            # Compute ECC for each block (with a progressively decreasing rate that is computed dynamically)
                            rate = feature_scaling(file.tell(), header_size, filesize, resilience_rate_s2, resilience_rate_s3) # find the rate for the current stream of data (interpolate between stage 2 and stage 3 rates depending on the cursor position in the file)
                            ecc_params_variable = compute_ecc_params(max_block_size, rate, hasher)
                            ecc_manager_variable = ECC(max_block_size, ecc_params_variable["message_size"])
                            db.write(''.join(compute_ecc_hash(ecc_manager_variable, hasher, buf, max_block_size, rate, ecc_params_variable["message_size"], as_string=True)))
                            # Load the next data block from file
                            buf = file.read(max_memory)
                files_done += 1
        ptee.write("All done! Total number of files processed: %i, skipped: %i" % (files_done, files_skipped))
        return 0

    # == Error Correction (and checking by hash) mode
    # For each file, check their headers by block by checking each block against a hash, and if the hash does not match, try to correct with Reed-Solomon and then check the hash again to see if we correctly repaired the block (else the ecc entry might have been corrupted, whether it's the hash or the ecc field, in both cases it's highly unlikely that a wrong repair will match the hash after this wrong repair)
    # TODO: this part is totally uncomplete!
    elif correct:
        ptee.write("====================================")
        ptee.write("Structural adaptive ECC correction, started on %s" % datetime.datetime.now().isoformat())
        ptee.write("====================================")

        # Prepare the list of files with errors to reduce the scan (only if provided)
        errors_filelist = []
        if errors_file:
            for row in csv.DictReader(open(errors_file, 'rb'), delimiter='|', fieldnames=['filepath', 'error']): # need to specify the fieldnames, else the first row in the csv file will be skipped (it will be used as the columns names)
                errors_filelist.append(row['filepath'])

        # Read the ecc file
        fileinfos = ''
        with open(database, 'rb') as db:
            # Counters
            files_count = 0
            files_corrupted = 0
            files_repaired_partially = 0
            files_repaired_completely = 0
            files_skipped = 0

            # Main loop: process each ecc entry
            entry = 1 # to start the while loop
            while tqdm.tqdm(entry, leave=True): # TODO: update progress bar based on ecc file size

                # -- Read the next ecc entry (extract the raw string from the ecc file)
                if replication_rate == 1:
                    entry = read_next_entry(db, entrymarker)

                # -- Disambiguation/Replication management: if replication rate was used, then fetch all entries for the same file at once, and then disambiguate by majority vote
                else:
                    entries = []
                    for i in xrange(replication_rate):
                        entries.append(read_next_entry(db, entrymarker))
                    entry = entries_disambiguate(entries, field_delim, ptee)
                # No entry? Then we finished because this is the end of file (stop condition)
                if not entry: break

                # -- Extract the fields from the ecc entry
                entry_p = entry_fields(entry, field_delim)

                # -- Get file infos
                relfilepath = entry_p["relfilepath"] # Relative file path
                filepath = os.path.join(folderpath, relfilepath) # Get full absolute filepath from given input folder (because the files may be specified in any folder, in the ecc file the paths are relative, so that the files can be moved around or burnt on optical discs)
                if errors_filelist and relfilepath not in errors_filelist: continue # if a list of files with errors was supplied (for example by rfigc.py), then we will check only those files and skip the others

                #print("Processing file %s\n" % relfilepath) # DEBUGLINE

                # -- Check filepath
                # Check that the filepath isn't corrupted (detectable mainly with replication_rate >= 3, but if a silent error erase a character (not only flip a bit), then it will also be detected this way
                if relfilepath.find("\x00") >= 0:
                    ptee.write("Error: ecc entry corrupted on filepath field, please try to manually repair the filepath (filepath: %s - missing/corrupted character at %i)." % (relfilepath, relfilepath.find("\x00")))
                    files_skipped += 1
                    continue
                # Check that file still exists before checking it
                if not os.path.isfile(filepath):
                    ptee.write("Error: file %s could not be found: either file was moved or the ecc entry was corrupted. If replication_rate is enabled, maybe the majority vote was wrong. You can try to fix manually the entry." % relfilepath)
                    files_skipped += 1
                    continue

                # -- Checking file size: if the size has changed, the blocks may not match anymore!
                filesize = os.stat(filepath).st_size
                if entry_p["filesize"] != filesize:
                    if ignore_size:
                        ptee.write("Warning: file %s has a different size: %s (before: %s). Will still try to correct it (but the blocks may not match!)." % (relfilepath, filesize, entry_p["filesize"]))
                    else:
                        ptee.write("Error: file %s has a different size: %s (before: %s). Skipping the file correction because blocks may not match." % (relfilepath, filesize, entry_p["filesize"]))
                        files_skipped += 1
                        continue

                files_count += 1
                # -- Check blocks and repair if necessary
                entry_asm = entry_assemble(entry_p, ecc_params, header_size, filepath) # Extract and assemble each message block from the original file with its corresponding ecc and hash
                corrupted = False # flag to signal that the file was corrupted and we need to reconstruct it afterwards
                repaired_partially = False # flag to signal if a file was repaired only partially
                # For each message block, check the message with hash and repair with ecc if necessary
                for i, e in enumerate(entry_asm):
                    # If the message block has a different hash, it was corrupted (or the hash is corrupted, or both)
                    if hasher.hash(e["message"]) != e["hash"]:
                        corrupted = True
                        # Try to repair the block using ECC
                        ptee.write("File %s: corruption in block %i. Trying to fix it." % (relfilepath, i))
                        repaired_block = ecc_manager.decode(e["message"], e["ecc"])
                        # Check if the repair was successful.
                        if repaired_block and hasher.hash(repaired_block) == e["hash"]: # If the hash now match the repaired message block, we commit the new block
                            entry_asm[i]["message_repaired"] = repaired_block # save the repaired block
                            ptee.write("File %s: block %i repaired!" % (relfilepath, i))
                        else: # Else the hash does not match: the repair failed (either because the ecc is too much tampered, or because the hash is corrupted. Either way, we don't commit). # TODO: maybe it's just the hash that was corrupted and the repair worked out, we need more resiliency against that by computing ecc for the hash too (I call this: intra-ecc).
                            ptee.write("Error: file %s could not repair block %i (hash mismatch). You may try with Dans-labs/bit-recover." % (relfilepath, i)) # you need to code yourself to use bit-recover, it's in perl but it should work given the hash computed by this script and the corresponding message block.
                            repaired_partially = True
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
                        out.write(''.join([e["message_repaired"] if "message_repaired" in e else e["message"] for e in entry_asm]))
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
        ptee.write("All done! Stats:\n- Total files processed: %i\n- Total files corrupted: %i\n- Total files repaired completely: %i\n- Total files repaired partially: %i\n- Total files corrupted but not repaired at all: %i\n- Total files skipped: %i" % (files_count, files_corrupted, files_repaired_completely, files_repaired_partially, files_corrupted - (files_repaired_partially + files_repaired_completely), files_skipped) )
        return 0

# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":
    sys.exit(main())
