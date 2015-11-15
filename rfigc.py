#!/usr/bin/env python
#
# Recursive/Relative Files Integrity Generator and Checker
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
#  Recursive/Relative Files Integrity Generator and Checker
#                by Stephen Larroque
#                       License: MIT
#              Creation date: 2015-02-27
#=================================
#
# TODO:
# - Copy corrupted/error files to another location (while preserving folders tree) so that user can try to repair them.
# - Add interface to a repair software/library? (at least for images and maybe videos and archives zip/tar.gz)
# - Check similar files: make list of hashes and compare each new file to the hashes database to see if a file that is not in our db ressembles a file in our db, maybe indicating that the file was moved (problem: the check currently is based on database: we walk through database entries, so we cannot detect new files. We would need to do another branch for this special check, or at least do it after the normal check.)
# - multidisks option: allow to continue checking files on removable drives so that you can spread your archives on several disks and check them all with only one database file.
# - moviepy try to open video file that is tampered?
# - add replace md5 and sha1 by farmhash and murmurhash? (non-cryptographic hashes, but it would require importing third-party libraries! no pure python anymore!)
#
# NOTE: this software is similar in purpose to the (more advanced) MD5deep / HashDeep for hash set auditing: http://md5deep.sourceforge.net/
#

from _infos import __version__

# Include the lib folder in the python import path (so that packaged modules can be easily called, such as gooey which always call its submodules via gooey parent module)
import sys, os
thispathname = os.path.dirname(sys.argv[0])
sys.path.append(os.path.join(thispathname, 'lib'))

# Import necessary libraries
from lib.aux_funcs import is_dir, is_dir_or_file, fullpath, recwalk, path2unix
import lib.argparse as argparse
import os, datetime, time, sys
import hashlib
import csv
import lib.tqdm as tqdm
import shlex # for string parsing as argv argument to main(), unnecessary otherwise
from lib.tee import Tee # Redirect print output to the terminal as well as in a log file
#import pprint # Unnecessary, used only for debugging purposes
try:
    import PIL.Image # It's advised that you use PILLOW instead of PIL, to get a wider array of supported filetypes.
    structure_check_import = True
except ImportError:
    structure_check_import = False

#***********************************
#                   FUNCTIONS
#***********************************

# Prepare the image filter once and for all in a global variable
if structure_check_import:
    PIL.Image.init() # Init PIL to access its supported formats
    img_filter = ['.'+x.lower() for x in PIL.Image.OPEN.keys()] # Load the supported formats
    img_filter = img_filter + ['.jpg', '.jpe'] # Add some extensions variations
