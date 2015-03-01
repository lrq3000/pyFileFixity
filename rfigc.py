#!/usr/bin/env python
#
# Recursive Files Integrity Generator and Checker
# Copyright (C) 2015 Larroque Stephen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the Lesser GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the Lesser General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
#=================================
#  Recursive Files Integrity Generator and Checker
#               by Stephen Larroque
#               License: Lesser GPL v3+ (LGPLv3 or Above)
#              Creation date: 2015-02-27
#          Last modification: 2015-02-27
#                     version: 0.3
#=================================

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
    def __init__(self, name, mode):
        self.file = open(name, mode)
        self.__del__.im_func.stdout = sys.stdout
        self.stdout = self.__del__.im_func.stdout # The weakref proxy is to prevent Python, or yourself from deleting the self.files variable somehow (if it is deleted, then it will not affect the original file list). If it is not the case that this is being deleted even though there are more references to the variable, then you can remove the proxy encapsulation. http://stackoverflow.com/questions/865115/how-do-i-correctly-clean-up-a-python-object
        sys.stdout = self
    def __del__(self):
        sys.stdout = self.__del__.im_func.stdout
        self.file.close()
    def write(self, data):
        self.file.write(data+"\n")
        self.file.flush()
        self.stdout.write(data+"\n")

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
    hasher_md5 = hashlib.md5()
    hasher_sha1 = hashlib.sha1()
    with open(filepath, 'rb') as afile:
        buf = afile.read(blocksize)
        while len(buf) > 0:
            hasher_md5.update(buf)
            hasher_sha1.update(buf)
            buf = afile.read(blocksize)
    return (hasher_md5.hexdigest(), hasher_sha1.hexdigest())

