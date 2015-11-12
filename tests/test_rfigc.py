from __future__ import print_function

import itertools
import hashlib

import sys

from .. import rfigc
from .aux_tests import check_eq_files, check_eq_folders

def test_one_file():
    """ Test creation and verification of database for one file """
    rfigc.main('-i "files/tux.jpg" -d "temp/d.csv" -g -f')
    rfigc.main('-i "files/tux.jpg" -d "temp/d.csv" -f')
