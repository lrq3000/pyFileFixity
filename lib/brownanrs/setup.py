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
                        Extension('cff', [os.path.join('cff'+ext)]),
                        Extension('cpolynomial', [os.path.join('cpolynomial'+ext)]),
                    ]

if USE_CYTHON: extensions = cythonize(extensions)

setup(
    name = "Brownan-Universal-Reed-Solomon",
    ext_modules = extensions
)