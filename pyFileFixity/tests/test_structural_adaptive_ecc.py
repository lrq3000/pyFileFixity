from __future__ import print_function

import sys
import os
import itertools
import hashlib

import shutil

from .. import structural_adaptive_ecc as saecc
from ..lib.aux_funcs import get_next_entry
from ..lib.eccman import ECCMan
from .aux_tests import check_eq_files, check_eq_dir, path_sample_files, tamper_file, find_next_entry, create_dir_if_not_exist, get_marker, dummy_ecc_file_gen

from io import BytesIO

def setup_module():
    """ Initialize the tests by emptying the out directory """
    outfolder = path_sample_files('output')
    shutil.rmtree(outfolder, ignore_errors=True)
    create_dir_if_not_exist(outfolder)

def test_one_file():
    """ saecc: test creation and verification of database for one file """
    filein = path_sample_files('input', 'tuxsmall.jpg')
    filedb = path_sample_files('output', 'saecc_file.db')
    fileout = path_sample_files('output', 'tuxsmall.jpg')
    fileout_rec = path_sample_files('output', 'rectemp', True) # temporary folder where repaired files will be placed (we expect none so this should be temporary, empty folder)
    fileres = path_sample_files('results', 'test_structural_adaptive_ecc_test_one_file.db')
    # Generate an ecc file
    assert saecc.main('-i "%s" -d "%s" --ecc_algo=3 -g -f --silent' % (filein, filedb)) == 0
    # Check that generated ecc file is correct
    startpos1 = next(find_next_entry(filedb, get_marker(type=1))) # need to skip the comments, so we detect where the first entrymarker begins
    startpos2 = next(find_next_entry(fileres, get_marker(type=1)))
    assert check_eq_files(filedb, fileres, startpos1=startpos1, startpos2=startpos2)
    # Check that the ecc file correctly validates the correct files
    assert saecc.main('-i "%s" -d "%s" -o "%s" --ecc_algo=3 -c --silent' % (filein, filedb, fileout_rec)) == 0

def test_one_file_tamper():
    """ saecc: test file repair """
    filein = path_sample_files('input', 'tuxsmall.jpg')
    filedb = path_sample_files('output', 'saecc_tamper.db')
    fileout = path_sample_files('output', 'tuxsmall.jpg')
    fileout2 = path_sample_files('output', 'repaired/tuxsmall.jpg')
    fileout2_dir = path_sample_files('output', 'repaired')
    fileres = path_sample_files('results', 'test_structural_adaptive_ecc_test_one_file_tamper.db')
    create_dir_if_not_exist(fileout2_dir)
    # Generate an ecc file
    assert saecc.main('-i "%s" -d "%s" --ecc_algo=3 -g -f --silent' % (filein, filedb)) == 0
    # Tamper the file
    shutil.copyfile(filein, fileout) # Copy it to avoid tampering the original
    tamper_file(fileout, 4, r'abcde')
    tamper_file(fileout, 1100, r'abcde') # tamper outside the range of header
    tamper_file(fileout, -5, r'abcde') # tamper end of file
    # Repair the file
    assert saecc.main('-i "%s" -d "%s" -o "%s" --ecc_algo=3 -c --silent' % (fileout, filedb, fileout2_dir)) == 0
    # Check that the file was completely repaired
    assert check_eq_files(filein, fileout2)

def test_dir():
    """ saecc: test creation and verification of database for a full directory """
    filein = path_sample_files('input', )
    filedb = path_sample_files('output', 'saecc_dir.db')
    fileout = path_sample_files('output', )
    fileout_rec = path_sample_files('output', 'rectemp', True) # temporary folder where repaired files will be placed (we expect none so this should be temporary, empty folder)
    fileres = path_sample_files('results', 'test_structural_adaptive_ecc_test_dir.db')
    # Generate an ecc file
    assert saecc.main('-i "%s" -d "%s" --ecc_algo=3 -g -f --silent' % (filein, filedb)) == 0
    # Check that generated ecc file is correct
    startpos1 = next(find_next_entry(filedb, get_marker(type=1))) # need to skip the comments, so we detect where the first entrymarker begins
    startpos2 = next(find_next_entry(fileres, get_marker(type=1)))
    assert check_eq_files(filedb, fileres, startpos1=startpos1, startpos2=startpos2)
    # Check that the ecc file correctly validates the correct files
    assert saecc.main('-i "%s" -d "%s" -o "%s" --ecc_algo=3 -c --silent' % (filein, filedb, fileout_rec)) == 0

