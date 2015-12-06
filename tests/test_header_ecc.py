from __future__ import print_function

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import itertools
import hashlib

import shutil
from StringIO import StringIO

import header_ecc as hecc
from lib.aux_funcs import get_next_entry
from lib.eccman import compute_ecc_params, ECCMan
from .aux_tests import check_eq_files, check_eq_dir, path_sample_files, tamper_file, find_next_entry, create_dir_if_not_exist, get_marker, dummy_ecc_file_gen

def setup_module():
    """ Initialize the tests by emptying the out directory """
    outfolder = path_sample_files('output')
    shutil.rmtree(outfolder, ignore_errors=True)
    create_dir_if_not_exist(outfolder)

def test_one_file():
    """ hecc: test creation and verification of database for one file """
    filein = path_sample_files('input', 'tuxsmall.jpg')
    filedb = path_sample_files('output', 'hecc_file.db')
    fileout = path_sample_files('output', 'tuxsmall.jpg')
    fileout_rec = path_sample_files('output', 'rectemp', True) # temporary folder where repaired files will be placed (we expect none so this should be temporary, empty folder)
    fileres = path_sample_files('results', 'test_header_ecc_test_one_file.db')
    # Generate an ecc file
    assert hecc.main('-i "%s" -d "%s" --ecc_algo=3 -g -f --silent' % (filein, filedb)) == 0
    # Check that generated ecc file is correct
    startpos1 = find_next_entry(filedb, get_marker(type=1)).next() # need to skip the comments, so we detect where the first entrymarker begins
    startpos2 = find_next_entry(fileres, get_marker(type=1)).next()
    assert check_eq_files(filedb, fileres, startpos1=startpos1, startpos2=startpos2)
    # Check that the ecc file correctly validates the correct files
    assert hecc.main('-i "%s" -d "%s" -o "%s" --ecc_algo=3 -c --silent' % (filein, filedb, fileout_rec)) == 0

def test_one_file_tamper():
    """ hecc: test file repair """
    filein = path_sample_files('input', 'tuxsmall.jpg')
    filedb = path_sample_files('output', 'hecc_tamper.db')
    fileout = path_sample_files('output', 'tuxsmall.jpg')
    fileout2 = path_sample_files('output', 'repaired/tuxsmall.jpg')
    fileout2_dir = path_sample_files('output', 'repaired')
    fileres = path_sample_files('results', 'test_header_ecc_test_one_file_tamper.db')
    create_dir_if_not_exist(fileout2_dir)
    # Generate an ecc file
    assert hecc.main('-i "%s" -d "%s" --ecc_algo=3 -g -f --silent' % (filein, filedb)) == 0
    # Tamper the file
    shutil.copyfile(filein, fileout) # Copy it to avoid tampering the original
    tamper_file(fileout, 4, r'abcde')
    # Repair the file
    assert hecc.main('-i "%s" -d "%s" -o "%s" --ecc_algo=3 -c --silent' % (fileout, filedb, fileout2_dir)) == 0
    # Check that the file was completely repaired
    assert check_eq_files(filein, fileout2)

def test_dir():
    """ hecc: test creation and verification of database for a full directory """
    filein = path_sample_files('input', )
    filedb = path_sample_files('output', 'hecc_dir.db')
    fileout = path_sample_files('output', )
    fileout_rec = path_sample_files('output', 'rectemp', True) # temporary folder where repaired files will be placed (we expect none so this should be temporary, empty folder)
    fileres = path_sample_files('results', 'test_header_ecc_test_dir.db')
    # Generate an ecc file
    assert hecc.main('-i "%s" -d "%s" --ecc_algo=3 -g -f --silent' % (filein, filedb)) == 0
    # Check that generated ecc file is correct
    startpos1 = find_next_entry(filedb, get_marker(type=1)).next() # need to skip the comments, so we detect where the first entrymarker begins
    startpos2 = find_next_entry(fileres, get_marker(type=1)).next()
    assert check_eq_files(filedb, fileres, startpos1=startpos1, startpos2=startpos2)
    # Check that the ecc file correctly validates the correct files
    assert hecc.main('-i "%s" -d "%s" -o "%s" --ecc_algo=3 -c --silent' % (filein, filedb, fileout_rec)) == 0

