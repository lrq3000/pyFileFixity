from __future__ import print_function, with_statement

import sys
import os
import itertools
import hashlib

import shutil

from .. import rfigc
from ..lib.aux_funcs import recwalk
from .aux_tests import check_eq_files, check_eq_dir, path_sample_files, tamper_file, create_dir_if_not_exist

def partial_eq(file, file_partial):
    """ Do a partial comparison, line by line, we compare only using "line2 in line1", where line2 is from file_partial """
    flag = True
    with open(file, 'rb') as outf, open(file_partial, 'rb') as expectedf:
        out = outf.read().strip('\n')
        expected = expectedf.read().strip('\n').split('\n')
        for exp in expected:
            if not exp in out:
                flag = False
                break
    return flag

def setup_module():
    """ Initialize the tests by emptying the out directory """
    outfolder = path_sample_files('output')
    shutil.rmtree(outfolder, ignore_errors=True)
    create_dir_if_not_exist(outfolder)

def test_one_file():
    """ rfigc: test creation and verification of rfigc database for one file """
    filein = path_sample_files('input', 'tuxsmall.jpg')
    filedb = path_sample_files('output', 'd_file.csv')
    fileres = path_sample_files('results', 'test_rfigc_test_one_file.csv')
    # Generate database file
    assert rfigc.main('-i "%s" -d "%s" -g -f --silent' % (filein, filedb)) == 0
    # Check files are ok
    assert rfigc.main('-i "%s" -d "%s" --silent' % (filein, filedb)) == 0
    # Check database file is the same as the pregenerated result
    with open(filedb, 'rb') as outf, open(fileres, 'rb') as expectedf:
        # Because of differing timestamps between local and git repo, we must only do a partial comparison (we compare the beginning of the file up to the timestamp)
        expected = expectedf.read().strip("\n")
        out = outf.read().strip("\n")
        assert expected in out

def test_dir():
    """ rfigc: test creation and verification of database for a full directory """
    filein = path_sample_files('input', )
    filedb = path_sample_files('output', 'd_dir.csv')
    fileres = path_sample_files('results', 'test_rfigc_test_dir.csv')
    # Generate database file
    assert rfigc.main('-i "%s" -d "%s" -g -f --silent' % (filein, filedb)) == 0
    # Check files are ok
    assert rfigc.main('-i "%s" -d "%s" --silent' % (filein, filedb)) == 0
    # Check database file is the same as the pregenerated result
    # We can't directly compare the two files because of timestamps!
    # So we manually process the expected results and compare each line to see if it's present in the output
    assert partial_eq(filedb, fileres)
    # TODO: add a regular expression to check that all fields are present

def test_error_file():
    """ rfigc: test tamper file and error file generation """
    filein = path_sample_files('input', 'tuxsmall.jpg')
    filedb = path_sample_files('output', 'd.csv')
    fileout = path_sample_files('output', 'tuxsmall.jpg')
    fileout2 = path_sample_files('output', 'errors.log')
    fileres = path_sample_files('results', 'test_rfigc_test_error_file.log')
    assert rfigc.main('-i "%s" -d "%s" -g -f --silent' % (filein, filedb)) == 0
    shutil.copyfile(filein, fileout)
    tamper_file(fileout, 3)
    assert rfigc.main('-i "%s" -d "%s" -e "%s" --silent' % (fileout, filedb, fileout2)) == 1
    check_eq_files(fileout2, fileres)

def test_filescrape():
    """ rfigc: test --filescraping_recovery """
    filein_dir = path_sample_files('input', )
    filedb = path_sample_files('output', 'db_filescrape.csv')
    fileout_dir = path_sample_files('output', 'filescrape')
    fileout_dir_rec = path_sample_files('output', 'filescrape_rec')
    create_dir_if_not_exist(fileout_dir)
    create_dir_if_not_exist(fileout_dir_rec)
    # Simulate a filescrape (copy the files but rename them all)
    i = 0
    for dirpath, filepath in recwalk(filein_dir):
        i += 1
        shutil.copyfile(os.path.join(dirpath, filepath), os.path.join(fileout_dir, "%s.stuff" % i))
    assert not check_eq_dir(filein_dir, fileout_dir) # check that we correctly filescraped!
    # Use rfigc to recover from filescrape
    assert rfigc.main('-i "%s" -d "%s" -g -f --silent' % (filein_dir, filedb)) == 0
    assert rfigc.main('-i "%s" -d "%s" --filescraping_recovery -o "%s" --silent' % (fileout_dir, filedb, fileout_dir_rec)) == 0
    assert check_eq_dir(filein_dir, fileout_dir_rec) # check that we recovered from filescraping!

def test_update():
    """ rfigc: test --update """
    filein = path_sample_files('input', )
    filedb = path_sample_files('output', 'd_update.csv')
    fileout_dir = path_sample_files('output', 'update')
    fileout = path_sample_files('output', 'update/added_file.txt')
    fileres1 = path_sample_files('results', 'test_rfigc_test_update_append.csv')
    fileres2 = path_sample_files('results', 'test_rfigc_test_update_remove.csv')
    # Generate a database from input files
    assert rfigc.main('-i "%s" -d "%s" -g -f --silent' % (filein, filedb)) == 0
    # Create a new file in another folder
    create_dir_if_not_exist(fileout_dir)
    with open(fileout, 'wb') as fh:
        fh.write('abcdefABCDEF\n1234598765')
    # Append file in database
    assert rfigc.main('-i "%s" -d "%s" --update --append --silent' % (fileout_dir, filedb)) == 0
    assert partial_eq(filedb, fileres1)
    # Remove all other files from database
    assert rfigc.main('-i "%s" -d "%s" --update --remove --silent' % (fileout_dir, filedb)) == 0
    assert partial_eq(filedb, fileres2)

def test_generate_hashes():
    """ rfigc: test internal: generate_hashes() """
    # Test with a file we make on the spot, so this should always be correct!
    infile0 = path_sample_files('output', 'test_rfigc_generate_hashes.txt')
    with open(infile0, 'wb') as f0:
        f0.write("Lorem ipsum etc\n"*20)
    assert rfigc.generate_hashes(infile0) == ('c6e0c87cbb8eeaca8179f22186384e6b', '6f46949be7cda1437bc3fb61fb827a6552beaf8b')
    # Test with input files, this may change if we change the files
    infile1 = path_sample_files('input', 'tux.jpg')
    infile2 = path_sample_files('input', 'alice.pdf')
    assert rfigc.generate_hashes(infile1) == ('81e19bbf2efaeb1d6d6473c21c48e4b7', '6e38ea91680ef0f960db0fd6a973cf50ef765369')
    assert rfigc.generate_hashes(infile2) == ('298aeefe8c00f2d92d660987bee67260', '106e7ad4d3927c5906cd366cc0d5bd887bdc3300')
