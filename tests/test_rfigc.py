from __future__ import print_function

import itertools
import hashlib

import sys
import shutil

from .. import rfigc
from .aux_tests import check_eq_files, check_eq_dir, path_input, path_results, path_output, tamper_file

def test_one_file():
    """ rfigc: test creation and verification of rfigc database for one file """
    filein = path_input('tux.jpg')
    filedb = path_output('d.csv')
    fileres = path_results('test_rfigc_test_one_file.csv')
    assert rfigc.main('-i "%s" -d "%s" -g -f --silent' % (filein, filedb)) == 0
    assert rfigc.main('-i "%s" -d "%s" --silent' % (filein, filedb)) == 0
    with open(filedb, 'rb') as outf, open(fileres, 'rb') as expectedf:
        expected = expectedf.read()
        out = outf.read()
        assert expected in out

def test_dir():
    """ rfigc: test creation and verification of database for a full directory """
    filein = path_input()
    filedb = path_output('d2.csv')
    fileres = path_results('test_rfigc_test_dir.csv')
    assert rfigc.main('-i "%s" -d "%s" -g -f --silent' % (filein, filedb)) == 0
    assert rfigc.main('-i "%s" -d "%s" --silent' % (filein, filedb)) == 0
    with open(filedb, 'rb') as outf, open(fileres, 'rb') as expectedf:
        # We can't directly compare the two files because of timestamps!
        # So we manually process the expected results and compare each line to see if it's present in the output
        out = outf.read()
        expected = expectedf.read().split('\n')
        for exp in expected:
            assert exp in out
    # TODO: add a regular expression to check that all fields are present
    #assert check_eq_files(filedb, fileres)

def test_error_file():
    """ rfigc: test tamper file and error file generate """
    filein = path_input('tux.jpg')
    filedb = path_output('d.csv')
    fileout = path_output('tux.jpg')
    fileout2 = path_output('errors.log')
    fileres = path_results('test_rfigc_test_error_file.log')
    assert rfigc.main('-i "%s" -d "%s" -g -f --silent' % (filein, filedb)) == 0
    shutil.copyfile(filein, fileout)
    tamper_file(fileout, 3)
    assert rfigc.main('-i "%s" -d "%s" -e "%s" --silent' % (fileout, filedb, fileout2)) == 1
    check_eq_files(fileout2, fileres)
