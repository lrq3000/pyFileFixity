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
#                 Runs on Python 2.7.6
#              Creation date: 2015-02-27
#          Last modification: 2015-03-11
#                     version: 0.8.5
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

# Import necessary libraries
import argparse
import os, datetime, time, sys
import hashlib
import csv
import tqdm
#import pprint # Unnecessary, used only for debugging purposes
try:
    import PIL.Image # It's advised that you use PILLOW instead of PIL, to get a wider array of supported filetypes.
    structure_check_import = True
except ImportError:
    structure_check_import = False

#***********************************
#                   FUNCTIONS
#***********************************

# Redirect print output to the terminal as well as in a log file
class Tee(object):
    def __init__(self, name=None, mode=None):
        self.file = None
        self.__del__.im_func.stdout = sys.stdout
        self.stdout = self.__del__.im_func.stdout # The weakref proxy is to prevent Python, or yourself from deleting the self.files variable somehow (if it is deleted, then it will not affect the original file list). If it is not the case that this is being deleted even though there are more references to the variable, then you can remove the proxy encapsulation. http://stackoverflow.com/questions/865115/how-do-i-correctly-clean-up-a-python-object
        if name is not None and mode is not None:
            self.file = open(name, mode)
            sys.stdout = self
    def __del__(self):
        if hasattr(self.__del__.im_func, 'stdout'): sys.stdout = self.__del__.im_func.stdout
        if self.file: self.file.close()
    def write(self, data):
        self.stdout.write(data+"\n")
        if self.file is not None:
            self.file.write(data+"\n")
            self.file.flush()

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

# Prepare the image filter once and for all in a global variable
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

def recwalk(folderpath):
    '''Recursively walk through a folder. This provides a mean to flatten out the files restitution (necessary to show a progress bar). This is a generator.'''
    for dirpath, dirs, files in os.walk(folderpath):	
        for filename in files:
            yield (dirpath, filename)



#***********************************
#                       MAIN
#***********************************

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

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