def recwalk(folderpath):
    '''Recursively walk through a folder. This provides a mean to flatten out the files restitution (necessary to show a progress bar.'''
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

    #== General vars
    delimiter = '|' # for slots files
    timedelimiter = ':'
    assign = '='
    defaultwait = 5 # default wait time (in minutes) to wait when there's no slotsfile for today before checking again for a new slotsfile existence
    margindelay = 120 # seconds to wait after the planned end time of a booking to switch to the next (this allows players to take the time to end the match) - this margindelay is not applied when there's no booking, the next booking will begin right on time

    desc = '''Recursive Files Integrity Generator and Checker ---
    Description: Recursively generate or check the integrity of files, by hash, modification date or data structure integrity (only for images).
    '''
    ep = ''' '''

    #== Commandline arguments
    #-- Constructing the parser
    main_parser = argparse.ArgumentParser(add_help=True, description=desc, epilog=ep)
    # Slots management arguments
    main_parser.add_argument('-i', '--input', metavar='/path/to/root/folder', type=is_dir, nargs=1, required=True,
                        help='Path to the root folder from where the scanning will occur.')
    main_parser.add_argument('-d', '--database', metavar='/some/folder/databasefile.csv', type=str, nargs=1, required=True, #type=argparse.FileType('rt')
                        help='Path to the csv file containing the hash informations.')
    main_parser.add_argument('-g', '--generate', action='store_true', required=False, default=False,
                        help='Generate the database? (do not specify this parameter to only check).')
    main_parser.add_argument('-s', '--structure_check', action='store_true', required=False, default=False,
                        help='Check images structures for corruption?')
    main_parser.add_argument('-l', '--log', metavar='/some/folder/filename.log', type=str, nargs=1, required=False,
                        help='Path to the log file. (Output will be piped to both the stdout and the log file)')
    main_parser.add_argument('-f', '--force', action='store_true', required=False, default=False,
                        help='Force overwriting the database file even if it already exists.')
    main_parser.add_argument('-m', '--disable_modification_date_checking', action='store_true', required=False, default=False,
                        help='Disable modification date checking.')

    #== Parsing the arguments
    args = main_parser.parse_args(argv) # Storing all arguments to args

    #-- Set variables from arguments
    folderpath = fullpath(args.input[0])
    database = os.path.basename(fullpath(args.database[0])) # Take only the filename.
    generate = args.generate
    structure_check = args.structure_check
    force = args.force
    disable_modification_date_checking = args.disable_modification_date_checking

    if structure_check and not structure_check_import:
        raise ImportError('PIL (Python Imaging Library) could not be imported. PIL is needed to do structure check, please install PIL (or you can disable structure check to continue).');

    if args.log:
        ptee = Tee(args.log[0], 'a')
        #sys.stdout = Tee(args.log[0], 'a')
        sys.stderr = Tee(args.log[0], 'a')

    # -- Generate the database file
    if generate:
        if not force and os.path.isfile(database):
            raise NameError('Database file already exists. Please choose another name to generate your database file.')
        with open(database, 'wb') as dbfile: # Must open in write + binary, because on Windows it will do weird things otherwise (at least with Python 2.7)
            # Preparing CSV writer
            csv_writer = csv.writer(dbfile)
            
            # Printing CSV headers
            csv_headers = ['path', 'md5', 'sha1', 'last_modification_timestamp', 'last_modification_date', 'size', 'ext']
            csv_writer.writerow(csv_headers)

            # Counting the total number of files that we will have to process
            filestodocount = 0
            for _ in recwalk(folderpath):
                filestodocount = filestodocount + 1

            # Recursively traversing the root directory and save the metadata in the db for each file
            for (dirpath, filename) in tqdm.tqdm(recwalk(folderpath), total=filestodocount, leave=True):
                    # Get full absolute filepath
                    filepath = os.path.join(dirpath,filename)
                    # Compute the hashes (leave it outside the with command because generate_hashes() open the file by itself, so that both hashes can be computed in a single sweep of the file at the same time)
                    md5hash, sha1hash = generate_hashes(filepath)
                    # Compute other metadata
                    with open(filepath) as thisfile:
                        # Check file structure if option is enabled
                        if structure_check:
                            struct_result = check_structure(filepath)
                            # Print/Log an error only if there's one (else we won't say anything)
                            if struct_result:
                                ptee.write("Structure error with file "+filepath+": "+struct_result)
                        ext = os.path.splitext(filepath)[1] # File's extension
                        statinfos = os.stat(filepath) # Various OS filesystem infos about the file
                        size = statinfos.st_size # File size
                        lastmodif = statinfos.st_mtime # File last modified date (as a timestamp)
                        lastmodif_readable = datetime.datetime.fromtimestamp(lastmodif).strftime("%Y-%m-%d %H:%M:%S") # File last modified date as a human readable date (ISO universal time)
                        relfilepath = os.path.relpath(filepath, folderpath) # File relative path from the root (so that we can easily check the files later even if the absolute path is different)
                        csv_row = [relfilepath, md5hash, sha1hash, lastmodif, lastmodif_readable, size, ext] # Prepare the CSV row
                        csv_writer.writerow(csv_row) # Save to the file
    # -- Check the files from a database
    else:
        ptee.write("====================================")
        ptee.write("Check started on %s" % datetime.datetime.now().isoformat())
        ptee.write("====================================")
        dbfile = csv.DictReader(open(database, 'rb')); filestodocount = len(list(dbfile)) # to compute the total number of files that we will check
        dbfile = csv.DictReader(open(database, 'rb')) # we need to reopen the file to put the reading cursor (the generator position) back to the beginning
        errorscount = 0
        filescount = 0
        for row in tqdm.tqdm(dbfile, total=filestodocount, leave=True):
            filescount = filescount + 1
            filepath = os.path.join(folderpath, row['path'])

            errors = []
            if not os.path.isfile(filepath):
                errors.append('File does not exist anymore!')
            # First generate the current file's metadata given the filepath from the CSV, and then we will check the differences from database
            else:
                # Generate hash
                md5hash, sha1hash = generate_hashes(filepath)
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
                    if md5hash != row['md5']:
                        errors.append('md5 hash failed')
                    if sha1hash != row['sha1']:
                        errors.append('sha1 hash failed')
                    if ext != row['ext']:
                        errors.append('extension has changed')
                    if size != int(row['size']):
                        errors.append("size has changed (before: %s - now: %s)" % (row['size'], size))
                    if not disable_modification_date_checking and lastmodif != float(row['last_modification_timestamp']):
                        errors.append("modification date has changed (before: %s - now: %s)" % (row['last_modification_date'], lastmodif_readable))
            # Print/Log all errors for this file if any happened
            if errors:
                errorscount = errorscount + 1
                ptee.write("\nError for file %s: %s." % (row['path'], ', '.join(errors)))
        # END OF CHECKING: show some stats
        ptee.write("----------------------------------------------------")
        ptee.write("All files checked: Total: %i - Files with errors: %i." % (filescount, errorscount))



# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":
    sys.exit(main())
