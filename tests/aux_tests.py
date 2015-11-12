""" Auxiliary functions for unit tests """

import os

def check_eq_files(path1, path2, blocksize=65535):
    """ Return True if both files are identical, False otherwise """
    flag = True
    with open(path1, 'rb') as f1, open(path2, 'rb') as f2:
        buf1 = 1
        buf2 = 1
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
