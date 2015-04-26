#!/usr/bin/env python
#
# Structural Adaptive Error Correction Code
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

__version__ = "1.2"

# Include the lib folder in the python import path (so that packaged modules can be easily called, such as gooey which always call its submodules via gooey parent module)
import sys, os
thispathname = os.path.dirname(sys.argv[0])
sys.path.append(os.path.join(thispathname, 'lib'))

# Import necessary libraries
import lib.argparse as argparse
import datetime, time
import lib.tqdm as tqdm
#import itertools
import math
#import operator # to get the max out of a dict
import csv # to process the errors_file from rfigc.py
import shlex # for string parsing as argv argument to main(), unnecessary otherwise
from lib.tee import Tee # Redirect print output to the terminal as well as in a log file
from StringIO import StringIO # to support intra-ecc
import struct # to support indexes backup file
#import pprint # Unnecessary, used only for debugging purposes

# ECC and hashing facade libraries
from lib.eccman import ECCMan, compute_ecc_params
from lib.hasher import Hasher
from lib.reedsolomon.reedsolo import ReedSolomonError



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

#--------------------------------

def find_next_entry(file, entrymarker="\xFF\xFF\xFF\xFF"):
    '''Find the next ecc entry in the ecc file, and return the start and end positions. This will find any string length between two entrymarkers. The reading is very tolerant, so it will always return any valid entry (but also scrambled entries if any, but the decoding will ensure everything's ok).'''
    blocksize = 65535
    found = False
    start = None # start and end vars are the relative position of the starting/ending entrymarkers in the current buffer
    end = None
    startcursor = None # startcursor and endcursor are the absolute position of the starting/ending entrymarkers inside the database file
    endcursor = None
    buf = 1
    # Continue the search as long as we did not find at least one starting marker and one ending marker (or end of file)
    while (not found and buf):
        # Read a long block at once, we will readjust the file cursor after
        buf = file.read(blocksize)
        # Find the start marker (if not found already)
        if start is None or start == -1:
            start = buf.find(entrymarker); # relative position of the starting marker in the currently read string
            if start >= 0 and not startcursor: # assign startcursor only if it's empty (meaning that we did not find the starting entrymarker, else if found we are only looking for 
                startcursor = file.tell() - len(buf) + start # absolute position of the starting marker in the file
            if start >= 0: start = start + len(entrymarker)
        # If we have a starting marker, we try to find a subsequent marker which will be the ending of our entry (if the entry is corrupted we don't care: it won't pass the entry_to_dict() decoding or subsequent steps of decoding and we will just pass to the next ecc entry). This allows to process any valid entry, no matter if previous ones were scrambled.
        if startcursor is not None and startcursor >= 0:
            end = buf.find(entrymarker, start)
            if end < 0 and len(buf) < blocksize: # Special case: we didn't find any ending marker but we reached the end of file, then we are probably in fact just reading the last entry (thus there's no ending marker for this entry)
                end = len(buf) # It's ok, we have our entry, the ending marker is just the end of file
            # If we found an ending marker (or if end of file is reached), then we compute the absolute cursor value and put the file reading cursor back in position, just before the next entry (where the ending marker is if any)
            if end >= 0:
                endcursor = file.tell() - len(buf) + end
                file.seek(endcursor)
                found = True
        #print("Start:", start, startcursor)
        #print("End: ", end, endcursor)
        # Stop criterion to avoid infinite loop: in the case we could not find any entry in the rest of the file and we reached the EOF, we just quit now
        if len(buf) < blocksize: break
        # Did not find the full entry in one buffer? Reinit variables for next iteration, but keep in memory startcursor.
        if start > 0: start = 0 # reset the start position for the end buf find at next iteration (ie: in the arithmetic operations to compute the absolute endcursor position, the start entrymarker won't be accounted because it was discovered in a previous buffer).
        if not endcursor: file.seek(file.tell()-len(entrymarker)) # Try to fix edge case where blocksize stops the buffer exactly in the middle of the ending entrymarker. The starting marker should always be ok because it should be quite close (or generally immediately after) the previous entry, but the end depends on the end of the current entry (size of the original file), thus the buffer may miss the ending entrymarker. should offset file.seek(-len(entrymarker)) before searching for ending.

    entry_pos = None # return None if there's no new entry to read
    if found: # if an entry was found, we return the starting position and ending position of the ecc entry (without the entrymarker). Note: we just return the reading positions and not the entry itself because it can get quite huge and may overflow memory, thus we will read each ecc blocks on request using a generator.
        entry_pos = [startcursor + len(entrymarker), endcursor]
        file.seek(startcursor+len(entrymarker))
    # Detect from first marker to the next
    return entry_pos

