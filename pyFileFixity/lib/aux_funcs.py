#!/usr/bin/env python
#
# Auxiliary functions library
# Copyright (C) 2015 Larroque Stephen
#

import os
import argparse
from pathlib2 import PurePath, PureWindowsPath, PurePosixPath # opposite operation of os.path.join (split a path into parts)
import posixpath # to generate unix paths
import shutil

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

def path2unix(path, nojoin=False, fromwinpath=False):
    '''From a path given in any format, converts to posix path format
    fromwinpath=True forces the input path to be recognized as a Windows path (useful on Unix machines to unit test Windows paths)'''
    if fromwinpath:
        pathparts = list(PureWindowsPath(path).parts)
    else:
        pathparts = list(PurePath(path).parts)
    if nojoin:
        return pathparts
    else:
        return posixpath.join(*pathparts)

def get_next_entry(file, entrymarker="\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF", only_coord=True, blocksize=65535):
    '''Find or read the next ecc entry in a given ecc file.
    Call this function multiple times with the same file handle to get subsequent markers positions (this is not a generator but it works very similarly, because it will continue reading from the file's current cursor position -- this can be used advantageously if you want to read only a specific entry by seeking before supplying the file handle).
    This will read any string length between two entrymarkers.
    The reading is very tolerant, so it will always return any valid entry (but also scrambled entries if any, but the decoding will ensure everything's ok).
    `file` is a file handle, not the path to the file.'''
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

def create_dir_if_not_exist(path):  # pragma: no cover
    """Create a directory if it does not already exist, else nothing is done and no error is return"""
    if not os.path.exists(path):
        os.makedirs(path)

def remove_if_exist(path):  # pragma: no cover
    """Delete a file or a directory recursively if it exists, else no exception is raised"""
    if os.path.exists(path):
        if os.path.isdir(path):
            shutil.rmtree(path)
            return True
        elif os.path.isfile(path):
            os.remove(path)
            return True
    return False

def copy_any(src, dst, only_missing=False):  # pragma: no cover
    """Copy a file or a directory tree, deleting the destination before processing"""
    if not only_missing:
        remove_if_exist(dst)
    if os.path.exists(src):
        if os.path.isdir(src):
            if not only_missing:
                shutil.copytree(src, dst, symlinks=False, ignore=None)
            else:
                for dirpath, filepath in recwalk(src):
                    srcfile = os.path.join(dirpath, filepath)
                    relpath = os.path.relpath(srcfile, src)
                    dstfile = os.path.join(dst, relpath)
                    if not os.path.exists(dstfile):
                        create_dir_if_not_exist(os.path.dirname(dstfile))
                        shutil.copyfile(srcfile, dstfile)
                        shutil.copystat(srcfile, dstfile)
            return True
        elif os.path.isfile(src) and (not only_missing or not os.path.exists(dst)):
            shutil.copyfile(src, dst)
            shutil.copystat(src, dst)
            return True
    return False

#### MULTIFILES AUX FUNCTIONS ####
# Here are the aux functions to cluster files of similar sizes in order to generate multifiles ecc tracks in header_ecc.py and structural_variable_ecc.py
# TODO in hecc and saecc:
#  * make intra-fields filepath with multiple files paths, separated by "|" (eg: "filepath1|filepath2|filepath3"
#  * make intra-fields multiple file sizes, just like filepaths: "filesize1|filesize2|filesize3"
#  * intra-ecc should work just the same
#  * adapt stream encoding and decoding to dispatch the bytes to the corresponding files.
#  * stream encoding/decoding should be robust: when a file ecc track is either ended (file was smaller than the others) or corrupted, then fill with null bytes, the rest should work the same (at decoding, maybe can use erasures decoding to double the recovery rate, at encoding maybe try to not store the null bytes? But how? Normally, the files in a group should be in descending size order, so the first file will always have a track, but if the other files are smaller then nvm their ecc just won't be appended, thus we end up with a shorter ecc track, but we know that and we can just computationally append the missing null bytes, no harm and no risk of corruption since these bytes aren't stored! So at encoding this doubles the recovery rate towards the end of the file for the bigger file)..
# TODO in group_files_by_size: try to use sortedcontainers.SortedList() ? https://pypi.python.org/pypi/sortedcontainers

