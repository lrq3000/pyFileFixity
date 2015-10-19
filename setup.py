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

# Get version from __init__.py
__version__ = None
version_file = os.path.join(os.path.dirname(__file__), '_infos.py')
for line in open(version_file).readlines():
    if (line.startswith('version_info') or line.startswith('__version__') or line.startswith('__author__') or line.startswith('__email__')):
        exec(line.strip())

# Python module configuration
setup(
    name = "PyFileFixity",
    version=__version__,
    description='Helping file fixity (long term storage of data) via redundant error correcting codes and hash auditing.',
    license='MIT License',
    author=__author__,
    author_email=__email__,
    url='https://github.com/lrq3000/pyFileFixity',
    maintainer=__author__,
    maintainer_email=__email__,
    platforms = ["any"],
    py_modules = ["pyfilefixity"],
    long_description = open("README.rst", "r").read(),
    classifiers=[  # Trove classifiers, see https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Environment :: Console',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Archiving',
        'Topic :: System :: Archiving :: Backup',
        'Topic :: System :: Monitoring',
        'Topic :: System :: Recovery Tools',
        'Topic :: Utilities',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
    ],
    keywords = 'file repair monitor change reed-solomon error correction',
    ext_modules = extensions,
)

# Use pypandoc to convert the Markdown readme into ReStructuredText for PyPi package generation
#import pypandoc
#converts markdown to reStructured
#z = pypandoc.convert('README','rst',format='markdown')
#writes converted file
#with open('README.rst','w') as outfile:
#    outfile.write(z)