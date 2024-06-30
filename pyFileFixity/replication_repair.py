#!/usr/bin/env python
#
# Replication repair
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
#=================================
#                   Replication repair
#                by Stephen Larroque
#                      License: MIT
#              Creation date: 2015-11-16
#=================================
#

# Include the lib folder in the python import path (so that packaged modules can be easily called, such as gooey which always call its submodules via gooey parent module)
import sys, os
thispathname = os.path.dirname(__file__)
sys.path.append(os.path.join(thispathname))

# Import necessary libraries
from lib._compat import _str, _range, _open_csv, _ord, b
from . import rfigc # optional
import shutil
from lib.aux_funcs import recwalk, path2unix, fullpath, is_dir_or_file, is_dir, is_file, create_dir_if_not_exist
import argparse
import datetime, time
import tqdm
import itertools
import math
#import operator # to get the max out of a dict
import csv # to process the database file from rfigc.py
import shlex # for string parsing as argv argument to main(), unnecessary otherwise
from lib.tee import Tee # Redirect print output to the terminal as well as in a log file
#import pprint # Unnecessary, used only for debugging purposes



#***********************************
#     AUXILIARY FUNCTIONS
#***********************************

def relpath_posix(recwalk_result, pardir, fromwinpath=False):
    ''' Helper function to convert all paths to relative posix like paths (to ease comparison) '''
    return recwalk_result[0], path2unix(os.path.join(os.path.relpath(recwalk_result[0], pardir),recwalk_result[1]), nojoin=True, fromwinpath=fromwinpath)

#def checkAllEqual(lst):
#    return not lst or [lst[0]]*len(lst) == lst

def sort_dict_of_paths(d):
    """ Sort a dict containing paths parts (ie, paths divided in parts and stored as a list). Top paths will be given precedence over deeper paths. """
    def nonesorter(a):
        """ Make None a sortable type (necessary for Python 3) """
        if not a:
            return ['']
        return a

    # Find the path that is the deepest, and count the number of parts
    max_rec = max(len(x) if x else 0 for x in d.values())
    # Pad other paths with empty parts to fill in, so that all paths will have the same number of parts (necessary to compare correctly, else deeper paths may get precedence over top ones, since the folder name will be compared to filenames!)
    for key in d.keys():
        if d[key]:
            d[key] = ['']*(max_rec-len(d[key])) + d[key]
    # Sort the dict relatively to the paths alphabetical order
    d_sort = sorted(d.items(), key=lambda x: nonesorter(x[1]))
    return d_sort

def sort_group(d, return_only_first=False):
    ''' Sort a dictionary of relative paths and cluster equal paths together at the same time '''
    # First, sort the paths in order (this must be a couple: (parent_dir, filename), so that there's no ambiguity because else a file at root will be considered as being after a folder/file since the ordering is done alphabetically without any notion of tree structure).
    d_sort = sort_dict_of_paths(d)
    # Pop the first item in the ordered list
    base_elt = (-1, None)
    while (base_elt[1] is None and d_sort):
        base_elt = d_sort.pop(0)
    # No element, then we just return
    if base_elt[1] is None:
        return None
    # Else, we will now group equivalent files together (remember we are working on multiple directories, so we can have multiple equivalent relative filepaths, but of course the absolute filepaths are different).
    else:
        # Init by creating the first group and pushing the first ordered filepath into the first group
        lst = []
        lst.append([base_elt])
        if d_sort:
            # For each subsequent filepath
            for elt in d_sort:
                # If the filepath is not empty (generator died)
                if elt[1] is not None:
                    # If the filepath is the same to the latest grouped filepath, we add it to the same group
                    if elt[1] == base_elt[1]:
                        lst[-1].append(elt)
                    # Else the filepath is different: we create a new group, add the filepath to this group, and replace the latest grouped filepath
                    else:
                        if return_only_first: break  # break here if we only need the first group
                        lst.append([elt])
                        base_elt = elt # replace the latest grouped filepath
        return lst

