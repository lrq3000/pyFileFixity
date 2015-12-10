from __future__ import print_function

import sys
import os

import shutil

from .. import resiliency_tester as restest
from .aux_tests import path_sample_files, tamper_file, create_dir_if_not_exist, remove_if_exist

from ..lib._compat import _StringIO

def setup_module():
    """ Initialize the tests by emptying the out directory """
    outfolder = path_sample_files('output')
    shutil.rmtree(outfolder, ignore_errors=True)
    create_dir_if_not_exist(outfolder)

def test_parse_configfile():
    """ restest: test internal: parse_configfile() """
    config = '''
before_tamper:
    cmd1 -i "arg1" -o "arg2"
    cmd2

tamper:
    cmd3
    cmd4

after_tamper:
    cmd5
    cmd6
    # a comment

repair:
    cmd7
    cmd8
    '''
    fconfig = _StringIO(config)
    parsed = restest.parse_configfile(fconfig)
    assert parsed == {'tamper': ['cmd3', 'cmd4'], 'after_tamper': ['cmd5', 'cmd6'], 'before_tamper': ['cmd1 -i "arg1" -o "arg2"', 'cmd2'], 'repair': ['cmd7', 'cmd8']}

def test_get_filename_no_ext():
    """ restest: test internal: get_filename_no_ext() """
    filepath = '/test/path/to/filename_no_ext.ext'
    res = restest.get_filename_no_ext(filepath)
    assert res == 'filename_no_ext'

def test_interpolate_dict():
    """ restest: test internal: interpolate_dict() """
    s = 'Some {var1} with {var2} makes for {var3} parties!'
    d = {'var1': 'wine', 'var2': 'beer', 'var3': 'fun', 'var4': 'Hidden'}
    res = restest.interpolate_dict(s, interp_args=d)
    assert res == 'Some wine with beer makes for fun parties!'

def test_get_dbfile():
    """ restest: test internal: get_dbfile() """
    res = restest.get_dbfile('databases', 10)
    assert 'databases' in res
    assert 'db10' in res

def test_diff_bytes_files():
    """ restest: test internal: diff_bytes_files() """
    filein = path_sample_files('input', 'tuxsmall.jpg')
    fileout1 = path_sample_files('output', 'bytes_tuxsmall1.jpg')
    fileout2 = path_sample_files('output', 'bytes_tuxsmall2.jpg')
    shutil.copy2(filein, fileout1)
    shutil.copy2(filein, fileout2)
    res = restest.diff_bytes_files(fileout1, fileout2, blocksize=1000, startpos1=0, startpos2=0)
    assert res[0] == 0
    assert res[1] == os.stat(fileout1).st_size
    tamper_file(fileout2, 0, "X")
    tamper_file(fileout2, 4, "X")
    tamper_file(fileout2, 2000, "X")
    res = restest.diff_bytes_files(fileout1, fileout2, blocksize=1000, startpos1=0, startpos2=0)
    assert res[0] == 3

def test_diff_count_files():
    """ restest: test internal: diff_count_files() """
    filein = path_sample_files('input', 'tuxsmall.jpg')
    fileout1 = path_sample_files('output', 'count_tuxsmall1.jpg')
    fileout2 = path_sample_files('output', 'count_tuxsmall2.jpg')
    shutil.copy2(filein, fileout1)
    shutil.copy2(filein, fileout2)
    res = restest.diff_count_files(fileout1, fileout2, blocksize=1000, startpos1=0, startpos2=0)
    assert res
    tamper_file(fileout2, 0, "X")
    tamper_file(fileout2, 4, "X")
    tamper_file(fileout2, 2000, "X")
    res = restest.diff_count_files(fileout1, fileout2, blocksize=1000, startpos1=0, startpos2=0)
    assert not res

def test_diff_bytes_dir():
    """ restest: test internal: diff_bytes_dir() """
    dirin = path_sample_files('input')
    dirout = path_sample_files('output', 'restest/bytes')
    fileout = path_sample_files('output', 'restest/bytes/tuxsmall.jpg')
    fileout2 = path_sample_files('output', 'restest/bytes/testaa.txt')
    remove_if_exist(dirout)
    shutil.copytree(dirin, dirout)

    # First compare the two folders that are identical
    res = restest.diff_bytes_dir(dirin, dirout)
    assert res[0] == 0

    # Tamper a few bytes of two files
    tamper_file(fileout, 0, "X")
    tamper_file(fileout, 4, "X")
    tamper_file(fileout, 2000, "X")
    tamper_file(fileout2, 0, "X")
    res = restest.diff_bytes_dir(dirin, dirout)
    assert res[0] == 4

    # Now remove a file altogether, its size should be added to the amount of differing bytes
    filesize = os.stat(fileout).st_size
    remove_if_exist(fileout)
    res = restest.diff_bytes_dir(dirin, dirout)
    assert res[0] == (filesize+1)

