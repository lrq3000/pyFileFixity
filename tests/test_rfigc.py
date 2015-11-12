from __future__ import print_function

import itertools
import hashlib

import sys

from .. import rfigc
from .aux_tests import check_eq_files, check_eq_dir, path_input, path_results, path_output

def test_one_file():
    """ Test creation and verification of database for one file """
    filein = path_input('tux.jpg')
    fileout = path_output('d.csv')
    fileres = path_results('test_rfigc_test_one_file1.csv')
    rfigc.main('-i "%s" -d "%s" -g -f --silent' % (filein, fileout))
    rfigc.main('-i "%s" -d "%s" -f --silent' % (filein, fileout))
    assert check_eq_files(fileout, fileres)

def test_dir():
    """ Test creation and verification of database for a full directory """
    filein = path_input()
    fileout = path_output('d2.csv')
    fileres = path_results('test_rfigc_test_one_file2.csv')
    rfigc.main('-i "%s" -d "%s" -g -f --silent' % (filein, fileout))
    rfigc.main('-i "%s" -d "%s" -f --silent' % (filein, fileout))
    assert check_eq_files(fileout, fileres)