def majority_vote_byte_scan(relfilepath, fileslist, outpath, blocksize=65535, default_char_null=False):
    '''Takes a list of files in string format representing the same data, and disambiguate by majority vote: for position in string, if the character is not the same accross all entries, we keep the major one. If none, it will be replaced by a null byte (because we can't know if any of the entries are correct about this character).
    relfilepath is the filename or the relative file path relative to the parent directory (ie, this is the relative path so that we can compare the files from several directories).'''
    # The idea of replication combined with ECC was a bit inspired by this paper: Friedman, Roy, Yoav Kantor, and Amir Kantor. "Combining Erasure-Code and Replication Redundancy Schemes for Increased Storage and Repair Efficiency in P2P Storage Systems.", 2013, Technion, Computer Science Department, Technical Report CS-2013-03
    # But it is a very well known concept in redundancy engineering, usually called triple-modular redundancy (which is here extended to n-modular since we can supply any number of files we want, not just three).
    # Preference in case of ambiguity is always given to the file of the first folder.

    # Store the return code and return message in a variable, so that we can continue executing code to clean up and close open file handles, otherwise we will have a leak!
    rtncodemesg = None

    # Open all files and store file handles in a list
    fileshandles = []
    for filepath in fileslist:
        if filepath:
            # Already a file handle? Just store it in the fileshandles list
            if hasattr(filepath, 'read'):
                fileshandles.append(filepath)
            # Else it's a string filepath, open the file
            else:
                fileshandles.append(open(filepath, 'rb'))

    # Create and open output (merged) file, except if we were already given a file handle
    if hasattr(outpath, 'write'):
        outfile = outpath
    else:
        outpathfull = os.path.join(outpath, relfilepath)
        pardir = os.path.dirname(outpathfull)
        if not os.path.exists(pardir):
            os.makedirs(pardir)
        outfile = open(outpathfull, 'wb')

    # Cannot vote if there's not at least 3 files!
    # In this case, just copy the file from the first folder, verbatim
    if len(fileshandles) < 3:
        # If there's at least one input file, then copy it verbatim to the output folder
        if fileshandles:
            create_dir_if_not_exist(os.path.dirname(outpathfull))
            buf = 1
            while (buf):
                buf = fileshandles[0].read()
                outfile.write(buf)
                outfile.flush()
        rtncodemesg = (1, "Error with file %s: only %i copies available, cannot vote (need at least 3)! Copied the first file from the first folder, verbatim." % (relfilepath, len(fileshandles)))

    if rtncodemesg is None:  # skip if error
        # Main majority vote routine
        errors = []
        entries = [1]*len(fileshandles)  # init with 0 to start the while loop
        while (entries.count(b('')) < len(fileshandles)):
            final_entry = []
            # Read a block from all input files into memory
            for i in _range(len(fileshandles)):
                entries[i] = fileshandles[i].read(blocksize)

            # End of file for all files, we exit
            if entries.count(b('')) == len(fileshandles):
                break
            # Else if there's only one file, just copy the file's content over
            elif entries.count(b('')) == (len(fileshandles) - 1):
                final_entry = entries[0]

            # Else, do the majority vote
            else:
                # Walk along each column (imagine the strings being rows in a matrix, then we pick one column at each iteration = all characters at position i of each string), so that we can compare these characters easily
                for i in _range(max(len(entry) for entry in entries)):
                    hist = {} # kind of histogram, we just memorize how many times a character is presented at the position i in each string TODO: use collections.Counter instead of dict()?
                    # Extract the character at position i of each string and compute the histogram at the same time (number of time this character appear among all strings at this position i)
                    for entry in entries:
                        # Check if we are not beyond the current entry's length
                        if i < len(entry): # TODO: check this line, this should allow the vote to continue even if some files are shorter than others
                            # Extract the character and use it to contribute to the histogram
                            # TODO: add warning message when one file is not of the same size as the others
                            key = str(_ord(entry[i])) # convert to the ascii value to avoid any funky problem with encoding in dict keys
                            hist[key] = hist.get(key, 0) + 1 # increment histogram for this value. If it does not exists, use 0. (essentially equivalent to hist[key] += 1 but with exception management if key did not already exists)
                    # If there's only one character (it's the same accross all strings at position i), then it's an exact match, we just save the character and we can skip to the next iteration
                    if len(hist) == 1:
                        final_entry.append(int(list(hist.keys())[0]))
                        continue
                    # Else, the character is different among different entries, we will pick the major one (mode)
                    elif len(hist) > 1:
                        # Sort the dict by value (and reverse because we want the most frequent first)
                        skeys = sorted(hist, key=hist.get, reverse=True)
                        # Ambiguity! If each entries present a different character (thus the major has only an occurrence of 1), then it's too ambiguous and we just set a null byte to signal that
                        if hist[skeys[0]] == 1:
                            if default_char_null:
                                if default_char_null is True:
                                    final_entry.append(0)
                                else:
                                    final_entry.append(_ord(default_char_null))
                            else:
                                # Use the entry of the first file that is still open
                                first_char = ''
                                for entry in entries:
                                    # Found the first file that has a character at this position: store it and break loop
                                    if i < len(entry):
                                        first_char = entry[i]
                                        break
                                # Use this character in spite of ambiguity
                                final_entry.append(_ord(first_char))
                            errors.append(outfile.tell() + i) # Print an error indicating the characters that failed
                        # Else if there is a tie (at least two characters appear with the same frequency), then we just pick one of them
                        elif hist[skeys[0]] == hist[skeys[1]]:
                            final_entry.append(int(skeys[0])) # TODO: find a way to account for both characters. Maybe return two different strings that will both have to be tested? (eg: maybe one has a tampered hash, both will be tested and if one correction pass the hash then it's ok we found the correct one)
                        # Else we have a clear major character that appear in more entries than any other character, then we keep this one
                        else:
                            final_entry.append(int(skeys[0])) # alternative one-liner: max(hist.iteritems(), key=operator.itemgetter(1))[0]
                        continue
                # Concatenate to a string (this is faster than using a string from the start and concatenating at each iteration because Python strings are immutable so Python has to copy over the whole string, it's in O(n^2)
                final_entry = ''.join([chr(x) for x in final_entry])

            # Commit to output file
            outfile.write(b(final_entry))
            outfile.flush()

        # Errors signaling
        if errors:
            error_msg = "Unrecoverable corruptions (because of ambiguity) in file %s on characters: %s." % (relfilepath, [hex(int(x)) for x in errors]) # Signal to user that this file has unrecoverable corruptions (he may try to fix the bits manually or with his own script)
            rtncodemesg = (1, error_msg) # return an error

    # CLEAN UP! Avoid tracemalloc warnings!
    # Close all input files
    for fh in fileshandles:
        fh.close()
    # Close output file
    if outfile != outpath:  # close only if we were not given a file handle in the first place
        outfile.flush()
        outfile.close()

    # Return!
    # We choose to return a tuple, so that the calling function can know not only that there was an error, but what kind of error more precisely.
    if rtncodemesg is None:
        # No error? We return a no error tuple then!
        return (0, None)
    else:
        # Else we return the error code and error message tuple we have
        return rtncodemesg

