# IMPORTANT: to be compatible with `python setup.py make alias`, you must make
# sure that you only put one command per line, and ALWAYS put a line return
# after an alias and before a command, eg:
#
#```
#all:
#	test
#	install
#test:
#	nosetest
#install:
#	python setup.py install
#    ```

testsetup:
	python setup.py check --restructuredtext --strict
	python setup.py make none

installdev:
	python setup.py develop --uninstall
	python setup.py develop

install:
	python setup.py install

build_cython:
	python setup.py build_ext --inplace

build:
	python setup.py sdist --formats=gztar,zip bdist_wininst
	python setup.py sdist bdist_wheel

pypimeta:
	python setup.py register

pypi:
	twine upload dist/*

none:
	none # used for unit testing
