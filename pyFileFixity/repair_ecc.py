#!/usr/bin/env python
#
# ECC repairer
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

from __future__ import print_function

from pyFileFixity import __version__

# Include the lib folder in the python import path (so that packaged modules can be easily called, such as gooey which always call its submodules via gooey parent module)
import sys, os
thispathname = os.path.dirname(__file__)
sys.path.append(os.path.join(thispathname))

# Import necessary libraries
from lib._compat import _str, _range, b
from lib.aux_funcs import fullpath
import lib.argparse as argparse
import datetime, time
import lib.tqdm as tqdm
import itertools
import math
#import operator # to get the max out of a dict
import shlex # for string parsing as argv argument to main(), unnecessary otherwise
from lib.tee import Tee # Redirect print output to the terminal as well as in a log file
import struct # to support indexes backup file
import shutil
from lib.distance.distance import hamming
#import pprint # Unnecessary, used only for debugging purposes

# ECC and hashing facade libraries
from lib.eccman import ECCMan, compute_ecc_params
from lib.hasher import Hasher
from lib.reedsolomon.reedsolo import ReedSolomonError



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

@AutoGooey
def main(argv=None):
    if argv is None: # if argv is empty, fetch from the commandline
        argv = sys.argv[1:]
    elif isinstance(argv, _str): # else if argv is supplied but it's a simple string, we need to parse it to a list of arguments before handing to argparse or any other argument parser
        argv = shlex.split(argv) # Parse string just like argv using shlex

    #==== COMMANDLINE PARSER ====

    #== Commandline description
    desc = '''ECC file repairer
Description: Repair the structure of an ecc file, mainly the ecc markers, so that at least the ecc correction can align correctly the ecc entries and fields.
Note: An ecc structure repair does NOT allow to recover from more errors on your files, it only allows to repair an ecc file so that its structure is valid and can be read correctly.
    '''
    ep = ''' '''

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
    main_parser.add_argument('-i', '--input', metavar='eccfile.txt', type=str, required=True,
                        help='Path to the ecc file to repair.', **widget_file)
    main_parser.add_argument('-o', '--output', metavar='eccfile_repaired.txt', type=str, required=True, #type=argparse.FileType('rt')
                        help='Output path where to save the repaired ecc file.', **widget_filesave)
    main_parser.add_argument('-t', '--threshold', type=float, default=0.3, required=False,
                        help='Distance threshold for the heuristic hamming distance repair. This must be a float, eg, 0.2 means that if there are 20% characters different between an ecc marker and a substring in the ecc file, it will be detected as a marker and corrected.', **widget_text)

    # Optional general arguments
    main_parser.add_argument('--index', metavar='eccfile.txt.idx', type=str, required=False,
                        help='Path to the index backup file corresponding to the ecc file (optional but helps a lot).', **widget_file)
    main_parser.add_argument('--ecc_algo', type=int, default=1, required=False,
                        help='What algorithm use to generate and verify the ECC? Values possible: 1-4. 1 is the formal, fully verified Reed-Solomon in base 3 ; 2 is a faster implementation but still based on the formal base 3 ; 3 is an even faster implementation but based on another library which may not be correct ; 4 is the fastest implementation supporting US FAA ADSB UAT RS FEC standard but is totally incompatible with the other three (a text encoded with any of 1-3 modes will be decodable with any one of them).', **widget_text)
    main_parser.add_argument('-l', '--log', metavar='/some/folder/filename.log', type=str, required=False,
                        help='Path to the log file. (Output will be piped to both the stdout and the log file)', **widget_filesave)
    main_parser.add_argument('-v', '--verbose', action='store_true', required=False, default=False,
                        help='Verbose mode (show more output).')
    main_parser.add_argument('--silent', action='store_true', required=False, default=False,
                        help='No console output (but if --log specified, the log will still be saved in the specified file).')

    main_parser.add_argument('-f', '--force', action='store_true', required=False, default=False,
                        help='Force overwriting the ecc file even if it already exists (if --generate).')


    #== Parsing the arguments
    args = main_parser.parse_args(argv) # Storing all arguments to args

    #-- Set hard-coded variables
    entrymarker = "\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF" # marker that will signal the beginning of an ecc entry - use an alternating pattern of several characters, this avoids confusion (eg: if you use "AAA" as a pattern, if the ecc block of the previous file ends with "EGA" for example, then the full string for example will be "EGAAAAC:\yourfolder\filea.jpg" and then the entry reader will detect the first "AAA" occurrence as the entry start - this should not make the next entry bug because there is an automatic trim - but the previous ecc block will miss one character that could be used to repair the block because it will be "EG" instead of "EGA"!)
    field_delim = "\xFA\xFF\xFA\xFF\xFA" # delimiter between fields (filepath, filesize, hash+ecc blocks) inside an ecc entry
    markers = [entrymarker, field_delim] # put them in a list for easy reference
    max_block_size = 27
    resilience_rate = 1

    #-- Set variables from arguments
    inputpath = fullpath(args.input)
    outputpath = fullpath(args.output)
    distance_threshold = args.threshold
    indexpath = None
    if args.index: indexpath = fullpath(args.index)
    force = args.force
    ecc_algo = args.ecc_algo
    verbose = args.verbose
    silent = args.silent

    # -- Checking arguments
    if not os.path.isfile(inputpath):
        raise NameError('Specified database ecc file %s does not exist!' % inputpath)
    if os.path.isfile(outputpath) and not force:
        raise NameError('Specified output path for the repaired ecc file %s already exists! Use --force if you want to overwrite.' % outputpath)
    if indexpath and not os.path.isfile(indexpath):
        raise NameError('Specified index backup file %s does not exist!' % indexpath)

    if max_block_size < 2 or max_block_size > 255:
        raise ValueError('RS max block size must be between 2 and 255.')

    # -- Configure the log file if enabled (ptee.write() will write to both stdout/console and to the log file)
    if args.log:
        ptee = Tee(args.log, 'a', nostdout=silent)
        #sys.stdout = Tee(args.log, 'a')
        sys.stderr = Tee(args.log, 'a', nostdout=silent)
    else:
        ptee = Tee(nostdout=silent)


    # == PROCESSING BRANCHING == #

    # Precompute some parameters and load up ecc manager objects (big optimization as g_exp and g_log tables calculation is done only once)
    hasher_none = Hasher('none') # for index ecc we don't use any hash
    ecc_params_idx = compute_ecc_params(max_block_size, resilience_rate, hasher_none)
    ecc_manager_idx = ECCMan(max_block_size, ecc_params_idx["message_size"], algo=ecc_algo)

    # == Main loop
    ptee.write("====================================")
    ptee.write("ECC repair, started on %s" % datetime.datetime.now().isoformat())
    ptee.write("====================================")
    ptee.write("Please note that this tool may not know if it found all the markers, so it may miss too much corrupted markers but it will repair the ones it finds (except if you have a fully valid index file, then you are guaranteed to always find all markers).")

    ecc_size = os.stat(inputpath).st_size
    if indexpath: idx_size = os.stat(indexpath).st_size
    shutil.copy2(inputpath, outputpath)
    blocksize = 65535
    with open(outputpath, 'r+b') as db:

        # == Index backup repair
        # This repair needs an index backup file which is normally generated at the same time as the ecc file. The index backup file is a file that stores the position of all ecc markers in the corresponding ecc file, and protects those positions using ecc.
        if indexpath:
            ptee.write("Using the index backup file %s to repair ecc markers, please wait..." % args.index)
            db.seek(0) # seek to the beginning of the database file
            idx_corrupted = 0
            idx_corrected = 0
            idx_total = 0
            markers_repaired = [0] * len(markers) # create one list for each marker type
            bardisp = tqdm.tqdm(total=idx_size, file=ptee, leave=True, desc='IDXREAD', unit='B', unit_scale=True) # display progress bar based on reading the database file (since we don't know how many files we will process beforehand nor how many total entries we have)
            with open(indexpath, 'rb') as dbidx:
                buf = 1
                while buf:
                    # The format of the index backup file is pretty simple: for each entrymarker or field_delim, a block is appended. Each such block is made of: the type on one byte (1 for entrymarker, 2 for field_delim), then the marker's position in the ecc file encoded in an unsigned long long (thus it's on a fixed 8 bytes), and finally an ecc for both the type and marker's position, and which is of fixed size (since we know that the marker's type + position = 9 bytes). Each such block is appended right after the precedent, so we know easily read them and such structure cannot be tampered by a soft error (there's no way a hard drive failure can chance the structure of the data, but a malicious user can! But it's then easy to fix that for a human user, you can clearly see the patterns, where the marker's positions begins and ends).
                    # Note that this constant sized structure of blocks is made on purpose, so that the structure of the index backup file is implicit, while the structure of the ecc file is explicit (it needs uncorrupted markers, which is a weak point that we try to address with the index backup file).
                    # eg of two blocks: 10000008Aecceccecc2000000F2ecceccecc
                    #
                    # Read one index block
                    curpos = dbidx.tell() # backup current position for error messages
                    buf = dbidx.read(max_block_size)
                    # Update progress bar
                    bardisp.update(dbidx.tell()-bardisp.n)
                    # If we have reached EOF, then we stop here
                    if not buf: break

                    # Else it's ok we have an index block, we process it
                    idx_total += 1
                    # Extract the marker's infos and the ecc
                    marker_str = buf[:ecc_params_idx["message_size"]]
                    ecc = buf[ecc_params_idx["message_size"]:]
                    # Check if the marker's infos are corrupted, if yes, then we will try to fix that using the ecc
                    if not ecc_manager_idx.check(marker_str, ecc):
                        # Trying to fix the marker's infos using the ecc
                        idx_corrupted += 1
                        marker_repaired, repaired_ecc = ecc_manager_idx.decode(marker_str, ecc)
                        # Repaired the marker's infos, all is good!
                        if ecc_manager_idx.check(marker_repaired, repaired_ecc):
                            marker_str = marker_repaired
                            idx_corrected += 1
                        # Else it's corrupted beyond repair, just skip
                        else:
                            ptee.write("\n- Index backup file: error on block starting at %i, corrupted and could not fix it. Skipping." % curpos)
                            marker_str = None
                            continue
                    if not marker_str: continue

                    # Repair ecc file's marker using our correct (or repaired) marker's infos
                    marker_type = int(chr(marker_str[0]) if isinstance(marker_str[0], int) else marker_str[0]) # marker's type is always stored on the first byte/character
                    marker_pos = struct.unpack('>Q', marker_str[1:]) # marker's position is encoded as a big-endian unsigned long long, in a 8 bytes/chars string
                    db.seek(marker_pos[0]) # move the ecc reading cursor to the beginning of the marker
                    current_marker = db.read(len(markers[marker_type-1])) # read the current marker (potentially corrupted)
                    db.seek(marker_pos[0])
                    if verbose:
                        ptee.write("- Found marker by index file: type=%i content=" % (marker_type))
                        ptee.write(db.read(len(markers[marker_type-1])+4))
                        db.seek(marker_pos[0]) # replace the reading cursor back in place before the marker
                    if current_marker != markers[marker_type-1]: # check if we really need to repair this marker
                        # Rewrite the marker over the ecc file
                        db.write(b(markers[marker_type-1]))
                        markers_repaired[marker_type-1] += 1
                    else:
                        ptee.write("skipped, no need to repair")
            # Done the index backup repair
            if bardisp.n > bardisp.total: bardisp.n = bardisp.total # just a workaround in case there's one byte more than the predicted total
            bardisp.close()
            ptee.write("Done. Total: %i/%i markers repaired (%i entrymarkers and %i field_delim), %i indexes corrupted and %i indexes repaired (%i indexes lost).\n" % (markers_repaired[0]+markers_repaired[1], idx_total, markers_repaired[0], markers_repaired[1], idx_corrupted, idx_corrected, idx_corrupted-idx_corrected) )

        # == Heuristical Greedy Hamming distance repair
        # This is a heuristical (doesn't need any other file than the ecc file) 2-pass algorithm: the first pass tries to find the markers positions, and then the second pass simply reads the original ecc file and copies it while repairing the found markers.
        # The first pass is obviously the most interesting, here's a description: we use a kind of greedy algorithm but with backtracking, meaning that we simply read through all the strings sequentially and just compare with the markers and compute the Hamming distance: if the Hamming distance gets below the threshold, we trigger the found marker flag. Then if the Hamming distance decreases, we save this marker position and disable the found marker flag. However, there can be false positives like this (eg, the marker is corrupted in the middle), so we have a backtracking mechanism: if a later string is found to have a Hamming distance that is below the threshold, then we check if the just previously found marker is in the range (ie, the new marker's position is smaller than the previous marker's length) and if the Hamming distance is smaller, then we replace the previous marker with the new marker's position, because the previous one was most likely a false positive.
        # This method doesn't require any other file than the ecc file, but it may not work on ecc markers that are too much tampered, and if the detection threshold is too low or the markers are too small, there may be lots of false positives.
        # So try to use long markers (consisting of many character, preferably an alternating pattern different than the null byte \x00) and a high enough detection threshold.
        ptee.write("Using heuristics (Hamming distance) to fix markers with a threshold of %i%%, please wait..." % (round(distance_threshold*100, 0)) )

        # Main loop for heuristical repair, try to find the substrings that minimize the hamming distance to one of the ecc markers
        markers_repaired = [0] * len(markers) # stat counter
        already_valid = 0 # stat counter
        db.seek(0) # seek to the beginning of the database file
        buf = 1 # init the buffer to 1 to initiate the while loop
        markers_pos = [[] for i in _range(len(markers))] # will contain the list of positions where a corrupted marker has been detected (not valid markers, they will be skipped)
        distance_thresholds = [round(len(x)*distance_threshold, 0) for x in markers] # calculate the number of characters maximum for distance
        skip_until = -1 # when a valid marker (non corrupted) is found, we use this variable to skip to after the marker length (to avoid detecting partial parts of this marker, which will have a hamming distance even if the marker is completely valid because the reading window will be after the beginning of the marker)
        bardisp = tqdm.tqdm(total=ecc_size, file=ptee, leave=True, desc='DBREAD', unit='B', unit_scale=True) # display progress bar based on reading the database file (since we don't know how many files we will process beforehand nor how many total entries we have)
        while buf: # until we have walked through the whole ecc file
            # Read a part of the ecc file into a buffer, this allows to process more quickly than just loading the size of a marker
            curpos = db.tell() # keep the current reading position
            buf = db.read(blocksize)
            # Update progress bar
            bardisp.update(db.tell()-bardisp.n)
            if not buf: break # reached EOF? quitting here

            # Scan the buffer, by splitting the buffer into substrings the length of the ecc markers
            for i in _range(len(buf)-max(len(entrymarker),len(field_delim))):
                # If we just came accross a non corrupted ecc marker, we skip until we are after this ecc marker (to avoid misdetections)
                if i < skip_until: continue
                # Compare each ecc marker type to this substring and compute the Hamming distance
                for m in _range(len(markers)):
                    d = hamming(b(buf[i:i+len(markers[m])]), b(markers[m])) # Compute the Hamming distance (simply the number of different characters)
                    mcurpos = curpos+i # current absolute position of this ecc marker
                    
                    # If there's no difference, then it's a valid, non-corrupted ecc marker
                    if d == 0:
                        already_valid += 1 # stats...
                        # If we previously wrongly detected a corrupted ecc marker near here, then it's probably a misdetection (because we just had a partial view on this marker until now), thus we just remove it from our list of markers to repair
                        if len(markers_pos[m]) > 0 and (mcurpos - markers_pos[m][-1][0]) <= len(markers[m]): # to detect that, we just check if the latest marker to repair is near the current marker (if its position is at maximum the length of the marker). This works because in the other condition below, we update the latest marker to repair if we find another one with a lower hamming distance very near.
                            del markers_pos[m][-1]
                        # Skip scanning until we are after the current marker to avoid misdetections
                        su = i+len(markers[m])
                        if su > skip_until: skip_until = su # update with the biggest marker (because both markers can be detected here if the pattern is similar)
                        break
                    # Else there's a difference/distance but it's below the threshold: we have a corrupted marker!
                    elif d > 0 and d <= distance_thresholds[m]:
                        # Updating case: If the latest marker to repair is quite close to the current one, but the current detection has a lower distance, we probably are detecting the same marker but we are better positionned now, so we update the previous marker's position with this one now.
                        if len(markers_pos[m]) > 0 and (mcurpos - markers_pos[m][-1][0]) <= len(markers[m]):
                            if d < markers_pos[m][-1][1]: # Update only if the distance is less
                                markers_pos[m][-1] = [mcurpos, d]
                            else: # Else, we probably are detecting the same marker as the last detected one, but since our scanning window has moved forward, we have increased the distance. Just skip it, we should not repair at this position (else we will probably be overwriting over real content).
                                continue
                        # Adding case: Else we just add this marker as a new one to repair by appending to the list
                        else:
                            markers_pos[m].append([mcurpos, d])
                    # Else the distance is too great for the threshold, it's not a marker at all, we go on to the next substring
            if db.tell() < ecc_size: db.seek(db.tell()-max(len(entrymarker),len(field_delim)))
        if bardisp.n > bardisp.total: bardisp.n = bardisp.total # just a workaround in case there's one byte more than the predicted total
        bardisp.close()

        # Committing the repair into the ecc file
        for m in _range(len(markers)): # for each type of markers
            marker = markers[m]
            if len(markers_pos[m]) > 0: # If there is any detected marker to repair for this type
                for pos in markers_pos[m]: # for each detected marker to repair, we rewrite it over into the file at the detected position
                    if verbose: ptee.write("- Detected marker type %i at position %i with distance %i (%i%%): repairing." % (m+1, pos[0], pos[1], (float(pos[1])/len(markers[m]))*100) )
                    db.seek(pos[0])
                    db.write(b(marker))

        #print(markers_pos)
        ptee.write("Done. Hamming heuristic with threshold %i%% repaired %i entrymarkers and %i field_delim (%i total) and %i were already valid.\n" % (round(distance_threshold*100, 0), len(markers_pos[0]), len(markers_pos[1]), len(markers_pos[0])+len(markers_pos[1]), already_valid) )
        del ptee
        return 0

# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
