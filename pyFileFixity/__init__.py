# -*- coding: utf-8 -*-

import os, json

__version__ = None
version_file = os.path.join(os.path.dirname(__file__), '_infos.json')
with open(version_file, 'r') as f:
    _infos = json.load(f)

__author__ = _infos['author']
__email__ = _infos['email']
__version__ = _infos['version']
__all__ = ['__author__', '__email__', '__version__']
