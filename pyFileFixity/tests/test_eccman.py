from __future__ import print_function

from nose.tools import assert_raises

import sys
import os
import shutil

from .aux_tests import get_marker, dummy_ecc_file_gen, check_eq_files, check_eq_dir, path_sample_files, tamper_file, find_next_entry, create_dir_if_not_exist, remove_if_exist

from ..lib.eccman import ECCMan, compute_ecc_params, detect_reedsolomon_parameters

from ..lib._compat import _StringIO, b

def setup_module():
    """ Initialize the tests by emptying the out directory """
    outfolder = path_sample_files('output')
    shutil.rmtree(outfolder, ignore_errors=True)
    create_dir_if_not_exist(outfolder)

def test_eccman_detect_rs_param():
    """ eccman: test reedsolomon param detection """
    message = b("hello world")
    mesecc_orig = [104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 187, 161, 157, 88, 92, 175, 116, 251, 116]
    mesecc_orig_tampered = [104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 187, 161, 157, 88, 0, 175, 116, 251, 116]
    n = len(mesecc_orig)
    k = len(message)
    params = [n, k, 2, 0x187, 120]
    res = detect_reedsolomon_parameters(message, mesecc_orig)
    res2 = detect_reedsolomon_parameters(message, mesecc_orig_tampered)
    assert ("Hamming distance 0 (0=perfect match):\ngen_nb=%i prim=%i(%s) fcr=%i" % (params[2], params[3], hex(params[3]), params[4])) in res
    assert ("Hamming distance 1:\ngen_nb=%i prim=%i(%s) fcr=%i" % (params[2], params[3], hex(params[3]), params[4])) in res2
    res3 = detect_reedsolomon_parameters(message, [-1]*len(mesecc_orig), [3])
    assert "Parameters could not be automatically detected" in res3
    with assert_raises(ValueError) as cm:
        detect_reedsolomon_parameters([257, 0, 0], [0, 0, 0], c_exp=8)
    with assert_raises(ValueError) as cm:
        detect_reedsolomon_parameters([0, 0, 0], [257, 0, 0], c_exp=8)

def test_eccman_compute_ecc_params():
    """ eccman: test ecc params computation """
    class Hasher(object):
        """ Dummy Hasher """
        def __len__(self):
            return 32
    hasher = Hasher()
    assert compute_ecc_params(255, 0.5, hasher) == {'ecc_size': 127, 'hash_size': 32, 'message_size': 128}
    assert compute_ecc_params(255, 0.0, hasher) == {'ecc_size': 0, 'hash_size': 32, 'message_size': 255}
    assert compute_ecc_params(255, 1.0, hasher) == {'ecc_size': 170, 'hash_size': 32, 'message_size': 85}
    assert compute_ecc_params(255, 0.3, hasher) == {'ecc_size': 96, 'hash_size': 32, 'message_size': 159}
    assert compute_ecc_params(255, 0.7, hasher) == {'ecc_size': 149, 'hash_size': 32, 'message_size': 106}
    assert compute_ecc_params(255, 2.0, hasher) == {'ecc_size': 204, 'hash_size': 32, 'message_size': 51}
    assert compute_ecc_params(255, 10.0, hasher) == {'ecc_size': 243, 'hash_size': 32, 'message_size': 12}
    assert compute_ecc_params(140, 10.0, hasher) == {'ecc_size': 133, 'hash_size': 32, 'message_size': 7}

def test_eccman_codecs():
    """ eccman: test ecc generation and decoding """
    expected = [
        [206, 234, 144, 153, 141, 196, 170, 96, 62],
        [206, 234, 144, 153, 141, 196, 170, 96, 62],
        [206, 234, 144, 153, 141, 196, 170, 96, 62],
        [187, 161, 157, 88, 92, 175, 116, 251, 116]
    ]
    message = b("hello world")
    message_eras = b("h\x00ll\x00 world")
    message_noise = b("h\x00ll\x00 worla")
    n = 20
    k = 11
    for i in range(1,5):
        eccman = ECCMan(n, k, algo=i)
        ecc = bytearray(b(eccman.encode(message)))
        assert list(ecc) == expected[i-1]
        assert b(eccman.decode(message_eras, ecc)[0]) == message
        assert b(eccman.decode(message_eras, ecc, enable_erasures=True)[0]) == message
        assert b(eccman.decode(message_eras, ecc, enable_erasures=True, only_erasures=True)[0]) == message
        #eccman.decode(message_noise, ecc, enable_erasures=True, only_erasures=True)[0]
        assert eccman.check(message, ecc)
        assert not eccman.check(message_eras, ecc)
        assert "Reed-Solomon with polynomials in Galois field of characteristic" in eccman.description()
    # Unknown algorithm test
    with assert_raises(Exception) as cm:
        eccman = ECCMan(n, k, algo=-1)
    eccman = ECCMan(n, k, algo=1)
    eccman.algo = -1
    assert "No description for this ECC algorithm." in eccman.description()

def test_eccman_pad():
    """ eccman: test ecc padding """
    message = b("hello world")
    ecc = b(''.join([chr(x) for x in [206, 234, 144, 153, 141, 196, 170, 96, 62]]))
    # Oversize parameters compared to the message and ecc
    n = 22 # should be 20
    k = 13 # should be 11, but we add +2, which bytes we will pad onto the ecc and the decoding should still work!
    eccman = ECCMan(n, k, algo=3)
    # Test left padding (the input message)
    pmessage = eccman.pad(message)
    assert pmessage == [b('\x00\x00hello world'), b('\x00\x00')] # format: [padded_message, padonly]
    assert eccman.check(pmessage[0], ecc)
    # Test right padding (the ecc block)
    pecc = eccman.rpad(ecc, 11)
    assert pecc == [b('\xce\xea\x90\x99\x8d\xc4\xaa`>\x00\x00'), b('\x00\x00')]
    assert eccman.check(message, pecc[0])
    # Test decoding with both padding!
    assert eccman.check(pmessage[0], pecc[0])

def test_eccman_lpad_decoding():
    """ eccman: test ecc decoding when message needs left padding """
    message = b("hello world")
    ecc = b(''.join([chr(x) for x in [206, 234, 144, 153, 141, 196, 170, 96, 62]]))
    message_eras = b("h\x00ll\x00 world")
    # Oversize parameters compared to the message and ecc
    n = 22 # should be 20
    k = 13 # should be 11, but we add +2, which bytes we will pad onto the ecc and the decoding should still work!
    eccman = ECCMan(n, k, algo=3)
    # Test decoding with erasure when the message needs to be padded
    assert eccman.decode(message_eras, ecc, enable_erasures=True)

def test_eccman_rpad_decoding():
    """ eccman: test ecc decoding when right padding """
    message = b("hello world")
    ecc = b(''.join([chr(x) for x in [206, 234, 144, 153, 141, 196, 170, 96, 62]]))
    message_eras = b("h\x00ll\x00 world")
    # Oversize parameters compared to the message and ecc
    n = 20 # should be 20
    k = 11 # should be 11, but we add +2, which bytes we will pad onto the ecc and the decoding should still work!
    eccman = ECCMan(n, k, algo=3)
    # Test decoding with erasure when the message needs to be padded
    assert eccman.decode(message_eras, ecc, enable_erasures=True)
    assert eccman.decode(message_eras, ecc[:-2])
