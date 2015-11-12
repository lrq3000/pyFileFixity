#!/usr/bin/env python
#
# Auxiliary functions library
# Copyright (C) 2015 Larroque Stephen
#

import os
import argparse
from pathlib2 import PurePath # opposite operation of os.path.join (split a path into parts)
import posixpath # to generate unix paths

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

def recwalk(inputpath):
    '''Recursively walk through a folder. This provides a mean to flatten out the files restitution (necessary to show a progress bar). This is a generator.'''
    # If it's only a single file, return this single file
    if os.path.isfile(inputpath):
        abs_path = fullpath(inputpath)
        yield os.path.dirname(abs_path), os.path.basename(abs_path)
    # Else if it's a folder, walk recursively and return every files
    else:
        for dirpath, dirs, files in os.walk(inputpath):	
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
