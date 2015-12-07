from __future__ import print_function

import sys
import os
import shutil
from StringIO import StringIO

from .aux_tests import get_marker, dummy_ecc_file_gen, check_eq_files, check_eq_dir, path_sample_files, tamper_file, find_next_entry, create_dir_if_not_exist, remove_if_exist

from ..lib.tee import Tee

def setup_module():
    """ Initialize the tests by emptying the out directory """
    outfolder = path_sample_files('output')
    shutil.rmtree(outfolder, ignore_errors=True)
    create_dir_if_not_exist(outfolder)

def test_tee_file():
    """ tee: test tee file output """
    instring1 = "First line\nSecond line\n"
    instring2 = "Third line\n"
    filelog = path_sample_files('output', 'tee1.log')
    remove_if_exist(filelog)
    # Write first string
    t = Tee(filelog, 'wb', nostdout=True)
    t.write(instring1, end='')
    del t # deleting Tee should close the file
    with open(filelog, 'rb') as fl:
        assert fl.read() == instring1
    # Write second string while appending
    t2 = Tee(filelog, 'ab', nostdout=True)
    t2.write(instring2, end='')
    del t2 # deleting Tee should close the file
    with open(filelog, 'rb') as fl:
        assert fl.read() == instring1+instring2

def test_tee_stdout():
    """ tee: test tee stdout """
    instring1 = "First line\nSecond line\n"
    instring2 = "Third line\n"
    filelog = path_sample_files('output', 'tee2.log')
    remove_if_exist(filelog)
    # Access stdout and memorize the cursor position just before the test
    sysout = sys.stdout
    startpos = sysout.tell()
    # Write first string
    t = Tee()
    t.write(instring1, end='')
    del t # deleting Tee should close the file
    # Read stdout and check Tee wrote into stdout
    sysout.seek(startpos)
    assert sysout.read() == instring1
    # Write second string
    t2 = Tee()
    t2.write(instring2, end='', flush=False)
    t2.flush() # try to manually flush by the way
    del t2 # deleting Tee should close the file
    # Read stdout and check Tee appended the second string into stdout
    sysout.seek(startpos)
    assert sysout.read().startswith(instring1+instring2) # sys.stdout appends a newline return at the second writing, don't know why...
