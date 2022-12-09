from __future__ import print_function

import unittest
import sys
import os
import shutil

from .aux_tests import path_sample_files, create_dir_if_not_exist

from ..lib.hasher import Hasher

class TestHasher(unittest.TestCase):
    def setup_module(self):
        """ Initialize the tests by emptying the out directory """
        outfolder = path_sample_files('output')
        shutil.rmtree(outfolder, ignore_errors=True)
        create_dir_if_not_exist(outfolder)

    def test_hasher(self):
        """ hasher: test hashes """
        instring = "Lorem ipsum and some more stuff\nThe answer to the question of life, universe and everything is... 42."
        # Put all hashing algo results here (format: "algo_name": [length, result_for_instring])
        algo_params = {"md5": [32, b'173efbe0280ce506ddbfbfc9aeb44a1a'],
                       "shortmd5": [8, b'MTczZWZi'],
                       "shortsha256": [8, b'NjgzMjRk'],
                       "minimd5":  [4, b'MTcz'],
                       "minisha256": [4, b'Njgz'],
                       "none": [0, ''],
                      }
        # For each hashing algo, produce a hash and check the length and hash
        for algo in Hasher.known_algo:
            h = Hasher(algo)
            shash = h.hash(instring)
            #print(algo+": "+shash) # debug
            assert len(shash) == algo_params[algo][0]
            assert shash == algo_params[algo][1]
        # Check that unknown algorithms raise an exception
        self.assertRaises(NameError, Hasher, "unknown_algo")
        # Second check of unknown algo raising exception
        h = Hasher()
        h.algo = "unknown_algo"
        self.assertRaises(NameError, h.hash, "abcdef")
