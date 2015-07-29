# See:
# https://docs.python.org/2/distutils/setupscript.html
# http://docs.cython.org/src/reference/compilation.html
# https://docs.python.org/2/extending/building.html
# http://docs.cython.org/src/userguide/source_files_and_compilation.html
try:
    from setuptools import setup
    from setuptools import Extension
except ImportError:
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
                        Extension('lib.reedsolomon.creedsolo', [os.path.join('lib', 'reedsolomon', 'creedsolo'+ext)]),
                    ]

if USE_CYTHON: extensions = cythonize(extensions)

setup(
    name = "PyFileFixity",
    ext_modules = extensions
)

# Use pypandoc to convert the Markdown readme into ReStructuredText for PyPi package generation
#import pypandoc
#converts markdown to reStructured
#z = pypandoc.convert('README','rst',format='markdown')
#writes converted file
#with open('README.rst','w') as outfile:
#    outfile.write(z)