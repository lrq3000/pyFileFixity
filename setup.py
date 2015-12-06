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
import shlex  # For Makefile parsing

# For Makefile parsing
try:    # pragma: no cover
    import ConfigParser
    import StringIO
except ImportError:    # pragma: no cover
    # Python 3 compatibility
    import configparser as ConfigParser
    import io as StringIO
import sys, subprocess


""" Makefile auxiliary functions """


def parse_makefile_aliases(filepath):
    '''
    Parse a makefile to find commands and substitute variables. Expects a
    makefile with only aliases and a line return between each command.

    Returns a dict, with a list of commands for each alias.
    '''

    # -- Parsing the Makefile using ConfigParser
    # Adding a fake section to make the Makefile a valid Ini file
    ini_str = '[root]\n'
    with open(filepath, 'r') as fd:
        ini_str = ini_str + fd.read().replace('@make ', '')
    ini_fp = StringIO.StringIO(ini_str)
    # Parse using ConfigParser
    config = ConfigParser.RawConfigParser()
    config.readfp(ini_fp)
    # Fetch the list of aliases
    aliases = config.options('root')

    # -- Extracting commands for each alias
    commands = {}
    for alias in aliases:
        # strip the first line return, and then split by any line return
        commands[alias] = config.get('root', alias).lstrip('\n').split('\n')

    # -- Commands substitution
    # Loop until all aliases are substituted by their commands:
    # Check each command of each alias, and if there is one command that is to
    # be substituted by an alias, try to do it right away. If this is not
    # possible because this alias itself points to other aliases , then stop
    # and put the current alias back in the queue to be processed again later.

    # Create the queue of aliases to process
    aliases_todo = commands.keys()
    # Create the dict that will hold the full commands
    commands_new = {}
    # Loop until we have processed all aliases
    while aliases_todo:
        # Pick the first alias in the queue
        alias = aliases_todo.pop(0)
        # Create a new entry in the resulting dict
        commands_new[alias] = []
        # For each command of this alias
        for cmd in commands[alias]:
            # Ignore self-referencing (alias points to itself)
            if cmd == alias:
                pass
            # Substitute full command
            elif cmd in aliases and cmd in commands_new:
                # Append all the commands referenced by the alias
                commands_new[alias].extend(commands_new[cmd])
            # Delay substituting another alias, waiting for the other alias to
            # be substituted first
            elif cmd in aliases and cmd not in commands_new:
                # Delete the current entry to avoid other aliases
                # to reference this one wrongly (as it is empty)
                del commands_new[alias]
                aliases_todo.append(alias)
                break
            # Full command (no aliases)
            else:
                commands_new[alias].append(cmd)
    commands = commands_new
    del commands_new

    # -- Prepending prefix to avoid conflicts with standard setup.py commands
    # for alias in commands.keys():
    #     commands['make_'+alias] = commands[alias]
    #     del commands[alias]

    return commands


def execute_makefile_commands(commands, alias, verbose=False):
    cmds = commands[alias]
    for cmd in cmds:
        # Parse string in a shell-like fashion
        # (incl quoted strings and comments)
        parsed_cmd = shlex.split(cmd, comments=True)
        # Execute command if not empty (ie, not just a comment)
        if parsed_cmd:
            if verbose:
                print("Running command: " + cmd)
            # Launch the command and wait to finish (synchronized call)
            subprocess.check_call(parsed_cmd)


""" Cython extensions """


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


""" Main setup.py config """


# Get version from __init__.py
__version__ = None
version_file = os.path.join(os.path.dirname(__file__), '_infos.py')
for line in open(version_file).readlines():
    if (line.startswith('version_info') or line.startswith('__version__') or line.startswith('__author__') or line.startswith('__email__')):
        exec(line.strip())


# Executing makefile commands if specified
if sys.argv[1].lower().strip() == 'make':
    # Filename of the makefile
    fpath = 'Makefile'
    # Parse the makefile, substitute the aliases and extract the commands
    commands = parse_makefile_aliases(fpath)

    # If no alias (only `python setup.py make`), print the list of aliases
    if len(sys.argv) < 3 or sys.argv[-1] == '--help':
        print("Shortcut to use commands via aliases. List of aliases:")
        for alias in sorted(commands.keys()):
            print("- " + alias)

    # Else process the commands for this alias
    else:
        arg = sys.argv[-1]
        # if unit testing, we do nothing (we just checked the makefile parsing)
        if arg == 'none':
            sys.exit(0)
        # else if the alias exists, we execute its commands
        elif arg in commands.keys():
            execute_makefile_commands(commands, arg, verbose=True)
        # else the alias cannot be found
        else:
            raise Exception("Provided alias cannot be found: make " + arg)
    # Stop the processing of setup.py here:
    # It's important to avoid setup.py raising an error because of the command
    # not being standard
    sys.exit(0)


""" Python package config """


# Python module configuration
setup(
    name = "pyFileFixity",
    version=__version__,
    description='Helping file fixity (long term storage of data) via redundant error correcting codes and hash auditing.',
    license='MIT License',
    author=__author__,
    author_email=__email__,
    url='https://github.com/lrq3000/pyFileFixity',
    maintainer=__author__,
    maintainer_email=__email__,
    platforms = ["any"],
    py_modules = [os.path.splitext(f)[0] for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.py')], # list all python files in current folder
    long_description = open("README.rst", "r").read(),
    classifiers=[  # Trove classifiers, see https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 5 - Production/Stable',
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
    #test_suite='nose.collector',
    #tests_require=['nose', 'coverage'],
)

# Use pypandoc to convert the Markdown readme into ReStructuredText for PyPi package generation
#import pypandoc
#converts markdown to reStructured
#z = pypandoc.convert('README','rst',format='markdown')
#writes converted file
#with open('README.rst','w') as outfile:
#    outfile.write(z)