from collections import OrderedDict
from sortedcontainers import SortedList
from random import randint
from itertools import izip_longest

def grouper(n, iterable, fillvalue=None):
    "grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return izip_longest(fillvalue=fillvalue, *args)

def group_files_by_size(fileslist, multi):  # pragma: no cover
    ''' Cluster files into the specified number of groups, where each groups total size is as close as possible to each other.

    Pseudo-code (O(n^g) time complexity):
    Input: number of groups G per cluster, list of files F with respective sizes
    - Order F by descending size
    - Until F is empty:
        - Create a cluster X
        - A = Pop first item in F
        - Put A in X[0] (X[0] is thus the first group in cluster X)
        For g in 1..len(G)-1 :
            - B = Pop first item in F
            - Put B in X[g]
            - group_size := size(B)
            If group_size != size(A):
                While group_size < size(A):
                    - Find next item C in F which size(C) <= size(A) - group_size
                    - Put C in X[g]
                    - group_size := group_size + size(C)
    '''
    flord = OrderedDict(sorted(fileslist.items(), key=lambda x: x[1], reverse=True))
    if multi <= 1:
        fgrouped = {}
        i = 0
        for x in flord.keys():
            i += 1
            fgrouped[i] = [[x]]
        return fgrouped

    fgrouped = {}
    i = 0
    while flord:
        i += 1
        fgrouped[i] = []
        big_key, big_value = flord.popitem(0)
        fgrouped[i].append([big_key])
        for j in xrange(multi-1):
            cluster = []
            if not flord: break
            child_key, child_value = flord.popitem(0)
            cluster.append(child_key)
            if child_value == big_value:
                fgrouped[i].append(cluster)
                continue
            else:
                diff = big_value - child_value
                for key, value in flord.iteritems():
                    if value <= diff:
                        cluster.append(key)
                        del flord[key]
                        if value == diff:
                            break
                        else:
                            child_value += value
                            diff = big_value - child_value
                fgrouped[i].append(cluster)
    return fgrouped

def group_files_by_size_fast(fileslist, nbgroups, mode=1):  # pragma: no cover
    '''Given a files list with sizes, output a list where the files are grouped in nbgroups per cluster.

    Pseudo-code for algorithm in O(n log(g)) (thank's to insertion sort or binary search trees)
    See for more infos: http://cs.stackexchange.com/questions/44406/fast-algorithm-for-clustering-groups-of-elements-given-their-size-time/44614#44614
    For each file:
        - If to-fill list is empty or file.size > first-key(to-fill):
          * Create cluster c with file in first group g1
          * Add to-fill[file.size].append([c, g2], [c, g3], ..., [c, gn])
        - Else:
          * ksize = first-key(to-fill)
          * c, g = to-fill[ksize].popitem(0)
          * Add file to cluster c in group g
          * nsize = ksize - file.size
          * if nsize > 0:
            . to-fill[nsize].append([c, g])
            . sort to-fill if not an automatic ordering structure
        '''
    ftofill = SortedList()
    ftofill_pointer = {}
    fgrouped = [] # [] or {}
    ford = sorted(fileslist.iteritems(), key=lambda x: x[1])
    last_cid = -1
    while ford:
        fname, fsize = ford.pop()
        #print "----\n"+fname, fsize
        #if ftofill: print "beforebranch", fsize, ftofill[-1]
        #print ftofill
        if not ftofill or fsize > ftofill[-1]:
            last_cid += 1
            #print "Branch A: create cluster %i" % last_cid
            fgrouped.append([])
            #fgrouped[last_cid] = []
            fgrouped[last_cid].append([fname])
            if mode==0:
                for g in xrange(nbgroups-1, 0, -1):
                    fgrouped[last_cid].append([])
                    if not fsize in ftofill_pointer:
                        ftofill_pointer[fsize] = []
                    ftofill_pointer[fsize].append((last_cid, g))
                    ftofill.add(fsize)
            else:
                for g in xrange(1, nbgroups):
                    try:
                        fgname, fgsize = ford.pop()
                        #print "Added to group %i: %s %i" % (g, fgname, fgsize)
                    except IndexError:
                        break
                    fgrouped[last_cid].append([fgname])
                    diff_size = fsize - fgsize
                    if diff_size > 0:
                        if not diff_size in ftofill_pointer:
                            ftofill_pointer[diff_size] = []
                        ftofill_pointer[diff_size].append((last_cid, g))
                        ftofill.add(diff_size)
        else:
            #print "Branch B"
            ksize = ftofill.pop()
            c, g = ftofill_pointer[ksize].pop()
            #print "Assign to cluster %i group %i" % (c, g)
            fgrouped[c][g].append(fname)
            nsize = ksize - fsize
            if nsize > 0:
                if not nsize in ftofill_pointer:
                    ftofill_pointer[nsize] = []
                ftofill_pointer[nsize].append((c, g))
                ftofill.add(nsize)
    return fgrouped

