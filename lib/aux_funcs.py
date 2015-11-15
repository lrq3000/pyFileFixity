#!/usr/bin/env python
#
# Auxiliary functions library
# Copyright (C) 2015 Larroque Stephen
#

import os
import argparse
from pathlib2 import PurePath # opposite operation of os.path.join (split a path into parts)
import posixpath # to generate unix paths

try:
    from scandir import walk # use the faster scandir module if available (Python >= 3.5), see https://github.com/benhoyt/scandir
except ImportError:
    from os import walk # else, default to os.walk()


def is_file(dirname):
    '''Checks if a path is an actual file that exists'''
    if not os.path.isfile(dirname):
        msg = "{0} is not an existing file".format(dirname)
        raise argparse.ArgumentTypeError(msg)
    else:
        return dirname

def is_dir(dirname):
    '''Checks if a path is an actual directory that exists'''
    if not os.path.isdir(dirname):
        msg = "{0} is not a directory".format(dirname)
        raise argparse.ArgumentTypeError(msg)
    else:
        return dirname

def is_dir_or_file(dirname):
    '''Checks if a path is an actual directory that exists or a file'''
    if not os.path.isdir(dirname) and not os.path.isfile(dirname):
        msg = "{0} is not a directory nor a file".format(dirname)
        raise argparse.ArgumentTypeError(msg)
    else:
        return dirname

def fullpath(relpath):
    '''Relative path to absolute'''
    if (type(relpath) is object or type(relpath) is file):
        relpath = relpath.name
    return os.path.abspath(os.path.expanduser(relpath))

def recwalk(inputpath, sorting=True):
    '''Recursively walk through a folder. This provides a mean to flatten out the files restitution (necessary to show a progress bar). This is a generator.'''
    # If it's only a single file, return this single file
    if os.path.isfile(inputpath):
        abs_path = fullpath(inputpath)
        yield os.path.dirname(abs_path), os.path.basename(abs_path)
    # Else if it's a folder, walk recursively and return every files
    else:
        for dirpath, dirs, files in walk(inputpath):	
            if sorting:
                files.sort()
                dirs.sort() # sort directories in-place for ordered recursive walking
            for filename in files:
                yield (dirpath, filename) # return directory (full path) and filename

def sizeof_fmt(num, suffix='B', mod=1024.0):
    '''Readable size format, courtesy of Sridhar Ratnakumar'''
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < mod:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= mod
    return "%.1f%s%s" % (num, 'Y', suffix)

def path2unix(path):
    '''From a path given in any format, converts to posix path format'''
    return posixpath.join(*list(PurePath(path).parts))

def get_next_entry(file, entrymarker="\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF", only_coord=True, blocksize=65535):
    '''Find or real the next ecc entry in a given ecc file.
    Call this function multiple times with the same file handle to get subsequent markers positions (this is not a generator but it works very similarly).
    This will read any string length between two entrymarkers.
    The reading is very tolerant, so it will always return any valid entry (but also scrambled entries if any, but the decoding will ensure everything's ok).'''
    found = False
    start = None # start and end vars are the relative position of the starting/ending entrymarkers in the current buffer
    end = None
    startcursor = None # startcursor and endcursor are the absolute position of the starting/ending entrymarkers inside the database file
    endcursor = None
    buf = 1
    # Sanity check: cannot screen the file's content if the window is of the same size as the pattern to match (the marker)
    if blocksize <= len(entrymarker): blocksize = len(entrymarker) + 1
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
                # Make sure we are not redetecting the same marker as the start marker
                if endcursor > startcursor:
                    file.seek(endcursor)
                    found = True
                else:
                    end = -1
                    encursor = None
        #print("Start:", start, startcursor)
        #print("End: ", end, endcursor)
        # Stop criterion to avoid infinite loop: in the case we could not find any entry in the rest of the file and we reached the EOF, we just quit now
        if len(buf) < blocksize: break
        # Did not find the full entry in one buffer? Reinit variables for next iteration, but keep in memory startcursor.
        if start > 0: start = 0 # reset the start position for the end buf find at next iteration (ie: in the arithmetic operations to compute the absolute endcursor position, the start entrymarker won't be accounted because it was discovered in a previous buffer).
        if not endcursor: file.seek(file.tell()-len(entrymarker)) # Try to fix edge case where blocksize stops the buffer exactly in the middle of the ending entrymarker. The starting marker should always be ok because it should be quite close (or generally immediately after) the previous entry, but the end depends on the end of the current entry (size of the original file), thus the buffer may miss the ending entrymarker. should offset file.seek(-len(entrymarker)) before searching for ending.

    if found: # if an entry was found, we seek to the beginning of the entry and then either read the entry from file or just return the markers positions (aka the entry bounds)
        file.seek(startcursor + len(entrymarker))
        if only_coord:
            # Return only coordinates of the start and end markers
            # Note: it is useful to just return the reading positions and not the entry itself because it can get quite huge and may overflow memory, thus we will read each ecc blocks on request using a generator.
            return [startcursor + len(entrymarker), endcursor]
        else:
            # Return the full entry's content
            return file.read(endcursor - startcursor - len(entrymarker))
    else:
        # Nothing found (or no new entry to find, we've already found them all), so we return None
        return None