def test_algo():
    """ saecc: test algorithms equivalence """
    filein = path_sample_files('input', 'tuxsmall.jpg')
    filedb = [path_sample_files('output', 'saecc_algo1.db'),
                path_sample_files('output', 'saecc_algo2.db'),
                path_sample_files('output', 'saecc_algo3.db'),
                ]
    fileres = path_sample_files('results', 'test_structural_adaptive_ecc_test_algo.db')
    fileout_rec = path_sample_files('output', 'rectemp', True)
    # For each algorithm
    for i in range(len(filedb)):
        # Generate an ecc file
        assert saecc.main('-i "%s" -d "%s" --ecc_algo=%i -g -f --silent' % (filein, filedb[i], i+1)) == 0
        # Check file with this ecc algo
        assert saecc.main('-i "%s" -d "%s" -o "%s" --ecc_algo=%i -c --silent' % (filein, filedb[i], fileout_rec, i+1)) == 0
    # Check that all generated ecc are the same, whatever the algo (up to 3)
    startpos1 = next(find_next_entry(filedb[0], get_marker(type=1))) # need to skip the comments, so we detect where the first entrymarker begins
    for i in range(1, len(filedb)):
        startpos2 = next(find_next_entry(filedb[i], get_marker(type=1)))
        assert check_eq_files(filedb[0], filedb[i], startpos1=startpos1, startpos2=startpos2)
    # Check against expected ecc file
    startpos1 = next(find_next_entry(filedb[0], get_marker(type=1)))
    startpos2 = next(find_next_entry(fileres, get_marker(type=1)))
    assert check_eq_files(filedb[0], fileres, startpos1=startpos1, startpos2=startpos2)

def test_entry_fields():
    """ saecc: test internal: entry_fields() """
    ecc = dummy_ecc_file_gen(3)
    eccf = BytesIO(ecc)
    ecc_entry_pos = get_next_entry(eccf, get_marker(1), only_coord=True)
    assert saecc.entry_fields(eccf, ecc_entry_pos, field_delim=get_marker(2)) == {'ecc_field_pos': [150, 195], 'filesize_ecc': b'filesize1_ecc', 'relfilepath_ecc': b'relfilepath1_ecc', 'relfilepath': b'file1.ext', 'filesize': b'filesize1'}
    ecc_entry_pos = get_next_entry(eccf, get_marker(1), only_coord=True)
    assert saecc.entry_fields(eccf, ecc_entry_pos, field_delim=get_marker(2)) == {'ecc_field_pos': [272, 362], 'filesize_ecc': b'filesize2_ecc', 'relfilepath_ecc': b'relfilepath2_ecc', 'relfilepath': b'file2.ext', 'filesize': b'filesize2'}

def test_stream_entry_assemble():
    """ saecc: test internal: stream_entry_assemble() """
    class Hasher(object):
        """ Dummy Hasher """
        def __len__(self):
            return 32
    tempfile = path_sample_files('output', 'saecc_stream_entry_assemble.txt')
    with open(tempfile, 'wb') as tfile:
        tfile.write(b"Lorem ipsum\nAnd stuff and stuff and stuff\n"*20)
    ecc = dummy_ecc_file_gen(3)
    eccf = BytesIO(ecc)
    ecc_entry_pos = get_next_entry(eccf, get_marker(1), only_coord=True)
    entry_fields = saecc.entry_fields(eccf, ecc_entry_pos, field_delim=get_marker(2))
    with open(tempfile, 'rb') as tfile:
        assert list( saecc.stream_entry_assemble(Hasher(), tfile, eccf, entry_fields, 255, 10, [0.7, 0.5, 0.3]) ) == [{'ecc': b'sh-ecc-entry_\xfe\xff\xfe\xff\xfe\xff\xfe\xff\xfe\xfffile2.ext\xfa\xff\xfa\xff\xfafilesize2\xfa\xff\xfa\xff\xfarelfilepath2_ecc\xfa\xff\xfa\xff\xfafilesize2_ecc\xfa\xff\xfa\xff\xfahash-ecc-entry_hash-ecc-entry_hash-ecc-entry_hash-ecc-entry', 'curpos': 0, 'rate': 0.7, 'ecc_params': {'ecc_size': 149, 'hash_size': 32, 'message_size': 106}, 'ecc_curpos': 150, 'hash': b'hash-ecc-entry_hash-ecc-entry_ha', 'message': b'Lorem ipsum\nAnd stuff and stuff and stuff\nLorem ipsum\nAnd stuff and stuff and stuff\nLorem ipsum\nAnd stuff '}]
    # TODO: check that several blocks can be assembled, currently we only check one block