def group_files_by_size_simple(fileslist, nbgroups):  # pragma: no cover
    """ Simple and fast files grouping strategy: just order by size, and group files n-by-n, so that files with the closest sizes are grouped together.
    In this strategy, there is only one file per subgroup, and thus there will often be remaining space left because there is no filling strategy here, but it's very fast. """
    ford = sorted(fileslist.iteritems(), key=lambda x: x[1], reverse=True)
    ford = [[x[0]] for x in ford]
    return [group for group in grouper(nbgroups, ford)]

def grouped_count_sizes(fileslist, fgrouped):  # pragma: no cover
    '''Compute the total size per group and total number of files. Useful to check that everything is OK.'''
    fsizes = {}
    total_files = 0
    allitems = None
    if isinstance(fgrouped, dict):
        allitems = fgrouped.iteritems()
    elif isinstance(fgrouped, list):
        allitems = enumerate(fgrouped)
    for fkey, cluster in allitems:
        fsizes[fkey] = []
        for subcluster in cluster:
            tot = 0
            if subcluster is not None:
                for fname in subcluster:
                    tot += fileslist[fname]
                    total_files += 1
            fsizes[fkey].append(tot)
    return fsizes, total_files

def gen_rand_fileslist(nbfiles=100, maxvalue=100):  # pragma: no cover
    fileslist = {}
    for i in xrange(nbfiles):
        fileslist["file_%i" % i] = randint(1, maxvalue)
    return fileslist

def gen_rand_fileslist2(nbfiles=100, maxvalue=100):  # pragma: no cover
    fileslist = []
    for i in xrange(nbfiles):
        fileslist.append( ("file_%i" % i, randint(1, maxvalue)) )
    return fileslist

def grouped_test(nbfiles=100, nbgroups=3):  # pragma: no cover
    fileslist = gen_rand_fileslist(nbfiles)
    fgrouped = group_files_by_size(fileslist, nbgroups)
    fsizes, total_files = grouped_count_sizes(fileslist, fgrouped)
    return [fgrouped, fsizes, total_files]

def grouped_fast_test(nbfiles=100, nbgroups=3, mode=1):  # pragma: no cover
    nbfiles = 100
    nbgroups = 3
    fileslist = gen_rand_fileslist(nbfiles)
    fgrouped = group_files_by_size_fast(fileslist, nbgroups, mode=mode)
    fsizes, total_files = grouped_count_sizes(fileslist, fgrouped)
    return [fgrouped, fsizes, total_files]

def grouped_simple_test(nbfiles=100, nbgroups=3):  # pragma: no cover
    fileslist = gen_rand_fileslist(nbfiles)
    fgrouped = group_files_by_size_simple(fileslist, nbgroups)
    fsizes, total_files = grouped_count_sizes(fileslist, fgrouped)
    return [fgrouped, fsizes, total_files]
