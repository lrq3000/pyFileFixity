from __future__ import print_function

from nose.tools import assert_raises

import sys
import os
import shutil

from .aux_tests import get_marker, dummy_ecc_file_gen, path_sample_files, create_dir_if_not_exist

from ..lib import aux_funcs as auxf
from ..lib.argparse import ArgumentTypeError
from ..lib._compat import _StringIO

def setup_module():
    """ Initialize the tests by emptying the out directory """
    outfolder = path_sample_files('output')
    shutil.rmtree(outfolder, ignore_errors=True)
    create_dir_if_not_exist(outfolder)

def test_get_next_entry():
    """ aux: test detection of next entry """
    entries = [
            '''file1.ext\xfa\xff\xfa\xff\xfafilesize1\xfa\xff\xfa\xff\xfarelfilepath1_ecc\xfa\xff\xfa\xff\xfafilesize1_ecc\xfa\xff\xfa\xff\xfahash-ecc-entry_hash-ecc-entry_hash-ecc-entry_''',
            '''file2.ext\xfa\xff\xfa\xff\xfafilesize2\xfa\xff\xfa\xff\xfarelfilepath2_ecc\xfa\xff\xfa\xff\xfafilesize2_ecc\xfa\xff\xfa\xff\xfahash-ecc-entry_hash-ecc-entry_hash-ecc-entry_hash-ecc-entry_hash-ecc-entry_hash-ecc-entry_'''
          ]
    entries_pos = [
                    [83, 195],
                    [205, 362]
                  ]

    filecontent = dummy_ecc_file_gen(2)
    fp1 = _StringIO(filecontent)
    entry = auxf.get_next_entry(fp1, entrymarker=get_marker(1), only_coord=False, blocksize=len(get_marker(1))+1)
    assert entry == entries[0]
    entry = auxf.get_next_entry(fp1, entrymarker=get_marker(1), only_coord=False, blocksize=len(get_marker(1))+1)
    assert entry == entries[1]
    fp2 = _StringIO(filecontent)
    entry = auxf.get_next_entry(fp2, entrymarker=get_marker(1), only_coord=True, blocksize=len(get_marker(1))+1)
    assert entry == entries_pos[0]
    entry = auxf.get_next_entry(fp2, entrymarker=get_marker(1), only_coord=True, blocksize=len(get_marker(1))+1)
    assert entry == entries_pos[1]

def test_sizeof_fmt():
    """ aux: test SI formatting """
    # Test without SI prefix
    assert auxf.sizeof_fmt(1023.0, suffix='B', mod=1024.0) == "1023.0B"
    # Test all possible SI prefixes
    pows = ['', 'K','M','G','T','P','E','Z', 'Y']
    for p in range(1, len(pows)):
        assert auxf.sizeof_fmt(1024.0**p, suffix='B', mod=1024.0) == ("1.0%sB" % pows[p])

def test_path2unix():
    """ aux: test path2unix """
    assert auxf.path2unix(r'test\some\folder\file.ext', fromwinpath=True) == r'test/some/folder/file.ext'
    assert auxf.path2unix(r'test\some\folder\file.ext', nojoin=True, fromwinpath=True) == ['test', 'some', 'folder', 'file.ext']
    assert auxf.path2unix(r'test/some/folder/file.ext') == r'test/some/folder/file.ext'

def test_is_file():
    """ aux: test is_file() """
    indir = path_sample_files('input')
    infile = path_sample_files('input', 'tux.jpg')
    assert auxf.is_file(infile)
    with assert_raises(ArgumentTypeError) as cm:
        auxf.is_file(indir)

def test_is_dir():
    """ aux: test is_dir() """
    indir = path_sample_files('input')
    infile = path_sample_files('input', 'tux.jpg')
    assert auxf.is_dir(indir)
    with assert_raises(ArgumentTypeError) as cm:
        auxf.is_dir(infile)

def test_is_dir_or_file():
    """ aux: test is_dir_or_file() """
    indir = path_sample_files('input')
    infile = path_sample_files('input', 'tux.jpg')
    indir_fake = r'path/that/do/not/exist/at/all'
    infile_fake = path_sample_files('input', 'random_gibberish_file_that_do_not_exists')
    assert auxf.is_dir_or_file(indir)
    assert auxf.is_dir_or_file(infile)
    with assert_raises(ArgumentTypeError) as cm:
        auxf.is_dir_or_file(indir_fake)
    with assert_raises(ArgumentTypeError) as cm:
        auxf.is_dir_or_file(infile_fake)

def test_recwalk():
    """ aux: test recwalk() """
    def list_paths_posix(recwalk_result):
        """ helper function to convert all paths to relative posix like paths (to ease comparison) """
        return [auxf.path2unix(os.path.join(os.path.relpath(x, pardir),y)) for x,y in recwalk_result]
    indir = path_sample_files('input')
    pardir = os.path.dirname(indir)
    # Compare between sorted and non-sorted path walking (the result should be different if on Windows! but sorted path should always be the same on all platforms!)
    res1 = list_paths_posix(auxf.recwalk(indir, sorting=True))
    res2 = list_paths_posix(auxf.recwalk(indir, sorting=False))
    # Absolute test: sorted walking should always return the same result on all platforms
    assert res1 == ['files/alice.pdf', 'files/testaa.txt', 'files/tux.jpg', 'files/tuxsmall.jpg', 'files/Sub2/testsub2.txt', 'files/sub/Snark.zip', 'files/sub/testsub.txt']
    # Relative test: compare with platform's results
    if os.name == 'nt':
        assert res2 != res1
        assert res2 == ['files/alice.pdf', 'files/testaa.txt', 'files/tux.jpg', 'files/tuxsmall.jpg', 'files/sub/Snark.zip', 'files/sub/testsub.txt', 'files/Sub2/testsub2.txt']
    elif os.name == 'posix':
        assert res2 == res1

def test_fullpath():
    """ aux: test fullpath() """
    def relpath(path, pardir):
        """ helper function to always return a relative posix-like path (ease comparisons) """
        return auxf.path2unix(os.path.relpath(path, pardir))
    # Can't really objectively test fullpath() but we can relatively compare the result
    indir = path_sample_files('input')
    infile = path_sample_files('input', 'tux.jpg')
    pardir = os.path.dirname(indir)
    # Directory test
    assert relpath(auxf.fullpath(indir), pardir) == 'files'
    # File test
    res1 = relpath(auxf.fullpath(infile), pardir)
    assert res1 == 'files/tux.jpg'
    # Opened file test
    with open(infile, 'rb') as fh:
        res2 = relpath(auxf.fullpath(fh), pardir)
    assert res1 == res2
