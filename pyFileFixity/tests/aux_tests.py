""" Auxiliary functions for unit tests """

from __future__ import with_statement

import os
import shutil

from ..lib._compat import _range, b

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
    for dirpath, dirs, files in os.walk(path1):
        files1.extend([os.path.relpath(os.path.join(dirpath, file), path1) for file in files])
    for dirpath, dirs, files in os.walk(path2):
        files2.extend([os.path.relpath(os.path.join(dirpath, file), path2) for file in files])
    # Ensure the same order for both lists (filesystem can spit the files in whatever order it wants)
    files1.sort()
    files2.sort()

    # Different files in one or both lists: we fail
    if files1 != files2:
        return False
    # Else we need to compare the files contents
    else:
        flag = True
        for i in _range(len(files1)):
            #print("files: %s %s" % (files1[i], files2[i]))  # debug
            # If the files contents are different, we fail
            if not check_eq_files(os.path.join(path1, files1[i]), os.path.join(path2, files2[i])):
                flag = False
                break
        # Else if all files contents were equal and all files are in both lists, success!
        return flag

def fullpath(relpath):
    '''Relative path to absolute'''
    if (type(relpath) is object or hasattr(relpath, 'read')): # relpath is either an object or file-like, try to get its name
        relpath = relpath.name
    return os.path.abspath(os.path.expanduser(relpath))

def path_sample_files(type=None, path=None, createdir=False):
    """ Helper function to return the full path to the test files """
    subdir = ''
    if not type:
        return ''
    elif type == 'input':
        subdir = 'files'
    elif type == 'results':
        subdir = 'results'
    elif type == 'output':
        subdir = 'out'

    dirpath = ''
    scriptpath = os.path.dirname(os.path.realpath(__file__))
    if path:
        dirpath = fullpath(os.path.join(scriptpath, subdir, path))
    else:
        dirpath = fullpath(os.path.join(scriptpath, subdir))

    if createdir:
        create_dir_if_not_exist(dirpath)

    return dirpath

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
            fh.write(b(replace_str))
    except IOError:
        return False
    finally:
        try:
            fh.close()
        except Exception:
            pass
    return True

def find_next_entry(path, marker="\xFF\xFF\xFF\xFF", initpos=0):
    '''Find the next position of a marker in a file'''
    blocksize = 65535
    start = None # start is the relative position of the marker in the current buffer
    startcursor = None # startcursor is the absolute position of the starting position of the marker in the file
    buf = 1
    infile = open(path, 'rb')
    if initpos > 0: infile.seek(initpos)
    # Enumerate all markers in a generator
    while (buf):
        # Read a long block at once, we will readjust the file cursor after
        buf = infile.read(blocksize)
        # Find the start marker
        start = buf.find(marker); # relative position of the starting marker in the currently read string
        if start >= 0: # assign startcursor only if it's empty (meaning that we did not find the starting entrymarker, else if found we are only looking for 
            startcursor = infile.tell() - len(buf) + start # absolute position of the starting marker in the file
            infile.close() # close the file before yielding result, to avoid locking the file
            yield startcursor
            infile = open(path, 'rb') # reopen the file just after yield before doing further processing
            infile.seek(startcursor+len(marker)) # place reading cursor just after the current marker to avoid repeatedly detecting the same marker
    infile.close() # don't forget to close after the loop!

def create_dir_if_not_exist(path):
    """Create a directory if it does not already exist, else nothing is done and no error is return"""
    if not os.path.exists(path):
        os.makedirs(path)

def remove_if_exist(path):
    """Delete a file or a directory recursively if it exists, else no exception is raised"""
    if os.path.exists(path):
        if os.path.isdir(path):
            shutil.rmtree(path)
            return True
        elif os.path.isfile(path):
            os.remove(path)
            return True
    return False

def get_marker(type=1):
    """Helper function to store the usual entry and fields markers in ecc files"""
    if type == 1:
        return "\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF"
    elif type == 2:
        return "\xFA\xFF\xFA\xFF\xFA"
    else:
        return ''

def dummy_ecc_file_gen(nb_files=1):
    """ Generate a dummy ecc file, following the specs (of course the ecc tracks are fake!) """
    # Create header comments
    fcontent = '''**SCRIPT_CODE_NAMEv111...000...000**\n** Comment 2\n** Yet another comment\n'''
    # Create files entries
    for i in range(1, nb_files+1):
        fcontent += get_marker(1)+("file%i.ext"%i)+get_marker(2)+("filesize%i"%i)+get_marker(2)+("relfilepath%i_ecc"%i)+get_marker(2)+("filesize%i_ecc"%i)+get_marker(2)+"hash-ecc-entry_"*(i*3)
    return fcontent
