from __future__ import print_function

from StringIO import StringIO
import shutil

from .aux_tests import get_marker, dummy_ecc_file_gen, check_eq_files, check_eq_dir, path_sample_files, tamper_file, find_next_entry, create_dir_if_not_exist

from pyFileFixity.lib.aux_funcs import get_next_entry

def setup_module():
    """ Initialize the tests by emptying the out directory """
    outfolder = path_sample_files('output')
    shutil.rmtree(outfolder, ignore_errors=True)
    create_dir_if_not_exist(outfolder)

def test_get_next_entry():
    """ aux: test detection of next entry """
    entries = [
            '''file1.ext\xfa\xff\xfa\xff\xfafilesize1\xfa\xff\xfa\xff\xfarelfilepath1_ecc\xfa\xff\xfa\xff\xfafilesize1_ecc\xfa\xff\xfa\xff\xfahash-ecc-entry_hash-ecc-entry_hash-ecc-entry_''',
            '''file2.ext\xfa\xff\xfa\xff\xfafilesize2\xfa\xff\xfa\xff\xfarelfilepath2_ecc\xfa\xff\xfa\xff\xfafilesize2_ecc\xfa\xff\xfa\xff\xfahash-ecc-entry_hash-ecc-entry_hash-ecc-entry_hash-ecc-entry_hash-ecc-entry_hash-ecc-entry_'''
          ]
    entries_pos = [
                    [83, 195],
                    [205, 362]
                  ]

    filecontent = dummy_ecc_file_gen(2)
    fp1 = StringIO(filecontent)
    entry = get_next_entry(fp1, entrymarker=get_marker(1), only_coord=False, blocksize=len(get_marker(1))+1)
    assert entry == entries[0]
    entry = get_next_entry(fp1, entrymarker=get_marker(1), only_coord=False, blocksize=len(get_marker(1))+1)
    assert entry == entries[1]
    fp2 = StringIO(filecontent)
    entry = get_next_entry(fp2, entrymarker=get_marker(1), only_coord=True, blocksize=len(get_marker(1))+1)
    assert entry == entries_pos[0]
    entry = get_next_entry(fp2, entrymarker=get_marker(1), only_coord=True, blocksize=len(get_marker(1))+1)
    assert entry == entries_pos[1]