Note that by default, the script is by default in check mode, to avoid wrong manipulations. It will also alert you if you generate over an already existing database file.
'''

    #== Commandline arguments
    #-- Constructing the parser
    main_parser = argparse.ArgumentParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter)
    # Required arguments
    main_parser.add_argument('-i', '--input', metavar='/path/to/root/folder', type=is_dir, nargs=1, required=True,
                        help='Path to the root folder from where the scanning will occur.')
    main_parser.add_argument('-d', '--database', metavar='/some/folder/databasefile.csv', type=str, nargs=1, required=True, #type=argparse.FileType('rt')
                        help='Path to the csv file containing the hash informations.')

    # Optional general arguments
    main_parser.add_argument('-l', '--log', metavar='/some/folder/filename.log', type=str, nargs=1, required=False,
                        help='Path to the log file. (Output will be piped to both the stdout and the log file)')
    main_parser.add_argument('--skip_hash', action='store_true', required=False, default=False,
                        help='Skip hash computation/checking (checks only the other metadata, this is a lot quicker).')

    # Checking mode arguments
    main_parser.add_argument('-s', '--structure_check', action='store_true', required=False, default=False,
                        help='Check images structures for corruption?')
    main_parser.add_argument('-e', '--errors_file', metavar='/some/folder/errorsfile.csv', type=str, nargs=1, required=False, #type=argparse.FileType('rt')
                        help='Path to the error file, where errors at checking will be stored in CSV for further processing by other softwares (such as file repair softwares).')
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

    #== Parsing the arguments
    args = main_parser.parse_args(argv) # Storing all arguments to args

    #-- Set variables from arguments
    folderpath = fullpath(args.input[0])
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

    errors_file = None
    if args.errors_file: errors_file = os.path.basename(fullpath(args.errors_file[0]))

    # -- Checking arguments
    if structure_check and not structure_check_import:
        raise ImportError('PIL (Python Imaging Library) could not be imported. PIL is needed to do structure check, please install PIL (or you can disable structure check to continue).');

    if update and (not append and not remove):
        raise ValueError('--update specified but not --append nor --remove. You must specify at least one of these modes when using --update!')

    # -- Configure the log file if enabled (ptee.write() will write to both stdout/console and to the log file)
    if args.log:
        ptee = Tee(args.log[0], 'a')
        #sys.stdout = Tee(args.log[0], 'a')
        sys.stderr = Tee(args.log[0], 'a')
    else:
        ptee = Tee()


    # == PROCESSING BRANCHING == #

    # -- Update the database file by removing missing files
    if update and remove:
        if not os.path.isfile(database):
            raise NameError('Specified database file does not exist, can\'t update!')

        ptee.write("====================================")
        ptee.write("RIFGC Database Update Removal of missing files, started on %s" % datetime.datetime.now().isoformat())
        ptee.write("====================================")

        # Precompute the total number of lines to process (this should be fairly quick)
        filestodocount = 0
        for row in csv.DictReader(open(database, 'rb')):
            filestodocount = filestodocount + 1

        # Preparing CSV writer for the temporary file that will have the lines removed
        with open(database+'.rem', 'wb') as dbfilerem:
            csv_writer = csv.writer(dbfilerem)

            # Printing CSV headers
            csv_headers = ['path', 'md5', 'sha1', 'last_modification_timestamp', 'last_modification_date', 'size', 'ext']
            csv_writer.writerow(csv_headers)

            dbf = open(database, 'rb')
            dbfile = csv.DictReader(dbf) # we need to reopen the file to put the reading cursor (the generator position) back to the beginning
            delcount = 0
            filescount = 0
            for row in tqdm.tqdm(dbfile, total=filestodocount, leave=True):
                filescount = filescount + 1
                filepath = os.path.join(folderpath, row['path'])

                errors = []
                if not os.path.isfile(filepath):
                    delcount = delcount + 1
                    ptee.write("\n- File %s is missing, removed from database." % row['path'])
                else:
                    csv_writer.writerow( [ row['path'], row['md5'], row['sha1'], row['last_modification_timestamp'], row['last_modification_date'], row['size'], row['ext'] ] )
        # REMOVE UPDATE DONE, we remove the old database file and replace it with the new
        dbf.close()
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
            csv_writer = csv.writer(dbfile)

            if generate:
                # Printing CSV headers
                csv_headers = ['path', 'md5', 'sha1', 'last_modification_timestamp', 'last_modification_date', 'size', 'ext']
                csv_writer.writerow(csv_headers)

            if (update and append):
                # Extract all paths already stored in database to avoid readding them
                db_paths = {}
                for row in csv.DictReader(open(database, 'rb')):
                    db_paths[row['path']] = True

            # Counting the total number of files that we will have to process
            ptee.write("Counting total number of files to process, please wait...")
            filestodocount = 0
            for _ in tqdm.tqdm(recwalk(folderpath)):
                filestodocount = filestodocount + 1
            ptee.write("Counting done.")

            # Recursively traversing the root directory and save the metadata in the db for each file
            ptee.write("Processing files to compute metadata to store in database, please wait...")
            filescount = 0
            addcount = 0
            for (dirpath, filename) in tqdm.tqdm(recwalk(folderpath), total=filestodocount, leave=True):
                    filescount = filescount + 1
                    # Get full absolute filepath
                    filepath = os.path.join(dirpath,filename)
                    # Get database relative path (from scanning root folder)
                    relfilepath = os.path.relpath(filepath, folderpath) # File relative path from the root (so that we can easily check the files later even if the absolute path is different)

                    # If update + append mode, then if the file is already in the database we skip it (we continue computing metadata only for new files)
                    if update and append and relfilepath in db_paths:
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

                        csv_row = [relfilepath, md5hash, sha1hash, lastmodif, lastmodif_readable, size, ext] # Prepare the CSV row
                        csv_writer.writerow(csv_row) # Save to the file
        ptee.write("----------------------------------------------------")
        ptee.write("All files processed: Total: %i - Added: %i.\n\n" % (filescount, addcount))

    # -- Check the files from a database
    elif not update and not generate:
        ptee.write("====================================")
        ptee.write("RIFGC Check started on %s" % datetime.datetime.now().isoformat())
        ptee.write("====================================")

        # Open errors file if supplied (where we will store every errors in a formatted csv so that it can later be easily processed by other softwares, such as repair softwares)
        if errors_file is not None:
            efile = open(errors_file, 'wb')
            e_writer = csv.writer(efile, delimiter='|')

        # Precompute the total number of lines to process (this should be fairly quick)
        filestodocount = 0
        for row in csv.DictReader(open(database, 'rb')):
            filestodocount = filestodocount + 1

        # Processing the files using the database list
        ptee.write("Checking for files corruption based on database %s, please wait..." % database)
        dbf = open(database, 'rb')
        dbfile = csv.DictReader(dbf) # we need to reopen the file to put the reading cursor (the generator position) back to the beginning
        errorscount = 0
        filescount = 0
        for row in tqdm.tqdm(dbfile, total=filestodocount, leave=True):
            filescount = filescount + 1
            filepath = os.path.join(folderpath, row['path'])

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
                        if not disable_modification_date_checking and lastmodif != float(row['last_modification_timestamp']):
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
        dbf.close()
        ptee.write("----------------------------------------------------")
        ptee.write("All files checked: Total: %i - Files with errors: %i.\n\n" % (filescount, errorscount))



# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":
    sys.exit(main())
