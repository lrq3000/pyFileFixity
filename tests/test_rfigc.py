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
    assert rfigc.main('-i "%s" -d "%s" -g -f --silent' % (filein, fileout)) == 0
    assert rfigc.main('-i "%s" -d "%s" -f --silent' % (filein, fileout)) == 0
    with open(fileout, 'rb') as outf, open(fileres, 'rb') as expectedf:
        expected = expectedf.read()
        out = outf.read()
        assert expected in out

def test_dir():
    """ Test creation and verification of database for a full directory """
    filein = path_input()
    fileout = path_output('d2.csv')
    fileres = path_results('test_rfigc_test_one_file2.csv')
    assert rfigc.main('-i "%s" -d "%s" -g -f --silent' % (filein, fileout)) == 0
    assert rfigc.main('-i "%s" -d "%s" -f --silent' % (filein, fileout)) == 0
    with open(fileout, 'rb') as outf, open(fileres, 'rb') as expectedf:
        # We can't directly compare the two files because of timestamps!
        # So we manually process the expected results and compare each line to see if it's present in the output
        out = outf.read()
        expected = expectedf.read().split('\n')
        for exp in expected:
            assert exp in out
    # TODO: add a regular expression to check that all fields are present
    #assert check_eq_files(fileout, fileres)