def synchronize_files(inputpaths, outpath, database=None, tqdm_bar=None, report_file=None, ptee=None, verbose=False):
    ''' Main function to synchronize files contents by majority vote
    The main job of this function is to walk through the input folders and align the files, so that we can compare every files across every folders, one by one.
    The whole trick here is to align files, so that we don't need to memorize all the files in memory and we compare all equivalent files together: to do that, we ensure that we walk through the input directories in alphabetical order, and we pick the relative filepath at the top of the alphabetical order, this ensures the alignment of files between different folders, without memorizing  the whole trees structures.
    '''
    # (Generator) Files Synchronization Algorithm:
    # Needs a function stable_dir_walking, which will walk through directories recursively but in always the same order on all platforms (same order for files but also for folders), whatever order it is, as long as it is stable.
    # Until there's no file in any of the input folders to be processed:
    # - curfiles <- load first file for each folder by using stable_dir_walking on each input folder.
    # - curfiles_grouped <- group curfiles_ordered:
    #    * curfiles_ordered <- order curfiles alphabetically (need to separate the relative parent directory and the filename, to account for both without ambiguity)
    #    * curfiles_grouped <- empty list
    #    * curfiles_grouped[0] = add first element in curfiles_ordered
    #    * last_group = 0
    #    * for every subsequent element nextelt in curfiles_ordered:
    #        . if nextelt == curfiles_grouped[last_group][0]: add nextelt into curfiles_grouped[last_group] (the latest group in curfiles_grouped)
    #        . else: create a new group in curfiles_grouped (last_group += 1) and add nextelt into curfiles_grouped[last_group]
    # At this stage, curfiles_grouped[0] should contain a group of files with the same relative filepath from different input folders, and since we used stable_dir_walking, we are guaranteed that this file is the next to be processed in alphabetical order.
    # - Majority vote byte-by-byte for each of curfiles_grouped[0], and output winning byte to the output file.
    # - Update files list alignment: we will now ditch files in curfiles_grouped[0] from curfiles, and replace by the next files respectively from each respective folder. Since we processed in alphabetical (or whatever) order, the next loaded files will match the files in other curfiles_grouped groups that we could not process before.
    # At this point (after the loop), all input files have been processed in order, without maintaining the whole files list in memory, just one file per input folder.

    # Init files walking generator for each inputpaths
    recgen = [recwalk(path, sorting=True) for path in inputpaths]
    curfiles = {}
    recgen_exhausted = {}
    recgen_exhausted_count = 0
    nbpaths = len(inputpaths)
    retcode = 0

    if not ptee: ptee = sys.stdout  # allow to specify an output to log, such as a StringIO as used in unit tests

    # Open report file and write header
    if report_file is not None:
        rfile = _open_csv(report_file, 'w')
        r_writer = csv.writer(rfile, delimiter='|', lineterminator='\n', quotechar='"')
        r_header = ['filepath'] + ["dir%i" % (i+1) for i in _range(nbpaths)] + ['hash-correct', 'error_code', 'errors']
        r_length = len(r_header)
        r_writer.writerow(r_header)

    # Initialization: load the first batch of files, one for each folder
    for i in _range(len(recgen)):
        recgen_exhausted[i] = False
        try:
            if curfiles.get(i, None) is None:
                curfiles[i] = relpath_posix(next(recgen[i]), inputpaths[i])[1]
        except StopIteration:
            recgen_exhausted[i] = True
            recgen_exhausted_count += 1

    # Files lists alignment loop
    while recgen_exhausted_count < nbpaths:
        errcode = 0
        errmsg = None

        # Init a new report's row
        if report_file: r_row = ["-"] * r_length

        # -- Group equivalent relative filepaths together
        #print curfiles # debug
        curfiles_grouped = sort_group(curfiles, True)

        # -- Extract first group of equivalent filepaths (this allows us to process with the same alphabetical order on all platforms)
        # Note that the remaining files in other groups will be processed later, because their alphabetical order is higher to the first group, this means that the first group is to be processed now
        to_process = curfiles_grouped[0]
        #print to_process # debug

        # -- Byte-by-byte majority vote on the first group of files
        # Need the relative filepath also (note that there's only one since it's a group of equivalent relative filepaths, only the absolute path is different between files of a same group)
        relfilepath = path2unix(os.path.join(*to_process[0][1]))
        if report_file: r_row[0] = relfilepath
        if verbose: ptee.write("- Processing file %s." % relfilepath)
        # Generate output path
        outpathfull = os.path.join(outpath, relfilepath)
        create_dir_if_not_exist(os.path.dirname(outpathfull))
        # Initialize the list of absolute filepaths
        fileslist = []
        for elt in to_process:
            i = elt[0]
            fileslist.append(os.path.join(inputpaths[i], os.path.join(*elt[1])))
            if report_file: r_row[i+1] = 'X' # put an X in the report file below each folder that contains this file
        # If there's only one file, just copy it over
        if len(to_process) == 1:
            shutil.copyfile(fileslist[0], outpathfull)
            id = to_process[0][0]
            if report_file: r_row[id+1] = 'O'
        # Else, merge by majority vote
        else:
            # Before-merge check using rfigc database, if provided
            # If one of the files in the input folders is already correct, just copy it over
            correct_file = None
            if database:
                for id, filepath in enumerate(fileslist):
                    if rfigc.main("-i \"%s\" -d \"%s\" -m --silent" % (filepath, database)) == 0:
                        correct_file = filepath
                        correct_id = to_process[id][0]
                        break

            # If one correct file was found, copy it over
            if correct_file:
                create_dir_if_not_exist(os.path.dirname(outpathfull))
                shutil.copyfile(correct_file, outpathfull)
                if report_file:
                    r_row[correct_id+1] = "O"
                    r_row[-3] = "OK"
            # Else, we need to do the majority vote merge
            else:
                # Do the majority vote merge
                errcode, errmsg = majority_vote_byte_scan(relfilepath, fileslist, outpath)

        # After-merge/move check using rfigc database, if provided
        if database:
            if rfigc.main("-i \"%s\" -d \"%s\" -m --silent" % (outpathfull, database)) == 1:
                errcode = 1
                r_row[-3] = "KO"
                if not errmsg: errmsg = ''
                errmsg += " File could not be totally repaired according to rfigc database."
            else:
                if report_file:
                    r_row[-3] = "OK"
                    if errmsg: errmsg += " But merged file is correct according to rfigc database."

        # Display errors if any
        if errcode:
            if report_file:
                r_row[-2] = "KO"
                r_row[-1] = errmsg
            ptee.write(errmsg)
            retcode = 1
        else:
            if report_file: r_row[-2] = "OK"

        # Save current report's row
        if report_file:
            r_writer.writerow(r_row)

        # -- Update files lists alignment (ie, retrieve new files but while trying to keep the alignment)
        for elt in to_process:  # for files of the first group (the ones we processed)
            i = elt[0]
            # Walk their respective folders and load up the next file
            try:
                if not recgen_exhausted.get(i, False):
                    curfiles[i] = relpath_posix(next(recgen[i]), inputpaths[i])[1]
            # If there's no file left in this folder, mark this input folder as exhausted and continue with the others
            except StopIteration:
                curfiles[i] = None
                recgen_exhausted[i] = True
                recgen_exhausted_count += 1
        if tqdm_bar: tqdm_bar.update()
    if tqdm_bar: tqdm_bar.close()

    # Closing report file
    if report_file:
        # Write list of directories and legend
        rfile.write("\n=> Input directories:")
        for id, ipath in enumerate(inputpaths):
            rfile.write("\n\t- dir%i = %s" % ((id+1), ipath))
        rfile.write("\n=> Output directory: %s" % outpath)
        rfile.write("\n=> Legend: X=existing/selected for majority vote, O=only used this file, - = not existing, OK = check correct, KO = check incorrect (file was not recovered)\n")
        # Close the report file handle
        rfile.close()

    return retcode


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

