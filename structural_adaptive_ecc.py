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
#          Last modification: 2015-03-10
#                     version: 0.0.1
#=================================
#
# From : http://simple.wikipedia.org/wiki/Reed-Solomon_error_correction
# The key idea behind a Reed-Solomon code is that the data encoded is first visualized as a polynomial. The code relies on a theorem from algebra that states that any k distinct points uniquely determine a polynomial of degree at most k-1.
# The sender determines a degree k-1 polynomial, over a finite field, that represents the k data points. The polynomial is then "encoded" by its evaluation at various points, and these values are what is actually sent. During transmission, some of these values may become corrupted. Therefore, more than k points are actually sent. As long as sufficient values are received correctly, the receiver can deduce what the original polynomial was, and decode the original data.
# In the same sense that one can correct a curve by interpolating past a gap, a Reed-Solomon code can bridge a series of errors in a block of data to recover the coefficients of the polynomial that drew the original curve.
#
# codeword_rate: rs = @(n,k) k / n
# @(n,k) (n - k) / k
#
# To get higher resilience against corruption: make the codeword bigger (decrease k and increase n = higher resilience ratio), and use smaller packets (n should be smaller). Source: Kumar, Sanjeev, and Ragini Gupta. "Bit error rate analysis of Reed-Solomon code for efficient communication system." International Journal of Computer Applications 30.12 (2011): 11-15.
# Note: in the paper, they told that their results indicate to use bigger blocks, but if you look at the Figure 4, this shows the opposite: the best performing parameters is: RS(246, 164) with code rate 0.66667 = resilience ratio 0.25
#
#  If 2s + r < 2t (s errors, r erasures) t
#
# TODO:
# - Use zfec (https://pypi.python.org/pypi/zfec) for more speed.
#

# Import necessary libraries
import lib.argparse as argparse
import os, datetime, time, sys
import hashlib, zlib
import lib.tqdm as tqdm
import itertools
import math
import shlex # for string parsing as argv argument to main(), unnecessary otherwise
from lib.tee import Tee # Redirect print output to the terminal as well as in a log file
#import pprint # Unnecessary, used only for debugging purposes

import lib.brownanrs.rs as brownanrs
rsmode = 1

# try:
    # import lib.brownanrs.rs as brownanrs
    # rsmode = 1
# except ImportError:
        # import lib.reedsolomon.reedsolo as reedsolo
        # rsmode = 2

#***********************************
#                   FUNCTIONS
#***********************************

# Check that an argument is a real directory
def is_dir(dirname):
    """Checks if a path is an actual directory"""
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

def generate_hashes(filepath, blocksize=65536):
    '''Generate several hashes (md5 and sha1) in a single sweep of the file. Using two hashes lowers the probability of collision and false negative (file modified but the hash is the same). Supports big files by streaming blocks by blocks to the hasher automatically. Blocksize can be any multiple of 128.'''
    # Init hashers
    hasher_md5 = hashlib.md5()
    hasher_sha1 = hashlib.sha1()
    # Read the file blocks by blocks
    with open(filepath, 'rb') as afile:
        buf = afile.read(blocksize)
        while len(buf) > 0:
            # Compute both hashes at the same time
            hasher_md5.update(buf)
            hasher_sha1.update(buf)
            # Load the next data block from file
            buf = afile.read(blocksize)
    return (hasher_md5.hexdigest(), hasher_sha1.hexdigest())

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


#***********************************
#                       MAIN
#***********************************

