from __future__ import print_function

import sys
import os

import shutil
from StringIO import StringIO

from .. import replication_repair as rep
from .. import rfigc
from .aux_tests import check_eq_files, check_eq_dir, path_sample_files, tamper_file, find_next_entry, create_dir_if_not_exist, get_marker


def change_letter(s, index, new_char):
    l = list(s)
    l[index] = new_char
    return ''.join(l)


def setup_module():
    """ Initialize the tests by emptying the out directory """
    outfolder = path_sample_files('output')
    shutil.rmtree(outfolder, ignore_errors=True)
    create_dir_if_not_exist(outfolder)

def test_relpath_posix():
    """ repli: test internal: relpath_posix()"""
    recwalk_result = [r'C:\test\some\path', r'relative\path\file.ext']
    pardir = r'C:\test\some'
    assert rep.relpath_posix(recwalk_result, pardir, True) == ('C:\\test\\some\\path', ('path/relative/path', 'file.ext'))
    recwalk_result = [r'/test/some/path', r'relative/path/file.ext']
    pardir = r'/test/some'
    assert rep.relpath_posix(recwalk_result, pardir, False) == ('/test/some/path', ('path/relative/path', 'file.ext'))
    recwalk_result = [r'/test/some/path', r'relative\path\file.ext']
    pardir = r'/test/some'
    assert rep.relpath_posix(recwalk_result, pardir, True) == ('/test/some/path', ('path/relative/path', 'file.ext'))

def test_sort_group():
    """ repli: test internal: sort_group()"""
    curfiles = {
                0: ('relative/path', 'file.ext'),
                1: ('relative/path', 'file.ext'),
                2: ('relative/path', 'zzzz.ext'),
                3: ('relative/path', 'zzzz.ext'),
                4: ('relative/path', 'bbbb.ext'),
               }
    assert rep.sort_group(curfiles, return_only_first=False) == \
              [
               [(4, ('relative/path', 'bbbb.ext'))],
               [(0, ('relative/path', 'file.ext')), (1, ('relative/path', 'file.ext'))],
               [(2, ('relative/path', 'zzzz.ext')), (3, ('relative/path', 'zzzz.ext'))]
              ]
    assert rep.sort_group(curfiles, return_only_first=True) == [[(4, ('relative/path', 'bbbb.ext'))]]