def test_diff_count_dir():
    """ restest: test internal: diff_count_dir() """
    dirin = path_sample_files('input')
    dirout = path_sample_files('output', 'restest/count')
    fileout = path_sample_files('output', 'restest/count/tuxsmall.jpg')
    fileout2 = path_sample_files('output', 'restest/count/testaa.txt')
    remove_if_exist(dirout)
    shutil.copytree(dirin, dirout)

    # First compare the two folders that are identical
    res = restest.diff_count_dir(dirin, dirout)
    assert res[0] == 0

    # Tamper a few bytes of two files
    tamper_file(fileout, 0, "X")
    tamper_file(fileout, 4, "X")
    tamper_file(fileout, 2000, "X")
    tamper_file(fileout2, 0, "X")
    res = restest.diff_count_dir(dirin, dirout)
    assert res[0] == 2

    # Now remove a file altogether, its size should be added to the amount of differing bytes
    filesize = os.stat(fileout).st_size
    remove_if_exist(fileout)
    res = restest.diff_count_dir(dirin, dirout)
    assert res[0] == 2

def test_compute_repair_power():
    """ restest: test internal: compute_repair_power() """
    # Note: be careful if you add tests here, the displayed value by print() may be rounded up! Use print(repr(copute_repair_power()))
    assert restest.compute_repair_power(0.3, 0.5) == 40.0
    assert restest.compute_repair_power(0.2, 0.8) == 75.0
    assert restest.compute_repair_power(0.6, 0.3) == -100.0
    assert restest.compute_repair_power(0.6, 0.0) == 0.6

def test_compute_diff_stats():
    """ restest: test internal: compute_diff_stats() """
    dirin = path_sample_files('input')
    dirout = path_sample_files('output', 'restest/count')
    fileout = path_sample_files('output', 'restest/count/tuxsmall.jpg')
    fileout2 = path_sample_files('output', 'restest/count/testaa.txt')
    remove_if_exist(dirout)
    shutil.copytree(dirin, dirout)

    # First compare the two folders that are identical
    res = restest.compute_diff_stats(dirin, dirin, dirout)
    assert dict(res) == {'diff_bytes': (0, 92955), 'diff_bytes_prev': (0, 92955), 'diff_count': (0, 7), 'diff_count_prev': (0, 7), 'repair_power': 0, 'error': 0.0}

    # Tamper a few bytes of two files
    tamper_file(fileout, 0, "X")
    tamper_file(fileout, 4, "X")
    tamper_file(fileout, 2000, "X")
    tamper_file(fileout2, 0, "X")
    res = restest.compute_diff_stats(dirin, dirin, dirout)
    assert dict(res) == {'diff_bytes': (4, 92955), 'diff_bytes_prev': (4, 92955), 'diff_count': (2, 7), 'diff_count_prev': (2, 7), 'repair_power': 0, 'error': 0.0043031574417729005}

def test_stats_running_average():
    """ restest: test internal: stats_running_average() """
    stats1 = {'diff_bytes': (0, 92955), 'diff_bytes_prev': (0, 92955), 'diff_count': (0, 7), 'diff_count_prev': (0, 7), 'repair_power': 0, 'error': 0.0}
    stats2 = {'diff_bytes': (4, 92955), 'diff_bytes_prev': (4, 92955), 'diff_count': (2, 7), 'diff_count_prev': (2, 7), 'repair_power': 0, 'error': 0.5}
    assert restest.stats_running_average({"tamper": stats1}, {"tamper": stats2}, 1) == {'tamper': {'diff_count_prev': [1.0, 7.0], 'diff_count': [1.0, 7.0], 'diff_bytes_prev': [2.0, 92955.0], 'error': 0.25, 'repair_power': 0.0, 'diff_bytes': [2.0, 92955.0]}}
    assert restest.stats_running_average({"tamper": stats1}, {"tamper": stats2}, 3) == {'tamper': {'diff_count_prev': [0.5, 7.0], 'diff_count': [0.5, 7.0], 'diff_bytes_prev': [1.0, 92955.0], 'error': 0.125, 'repair_power': 0.0, 'diff_bytes': [1.0, 92955.0]}}

def test_main():
    """ restest: test main() """
    # Change directory so that the config's commands can access pyFileFixity scripts
    thispathname = os.path.dirname(__file__)
    sys.path.append(os.path.join(thispathname, '..'))
    # Setup paths
    dirin = path_sample_files('input')
    dirout = path_sample_files('output', 'restest/fulltest')
    configfile = path_sample_files('results', 'resiliency_tester_config_easy.cfg')
    configfile_hard = path_sample_files('results', 'resiliency_tester_config_hard.cfg')
    # Should be no error with the easy scenario (repair should be successful)
    assert restest.main("-i \"%s\" -o \"%s\" -c \"%s\" -f --silent" % (dirin, dirout, configfile)) == 0
    # Should be error with the hard scenario
    assert restest.main("-i \"%s\" -o \"%s\" -c \"%s\" -m 2 -f --silent" % (dirin, dirout, configfile_hard)) == 1
    # TODO: catch sys.stdout and check for the end stats?