def main(argv=None):
    if argv is None: # if argv is empty, fetch from the commandline
        argv = sys.argv[1:]
    elif isinstance(argv, basestring): # else if argv is supplied but it's a simple string, we need to parse it to a list of arguments before handing to argparse or any other argument parser
        argv = shlex.split(argv) # Parse string just like argv using shlex

    #==== COMMANDLINE PARSER ====

    #== Commandline description
    desc = '''Structural Adaptive Error Correction Code generator and checker
Description: Given a directory, this application will generate error correcting codes or correct corrupt files, using a structural adaptive approach (the headers will be protected by more ecc bits than subsequent parts, progressively decreasing in the resilience).
    '''
    ep = ''' '''

    #== Commandline arguments
    #-- Constructing the parser
    main_parser = argparse.ArgumentParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter)
    # Required arguments
    main_parser.add_argument('-i', '--input', metavar='/path/to/root/folder', type=is_dir, nargs=1, required=True,
                        help='Path to the root folder from where the scanning will occur.')
    main_parser.add_argument('-d', '--database', metavar='/some/folder/ecc.txt', type=str, nargs=1, required=True, #type=argparse.FileType('rt')
                        help='Path to the file containing the ECC informations.')
    main_parser.add_argument('--max_block_size', type=int, default=255, required=False,
                        help='Max block size (maximum = 255). Set it lower to get more resilience.')
    main_parser.add_argument('-rh', '--resilience_header_size', type=int, default=1024, required=False,
                        help='Headers block size to protect with resilience rate stage 1 (eg: 1024 meants that the first 1k of each file will be protected by stage 1).')
    main_parser.add_argument('-r1', '--resilience_rate_stage1', type=float, default=0.3, required=False,
                        help='Resilience rate for files headers (eg: 0.3 = 30% of errors can be recovered but size of codeword will be 60% of the data block).')
    main_parser.add_argument('-r2', '--resilience_rate_stage2', type=float, default=0.2, required=False,
                        help='Resilience rate for stage 2 (after headers, this is the starting rate applied to the rest of the file, which will be gradually lessened towards the end of the file to the stage 3 rate).')
    main_parser.add_argument('-r3', '--resilience_rate_stage3', type=float, default=0.1, required=False,
                        help='Resilience rate for stage 3 (rate that will be applied towards the end of the files).')
    main_parser.add_argument('--replication_rate', type=int, default=1, required=False,
                        help='Replication rate, if you want to duplicate each ecc entry.')
                        

    # Optional general arguments
    main_parser.add_argument('-l', '--log', metavar='/some/folder/filename.log', type=str, nargs=1, required=False,
                        help='Path to the log file. (Output will be piped to both the stdout and the log file)')
    main_parser.add_argument('-s', '--statistics_only', action='store_true', required=False, default=False,
                        help='Only show the predicted total size of the ECC file given the parameters.')
    main_parser.add_argument('--max_memory', type=int, default=65535, required=False,
                        help='Maximum memory used to process files (more memory will help process faster as there will be less IO).')

    # Correction mode arguments
    main_parser.add_argument('-c', '--correct', action='store_true', required=False, default=False,
                        help='Correct the files')
    main_parser.add_argument('-o', '--output', metavar='/path/to/output/folder', type=is_dir, nargs=1, required=False,
                        help='Path of the folder where the corrected files will be copied (only corrupted files will be copied there).')
    main_parser.add_argument('-e', '--errors_file', metavar='/some/folder/errorsfile.csv', type=str, nargs=1, required=False, #type=argparse.FileType('rt')
                        help='Path to the error file generated by RFIGC.py. The software will automatically correct those files and only those files.')

    # Generate mode arguments
    main_parser.add_argument('-g', '--generate', action='store_true', required=False, default=False,
                        help='Generate the database?')
    main_parser.add_argument('-f', '--force', action='store_true', required=False, default=False,
                        help='Force overwriting the database file even if it already exists (if --generate).')

    #== Parsing the arguments
    args = main_parser.parse_args(argv) # Storing all arguments to args

    #-- Set variables from arguments
    folderpath = fullpath(args.input[0])
    database = fullpath(args.database[0])
    generate = args.generate
    correct = args.correct
    force = args.force
    statistics_only = args.statistics_only
    replication_rate = args.replication_rate
    max_block_size = args.max_block_size
    resilience_header_size = args.resilience_header_size
    resilience_rate_s1 = args.resilience_rate_stage1
    resilience_rate_s2 = args.resilience_rate_stage2
    resilience_rate_s3 = args.resilience_rate_stage3

    if correct:
        outputpath = fullpath(args.output[0])

    max_memory = 65535
    if args.max_memory and args.max_memory > 0: max_memory = args.max_memory

    errors_file = None
    if args.errors_file: errors_file = os.path.basename(fullpath(args.errors_file[0]))

    # -- Checking arguments
    if not statistics_only and not generate and not os.path.isfile(database):
        raise NameError('Specified database file does not exist!')
    elif generate and os.path.isfile(database) and not force:
        raise NameError('Specified database file already exists! Use --force if you want to overwrite.')

    if resilience_rate_s1 <= 0 or resilience_rate_s2 <= 0 or resilience_rate_s3 <= 0:
        raise ValueError('Resilience rates cannot be negative and they must be floating numbers.');

    if max_block_size < 2 or max_block_size > 255:
        raise ValueError('Max block size must be between 2 and 255.')

    if resilience_header_size < 1:
        raise ValueError('Header size cannot be negative.')

    # -- Configure the log file if enabled (ptee.write() will write to both stdout/console and to the log file)
    if args.log:
        ptee = Tee(args.log[0], 'a')
        #sys.stdout = Tee(args.log[0], 'a')
        sys.stderr = Tee(args.log[0], 'a')
    else:
        ptee = Tee()


    # == PROCESSING BRANCHING == #
    
    # Precompute the list of files to process
    fileslist = []
    filessizes = []
    filescount = 0
    ptee.write("Precomputing list of files...")
    for (dirpath, filename) in tqdm.tqdm(recwalk(folderpath)):
        filescount = filescount + 1
        # Get full absolute filepath
        filepath = os.path.join(dirpath,filename)
        # Get database relative path (from scanning root folder)
        relfilepath = os.path.relpath(filepath, folderpath) # File relative path from the root (so that we can easily check the files later even if the absolute path is different)
        fileslist.append(relfilepath)
        filessizes.append(os.stat(filepath).st_size)
    ptee.write("Precomputing list of files done.")
    ptee.write("Computing predicted statistics.")
    filessizes2 = filessizes
    totalsize = 0
    maxcol = max(filessizes)

    fs1 = sum([resilience_header_size if x > resilience_header_size else x for x in filessizes])
    fs2 = sum([(x - resilience_header_size) / 2 if x > resilience_header_size and x < (maxcol / 2) else x for x in filessizes])
    fs3 = sum([x for x in filessizes if x >= (maxcol / 2)])
        
    total_predicted = fs1 * (resilience_rate_s1 * 2) + fs2 * (resilience_rate_s2 * 2) + fs3 * (resilience_rate_s3 * 2)
    total_filesize = sum(filessizes)
    total_pred_percentage = total_predicted * 100 / total_filesize
    ptee.write("Total ECC size estimation: %s = %g%% of total files sizes." % (sizeof_fmt(total_predicted), total_pred_percentage))

    # More precise way to compute but it's taking too long...
    # for i in tqdm.tqdm(xrange(maxcol)):
        # col = i+1
        # filessizes2 = filter(lambda x: x >= col, filessizes2)
        # if col <= resilience_header_size:
            # rate = resilience_rate_s1
        # else:
            # rate = resilience_rate_s3 + float(col - resilience_header_size) * (resilience_rate_s3 - resilience_rate_s2) / (maxcol - resilience_header_size) # generalized feature scaling http://en.wikipedia.org/wiki/Normalization_(statistics)

        # totalsize = totalsize + len(filessizes2) * rate * 2

    if statistics_only: return True

    if generate:
        ptee.write("====================================")
        ptee.write("Structural adaptive ECC generation, started on %s" % datetime.datetime.now().isoformat())
        ptee.write("====================================")
        
        with open(database, 'wb') as db:
            db.write("**PYSTRUCTADAPTECC0101020203030404**\n")
            # Compile the list of files to put in the header
            filesheader = [':'.join([str(i), str(item[0]), str(item[1])]) for i, item in enumerate(itertools.izip(fileslist, filessizes))]
            for i in xrange(4): # replicate the headers several times as a safeguard for corruption
                db.write("**" + '|'.join(filesheader) + "**\n")

            for (filepath, filesize) in tqdm.tqdm(itertools.izip(fileslist, filessizes)):
                print("Processing file %s\n" % filepath)
                with open(os.path.join(folderpath,filepath), 'rb') as file:
                    db.write("\xFF\xFF\xFF\xFF%s\xFF%s\xFF" % (filepath, filesize))
                    buf = file.read(resilience_header_size)
                    db.write(''.join(compute_ecc_crc(buf, max_block_size, resilience_rate_s1, True)))
                    buf = file.read(max_memory)
                    while len(buf) > 0:
                        # Compute ECC for each block
                        rate = feature_scaling(file.tell(), resilience_header_size, filesize, resilience_rate_s2, resilience_rate_s3) # find the rate for the current stream of data (interpolate between stage 2 and stage 3 rates depending on the cursor position in the file)
                        db.write(compute_ecc_crc(buf, max_block_size, rate, True))
                        # Load the next data block from file
                        buf = file.read(max_memory)
        ptee.write("All done! Total number of files processed: %i." % len(fileslist))
        return True

    elif correct:
        ptee.write("====================================")
        ptee.write("Structural adaptive ECC correction, started on %s" % datetime.datetime.now().isoformat())
        ptee.write("====================================")

        buf = ''
        fileinfos = ''
        waitcomplete = False
        with open(database, 'rb') as db:
            buf = db.read(max_memory)
            if not waitcomplete:
                try:
                    startpos = buf.position("\xFF\xFF\xFF\xFF")
                    fileinfos = buf[startpos+4:]
                    if not (fileinfos.count("\xFF") == 2):
                        waitcomplete = True
                except ValueError:
                    pass
            else:
                fileinfos = fileinfos + buf
                if fileinfos.count("\xFF") == 2:
                    waitcomplete = False
                
                filepath, filesize, _ = fileinfos.split("\xFF")
                content_start_pos = findnth(fileinfos, "\xFF", 2)
                content = fileinfos[content_start_pos+1:]
                

        ptee.write("All done! Total number of files processed: %i." % len(fileslist))

