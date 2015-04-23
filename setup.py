# See:
# https://docs.python.org/2/distutils/setupscript.html
# http://docs.cython.org/src/reference/compilation.html
# https://docs.python.org/2/extending/building.html
# http://docs.cython.org/src/userguide/source_files_and_compilation.html
from distutils.core import setup
from distutils.extension import Extension
import os

try:
    from Cython.Build import cythonize
    USE_CYTHON = True
except ImportError:
    USE_CYTHON = False

ext = '.pyx' if USE_CYTHON else '.c'

extensions = [
                        Extension('lib.brownanrs.cff', [os.path.join('lib', 'brownanrs', 'cff'+ext)]),
                        Extension('lib.brownanrs.cpolynomial', [os.path.join('lib', 'brownanrs', 'cpolynomial'+ext)]),
                    ]

if USE_CYTHON: extensions = cythonize(extensions)

setup(
    name = "PyFileFixity",
    ext_modules = extensions
)