def entry_fields(file, entry_pos, field_delim="\xFF"):
    '''From an ecc entry position (a list with starting and ending positions), extract the filename, filesize, and the starting/ending positions of the rest of the ecc entry (containing variably encoded blocks of hash and ecc per blocks of the original file's header)'''
    # Read the the beginning of the ecc entry
    blocksize = 65535
    file.seek(entry_pos[0])
    entry = file.read(blocksize)
    entry = entry.lstrip(field_delim) # if there was some slight adjustment error (example: the last ecc block of the last file was the field_delim, then we will start with a field_delim, and thus we need to remove the trailing field_delim which is useless and will make the field detection buggy). This is not really a big problem for the previous file's ecc block: the missing ecc characters (which were mistaken for a field_delim), will just be missing (so we will lose a bit of resiliency for the last block of the previous file, but that's not a huge issue, the correction can still rely on the other characters).
    # TODO: do in a while loop in case the filename is really big (bigger than blocksize) - or in case we add intra-ecc for filename

    # Find field delimiters positions
    first = entry.find(field_delim)
    second = entry.find(field_delim, first+len(field_delim))
    third = entry.find(field_delim, second+len(field_delim))
    # Note: we do not try to find all the field delimiters because we optimize here: we just walk the string to find the exact number of field_delim we are looking for, and after we stop, no need to walk through the whole string.

    # Extract each field
    relfilepath = entry[:first]
    filesize = entry[first+len(field_delim):second]
    relfilepath_ecc = entry[second+len(field_delim):third]
    ecc_field_pos = [entry_pos[0]+third+len(field_delim), entry_pos[1]] # return the starting and ending position of the rest of the ecc track, which contains blocks of hash/ecc of the original file's content.

    # Place the cursor at the beginning of the ecc_field
    file.seek(ecc_field_pos[0])

    # Try to convert to an int, an error may happen
    try:
        filesize = int(filesize)
    except Exception, e:
        print("Exception when trying to detect the filesize in ecc field (it may be corrupted), skipping: ")
        print(e)
        filesize = 0

    # entries = [ {"message":, "ecc":, "hash":}, etc.]
    return {"relfilepath": relfilepath, "relfilepath_ecc": relfilepath_ecc, "filesize": filesize, "ecc_field_pos": ecc_field_pos}

def stream_entry_assemble(hasher, file, eccfile, entry_fields, max_block_size, header_size, resilience_rates, constantmode=False):
    '''From an entry with its parameters (filename, filesize), assemble a list of each block from the original file along with the relative hash and ecc for easy processing later.'''
    # Cut the header and the ecc entry into blocks, and then assemble them so that we can easily process block by block
    eccfile.seek(entry_fields["ecc_field_pos"][0])
    curpos = file.tell()
    ecc_curpos = eccfile.tell()
    while (ecc_curpos < entry_fields["ecc_field_pos"][1]): # continue reading the input file until we reach the position of the previously detected ending marker
        # Compute the current rate, depending on where we are inside the input file (headers? later stage?)
        if curpos < header_size or constantmode: # header stage: constant rate
            rate = resilience_rates[0]
        else: # later stage 2 or 3: progressive rate
            rate = feature_scaling(curpos, header_size, entry_fields["filesize"], resilience_rates[1], resilience_rates[2]) # find the rate for the current stream of data (interpolate between stage 2 and stage 3 rates depending on the cursor position in the file)
        # From the rate, compute the ecc parameters
        ecc_params = compute_ecc_params(max_block_size, rate, hasher)
        # Extract the message block from input file, given the computed ecc parameters
        mes = file.read(ecc_params["message_size"])
        if len(mes) == 0: return # quit if message is empty (reached end-of-file), this is a safeguard if ecc pos ending was miscalculated (we thus only need the starting position to be correct)
        buf = eccfile.read(ecc_params["hash_size"]+ecc_params["ecc_size"])
        hash = buf[:ecc_params["hash_size"]]
        ecc = buf[ecc_params["hash_size"]:]

        yield {"message": mes, "hash": hash, "ecc": ecc, "rate": rate, "ecc_params": ecc_params, "curpos": curpos, "ecc_curpos": ecc_curpos}
        # Prepare for the next iteration of the loop
        curpos = file.tell()
        ecc_curpos = eccfile.tell()
    # Just a quick safe guard against ecc ending marker misdetection
    file.seek(0, os.SEEK_END) # alternative way of finding the total size: go to the end of the file
    size = file.tell()
    if curpos < size: print("WARNING: end of ecc track reached but not the end of file! Either the ecc ending marker was misdetected, or either the file hash changed! Some blocks maybe may not have been properly checked!")

 # TODO: entries_disambiguate() NOT READY! we can either disambiguate on the fly (since the ecc field is not longer completely loaded in memory) each block (should be implemented inside (entry_fields and entry_assemble) or we can pre-compute disambiguation by reading each character in parallel from the file and then outputting to a temporary file.
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