def findnth(haystack, needle, n):
    parts= haystack.split(needle, n+1)
    if len(parts)<=n+1:
        return -1
    return len(haystack)-len(parts[-1])-len(needle)

def split_len_and_func(seq, length, func, args):
    return [func(seq[i:i+length], *args) for i in xrange(0, len(seq), length)]

def feature_scaling(x, xmin, xmax, a=0, b=1):
    '''Generalized feature scaling'''
    return a + float(x - xmin) * (b - a) / (xmax - xmin)

def compute_ecc_crc(buf, max_block_size, rate, as_string=False):
    result = []
    message_size = max_block_size - int(round(max_block_size * rate * 2, 0))
    for i in xrange(0, len(buf), message_size):
        mes = buf[i:i+message_size]
        ecc = ecc_encode(mes, max_block_size, message_size)
        crc = zlib.crc32(mes)
        if as_string:
            result.append("%s%s" % (str(crc),str(ecc)))
        else:
            result.append([crc, ecc])
    return result

def ecc_encode(message, n, k):
    pad = None
    if len(message) < k:
        pad = "\x00" * (k-len(message))
        message = pad + message
    if rsmode == 1:
        rs = brownanrs.RSCoder(n, k)
        mesecc = rs.encode(message)
        ecc = mesecc[len(message):]
        return ecc

def ecc_decode(message, ecc, n, k):
    pad = None
    if len(message) < k:
        pad = "\x00" * (k-len(message))
        message = pad + message
    if rsmode == 1:
        rs = brownanrs.RSCoder(n, k)
        res = rs.decode(message + ecc, nostrip=True)
        if pad:
            res = res[len(pad):len(res)]


# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":
    sys.exit(main())
