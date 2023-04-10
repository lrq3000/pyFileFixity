#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

try: # compatibility with Python 3+
    _range = xrange
except NameError:
    _range = range

try:
    from cStringIO import StringIO
    _StringIO = StringIO
except (ImportError, NameError): #python3.x
    from io import StringIO
    _StringIO = StringIO

try:
    from itertools import izip
    _izip = izip
except ImportError:  #python3.x
    _izip = zip

try:
    _str = basestring
except NameError:
    _str = str

if sys.version_info < (3,):
    def b(x):
        return x
else:
    import codecs
    def b(x):
        if isinstance(x, _str):
            return codecs.latin_1_encode(x)[0]
        else:
            return x

if sys.version_info < (3,):
    import io
    def _open_csv(x, mode='r'):
        return io.open(x, mode+'b')  # on Py3, io.open() is the same as open(), see: https://stackoverflow.com/questions/5250744/difference-between-open-and-codecs-open-in-python
else:
    def _open_csv(x, mode='r'):
        return open(x, mode+'t', newline='', encoding='utf-8')  # for csv module, open() mode needed to be binary for Python 2, but on Py3 it needs to be text mode, no binary! https://stackoverflow.com/a/34283957/1121352

if sys.version_info < (3,):
    def _ord(x):
        return ord(x)
else:
    def _ord(x):
        if isinstance(x, int):
            return x
        else:
            return ord(x)

if sys.version_info < (3,):
    def _bytes(x):
        return bytes(x)
else:
    def _bytes(x):
        if isinstance(x, (bytes, bytearray)):
            return x
        else:
            return bytes(x, 'latin-1')

try:
    from itertools import izip
    _izip = izip
except ImportError:
    _izip = zip
