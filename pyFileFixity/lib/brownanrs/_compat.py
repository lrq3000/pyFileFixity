#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