def test_stream_compute_ecc_hash():
    """ saecc: test internal: stream_compute_ecc_hash() and compute_ecc_hash_from_string() """
    class Hasher(object):
        """ Dummy Hasher """
        def hash(self, mes):
            return "dummyhsh"
        def __len__(self):
            return 8
    n = 20 # aka max_block_size
    k = 11
    resilience_rates = [0.7, 0.5, 0.3]
    instring = b"hello world!"*10
    tempfile = path_sample_files('output', 'saecc_stream_compute_ecc_hash.txt')
    with open(tempfile, 'wb') as tfile:
        tfile.write(instring)
    eccman = ECCMan(n, k, algo=3)
    with open(tempfile, 'rb') as tfile:
        assert list( saecc.stream_compute_ecc_hash(eccman, Hasher(), tfile, n, int(len(instring)/4), resilience_rates) ) == [[b'dummyhsh', bytearray(b'\x8f=\xae\x11\xe1\xf7F\x94A\xb8\x00\x8d'), {'ecc_size': 12, 'hash_size': 8, 'message_size': 8}], [b'dummyhsh', bytearray(b'\x97\x13\xe8G*\x15\xb5\xb2hn\xdf\x88'), {'ecc_size': 12, 'hash_size': 8, 'message_size': 8}], [b'dummyhsh', bytearray(b'r\x9d\xb7#f\xa3=*\xda\x17WC'), {'ecc_size': 12, 'hash_size': 8, 'message_size': 8}], [b'dummyhsh', bytearray(b'\x8f=\xae\x11\xe1\xf7F\x94A\xb8\x00\x8d'), {'ecc_size': 12, 'hash_size': 8, 'message_size': 8}], [b'dummyhsh', bytearray(b'\xab\x8c\xae\r\xbb\x9b\x93\xbd\xd5\x8f'), {'ecc_size': 10, 'hash_size': 8, 'message_size': 10}], [b'dummyhsh', bytearray(b'\xb8S\x1cz\xb2\xeb\x9fu\x19\x83'), {'ecc_size': 10, 'hash_size': 8, 'message_size': 10}], [b'dummyhsh', bytearray(b'\x07\xc4\xce\xe2\xdf\x0b\t\x17,'), {'ecc_size': 9, 'hash_size': 8, 'message_size': 11}], [b'dummyhsh', bytearray(b'\xd6(og\xb5}\x06\xe3\xd2'), {'ecc_size': 9, 'hash_size': 8, 'message_size': 11}], [b'dummyhsh', bytearray(b'v\x9dP\x0c\x01\x03\x83Q!'), {'ecc_size': 9, 'hash_size': 8, 'message_size': 11}], [b'dummyhsh', bytearray(b'\xc4\x12q\xd9\x0fq\xef\xc2\xba'), {'ecc_size': 9, 'hash_size': 8, 'message_size': 11}], [b'dummyhsh', bytearray(b'6\xd0\xe8\xe9\xfe(y\x13'), {'ecc_size': 8, 'hash_size': 8, 'message_size': 12}], [b'dummyhsh', bytearray(b'6\xd0\xe8\xe9\xfe(y\x13'), {'ecc_size': 8, 'hash_size': 8, 'message_size': 12}]]
    assert saecc.compute_ecc_hash_from_string(instring, eccman, Hasher(), n, resilience_rates[0]) == b'\x8f=\xae\x11\xe1\xf7F\x94A\xb8\x00\x8d\x97\x13\xe8G*\x15\xb5\xb2hn\xdf\x88r\x9d\xb7#f\xa3=*\xda\x17WC\x8f=\xae\x11\xe1\xf7F\x94A\xb8\x00\x8d\x97\x13\xe8G*\x15\xb5\xb2hn\xdf\x88r\x9d\xb7#f\xa3=*\xda\x17WC\x8f=\xae\x11\xe1\xf7F\x94A\xb8\x00\x8d\x97\x13\xe8G*\x15\xb5\xb2hn\xdf\x88r\x9d\xb7#f\xa3=*\xda\x17WC\x8f=\xae\x11\xe1\xf7F\x94A\xb8\x00\x8d\x97\x13\xe8G*\x15\xb5\xb2hn\xdf\x88r\x9d\xb7#f\xa3=*\xda\x17WC\x8f=\xae\x11\xe1\xf7F\x94A\xb8\x00\x8d\x97\x13\xe8G*\x15\xb5\xb2hn\xdf\x88r\x9d\xb7#f\xa3=*\xda\x17WC'
