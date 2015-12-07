# -*- coding: utf-8 -*- 

# Distance - Utilities for comparing sequences
# Copyright (C) 2013 Michaël Meyer

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


import os, sys, ast, _ast, re
from distutils.core import setup, Extension

this_dir = os.path.dirname(os.path.abspath(__file__))
pkg_dir  = os.path.join(this_dir, "distance")
cpkg_dir  = os.path.join(this_dir, "cdistance")

ctypes = ["unicode", "byte", "array"]

cfunctions = {
	"levenshtein": ["levenshtein", "nlevenshtein"],
	"hamming": ["hamming"],
	"lcsubstrings": ["lcsubstrings"],
	"fastcomp": ["fastcomp"],
}

sequence_compare = """\
#define SEQUENCE_COMPARE(s1, i1, s2, i2) \\
(PyObject_RichCompareBool( \\
	PySequence_Fast_GET_ITEM((s1), (i1)), \\
	PySequence_Fast_GET_ITEM((s2), (i2)), \\
	Py_EQ) \\
)
"""

def make_c_doc():
	buff = []
	py_sources = [f for f in os.listdir(pkg_dir) if f.endswith('.py')]
	for file in py_sources:
		with open(os.path.join(pkg_dir, file)) as f:
			content = f.read()
		tree = ast.parse(content)
		for doc_string in parse_tree(tree, content):
			buff.append(doc_string)
	join_str = 2 * '\n'
	return join_str.join(buff) + '\n'


def parse_tree(tree, content):
	for node in ast.iter_child_nodes(tree):
		if not isinstance(node, _ast.FunctionDef):
			continue
		doc_string = ast.get_docstring(node)
		if not doc_string:
			continue
		func_def = re.findall("def\s%s\s*(.+?)\s*:" % node.name, content)
		assert func_def and len(func_def) == 1
		func_def = node.name + func_def[0] + 2 * '\\n\\\n'
		doc_string = doc_string.replace('\n', '\\n\\\n').replace('"', '\\"')
		doc_string = doc_string.replace('\n' + 8 * ' ', '\n' + 4 * ' ')
		doc_string = '#define %s_doc \\\n"%s%s"\n' % (node.name, func_def, doc_string)
		yield doc_string


def format_header():
	yield sequence_compare
	for cfile, cfuncs in cfunctions.items():
		for ctype in ctypes:
			if ctype == "array":
				yield("#define SEQUENCE_COMP SEQUENCE_COMPARE")
			yield('#define unicode %(type)s' % dict(type=ctype))
			for cfunc in cfuncs:
				yield("#define %(function)s %(tcode)s%(function)s" % dict(function=cfunc, tcode=ctype[0]))
			yield('#include "%(file)s.c"' % dict(file=cfile))
			yield("#undef unicode")
			for cfunc in cfuncs:
				yield("#undef %(function)s" % dict(function=cfunc))
			if ctype == "array":
				yield("#undef SEQUENCE_COMP")
			yield("")


def prepare():
	with open(os.path.join(cpkg_dir, "includes.h"), "w") as f:
		f.write(make_c_doc())
		f.write(4 * '\n')
		f.write('\n'.join(format_header()))


args = sys.argv[1:]
if "prepare" in args:
	prepare()
	sys.exit()

if "--with-c" in args:
	args.remove("--with-c")
	ext_modules = [Extension('distance.cdistance', sources=["cdistance/distance.c"])]
else:
	sys.stderr.write("notice: no C support available\n")
	ext_modules = []

with open(os.path.join(this_dir, "README.md")) as f:
    long_description = f.read()

setup (
    name = 'Distance',
    version = '0.1.3',
    description = 'Utilities for comparing sequences',
    long_description = long_description,
    author='Michaël Meyer',
    author_email='michaelnm.meyer@gmail.com',
    url='https://github.com/doukremt/distance',
    ext_modules = ext_modules,
    script_args = args,
    packages = ['distance'],
    classifiers=(
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: C',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.3',
    )
)