def test_majority_vote_byte_scan():
    """ repli: test internal: majority_vote_byte_scan()"""
    
    def make_filehandles(fileslist):
        return [StringIO(f) for f in fileslist]
    
    # Necessary variables
    relfilepath = 'relative/path/file.ext'
    s = "Hello world\n"*3
    
    # 1- simple test, only a few characters are tampered/removed towards the end
    files = []
    files.append(change_letter(s[:-2], 2, 'X'))
    files.append(change_letter(s[:-1], 4, 'W'))
    files.append(s)
    fileshandles = make_filehandles(files)
    outfile = StringIO()

    errcode, errmsg = rep.majority_vote_byte_scan(relfilepath, fileshandles, outfile, blocksize=10, default_char_null=False)
    assert errcode == 0
    assert errmsg == None
    outfile.seek(0)
    out = outfile.read()
    assert out == s

    # 2- Test ambiguity, the first files should take precedence
    files = []
    files.append(s)
    # Set an ambiguity on the 3rd character
    files.append(change_letter(s, 2, 'X'))
    files.append(change_letter(s, 2, 'W'))

    # First run: the original string will take precedence since it's first in the list
    outfile = StringIO()
    fileshandles = make_filehandles(files)
    errcode, errmsg = rep.majority_vote_byte_scan(relfilepath, fileshandles, outfile, blocksize=10, default_char_null=False)
    assert errcode == 1
    outfile.seek(0)
    out = outfile.read()
    assert out == s

    # Second run: put the original string last, now we will have the tampered string taking precedence
    files.append(files.pop(0))
    fileshandles = make_filehandles(files)
    outfile = StringIO()
    errcode, errmsg = rep.majority_vote_byte_scan(relfilepath, fileshandles, outfile, blocksize=10, default_char_null=False)
    assert errcode == 1
    outfile.seek(0)
    out = outfile.read()
    assert 'HeXlo world' in out

    # Do the same, the third (tampered) string will take precedence
    files.append(files.pop(0))
    fileshandles = make_filehandles(files)
    outfile = StringIO()
    errcode, errmsg = rep.majority_vote_byte_scan(relfilepath, fileshandles, outfile, blocksize=10, default_char_null=False)
    assert errcode == 1
    outfile.seek(0)
    out = outfile.read()
    assert 'HeWlo world' in out

    # Set a default char this time
    files.append(files.pop(0))
    fileshandles = make_filehandles(files)
    outfile = StringIO()
    errcode, errmsg = rep.majority_vote_byte_scan(relfilepath, fileshandles, outfile, blocksize=10, default_char_null=True)
    assert errcode == 1
    outfile.seek(0)
    out = outfile.read()
    assert "He\x00lo world" in out

    # Set a custom default char
    files.append(files.pop(0))
    fileshandles = make_filehandles(files)
    outfile = StringIO()
    errcode, errmsg = rep.majority_vote_byte_scan(relfilepath, fileshandles, outfile, blocksize=10, default_char_null="A")
    assert errcode == 1
    outfile.seek(0)
    out = outfile.read()
    assert "HeAlo world" in out
    
    # 3- Test ambiguity when some files are already ended, the first still opened file should take precedence
    files = []
    files.append(s)
    # Shorten the second file
    files.append(s[:-3])
    # Set an ambiguity on the 2nd character to the end of file
    files.append(change_letter(s, -2, 'X'))

    # First run: the original string will take precedence since it's first in the list
    outfile = StringIO()
    fileshandles = make_filehandles(files)
    errcode, errmsg = rep.majority_vote_byte_scan(relfilepath, fileshandles, outfile, blocksize=10, default_char_null=False)
    assert errcode == 1
    outfile.seek(0)
    out = outfile.read()
    assert out == s

    # Move the original string to the last, and see if the tampered string takes precedence (skipping the ended string)
    files.append(files.pop(0))
    fileshandles = make_filehandles(files)
    outfile = StringIO()
    errcode, errmsg = rep.majority_vote_byte_scan(relfilepath, fileshandles, outfile, blocksize=10, default_char_null=False)
    assert errcode == 1
    outfile.seek(0)
    out = outfile.read()
    assert 'Hello worlX' in out

