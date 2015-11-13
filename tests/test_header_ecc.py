from __future__ import print_function

import itertools
import hashlib

import sys

import shutil

from pyFileFixity import header_ecc
from .aux_tests import check_eq_files, check_eq_dir, path_input, path_results, path_output, tamper_file, find_next_entry, create_dir_if_not_exist

def test_one_file():
    """ hecc: test creation and verification of database for one file """
    filein = path_input('tux.jpg')
    filedb = path_output('hecc.db')
    fileout = path_output('tux.jpg')
    fileres = path_results('test_header_ecc_test_one_file.db')
    # Generate an ecc file
    assert header_ecc.main('-i "%s" -d "%s" -g -f --silent' % (filein, filedb)) == 0
    # Check that generated ecc file is correct
    startpos1 = find_next_entry(filedb, "\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF").next() # need to skip the comments, so we detect where the first entrymarker begins
    startpos2 = find_next_entry(fileres, "\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF").next()
    assert check_eq_files(filedb, fileres, startpos1=startpos1, startpos2=startpos2)

def test_one_file_tamper():
    """ hecc: test file repair """
    filein = path_input('tux.jpg')
    filedb = path_output('hecc3.db')
    fileout = path_output('tux.jpg')
    fileout2 = path_output('repaired/tux.jpg')
    fileout2_dir = path_output('repaired')
    fileres = path_results('test_header_ecc_test_one_file_tamper.db')
    create_dir_if_not_exist(fileout2_dir)
    # Generate an ecc file
    assert header_ecc.main('-i "%s" -d "%s" -g -f --silent' % (filein, filedb)) == 0
    # Tamper the file
    shutil.copyfile(filein, fileout) # Copy it to avoid tampering the original
    tamper_file(fileout, 4, r'abcde')
    # Repair the file
    assert header_ecc.main('-i "%s" -d "%s" -o "%s" -c --silent' % (fileout, filedb, fileout2_dir)) == 0
    # Check that the file was completely repaired
    assert check_eq_files(filein, fileout2)

def test_dir():
    """ hecc: test creation and verification of database for a full directory """
    filein = path_input()
    filedb = path_output('hecc2.db')
    fileout = path_output()
    fileres = path_results('test_header_ecc_test_dir.db')
    # Generate an ecc file
    assert header_ecc.main('-i "%s" -d "%s" -g -f --silent' % (filein, filedb)) == 0
    # Check that generated ecc file is correct
    startpos1 = find_next_entry(filedb, "\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF").next() # need to skip the comments, so we detect where the first entrymarker begins
    startpos2 = find_next_entry(fileres, "\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF\xFE\xFF").next()
    with open(filedb, 'rb') as f1, open(fileres, 'rb') as f2:
        print("First file:\n")
        print(f1.read())
        print("Second file:\n")
        print(f2.read())
    assert check_eq_files(filedb, fileres, startpos1=startpos1, startpos2=startpos2)
