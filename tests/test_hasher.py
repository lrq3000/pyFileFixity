from __future__ import print_function

import shutil

from .aux_tests import path_sample_files, create_dir_if_not_exist

from ..lib.hasher import Hasher

def setup_module():
    """ Initialize the tests by emptying the out directory """
    outfolder = path_sample_files('output')
    shutil.rmtree(outfolder, ignore_errors=True)
    create_dir_if_not_exist(outfolder)

def test_hasher():
    """ hasher: test hashes """
    instring = "Lorem ipsum and some more stuff\nThe answer to the question of life, universe and everything is... 42."
    # Put all hashing algo results here (format: "algo_name": [length, result_for_instring])
    algo_params = {"md5": [32, '173efbe0280ce506ddbfbfc9aeb44a1a'],
                   "shortmd5": [8, 'MTczZWZi'],
                   "shortsha256": [8, 'NjgzMjRk'],
                   "minimd5":  [4, 'MTcz'],
                   "minisha256": [4, 'Njgz'],
                   "none": [0, ''],
                  }
    # For each hashing algo, produce a hash and check the length and hash
    for algo in Hasher.known_algo:
        h = Hasher(algo)
        shash = h.hash(instring)
        #print(algo+": "+shash) # debug
        assert len(shash) == algo_params[algo][0]
        assert shash == algo_params[algo][1]