def test_synchronize_files():
    """ repli: test main() and synchronize_files()"""
    
    def quote_paths(inputpaths):
        return ' '.join(["\"%s\"" % path for path in inputpaths])

    # -- First make replications of test files
    filein = path_sample_files('input', 'tuxsmall.jpg')
    filein2 = path_sample_files('input', 'testaa.txt')
    filein3 = path_sample_files('input', 'sub/testsub.txt')
    #filein4 = path_sample_files('input', 'tux.jpg')
    # Create replications directories
    inputpaths = [path_sample_files('output', 'repli/dir%i' % (i+1), True) for i in xrange(4)]
    outpath = path_sample_files('output', 'repli/dirout')
    # Report file
    report_file = path_sample_files('output', 'repli_report.csv')
    # Generate the replications
    fileout = [path_sample_files('output', 'repli/dir%i/tuxsmall.jpg' % (i+1)) for i in xrange(4)]
    fileout2 = [path_sample_files('output', 'repli/dir%i/testaa.txt' % (i+1)) for i in xrange(4) if i != 2]
    path_sample_files('output', 'repli/dir3/sub/', True)
    fileout3 = path_sample_files('output', 'repli/dir3/sub/testsub.txt')
    #fileout4 = [path_sample_files('output', 'repli/dir%i/tux.jpg' % (i+1)) for i in xrange(4)]
    for f in fileout:
        shutil.copy2(filein, f)
    for f in fileout2:
        shutil.copy2(filein2, f)
    shutil.copy2(filein3, fileout3)
    # Backup of original files (to generate rfigc database)
    dirorig = path_sample_files('output', 'repli/dirorig', True)
    shutil.copy2(filein, dirorig)
    shutil.copy2(filein2, dirorig)
    shutil.copy2(filein3, path_sample_files('output', 'repli/dirorig/sub', True))
    # Database file
    filedb = path_sample_files('output', 'repli_rfigc_db.csv')

    # Tamper the replications
    # 1st file: tamper all copies but at different positions, to force merge by majority vote
    for i, f in enumerate(fileout):
        tamper_file(f, i, "A")
    # 2nd file: tamper all copies but one, to test rfigc interface
    for i, f in enumerate(fileout2):
        if i < 2:
            tamper_file(f, 0, "A")
    # 3rd file: no tamper, there's just one file, check that the file is just copied
    
    # 1- Majority vote!
    res1 = "filepath|dir1|dir2|dir3|dir4|hash-correct|error_code|errors\ntestaa.txt|X|X|-|X|-|OK|-\ntuxsmall.jpg|X|X|X|X|-|OK|-\nsub/testsub.txt|-|-|O|-|-|OK|-\n"
    errcode = rep.synchronize_files(inputpaths, outpath, report_file=report_file)
    assert errcode == 0
    with open(report_file, 'rb') as rfile:
        rout = rfile.read()
    assert res1 in rout
    # Do the same test with the main() func, this should give exactly the same result
    errcode = rep.main("-i %s -o \"%s\" -r \"%s\" -f --silent" % (quote_paths(inputpaths), outpath, report_file))
    assert errcode == 0
    with open(report_file, 'rb') as rfile:
        rout = rfile.read()
    assert res1 in rout

    # 2- rfigc database interfacing!
    res2 = "filepath|dir1|dir2|dir3|dir4|hash-correct|error_code|errors\ntestaa.txt|X|X|-|O|OK|OK|-\ntuxsmall.jpg|X|X|X|X|OK|OK|-\nsub/testsub.txt|-|-|O|-|OK|OK|-\n"
    # Generate rfigc database against original files
    assert rfigc.main('-i "%s" -d "%s" -g -f --silent' % (dirorig, filedb)) == 0
    # Replication repair using rfigc database to check results
    errcode = rep.synchronize_files(inputpaths, outpath, database=filedb, report_file=report_file)
    assert errcode == 0
    with open(report_file, 'rb') as rfile:
        rout = rfile.read()
    assert res2 in rout
    # Do the same test with the main() func, this should give exactly the same result
    errcode = rep.main("-i %s -o \"%s\" -r \"%s\" -d \"%s\" -f --silent" % (quote_paths(inputpaths), outpath, report_file, filedb))
    assert errcode == 0
    with open(report_file, 'rb') as rfile:
        rout = rfile.read()
    assert res2 in rout

    # 3- Ambiguous voting + bad decoding
    # Ambiguous tampering
    # fileout[0] is kept intact, and will take precedence since it's first
    tamper_file(fileout[1], 10, "B")
    tamper_file(fileout[2], 10, "C")
    tamper_file(fileout[3], 10, "D")
    
    # Wrong decoding (vote is OK but wrong)
    tamper_file(fileout2[0], 0, "A")
    tamper_file(fileout2[1], 0, "A")
    tamper_file(fileout2[2], 0, "A")

    # Replication repair using rfigc database to check results
    res3 = "filepath|dir1|dir2|dir3|dir4|hash-correct|error_code|errors\ntestaa.txt|X|X|-|X|KO|KO| File could not be totally repaired according to rfigc database.\ntuxsmall.jpg|X|X|X|X|OK|KO|Unrecoverable corruptions (because of ambiguity) in file tuxsmall.jpg on characters: ['0xaL']. But merged file is correct according to rfigc database.\nsub/testsub.txt|-|-|O|-|OK|OK|-\n"
    ptee = StringIO()
    errcode = rep.synchronize_files(inputpaths, outpath, database=filedb, report_file=report_file, ptee=ptee)
    assert errcode == 1
    with open(report_file, 'rb') as rfile:
        rout = rfile.read()
    ptee.seek(0)
    errmsg = ptee.read()
    assert len(errmsg) > 0
    assert res3 in rout
    # Same with main()...
    errcode = rep.main("-i %s -o \"%s\" -r \"%s\" -d \"%s\" -f --silent" % (quote_paths(inputpaths), outpath, report_file, filedb))
    assert errcode == 1
    with open(report_file, 'rb') as rfile:
        rout = rfile.read()
    ptee.seek(0)
    errmsg = ptee.read()
    assert len(errmsg) > 0
    assert res3 in rout
