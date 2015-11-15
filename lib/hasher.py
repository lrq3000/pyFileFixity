#!/usr/bin/env python
#
# Hash manager facade api
# Allows to easily use different kinds of hashing algorithms, size and libraries under one single class.
# Copyright (C) 2015 Larroque Stephen
#
# Licensed under the MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import hashlib
#import zlib

class Hasher(object):
    '''Class to provide a hasher object with various hashing algorithms. What's important is to provide the __len__ so that we can easily compute the block size of ecc entries. Must only use fixed size hashers for the rest of the script to work properly.'''
    
    known_algo = ["md5", "shortmd5", "shortsha256", "minimd5", "minisha256", "none"]
    __slots__ = ['algo', 'length']

    def __init__(self, algo="md5"):
        # Store the selected hashing algo
        self.algo = algo.lower()
        # Precompute length so that it's very fast to access it later
        if self.algo == "md5":
            self.length = 32
        elif self.algo == "shortmd5" or self.algo == "shortsha256":
            self.length = 8
        elif self.algo == "minimd5" or self.algo == "minisha256":
            self.length = 4
        elif self.algo == "none":
            self.length = 0
        else:
            raise NameError('Hashing algorithm %s is unknown!' % algo)

    def hash(self, mes):
        # use hashlib.algorithms_guaranteed to list algorithms
        if self.algo == "md5":
            return hashlib.md5(mes).hexdigest()
        elif self.algo == "shortmd5": # from: http://www.peterbe.com/plog/best-hashing-function-in-python
            return hashlib.md5(mes).hexdigest().encode('base64')[:8]
        elif self.algo == "shortsha256":
            return hashlib.sha256(mes).hexdigest().encode('base64')[:8]
        elif self.algo == "minimd5":
            return hashlib.md5(mes).hexdigest().encode('base64')[:4]
        elif self.algo == "minisha256":
            return hashlib.sha256(mes).hexdigest().encode('base64')[:4]
        elif self.algo == "none":
            return ''
        else:
            raise NameError('Hashing algorithm %s is unknown!' % self.algo)

    def __len__(self):
        return self.length