def stream_compute_ecc_hash(ecc_manager, hasher, file, max_block_size, header_size, resilience_rates):
    '''Generate a stream of hash/ecc blocks, of variable encoding rate and size, given a file.'''
    curpos = file.tell() # init the reading cursor at the beginning of the file
    # Find the total size to know when to stop
    #size = os.fstat(file.fileno()).st_size # old way of doing it, doesn't work with StringIO objects
    file.seek(0, os.SEEK_END) # alternative way of finding the total size: go to the end of the file
    size = file.tell()
    file.seek(0, curpos) # place the reading cursor back at the beginning of the file
    # Main encoding loop
    while curpos < size: # Continue encoding while we do not reach the end of the file
        # Calculating the encoding rate
        if curpos < header_size: # if we are still reading the file's header, we use a constant rate
            rate = resilience_rates[0]
        else: # else we use a progressive rate for the rest of the file the we calculate on-the-fly depending on our current reading cursor position in the file
            rate = feature_scaling(curpos, header_size, size, resilience_rates[1], resilience_rates[2]) # find the rate for the current stream of data (interpolate between stage 2 and stage 3 rates depending on the cursor position in the file)

        # Compute the ecc parameters given the calculated rate
        ecc_params = compute_ecc_params(max_block_size, rate, hasher)
        #ecc_manager = ECCMan(max_block_size, ecc_params["message_size"]) # not necessary to create an ecc manager anymore, as it is very costly. Now we can specify a value for k on the fly (tables for all possible values of k are pre-generated in the reed-solomon libraries)

        # Compute the ecc and hash for the current message block
        mes = file.read(ecc_params["message_size"])
        hash = hasher.hash(mes)
        ecc = ecc_manager.encode(mes, k=ecc_params["message_size"])
        #print("mes %i (%i) - ecc %i (%i) - hash %i (%i)" % (len(mes), message_size, len(ecc), ecc_params["ecc_size"], len(hash), ecc_params["hash_size"])) # DEBUGLINE

        # Return the result
        yield [hash, ecc, ecc_params]
        # Prepare for next iteration
        curpos = file.tell()



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
Note1: this is a pure-python implementation (except for MD5 hash but a pure-python alternative is provided in lib/md5py.py), thus it may be VERY slow to generate an ecc file. To speed-up things considerably, you can use PyPy v2.5.0 or above, there will be a speed-up of at least 100x from our experiments (you can expect an encoding rate of more than 1MB/s). Feel free to profile using easy_profiler.py and try to optimize the encoding parts of the reed-solomon libraries.

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
    main_parser.add_argument('--ecc_algo', type=int, default=1, required=False,
                        help='What algorithm use to generate and verify the ECC? Values possible: 1-4. 1 is the formal, fully verified Reed-Solomon in base 3 ; 2 is a faster implementation but still based on the formal base 3 ; 3 is an even faster implementation but based on another library which may not be correct ; 4 is the fastest implementation supporting US FAA ADSB UAT RS FEC standard but is totally incompatible with the other three (a text encoded with any of 1-3 modes will be decodable with any one of them).', **widget_text)
    main_parser.add_argument('--max_block_size', type=int, default=255, required=False,
                        help='Reed-Solomon max block size (maximum = 255). It is advised to keep it at the maximum for more resilience (see comments at the top of the script for more info). However, if encoding it too slow, using a smaller value will speed things up greatly, at the expense of more storage space (because hash will relatively take more space - you can use --hash "shortmd5" or --hash "minimd5" to counter balance).', **widget_text)
    main_parser.add_argument('-s', '--size', type=int, default=1024, required=False,
                        help='Headers block size to protect with resilience rate stage 1 (eg: 1024 meants that the first 1k of each file will be protected by stage 1).', **widget_text)
    main_parser.add_argument('-r1', '--resilience_rate_stage1', type=float, default=0.3, required=False,
                        help='Resilience rate for files headers (eg: 0.3 = 30% of errors can be recovered but size of codeword will be 60% of the data block).', **widget_text)
    main_parser.add_argument('-r2', '--resilience_rate_stage2', type=float, default=0.2, required=False,
                        help='Resilience rate for stage 2 (after headers, this is the starting rate applied to the rest of the file, which will be gradually lessened towards the end of the file to the stage 3 rate).', **widget_text)
    main_parser.add_argument('-r3', '--resilience_rate_stage3', type=float, default=0.1, required=False,
                        help='Resilience rate for stage 3 (rate that will be applied towards the end of the files).', **widget_text)
    main_parser.add_argument('-ri', '--resilience_rate_intra', type=float, default=0.5, required=False,
                        help='Resilience rate for intra-ecc (ecc on meta-data, such as filepath, thus this defines the ecc for the critical spots!).', **widget_text)
    main_parser.add_argument('--replication_rate', type=int, default=1, required=False,
                        help='Replication rate, if you want to duplicate each ecc entry (DO NOT USE, not implemented yet, see sourcecode for what to implement).', **widget_text)
    main_parser.add_argument('-l', '--log', metavar='/some/folder/filename.log', type=str, nargs=1, required=False,
                        help='Path to the log file. (Output will be piped to both the stdout and the log file)', **widget_filesave)
    main_parser.add_argument('--stats_only', action='store_true', required=False, default=False,
                        help='Only show the predicted total size of the ECC file given the parameters.')
    main_parser.add_argument('--hash', metavar='md5;shortmd5;shortsha256...', type=str, required=False,
                        help='Hash algorithm to use. Choose between: md5, shortmd5, shortsha256, minimd5, minisha256.', **widget_text)
    main_parser.add_argument('-v', '--verbose', action='store_true', required=False, default=False,
                        help='Verbose mode (show more output).')

    # Correction mode arguments
    main_parser.add_argument('-c', '--correct', action='store_true', required=False, default=False,
                        help='Check/Correct the files')
    main_parser.add_argument('-o', '--output', metavar='/path/to/output/folder', type=is_dir, nargs=1, required=False,
                        help='Path of the folder where the corrected files will be copied (only corrupted files will be copied there).', **widget_dir)
    main_parser.add_argument('-e', '--errors_file', metavar='/some/folder/errorsfile.csv', type=str, nargs=1, required=False, #type=argparse.FileType('rt')
                        help='Path to the error file generated by RFIGC.py. The software will automatically correct those files and only those files.', **widget_file)
    main_parser.add_argument('--ignore_size', action='store_true', required=False, default=False,
                        help='On correction, if the file size differs from when the ecc file was generated, ignore and try to correct anyway (this may work with file where data was appended without changing the rest. For compressed formats like zip, this will probably fail).')
    main_parser.add_argument('--no_fast_check', action='store_true', required=False, default=False,
                        help='On correction, block corruption is only checked with the hash (the ecc will still be checked after correction, but not before). If no_fast_check is enabled, then ecc will also be checked before. This allows to find blocks corrupted by malicious intent (the block is corrupted but the hash has been corrupted as well to match the corrupted block, because it\'s almost impossible that following a hardware or logical fault, the hash match the corrupted block).')
    main_parser.add_argument('--skip_missing', action='store_true', required=False, default=False,
                        help='Skip missing files (no warning).')

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
    resilience_rate_intra = args.resilience_rate_intra
    replication_rate = args.replication_rate
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

    if resilience_rate_s1 <= 0 or resilience_rate_s2 <= 0 or resilience_rate_s3 <= 0 or resilience_rate_intra <= 0:
        raise ValueError('Resilience rates cannot be negative nor zero and they must be floating numbers.');

    if max_block_size < 2 or max_block_size > 255:
        raise ValueError('RS max block size must be between 2 and 255.')

    if header_size < 1:
        raise ValueError('Header size cannot be negative.')

    if replication_rate < 0 or replication_rate == 2:
        raise ValueError('Replication rate must either be 1 (no replication) or above 3 to be useful (cannot disambiguate with only 2 replications).')

    if hash_algo not in Hasher.known_algo:
        raise ValueError("Specified hash algorithm %s is unknown!" % hash_algo)

    # -- Configure the log file if enabled (ptee.write() will write to both stdout/console and to the log file)
    if args.log:
        ptee = Tee(args.log[0], 'a')
        #sys.stdout = Tee(args.log[0], 'a')
        sys.stderr = Tee(args.log[0], 'a')
    else:
        ptee = Tee()


    # == PROCESSING BRANCHING == #

    # Precompute some parameters and load up ecc manager objects (big optimization as g_exp and g_log tables calculation is done only once)
    resilience_rates = [resilience_rate_s1, resilience_rate_s2, resilience_rate_s3]
    hasher = Hasher(hash_algo)
    hasher_intra = Hasher('none') # for intra_ecc we don't use any hash
    ecc_params_header = compute_ecc_params(max_block_size, resilience_rate_s1, hasher)
    ecc_manager_header = ECCMan(max_block_size, ecc_params_header["message_size"], algo=ecc_algo)
    ecc_manager_variable = ECCMan(max_block_size, 1, algo=ecc_algo)
    ecc_params_intra = compute_ecc_params(max_block_size, resilience_rate_intra, hasher_intra)
    ecc_manager_intra = ECCMan(max_block_size, ecc_params_intra["message_size"], algo=ecc_algo)
    ecc_params_idx = compute_ecc_params(27, 1, hasher_intra)
    ecc_manager_idx = ECCMan(27, ecc_params_idx["message_size"], algo=ecc_algo)
    # for stats only
    ecc_params_variable_average = compute_ecc_params(max_block_size, (resilience_rate_s2 + resilience_rate_s3)/2, hasher) # compute the average variable rate to compute statistics
    ecc_params_s2 = compute_ecc_params(max_block_size, resilience_rate_s2, hasher)
    ecc_params_s3 = compute_ecc_params(max_block_size, resilience_rate_s3, hasher)

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
        # Size of the ecc entry for this file will be: entrymarker-bytes + field_delim-bytes*occurrence + length-filepath-string + length-size-string + length-filepath-ecc + size of the ecc per block for all blocks in file header + size of the hash per block for all blocks in file header.
        sizeecc += replication_rate * (len(entrymarker) + len(field_delim)*3 + len(relfilepath) + len(str(size)) + int(float(len(relfilepath))*resilience_rate_intra) + (int(math.ceil(float(filesize_header) / ecc_params_header["message_size"])) * (ecc_params_header["ecc_size"]+ecc_params_header["hash_size"])) + (int(math.ceil(float(filesize_content) / ecc_params_variable_average["message_size"])) * (ecc_params_variable_average["ecc_size"]+ecc_params_variable_average["hash_size"])) ) # Compute the total number of bytes we will add with ecc + hash (accounting for the padding of the remaining characters at the end of the sequence in case it doesn't fit with the message_size, by using ceil() )
    ptee.write("Precomputing done.")
    if generate: # show statistics only if generating an ecc file
        # TODO: add the size of the ecc format header? (arguments string + PYHEADERECC identifier)
        total_pred_percentage = sizeecc * 100 / sizetotal
        ptee.write("Total ECC size estimation: %s = %g%% of total files size %s." % (sizeof_fmt(sizeecc), total_pred_percentage, sizeof_fmt(sizetotal)))
        ptee.write("Details per stage:")
        ptee.write("- Resiliency stage1 of %i%%: For the header (first %i characters) of each file: each block of %i chars will get an ecc of %i chars." % (resilience_rate_s1*100, header_size, ecc_params_header["message_size"], ecc_params_header["ecc_size"]))
        ptee.write("- Resiliency stage2 of %i%%: for the rest of the file, the parameters will start with: each block of %i chars will get an ecc of %i chars." % (resilience_rate_s2*100, ecc_params_s2["message_size"], ecc_params_s2["ecc_size"]))
        ptee.write("- Resiliency stage3 of %i%%: progressively towards the end, the parameters will gradually become: each block of %i chars will get an ecc of %i chars." % (resilience_rate_s3*100, ecc_params_s3["message_size"], ecc_params_s3["ecc_size"]))
        if max_block_size > 100: ptee.write("Note: current max_block_size (size of message+ecc blocks) is %i. Consider using a smaller value to greatly speedup the processing (because Reed-Solomon encoding complexity is about O(max_block_size^2)) at the expense of generating a bigger ecc file." % max_block_size)

    if stats_only: return 0

    # == Generation mode
    # Generate an ecc file, containing ecc entries for every files recursively in the specified root folder.
    # The file header will be split by blocks depending on max_block_size and resilience_rate, and each of those blocks will be hashed and a Reed-Solomon code will be produced.
    if generate:
        ptee.write("====================================")
        ptee.write("Structural adaptive ECC generation, started on %s" % datetime.datetime.now().isoformat())
        ptee.write("====================================")

        with open(database, 'wb') as db, open(database+".idx", 'wb') as dbidx:
            # Write ECC file header identifier (unique string + version)
            db.write("**PYSTRUCTADAPTECCv%s**\n" % (''.join([x * 3 for x in __version__]))) # each character in the version will be repeated 3 times, so that in case of tampering, a majority vote can try to disambiguate)
            # Write the parameters (they are NOT reloaded automatically, you have to specify them at commandline! It's the user role to memorize those parameters (using any means: own brain memory, keep a copy on paper, on email, etc.), so that the parameters are NEVER tampered. The parameters MUST be ultra reliable so that errors in the ECC file can be more efficiently recovered.
            for i in xrange(3): db.write("** Parameters: "+" ".join(sys.argv[1:]) + "\n") # copy them 3 times just to be redundant in case of ecc file corruption
            db.write("** Generated under %s\n" % ecc_manager_variable.description())
            # NOTE: there's NO HEADER for the ecc file! Ecc entries are all independent of each others, you just need to supply the decoding arguments at commandline, and the ecc entries can be decoded. This is done on purpose to be remove the risk of critical spots in ecc file.

            # Compile the list of files to put in the header
            #filesheader = [':'.join([str(i), str(item[0]), str(item[1])]) for i, item in enumerate(itertools.izip(fileslist, filessizes))]
            #for i in xrange(4): # replicate the headers several times as a safeguard for corruption
                #db.write("**" + '|'.join(filesheader) + "**\n")

            # Processing ecc on files
            files_done = 0
            files_skipped = 0
            bardisp = tqdm.tqdm(total=sizetotal, leave=True, unit='B', unit_format=True, mininterval=1)
            for (dirpath, filename) in recwalk(folderpath):
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
                if verbose: print("\n- Processing file %s" % relfilepath)
                for i in xrange(replication_rate): # TODO: that's a shame because we recompute several times the whole ecc entry. Try to put the ecc entry in a temporary file at first or in StringIO (does it buffer in a file?), and then streamline copy to the ecc file. Or alternative: ecc fields are replicated, not the whole ecc entry.
                    with open(os.path.join(folderpath,filepath), 'rb') as file:
                        entrymarker_pos = db.tell() # backup the position of the start of this ecc entry
                        # -- Intra-ecc generation: Compute an ecc for the filepath, to avoid a critical spot here (so that we don't care that the filepath gets corrupted, we have an ecc to fix it!)
                        fpfile = StringIO(relfilepath)
                        intra_ecc = ''.join( [str(x[1]) for x in stream_compute_ecc_hash(ecc_manager_intra, hasher_intra, fpfile, max_block_size, len(relfilepath), [resilience_rate_intra])] ) # "hack" the function by tricking it to always use a constant rate, by setting the header_size=len(relfilepath), and supplying the resilience_rate_intra instead of resilience_rate_s1 (the one for header)
                        db.write(("%s%s%s%s%s%s%s") % (entrymarker, relfilepath, field_delim, filesize, field_delim, intra_ecc, field_delim)) # first save the file's metadata (filename, filesize, ecc for filename, ...), separated with field_delim
                        # -- External indexes backup: calculate the position of the entrymarker and of each field delimiter, and compute their ecc, and save into the index backup file. This will allow later to retrieve the position of each marker in the ecc file, and repair them if necessary, while just incurring a very cheap storage cost.
                        markers_pos = [entrymarker_pos, entrymarker_pos+len(entrymarker)+len(relfilepath), entrymarker_pos+len(entrymarker)+len(relfilepath)+len(field_delim)+len(str(filesize)), db.tell()-len(field_delim)] # Make the list of all markers positions for this ecc entry. The first and last indexes are the most important (first is the entrymarker, the last is the field_delim just before the ecc track start)
                        markers_pos = [struct.pack('>Q', x) for x in markers_pos] # Convert to a binary representation in 8 bytes using unsigned long long (up to 16 EB, this should be more than sufficient)
                        markers_types = ["1", "2", "2", "2"]
                        markers_pos_ecc = [ecc_manager_idx.encode(x+y) for x,y in zip(markers_types,markers_pos)] # compute the ecc for each number
                        dbidx.write(''.join([str(x) for items in zip(markers_types,markers_pos,markers_pos_ecc) for x in items])) # couple each marker's position with its ecc, and write them all consecutively into the index backup file
                        # -- Hash/Ecc encoding of file's content (everything is managed inside stream_compute_ecc_hash)
                        for ecc_entry in stream_compute_ecc_hash(ecc_manager_variable, hasher, file, max_block_size, header_size, resilience_rates): # then compute the ecc/hash entry for this file's header (each value will be a block, a string of hash+ecc per block of data, because Reed-Solomon is limited to a maximum of 255 bytes, including the original_message+ecc! And in addition we want to use a variable rate for RS that is decreasing along the file)
                            db.write( "%s%s" % (str(ecc_entry[0]),str(ecc_entry[1])) ) # note that there's no separator between consecutive blocks, but by calculating the ecc parameters, we will know when decoding the size of each block!
                            bardisp.update(ecc_entry[2]['message_size'])
                files_done += 1
        if bardisp.n > bardisp.total: bardisp.total = bardisp.n # small workaround because n may be higher than total (because of files ending before 'message_size', thus the message is padded and in the end, we have outputted and processed a bit more characters than are really in the files, thus why total can be below n). Doing this allows to keep the trace of the progression bar.
        bardisp.close()
        ptee.write("All done! Total number of files processed: %i, skipped: %i" % (files_done, files_skipped))
        return 0

    # == Error Correction (and checking by hash) mode
    # For each file, check their headers by block by checking each block against a hash, and if the hash does not match, try to correct with Reed-Solomon and then check the hash again to see if we correctly repaired the block (else the ecc entry might have been corrupted, whether it's the hash or the ecc field, in both cases it's highly unlikely that a wrong repair will match the hash after this wrong repair)
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
        dbsize = os.stat(database).st_size # must get db file size before opening it in order not to move the cursor
        with open(database, 'rb') as db:
            # Counters
            files_count = 0
            files_corrupted = 0
            files_repaired_partially = 0
            files_repaired_completely = 0
            files_skipped = 0
            bardisp_first_open = True

            # Main loop: process each ecc entry
            entry = 1 # to start the while loop
            bardisp = tqdm.tqdm(total=dbsize, leave=True, desc='DBREAD', unit='B', unit_format=True) # display progress bar based on reading the database file (since we don't know how many files we will process beforehand nor how many total entries we have)
            while entry:

                # -- Read the next ecc entry (extract the raw string from the ecc file)
                if replication_rate == 1:
                    entry_pos = find_next_entry(db, entrymarker)
                    if entry_pos:
                        if bardisp_first_open: bardisp.n = entry_pos[0]-len(entrymarker) # add the size of the comments in the ecc header
                        bardisp.update(entry_pos[1]-entry_pos[0]+len(entrymarker)) # update progress bar

                # -- Disambiguation/Replication management: if replication rate was used, then fetch all entries for the same file at once, and then disambiguate by majority vote
                else: # TODO: replication not ready yet
                    entries_pos = []
                    for i in xrange(replication_rate):
                        entries_pos.append(find_next_entry(db, entrymarker))
                    entry_pos = entries_disambiguate(entries_pos, field_delim, ptee)
                    if entry_pos: bardisp.update((entry_pos[1]-entry_pos[0]+len(entrymarker))*replication_rate) # update progress bar
                # No entry? Then we finished because this is the end of file (stop condition)
                if not entry_pos: break

                # -- Extract the fields from the ecc entry
                entry_p = entry_fields(db, entry_pos, field_delim)

                # -- Get file path, check its correctness and correct it by using intra-ecc if necessary
                relfilepath = entry_p["relfilepath"] # Relative file path, given in the ecc fields
                # convert strings to StringIO object so that we can trick our ecc reading functions that normally works only on files
                fpfile = StringIO(relfilepath)
                fpfile_ecc = StringIO(entry_p["relfilepath_ecc"])
                fpentry_p = {"ecc_field_pos": [0, len(relfilepath)]} # create a fake entry_pos so that the ecc reading function works correctly
                relfilepath_correct = [] # will store each block of the corrected (or already correct) filepath
                fpcorrupted = False # check if filepath was corrupted
                fpcorrected = True # check if filepath was corrected (if it was corrupted)
                # Decode each block of the filepath
                for e in stream_entry_assemble(hasher_intra, fpfile, fpfile_ecc, fpentry_p, max_block_size, len(relfilepath), [resilience_rate_intra], constantmode=True):
                    # Check if this block of the filepath is OK, if yes then we just copy it over
                    if ecc_manager_intra.check(e["message"], e["ecc"]):
                        relfilepath_correct.append(e["message"])
                    else: # Else this block is corrupted, we will try to fix it using the ecc
                        fpcorrupted = True
                        # Repair the message block and the ecc
                        repaired_block, repaired_ecc = ecc_manager_intra.decode(e["message"], e["ecc"])
                        # Check if the block was successfully repaired: if yes then we copy the repaired block...
                        if ecc_manager_intra.check(repaired_block, repaired_ecc):
                            relfilepath_correct.append(repaired_block)
                        else: # ... else it failed, then we copy the original corrupted block and report an error later
                            relfilepath_correct.append(e["message"])
                            fpcorrected = False
                # Join all the blocks into one string to build the final filepath
                relfilepath = ''.join(relfilepath_correct)
                # Report errors
                if fpcorrupted:
                    if fpcorrected: ptee.write("\n- Fixed error in filepath %s." % relfilepath)
                    else: ptee.write("\n- Error in filepath, could not correct completely: %s. Please fix manually by editing the ecc file or at least set the corrupted characters to null bytes." % relfilepath)
                # -- End of intra-ecc on filepath

                # Build the absolute file path
                filepath = os.path.join(folderpath, relfilepath) # Get full absolute filepath from given input folder (because the files may be specified in any folder, in the ecc file the paths are relative, so that the files can be moved around or burnt on optical discs)
                if errors_filelist and relfilepath not in errors_filelist: continue # if a list of files with errors was supplied (for example by rfigc.py), then we will check only those files and skip the others

                if verbose: print("\n- Processing file %s" % relfilepath)

                # -- Check filepath
                # Check that the filepath isn't corrupted (detectable mainly with replication_rate >= 3, but if a silent error erase a character (not only flip a bit), then it will also be detected this way
                if relfilepath.find("\x00") >= 0:
                    ptee.write("Error: ecc entry corrupted on filepath field, please try to manually repair the filepath (filepath: %s - missing/corrupted character at %i)." % (relfilepath, relfilepath.find("\x00")))
                    files_skipped += 1
                    continue
                # Check that file still exists before checking it
                if not os.path.isfile(filepath):
                    if not skip_missing: ptee.write("Error: file %s could not be found: either file was moved or the ecc entry was corrupted (filepath is incorrect?)." % relfilepath)
                    files_skipped += 1
                    continue

                # -- Checking file size: if the size has changed, the blocks may not match anymore!
                filesize = os.stat(filepath).st_size
                if entry_p["filesize"] != filesize:
                    if ignore_size:
                        ptee.write("Warning: file %s has a different size: %s (before: %s). Will still try to correct it (but the blocks may not match!)." % (relfilepath, filesize, entry_p["filesize"]))
                    else:
                        ptee.write("Error: file %s has a different size: %s (before: %s). Skipping the file correction because blocks may not match (you can set --ignore_size to still correct even if size is different, maybe just the entry was corrupted)." % (relfilepath, filesize, entry_p["filesize"]))
                        files_skipped += 1
                        continue

                files_count += 1
                # -- Check blocks and repair if necessary
                corrupted = False # flag to signal that the file was corrupted and we need to reconstruct it afterwards
                repaired_partially = False # flag to signal if a file was repaired only partially
                # Do a first run to check if there's any error. If yes, then we will begin back from the start of the file but this time we will streamline copy the data to an output file.
                with open(filepath, 'rb') as file:
                    # For each message block, check the message with hash and repair with ecc if necessary
                    for i, e in enumerate(stream_entry_assemble(hasher, file, db, entry_p, max_block_size, header_size, resilience_rates)): # Extract and assemble each message block from the original file with its corresponding ecc and hash
                        # If the message block has a different hash or the message+ecc is corrupted (syndrome is not null), it was corrupted (or the hash is corrupted or one of the characters of the ecc was corrupted, or both). In any case, it's an any clause here (any potential corruption condition triggers the correction).
                        if hasher.hash(e["message"]) != e["hash"] or (not fast_check and not ecc_manager_variable.check(e["message"], e["ecc"], k=e["ecc_params"]["message_size"])):
                            corrupted = True
                            break
                # -- Reconstruct/Copying the repaired file
                # If the first run detected a corruption, then we try to repair the file (we create an output file where good blocks will be copied as-is but bad blocks will be repaired, if it's possible)
                if corrupted:
                    files_corrupted += 1
                    repaired_one_block = False # flag to check that we could repair at least one block, else we will delete the output file since we didn't do anything
                    err_consecutive = True # flag to check if the ecc track is misaligned/misdetected (we only encounter corrupted blocks that we can't fix)
                    with open(filepath, 'rb') as file:
                        outfilepath = os.path.join(outputpath, relfilepath) # get the full path to the output file
                        outfiledir = os.path.dirname(outfilepath)
                        if not os.path.isdir(outfiledir): os.makedirs(outfiledir) # if the target directory does not exist, create it (and create recursively all parent directories too)
                        with open(outfilepath, 'wb') as outfile:
                            # TODO: optimize to copy over what we have already checked, so that we get directly to the first error that triggered the correction
                            # For each message block, check the message with hash and repair with ecc if necessary
                            for i, e in enumerate(stream_entry_assemble(hasher, file, db, entry_p, max_block_size, header_size, resilience_rates)): # Extract and assemble each message block from the original file with its corresponding ecc and hash
                                # If the message block has a different hash, it was corrupted (or the hash is corrupted, or both)
                                if hasher.hash(e["message"]) == e["hash"] and (fast_check or ecc_manager_variable.check(e["message"], e["ecc"], k=e["ecc_params"]["message_size"])):
                                    outfile.write(e["message"])
                                    err_consecutive = False
                                else:
                                    # Try to repair the block using ECC
                                    ptee.write("File %s: corruption in block %i. Trying to fix it." % (relfilepath, i))
                                    try:
                                        repaired_block, repaired_ecc = ecc_manager_variable.decode(e["message"], e["ecc"], k=e["ecc_params"]["message_size"])
                                    except ReedSolomonError, e: # the reedsolo lib may raise an exception when it can't decode. We ensure that we can still continue to decode the rest of the file, and the other files.
                                        repaired_block = None
                                        repaired_ecc = None
                                        print(e)
                                    # Check if the repair was successful. This is an "all" condition: if all checks fail, then the correction failed. Else, we assume that the checks failed because the ecc entry was partially corrupted (it's highly improbable that any one check success by chance, it's a lot more probable that it's simply that the entry was partially corrupted, eg: the hash was corrupted and thus cannot match anymore).
                                    hash_ok = (hasher.hash(repaired_block) == e["hash"])
                                    ecc_ok = ecc_manager_variable.check(repaired_block, repaired_ecc, k=e["ecc_params"]["message_size"])
                                    if repaired_block and (hash_ok or ecc_ok): # If the hash now match the repaired message block, we commit the new block
                                        outfile.write(repaired_block) # save the repaired block
                                        # Show a precise report about the repair
                                        if hash_ok and ecc_ok: ptee.write("File %s: block %i repaired!" % (relfilepath, i))
                                        elif not hash_ok: ptee.write("File %s: block %i probably repaired with matching ecc check but with a hash error (assume the hash was corrupted)." % (relfilepath, i))
                                        elif not ecc_ok: ptee.write("File %s: block %i probably repaired with matching hash but with ecc check error (assume the ecc was partially corrupted)." % (relfilepath, i))
                                        # Turn on the repaired flag, to trigger the copying of the file (else it will be removed if all blocks repairs failed in this file)
                                        repaired_one_block = True
                                        err_consecutive = False
                                    else: # Else the hash does not match: the repair failed (either because the ecc is too much tampered, or because the hash is corrupted. Either way, we don't commit).
                                        outfile.write(e["message"]) # copy the bad block that we can't repair...
                                        ptee.write("Error: file %s could not repair block %i (both hash and ecc check mismatch). If you know where the errors are, you can set the characters to a null character so that the ecc may correct twice more characters." % (relfilepath, i)) # you need to code yourself to use bit-recover, it's in perl but it should work given the hash computed by this script and the corresponding message block.
                                        repaired_partially = True
                                        # Detect if the ecc track is misaligned/misdetected (we encounter only errors that we can't fix)
                                        if err_consecutive and i >= 10: # threshold is ten consecutive uncorrectable errors
                                            ptee.write("Failure: Too many consecutive uncorrectable errors for %s. Most likely, the ecc track was misdetected (try to repair the entrymarkers and field delimiters). Skipping this track/file." % relfilepath)
                                            db.seek(entry_p["ecc_field_pos"][1]) # Optimization: move the reading cursor to the beginning of the next ecc entry, this will save some iterations in find_next_entry()
                                            break
                    # Copying the last access time and last modification time from the original file TODO: a more reliable way would be to use the db computed by rfigc.py, because if a software maliciously tampered the data, then the modification date may also have changed (but not if it's a silent error, in that case we're ok).
                    filestats = os.stat(filepath)
                    os.utime(outfilepath, (filestats.st_atime, filestats.st_mtime))
                    # Check that at least one block was repaired, else we couldn't fix anything in the file and thus we should just remove the output file which is an exact copy of the original without any added value
                    if not repaired_one_block:
                        os.remove(outfilepath)
                    # Counters...
                    elif repaired_partially:
                        files_repaired_partially += 1
                    else:
                        files_repaired_completely += 1
        # All ecc entries processed for checking and potentally repairing, we're done correcting!
        bardisp.close() # at the end, the bar may not be 100% because of the headers that are skipped by read_next_entry() and are not accounted in bardisp.
        ptee.write("All done! Stats:\n- Total files processed: %i\n- Total files corrupted: %i\n- Total files repaired completely: %i\n- Total files repaired partially: %i\n- Total files corrupted but not repaired at all: %i\n- Total files skipped: %i" % (files_count, files_corrupted, files_repaired_completely, files_repaired_partially, files_corrupted - (files_repaired_partially + files_repaired_completely), files_skipped) )
        return 0

# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":
    sys.exit(main())
