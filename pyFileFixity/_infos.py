# -*- coding: utf-8 -*-

__author__ = 'Stephen Larroque'
__email__ = 'LRQ3000@gmail.com'

# Definition of the version number
version_info = 3, 0, 0  # major, minor, patch, extra

# Nice string for the version (mimic how IPython composes its version str)
__version__ = '-'.join(map(str, version_info)).replace('-', '.').strip('-')