#@conditional_decorator(check_gui_arg(), gooey.Gooey) # alternative to AutoGooey which also correctly works
@AutoGooey
def main(argv=None, command=None):
    if argv is None: # if argv is empty, fetch from the commandline
        argv = sys.argv[1:]
    elif isinstance(argv, _str): # else if argv is supplied but it's a simple string, we need to parse it to a list of arguments before handing to argparse or any other argument parser
        argv = shlex.split(argv) # Parse string just like argv using shlex

    #==== COMMANDLINE PARSER ====

    #== Commandline description
    desc = '''Replication Repair
Description: Given a set of directories (or files), try to repair your files by scanning each byte, cast a majority vote among all copies, and then output the winning byte. This process is usually called triple-modular redundancy (but here it should be called n-modular redundancy since you can use as many copies as you have).
It is recommended for long term storage to store several copies of your files on different storage mediums. Everything's fine until all your copies are partially corrupted. In this case, this script can help you, by taking advantage of your multiple copies, without requiring a pregenerated ecc file. Just specify the path to every copies, and the script will try to recover them.
Replication can repair exactly r-2 errors using majority vote (you need at least 2 blocks for majority vote to work), where r is the number of replications: if r=3, you get a redundancy rate of 1/3, if r=4, rate is 2/4, etc.
This script can also take advantage of a database generated by rfigc.py to make sure that the recovered files are correct, or to select files that are already correct.

Note: in case the end result is not what you expected, you can try a different order of input directories: in case of ambiguity, the first input folder has precedence over subsequent folders.
Note2: in case some files with the same names are of different length, the merging will continue until the longest file is exhausted.
Note3: last modification date is not (yet) accounted for.
    '''
    ep = '''Use --gui as the first argument to use with a GUI (via Gooey).
'''

    #== Commandline arguments
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
        widget_multidir = {"widget": "MultiDirChooser"}
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
        widget_multidir = {}

    # Required arguments
    main_parser.add_argument('-i', '--input', metavar='"/path/to/copy1/" "/path/to/copy2/" "etc."', type=is_dir_or_file, nargs='+', required=True,
                        help='Specify the paths to every copies you have (minimum 3 copies, else it won\'t work!). Can be folders or files (if you want to repair only one file). Order matters: in case of ambiguity, the first folder where the file exists will be chosen.', **widget_multidir)
    main_parser.add_argument('-o', '--output', metavar='/ouput/folder/', nargs=1, required=True,
                        help='Where the recovered files will be stored.', **widget_dir)

    # Optional general arguments
    main_parser.add_argument('-d', '--database', metavar='database.csv', type=is_file, required=False,
                        help='Path to a previously generated rfigc.py database. If provided, this will be used to check that the repaired files are correct (and also to find already correct files in copies).', **widget_file)
    main_parser.add_argument('-r', '--report', metavar='/some/folder/report.csv', type=str, required=False,
                        help='Save all results of the repair process in a report file, with detailed descriptions of ambiguous repairs (ie, when majority vote came to a draw).', **widget_filesave)
    main_parser.add_argument('-l', '--log', metavar='/some/folder/filename.log', type=str, nargs=1, required=False,
                        help='Path to the log file. (Output will be piped to both the stdout and the log file)', **widget_filesave)
    main_parser.add_argument('-f', '--force', action='store_true', required=False, default=False,
                        help='Force overwriting the output folder even if it already exists.')
    main_parser.add_argument('-v', '--verbose', action='store_true', required=False, default=False,
                        help='Verbose mode (show more output).')
    main_parser.add_argument('--silent', action='store_true', required=False, default=False,
                        help='No console output (but if --log specified, the log will still be saved in the specified file).')

    #== Parsing the arguments
    args = main_parser.parse_args(argv) # Storing all arguments to args

    #-- Set variables from arguments
    inputpaths = [fullpath(x) for x in args.input] # path to the files to repair (ie, paths to all the different copies the user has)
    outputpath = fullpath(args.output[0])
    force = args.force
    verbose = args.verbose
    silent = args.silent

    if len(inputpaths) < 3:
        raise Exception('Need at least 3 copies to do a replication repair/majority vote!')

    #if os.path.isfile(inputpath): # if inputpath is a single file (instead of a folder), then define the rootfolderpath as the parent directory (for correct relative path generation, else it will also truncate the filename!)
        #rootfolderpath = os.path.dirname(inputpath)

    report_file = None
    if args.report: report_file = os.path.basename(fullpath(args.report))
    database = None
    if args.database: database = args.database

    # -- Checking arguments
    if os.path.exists(outputpath) and not force:
        raise NameError('Specified output path %s already exists! Use --force if you want to overwrite.' % outputpath)

    if database and not os.path.isfile(database):
        raise NameError('Specified rfigc database file %s does not exist!' % database)

    # -- Configure the log file if enabled (ptee.write() will write to both stdout/console and to the log file)
    if args.log:
        ptee = Tee(args.log[0], 'a', nostdout=silent)
        #sys.stdout = Tee(args.log[0], 'a')
        sys.stderr = Tee(args.log[0], 'a', nostdout=silent)
    else:
        ptee = Tee(nostdout=silent)


    # == PROCESSING BRANCHING == #

    # == Precomputation of ecc file size
    # Precomputing is important so that the user can know what size to expect before starting (and how much time it will take...).
    filescount = 0
    #sizetotal = 0 # TODO: unused
    sizeheaders = 0
    visitedfiles = {}
    ptee.write("Precomputing list of files and predicted statistics...")
    prebar = tqdm.tqdm(file=ptee, disable=silent)
    for inputpath in inputpaths:
        for (dirpath, filename) in recwalk(inputpath):
            # Get full absolute filepath
            filepath = os.path.join(dirpath, filename)
            relfilepath = path2unix(os.path.relpath(filepath, inputpath)) # File relative path from the root (we truncate the rootfolderpath so that we can easily check the files later even if the absolute path is different)

            # Only increase the files count if we didn't see this file before
            if not visitedfiles.get(relfilepath, None):
                # Counting the total number of files we will process (so that we can show a progress bar with ETA)
                filescount = filescount + 1
                # Add the file to the list of already visited files
                visitedfiles[relfilepath] = True
                # Get the current file's size # TODO: unused
                #size = os.stat(filepath).st_size
                # Compute total size of all files # TODO: unused
                #sizetotal = sizetotal + size
            prebar.update()
    prebar.close()
    ptee.write("Precomputing done.")

    # == Majority vote repair
    # For each folder, align the files lists and then majority vote over each byte to repair
    ptee.write("====================================")
    ptee.write("Replication repair, started on %s" % datetime.datetime.now().isoformat())
    ptee.write("====================================")

    # Prepare progress bar if necessary
    if silent:
        tqdm_bar = None
    else:
        tqdm_bar = tqdm.tqdm(total=filescount, file=ptee, leave=True, unit="files")
    # Call the main function to synchronize files using majority vote
    errcode = synchronize_files(inputpaths, outputpath, database=database, tqdm_bar=tqdm_bar, report_file=report_file, ptee=ptee, verbose=verbose)
    #ptee.write("All done! Stats:\n- Total files processed: %i\n- Total files corrupted: %i\n- Total files repaired completely: %i\n- Total files repaired partially: %i\n- Total files corrupted but not repaired at all: %i\n- Total files skipped: %i" % (files_count, files_corrupted, files_repaired_completely, files_repaired_partially, files_corrupted - (files_repaired_partially + files_repaired_completely), files_skipped) )
    if tqdm_bar: tqdm_bar.close()
    ptee.write("All done!")
    if report_file: ptee.write("Saved replication repair results in report file: %s" % report_file)
    ptee.close()
    return errcode

# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