def test_algo():
    """ hecc: test algorithms equivalence """
    filein = path_sample_files('input', 'tuxsmall.jpg')
    filedb = [path_sample_files('output', 'hecc_algo1.db'),
                path_sample_files('output', 'hecc_algo2.db'),
                path_sample_files('output', 'hecc_algo3.db'),
                ]
    fileres = path_sample_files('results', 'test_header_ecc_test_algo.db')
    fileout_rec = path_sample_files('output', 'rectemp', True) # temporary folder where repaired files will be placed (we expect none so this should be temporary, empty folder)
    # For each algorithm
    for i in range(len(filedb)):
        # Generate an ecc file
        assert hecc.main('-i "%s" -d "%s" --ecc_algo=%i -g -f --silent' % (filein, filedb[i], i+1)) == 0
        # Check file with this ecc algo
        assert hecc.main('-i "%s" -d "%s" -o "%s" --ecc_algo=%i -c --silent' % (filein, filedb[i], fileout_rec, i+1)) == 0
    for i in range(1, len(filedb)):
        # Check that generated ecc file is correct
        startpos1 = find_next_entry(filedb[0], get_marker(type=1)).next() # need to skip the comments, so we detect where the first entrymarker begins
        startpos2 = find_next_entry(filedb[i], get_marker(type=1)).next()
        assert check_eq_files(filedb[0], filedb[i], startpos1=startpos1, startpos2=startpos2)
    # Check against expected ecc file
    startpos1 = find_next_entry(filedb[0], get_marker(type=1)).next()
    startpos2 = find_next_entry(fileres, get_marker(type=1)).next()
    assert check_eq_files(filedb[0], fileres, startpos1=startpos1, startpos2=startpos2)

def test_entry_fields():
    """ hecc: test internal: entry_fields() """
    ecc = dummy_ecc_file_gen(3)
    eccf = StringIO(ecc)
    ecc_entry = get_next_entry(eccf, get_marker(1), only_coord=False)
    assert hecc.entry_fields(ecc_entry, field_delim=get_marker(2)) == {'ecc_field': 'hash-ecc-entry_hash-ecc-entry_hash-ecc-entry_', 'filesize_ecc': 'filesize1_ecc', 'relfilepath_ecc': 'relfilepath1_ecc', 'relfilepath': 'file1.ext', 'filesize': 'filesize1'}
    ecc_entry = get_next_entry(eccf, get_marker(1), only_coord=False)
    assert hecc.entry_fields(ecc_entry, field_delim=get_marker(2)) == {'ecc_field': 'hash-ecc-entry_hash-ecc-entry_hash-ecc-entry_hash-ecc-entry_hash-ecc-entry_hash-ecc-entry_', 'filesize_ecc': 'filesize2_ecc', 'relfilepath_ecc': 'relfilepath2_ecc', 'relfilepath': 'file2.ext', 'filesize': 'filesize2'}

def test_entry_assemble():
    """ hecc: test internal: entry_assemble() """
    class Hasher(object):
        """ Dummy Hasher """
        def __len__(self):
            return 32
    tempfile = path_sample_files('output', 'hecc_entry_assemble.txt')
    with open(tempfile, 'wb') as tfile:
        tfile.write("Lorem ipsum\nAnd stuff and stuff and stuff\n"*20)
    ecc = dummy_ecc_file_gen(3)
    eccf = StringIO(ecc)
    ecc_entry = get_next_entry(eccf, get_marker(1), only_coord=False)
    entry_fields = hecc.entry_fields(ecc_entry, field_delim=get_marker(2))
    ecc_params = compute_ecc_params(255, 0.5, Hasher())
    assert hecc.entry_assemble(entry_fields, ecc_params, 10, tempfile, fileheader=None) == [{'ecc': 'sh-ecc-entry_', 'message': 'Lorem ipsu', 'hash': 'hash-ecc-entry_hash-ecc-entry_ha'}]
    # TODO: check that several blocks can be assembled, currently we only check one block

def test_compute_ecc_hash():
    """ hecc: test internal: compute_ecc_hash() """
    class Hasher(object):
        """ Dummy Hasher """
        def hash(self, mes):
            return "dummyhsh"
        def __len__(self):
            return 8
    n = 20
    k = 11
    instring = "hello world!"*20
    header_size = 1024
    eccman = ECCMan(n, k, algo=3)
    assert hecc.compute_ecc_hash(eccman, Hasher(), instring[:header_size], 255, 0.5, message_size=None, as_string=False) == [['dummyhsh', b'\x9b\x18\xeb\xc9z\x01c\xf2\x07'], ['dummyhsh', b'\xa2Q\xc0Y\xae\xc3b\xd5\x81']]
    assert hecc.compute_ecc_hash(eccman, Hasher(), instring[:header_size], 255, 0.5, message_size=None, as_string=True) == ['dummyhsh\x9b\x18\xeb\xc9z\x01c\xf2\x07', 'dummyhsh\xa2Q\xc0Y\xae\xc3b\xd5\x81']