def check_structure(filepath):
    """Returns False if the file is okay, None if file format is unsupported by PIL/PILLOW, or returns an error string if the file is corrupt."""
    #http://stackoverflow.com/questions/1401527/how-do-i-programmatically-check-whether-an-image-png-jpeg-or-gif-is-corrupted/1401565#1401565
    
    # Check structure only for images (not supported for other types currently)
    if filepath.lower().endswith(tuple(img_filter)):
        try:
            #try:
            im = PIL.Image.open(filepath)
            #except IOError: # File format not supported by PIL, we skip the check_structure - ARG this is also raised if a supported image file is corrupted...
                #print("File: %s: DETECTNOPE" % filepath)
                #return None
            im.verify()
        # If an error occurred, the structure is corrupted
        except Exception as e:
            return str(e)
        # Else no exception, there's no corruption
        return False
    # Else the format does not currently support structure checking, we just return None to signal we didin't check
    else:
        return None

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
    elif isinstance(argv, basestring): # else if argv is supplied but it's a simple string, we need to parse it to a list of arguments before handing to argparse or any other argument parser
        argv = shlex.split(argv) # Parse string just like argv using shlex

    #==== COMMANDLINE PARSER ====

    #== Commandline description
    desc = '''Recursive/Relative Files Integrity Generator and Checker
Description: Recursively generate or check the integrity of files by MD5 and SHA1 hashes, size, modification date or by data structure integrity (only for images).

This script is originally meant to be used for data archival, by allowing an easy way to check for silent file corruption. Thus, this script uses relative paths so that you can easily compute and check the same redundant data copied on different mediums (hard drives, optical discs, etc.). This script is not meant for system files corruption notification, but is more meant to be used from times-to-times to check up on your data archives integrity.
    '''
    ep = '''Example usage:
- To generate the database (only needed once):
python rfigc.py -i "folderimages" -d "dbhash.csv" -g
- To check:
python rfigc.py -i "folderimages" -d "dbhash.csv" -l log.txt -s
- To update your database by appending new files:
python rfigc.py -i "folderimages" -d "dbhash.csv" -u -a 
- To update your database by appending new files AND removing inexistent files:
python rfigc.py -i "folderimages" -d "dbhash.csv" -u -a -r
- To use with a gui:
python rfigc.py --gui

Note that by default, the script is by default in check mode, to avoid wrong manipulations. It will also alert you if you generate over an already existing database file.
Note2: you can use PyPy to speed the generation, but you should avoid using PyPy when in checking mode (from our tests, it will slow things down a lot).
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
    main_parser.add_argument('-d', '--database', metavar='/some/folder/databasefile.csv', type=str, nargs=1, required=True, #type=argparse.FileType('rt')
                        help='Path to the csv file containing the hash informations.', **widget_filesave)

    # Optional general arguments
    main_parser.add_argument('-l', '--log', metavar='/some/folder/filename.log', type=str, nargs=1, required=False,
                        help='Path to the log file. (Output will be piped to both the stdout and the log file)', **widget_filesave)
    main_parser.add_argument('--skip_hash', action='store_true', required=False, default=False,
                        help='Skip hash computation/checking (checks only the other metadata, this is a lot quicker).')
    main_parser.add_argument('-v', '--verbose', action='store_true', required=False, default=False,
                        help='Verbose mode (show more output).')
    main_parser.add_argument('--silent', action='store_true', required=False, default=False,
                        help='No console output (but if --log specified, the log will still be saved in the specified file).')

    # Checking mode arguments
    main_parser.add_argument('-s', '--structure_check', action='store_true', required=False, default=False,
                        help='Check images structures for corruption?')
    main_parser.add_argument('-e', '--errors_file', metavar='/some/folder/errorsfile.csv', type=str, nargs=1, required=False, #type=argparse.FileType('rt')
                        help='Path to the error file, where errors at checking will be stored in CSV for further processing by other softwares (such as file repair softwares).', **widget_filesave)
    main_parser.add_argument('-m', '--disable_modification_date_checking', action='store_true', required=False, default=False,
                        help='Disable modification date checking.')
    main_parser.add_argument('--skip_missing', action='store_true', required=False, default=False,
                        help='Skip missing files when checking (useful if you split your files into several mediums, for example on optical discs with limited capacity).')

    # Generate mode arguments
    main_parser.add_argument('-g', '--generate', action='store_true', required=False, default=False,
                        help='Generate the database? (omit this parameter to check instead of generating).')
    main_parser.add_argument('-f', '--force', action='store_true', required=False, default=False,
                        help='Force overwriting the database file even if it already exists (if --generate).')

    # Update mode arguments
    main_parser.add_argument('-u', '--update', action='store_true', required=False, default=False,
                        help='Update database (you must also specify --append or --remove).')
    main_parser.add_argument('-a', '--append', action='store_true', required=False, default=False,
                        help='Append new files (if --update).')
    main_parser.add_argument('-r', '--remove', action='store_true', required=False, default=False,
                        help='Remove missing files (if --update).')

    # Recover from file scraping
    main_parser.add_argument('--filescraping_recovery', action='store_true', required=False, default=False,
                        help='Given a folder of unorganized files, compare to the database and restore the filename and directory structure into the output folder.')
    main_parser.add_argument('-o', '--output', metavar='/path/to/root/folder', type=is_dir, nargs=1, required=False,
                        help='Path to the output folder where to output (copy) the files reorganized after --recover_from_filescraping.', **widget_dir)

    #== Parsing the arguments
    args = main_parser.parse_args(argv) # Storing all arguments to args

    #-- Set variables from arguments
    inputpath = fullpath(args.input[0]) # path to the files to protect (either a folder or a single file)
    rootfolderpath = inputpath # path to the root folder (to compute relative paths)
    #database = os.path.basename(fullpath(args.database[0])) # Take only the filename.
    database = fullpath(args.database[0])
    generate = args.generate
    structure_check = args.structure_check
    force = args.force
    disable_modification_date_checking = args.disable_modification_date_checking
    skip_missing = args.skip_missing
    skip_hash = args.skip_hash
    update = args.update
    append = args.append
    remove = args.remove
    outputpath = None
    if args.output: outputpath = fullpath(args.output[0])
    filescraping = args.filescraping_recovery
    verbose = args.verbose
    silent = args.silent

    if os.path.isfile(inputpath): # if inputpath is a single file (instead of a folder), then define the rootfolderpath as the parent directory (for correct relative path generation, else it will also truncate the filename!)
        rootfolderpath = os.path.dirname(inputpath)

    errors_file = None
    if args.errors_file: errors_file = fullpath(args.errors_file[0])

    # -- Checking arguments
    if structure_check and not structure_check_import:
        raise ImportError('PIL (Python Imaging Library) could not be imported. PIL is needed to do structure check, please install PIL (or you can disable structure check to continue).');

    if update and (not append and not remove):
        raise ValueError('--update specified but not --append nor --remove. You must specify at least one of these modes when using --update!')

    if filescraping and not outputpath:
        raise ValueError('Output path needed when --recover_from_filescraping.')

    # -- Configure the log file if enabled (ptee.write() will write to both stdout/console and to the log file)
    if args.log:
        ptee = Tee(args.log[0], 'a', nostdout=silent)
        #sys.stdout = Tee(args.log[0], 'a')
        sys.stderr = Tee(args.log[0], 'a', nostdout=silent)
    else:
        ptee = Tee(nostdout=silent)


    # == PROCESSING BRANCHING == #
    retval = 0 # Returned value: 0 OK, 1 KO (files in error), -1 Error

    # -- Update the database file by removing missing files
    if update and remove:
        if not os.path.isfile(database):
            raise NameError('Specified database file does not exist, can\'t update!')

        ptee.write("====================================")
        ptee.write("RIFGC Database Update Removal of missing files, started on %s" % datetime.datetime.now().isoformat())
        ptee.write("====================================")

        # Precompute the total number of lines to process (this should be fairly quick)
        filestodocount = 0
        with open(database, 'rb') as dbf:
            for row in csv.DictReader(dbf, lineterminator='\n', delimiter='|', quotechar='"'):
                filestodocount = filestodocount + 1

            # Preparing CSV writer for the temporary file that will have the lines removed
            with open(database+'.rem', 'wb') as dbfilerem:
                csv_writer = csv.writer(dbfilerem, lineterminator='\n', delimiter='|', quotechar='"')

                # Printing CSV headers
                csv_headers = ['path', 'md5', 'sha1', 'last_modification_timestamp', 'last_modification_date', 'size', 'ext']
                csv_writer.writerow(csv_headers)

                dbf.seek(0)
                dbfile = csv.DictReader(dbf, lineterminator='\n', delimiter='|', quotechar='"') # we need to reopen the file to put the reading cursor (the generator position) back to the beginning
                delcount = 0
                filescount = 0
                for row in tqdm.tqdm(dbfile, file=ptee, total=filestodocount, leave=True):
                    filescount = filescount + 1
                    filepath = os.path.join(rootfolderpath, row['path']) # Build the absolute file path

                    if verbose: ptee.write("\n- Processing file %s" % row['path'])
                    errors = []
                    if not os.path.isfile(filepath):
                        delcount = delcount + 1
                        ptee.write("\n- File %s is missing, removed from database." % row['path'])
                    else:
                        csv_writer.writerow( [ path2unix(row['path']), row['md5'], row['sha1'], row['last_modification_timestamp'], row['last_modification_date'], row['size'], row['ext'] ] )

        # REMOVE UPDATE DONE, we remove the old database file and replace it with the new
        os.remove(database) # delete old database
        os.rename(database+'.rem', database) # rename new database to match old name
        # Show some stats
        ptee.write("----------------------------------------------------")
        ptee.write("All files processed: Total: %i - Removed/Missing: %i.\n\n" % (filescount, delcount))

    # -- Generate the database file or update/append (both will walk through the filesystem to get new files, contrary to other branchs which walk through the database csv)
    if generate or (update and append):
        if not force and os.path.isfile(database) and not update:
            raise NameError('Database file already exists. Please choose another name to generate your database file.')

        if generate:
            dbmode = 'wb'
        elif (update and append):
            dbmode = 'ab'
        with open(database, dbmode) as dbfile: # Must open in write + binary, because on Windows it will do weird things otherwise (at least with Python 2.7)
            ptee.write("====================================")
            if generate:
                ptee.write("RIFGC Database Generation started on %s" % datetime.datetime.now().isoformat())
            elif update and append:
                ptee.write("RIFGC Database Update Append new files, started on %s" % datetime.datetime.now().isoformat())
            ptee.write("====================================")

            # Preparing CSV writer
            csv_writer = csv.writer(dbfile, lineterminator='\n', delimiter='|', quotechar='"')

            if generate:
                # Printing CSV headers
                csv_headers = ['path', 'md5', 'sha1', 'last_modification_timestamp', 'last_modification_date', 'size', 'ext']
                csv_writer.writerow(csv_headers)

            if (update and append):
                # Extract all paths already stored in database to avoid readding them
                db_paths = {}
                with open(database, 'rb') as dbf:
                    for row in csv.DictReader(dbf, lineterminator='\n', delimiter='|', quotechar='"'):
                        db_paths[row['path']] = True

            # Counting the total number of files that we will have to process
            ptee.write("Counting total number of files to process, please wait...")
            filestodocount = 0
            for _ in tqdm.tqdm(recwalk(inputpath), file=ptee):
                filestodocount = filestodocount + 1
            ptee.write("Counting done.")

            # Recursively traversing the root directory and save the metadata in the db for each file
            ptee.write("Processing files to compute metadata to store in database, please wait...")
            filescount = 0
            addcount = 0
            for (dirpath, filename) in tqdm.tqdm(recwalk(inputpath), file=ptee, total=filestodocount, leave=True):
                    filescount = filescount + 1
                    # Get full absolute filepath
                    filepath = os.path.join(dirpath, filename)
                    # Get database relative path (from scanning root folder)
                    relfilepath = path2unix(os.path.relpath(filepath, rootfolderpath)) # File relative path from the root (so that we can easily check the files later even if the absolute path is different)
                    if verbose: ptee.write("\n- Processing file %s" % relfilepath)

                    # If update + append mode, then if the file is already in the database we skip it (we continue computing metadata only for new files)
                    if update and append and relfilepath in db_paths:
                        if verbose: ptee.write("... skipped")
                        continue
                    else:
                        addcount = addcount + 1

                    # Compute the hashes (leave it outside the with command because generate_hashes() open the file by itself, so that both hashes can be computed in a single sweep of the file at the same time)
                    if not skip_hash:
                        md5hash, sha1hash = generate_hashes(filepath)
                    else:
                        md5hash = sha1hash = 0
                    # Compute other metadata
                    with open(filepath) as thisfile:
                        # Check file structure if option is enabled
                        if structure_check:
                            struct_result = check_structure(filepath)
                            # Print/Log an error only if there's one (else we won't say anything)
                            if struct_result:
                                ptee.write("\n- Structure error with file "+filepath+": "+struct_result)
                        ext = os.path.splitext(filepath)[1] # File's extension
                        statinfos = os.stat(filepath) # Various OS filesystem infos about the file
                        size = statinfos.st_size # File size
                        lastmodif = statinfos.st_mtime # File last modified date (as a timestamp)
                        lastmodif_readable = datetime.datetime.fromtimestamp(lastmodif).strftime("%Y-%m-%d %H:%M:%S") # File last modified date as a human readable date (ISO universal time)

                        csv_row = [path2unix(relfilepath), md5hash, sha1hash, lastmodif, lastmodif_readable, size, ext] # Prepare the CSV row
                        csv_writer.writerow(csv_row) # Save to the file
        ptee.write("----------------------------------------------------")
        ptee.write("All files processed: Total: %i - Added: %i.\n\n" % (filescount, addcount))

    # -- Filescraping recovery mode
    # We will compare all files from the input path and reorganize the ones that are recognized into the output path
    elif filescraping:
        import shutil
        ptee.write("====================================")
        ptee.write("RIFGC File Scraping Recovery started on %s" % datetime.datetime.now().isoformat())
        ptee.write("====================================")

        ptee.write("Loading the database into memory, please wait...")
        md5list = {}
        sha1list = {}
        dbrows = {} # TODO: instead of memorizing everything in memory, store just the reading cursor position at the beginning of the line with the size and then just read when necessary from the db file directly
        id = 0
        with open(database, 'rb') as db:
            for row in csv.DictReader(db, lineterminator='\n', delimiter='|', quotechar='"'):
                id += 1
                if (len(row['md5']) > 0 and len(row['sha1']) > 0):
                    md5list[row['md5']] = id
                    sha1list[row['sha1']] = id
                    dbrows[id] = row
        ptee.write("Loading done.")

        if len(dbrows) == 0:
            ptee.write("Nothing to do, there's no md5 nor sha1 hashes in the database file!")
            return(1) # return with an error

        # Counting the total number of files that we will have to process
        ptee.write("Counting total number of files to process, please wait...")
        filestodocount = 0
        for _ in tqdm.tqdm(recwalk(inputpath), file=ptee):
            filestodocount = filestodocount + 1
        ptee.write("Counting done.")
        
        # Recursively traversing the root directory and save the metadata in the db for each file
        ptee.write("Processing file scraping recovery, walking through all files from input folder...")
        filescount = 0
        copiedcount = 0
        for (dirpath, filename) in tqdm.tqdm(recwalk(inputpath), file=ptee, total=filestodocount, leave=True):
                filescount = filescount + 1
                # Get full absolute filepath
                filepath = os.path.join(dirpath,filename)
                # Get database relative path (from scanning root folder)
                relfilepath = path2unix(os.path.relpath(filepath, rootfolderpath)) # File relative path from the root (we truncate the rootfolderpath so that we can easily check the files later even if the absolute path is different)
                if verbose: ptee.write("\n- Processing file %s" % relfilepath)

                # Generate the hashes from the currently inspected file
                md5hash, sha1hash = generate_hashes(filepath)
                # If it match with a file in the database, we will copy it over with the correct name, directory structure, file extension and last modification date
                if md5hash in md5list and sha1hash in sha1list and md5list[md5hash] == sha1list[sha1hash]:
                    # Load the db infos for this file
                    row = dbrows[md5list[md5hash]]
                    ptee.write("- Found: %s --> %s.\n" % (filepath, row['path']))
                    # Generate full absolute filepath of the output file
                    outfilepath = os.path.join(outputpath, row['path'])
                    # Recursively create the directory tree structure
                    outfiledir = os.path.dirname(outfilepath)
                    if not os.path.isdir(outfiledir): os.makedirs(outfiledir) # if the target directory does not exist, create it (and create recursively all parent directories too)
                    # Copy over and set attributes
                    shutil.copy2(filepath, outfilepath)
                    filestats = os.stat(filepath)
                    os.utime(outfilepath, (filestats.st_atime, float(row['last_modification_timestamp'])))
                    # Counter...
                    copiedcount += 1
        ptee.write("----------------------------------------------------")
        ptee.write("All files processed: Total: %i - Recovered: %i.\n\n" % (filescount, copiedcount))

    # -- Check mode: check the files using a database file
    elif not update and not generate and not filescraping:
        ptee.write("====================================")
        ptee.write("RIFGC Check started on %s" % datetime.datetime.now().isoformat())
        ptee.write("====================================")

        # Open errors file if supplied (where we will store every errors in a formatted csv so that it can later be easily processed by other softwares, such as repair softwares)
        if errors_file is not None:
            efile = open(errors_file, 'wb')
            e_writer = csv.writer(efile, delimiter='|', lineterminator='\n', quotechar='"')

        # Precompute the total number of lines to process (this should be fairly quick)
        filestodocount = 0
        with open(database, 'rb') as dbf:
            for row in csv.DictReader(dbf, lineterminator='\n', delimiter='|', quotechar='"'):
                filestodocount = filestodocount + 1

            # Processing the files using the database list
            ptee.write("Checking for files corruption based on database %s on input path %s, please wait..." % (database, inputpath))
            dbf.seek(0)
            dbfile = csv.DictReader(dbf, lineterminator='\n', delimiter='|', quotechar='"') # we need to reopen the file to put the reading cursor (the generator position) back to the beginning
            errorscount = 0
            filescount = 0
            for row in tqdm.tqdm(dbfile, file=ptee, total=filestodocount, leave=True):
                filescount = filescount + 1
                filepath = os.path.join(rootfolderpath, row['path'])

                if verbose: ptee.write("\n- Processing file %s" % row['path'])
                errors = []
                if not os.path.isfile(filepath):
                    if not skip_missing: errors.append('file is missing')
                # First generate the current file's metadata given the filepath from the CSV, and then we will check the differences from database
                else:
                    try: # Try to be resilient to various file access errors
                        # Generate hash
                        if not skip_hash:
                            md5hash, sha1hash = generate_hashes(filepath)
                        else:
                            md5hash = sha1hash = 0
                        # Check structure integrity if enabled
                        if structure_check:
                            struct_result = check_structure(filepath)
                            if struct_result:
                                errors.append("structure error (%s)" % struct_result)
                        # Compute other metadata
                        with open(filepath) as thisfile:
                            ext = os.path.splitext(filepath)[1]
                            statinfos = os.stat(filepath)
                            size = statinfos.st_size
                            lastmodif = statinfos.st_mtime
                            lastmodif_readable = datetime.datetime.fromtimestamp(lastmodif).strftime("%Y-%m-%d %H:%M:%S")

                            # CHECK THE DIFFERENCES
                            if not skip_hash and md5hash != row['md5'] and sha1hash != row['sha1']:
                                errors.append('both md5 and sha1 hash failed')
                            elif not skip_hash and ((md5hash == row['md5'] and sha1hash != row['sha1']) or (md5hash != row['md5'] and sha1hash == row['sha1'])):
                                errors.append('one of the hash failed but not the other (which may indicate that the database file is corrupted)')
                            if ext != row['ext']:
                                errors.append('extension has changed')
                            if size != int(row['size']):
                                errors.append("size has changed (before: %s - now: %s)" % (row['size'], size))
                            if not disable_modification_date_checking and (lastmodif != float(row['last_modification_timestamp']) and round(lastmodif,0) != round(float(row['last_modification_timestamp']),0)): # for usage with PyPy: last modification time is differently managed (rounded), thus we need to round here manually to compare against PyPy.
                                errors.append("modification date has changed (before: %s - now: %s)" % (row['last_modification_date'], lastmodif_readable))
                    except IOError as e: # Catch IOError as a file error
                        errors.append('file can\'t be read, IOError (inaccessible, maybe bad sector?)')
                    except Exception as e: # Any other exception when accessing the file will also be caught as a file error
                        errors.append('file can\'t be accessed: %s' % e)
                # Print/Log all errors for this file if any happened
                if errors:
                    errorscount = errorscount + 1
                    ptee.write("\n- Error for file %s: %s." % (row['path'], ', '.join(errors)))
                    if errors_file is not None: # Write error in a csv file if supplied (for easy processing later by other softwares such as file repair softwares)
                        e_writer.writerow( [row['path'], ', '.join(errors)] )
        # END OF CHECKING: show some stats
        ptee.write("----------------------------------------------------")
        ptee.write("All files checked: Total: %i - Files with errors: %i.\n\n" % (filescount, errorscount))
        retval = (errorscount > 0)

    return retval # return error code if any

# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":
    sys.exit(main())
