from __future__ import print_function

import itertools
import hashlib

import sys

import shutil

from pyFileFixity import repair_ecc as recc
from pyFileFixity import header_ecc as hecc
from .aux_tests import check_eq_files, check_eq_dir, path_sample_files, tamper_file, find_next_entry, create_dir_if_not_exist, get_marker

def get_db():
    return [path_sample_files('output', 'recc_file.db'), path_sample_files('output', 'recc_file.db_bak')]

def get_db_idx():
    return [path_sample_files('output', 'recc_file.db.idx'), path_sample_files('output', 'recc_file.db.idx_bak')]

def restore_db():
    filedb, filedb_bak = get_db()
    shutil.copyfile(filedb_bak, filedb)
    return 0

def restore_db_idx():
    filedb_idx, filedb_idx_bak = get_db_idx()
    shutil.copyfile(filedb_idx_bak, filedb_idx)
    return 0

def setup_module():
    """ Initialize the tests by emptying the out directory """
    outfolder = path_sample_files('output')
    shutil.rmtree(outfolder, ignore_errors=True)
    create_dir_if_not_exist(outfolder)
    # Generate an ecc file for the repair tests to use
    filein = path_sample_files('input')
    filedb, filedb_bak = get_db()
    filedb_idx, filedb_idx_bak = get_db_idx()
    hecc.main('-i "%s" -d "%s" --ecc_algo=3 -g -f --silent' % (filein, filedb))
    shutil.copyfile(filedb, filedb_bak) # keep a backup, we will reuse it for each test
    shutil.copyfile(filedb_idx, filedb_idx_bak)

def test_check():
    """ recc: check db and index files are the same as expected """
    filedb, filedb_bak = get_db()
    filedb_idx, filedb_idx_bak = get_db_idx()
    fileres = path_sample_files('results', 'test_repair_ecc_check.db')
    fileres_idx = path_sample_files('results', 'test_repair_ecc_check.db.idx')
    # Check that generated files are correct
    startpos1 = find_next_entry(filedb, get_marker(type=1)).next() # need to skip the comments, so we detect where the first entrymarker begins
    startpos2 = find_next_entry(fileres, get_marker(type=1)).next()
    assert check_eq_files(filedb, fileres, startpos1=startpos1, startpos2=startpos2)
    assert check_eq_files(filedb_idx, fileres_idx)

def test_repair_by_index():
    """ recc: tamper ecc file and repair by index file """
    filedb, filedb_bak = get_db()
    filedb_idx, filedb_idx_bak = get_db_idx()
    fileout = path_sample_files('output', 'recc_file_repaired.db')
    marker1 = get_marker(type=1)
    marker2 = get_marker(type=2)
    restore_db()
    restore_db_idx()
    # Completely overwrite a few markers (hence they cannot be recovered by hamming)
    startpos1 = find_next_entry(filedb, marker1).next()
    startpos2 = find_next_entry(filedb, marker1, startpos1+len(marker1)).next()
    startpos3 = find_next_entry(filedb, marker2, startpos2+len(marker1)).next()
    tamper_file(filedb, startpos1, "a"*len(marker1))
    tamper_file(filedb, startpos2, "a"*len(marker1))
    tamper_file(filedb, startpos3, "a"*len(marker2))
    # Repair ecc file using index file
    assert recc.main('-i "%s" --index "%s" -o "%s" -t 0.0 -f --silent' % (filedb, filedb_idx, fileout)) == 0
    assert check_eq_files(filedb_bak, fileout)

def test_repair_by_hamming():
    """ recc: tamper ecc file and repair by hamming distance """
    filedb, filedb_bak = get_db()
    fileout = path_sample_files('output', 'recc_file_repaired.db')
    marker1 = get_marker(type=1)
    marker2 = get_marker(type=2)
    restore_db()
    # Completely overwrite a few markers (hence they cannot be recovered by hamming)
    startpos1 = find_next_entry(filedb, marker1).next()
    startpos2 = find_next_entry(filedb, marker1, startpos1+len(marker1)).next()
    startpos3 = find_next_entry(filedb, marker2, startpos2+len(marker1)).next()
    tamper_file(filedb, startpos1, "a"*int(len(marker1)*0.3))
    tamper_file(filedb, startpos2, "a"*int(len(marker1)*0.3))
    tamper_file(filedb, startpos3, "a"*int(len(marker2)*0.3))
    # Repair ecc file by hamming similarity
    assert recc.main('-i "%s" -o "%s" -t 0.3 -f --silent' % (filedb, fileout)) == 0
    assert check_eq_files(filedb_bak, fileout)

def test_tamper_index():
    """ recc: tamper index file and see if it can repair itself """
    filedb, filedb_bak = get_db()
    filedb_idx, filedb_idx_bak = get_db_idx()
    fileout = path_sample_files('output', 'recc_file_repaired.db')
    marker1 = get_marker(type=1)
    marker2 = get_marker(type=2)
    restore_db()
    restore_db_idx()
    # Completely overwrite a few markers (hence they cannot be recovered by hamming)
    startpos1 = find_next_entry(filedb, marker1).next()
    startpos2 = find_next_entry(filedb, marker1, startpos1+len(marker1)).next()
    startpos3 = find_next_entry(filedb, marker2, startpos2+len(marker1)).next()
    tamper_file(filedb, startpos1, "a"*len(marker1))
    tamper_file(filedb, startpos2, "a"*len(marker1))
    tamper_file(filedb, startpos3, "a"*len(marker2))
    # Tamper index file
    tamper_file(filedb_idx, 0, "abcd")
    tamper_file(filedb_idx, 9, "abcd")
    tamper_file(filedb_idx, 27, "abcd")
    assert recc.main('-i "%s" --index "%s" -o "%s" -t 0.0 -f --silent' % (filedb, filedb_idx, fileout)) == 0
    assert check_eq_files(filedb_bak, fileout)
