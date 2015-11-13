""" Auxiliary functions for unit tests """

from __future__ import with_statement

import os

def check_eq_files(path1, path2, blocksize=65535, startpos1=0, startpos2=0):
    """ Return True if both files are identical, False otherwise """
    flag = True
    with open(path1, 'rb') as f1, open(path2, 'rb') as f2:
        buf1 = 1
        buf2 = 1
        f1.seek(startpos1)
        f2.seek(startpos2)
        while 1:
            buf1 = f1.read(blocksize)
            buf2 = f2.read(blocksize)
            if buf1 != buf2 or (buf1 and not buf2) or (buf2 and not buf1):
                # Reached end of file or the content is different, then return false
                flag = False
                break
            elif (not buf1 and not buf2):
                # End of file for both files
                break
    return flag
    #return filecmp.cmp(path1, path2, shallow=False)  # does not work on Travis

def check_eq_dir(path1, path2):
    """ Return True if both folders have same structure totally identical files, False otherwise """
    # List files in both directories
    files1 = []
    files2 = []
    for root, dirs, files in os.walk(path1):
        files1.extend(files)
    for root, dirs, files in os.walk(path2):
        files2.extend(files)
    # Ensure the same order for both lists (filesystem can spit the files in whatever order it wants)
    files1.sort()
    files2.sort()

    # Different files in one or both lists: we fail
    if files1 != files2:
        return False
    # Else we need to compare the files contents
    else:
        flag = True
        for i in xrange(len(files1)):
            #print("files: %s %s" % (files1[i], files2[i]))  # debug
            # If the files contents are different, we fail
            if not check_eq_files(os.path.join(path1, files1[i]), os.path.join(path2, files2[i])):
                flag = False
                break
        # Else if all files contents were equal and all files are in both lists, success!
        return flag

def fullpath(relpath):
    '''Relative path to absolute'''
    if (type(relpath) is object or type(relpath) is file):
        relpath = relpath.name
    return os.path.abspath(os.path.expanduser(relpath))

def path_input(path=None):
    if path:
        return fullpath(os.path.join('tests', 'files', path))
    else:
        return fullpath(os.path.join('tests', 'files'))

def path_results(path=None):
    if path:
        return fullpath(os.path.join('tests', 'results', path))
    else:
        return fullpath(os.path.join('tests', 'results'))

def path_output(path=None):
    if path:
        return fullpath(os.path.join('tests', 'out', path))
    else:
        return fullpath(os.path.join('tests', 'out'))

def tamper_file(path, pos=0, replace_str=None):
    """Tamper a file at the given position and using the given string"""
    if not replace_str:
        replace_str = "\x00"
    try:
        with open(path, "r+b") as fh:
            if pos < 0: # if negative, we calculate the position backward from the end of file
                fsize = os.fstat(fh.fileno()).st_size
                pos = fsize + pos
            fh.seek(pos)
            fh.write(replace_str)
    except IOError:
        return False
    return True

def find_next_entry(path, marker="\xFF\xFF\xFF\xFF"):
    '''Find the next position of a marker in a file'''
    blocksize = 65535
    start = None # start is the relative position of the marker in the current buffer
    startcursor = None # startcursor is the absolute position of the starting position of the marker in the file
    buf = 1
    with open(path, 'rb') as infile:
        # Enumerate all markers in a generator
        while (buf):
            # Read a long block at once, we will readjust the file cursor after
            buf = infile.read(blocksize)
            # Find the start marker
            start = buf.find(marker); # relative position of the starting marker in the currently read string
            if start >= 0: # assign startcursor only if it's empty (meaning that we did not find the starting entrymarker, else if found we are only looking for 
                startcursor = infile.tell() - len(buf) + start # absolute position of the starting marker in the file
                yield startcursor
                infile.seek(startcursor+len(marker)) # place reading cursor just after the current marker to avoid repeatedly detecting the same marker

def create_dir_if_not_exist(path):
    if not os.path.exists(path):
        os.makedirs(path)
