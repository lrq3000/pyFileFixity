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

alltests:
	@make testcoverage
	@make testsetup

all:
	@make alltests
	@make build

test:
	tox --skip-missing-interpreters

testnose:
	nosetests tests/ -d -v

testsetup:
	python setup.py check --restructuredtext --strict
	python setup.py make none

testcoverage:
	rm -f .coverage  # coverage erase
	nosetests tests/ --with-coverage --cover-package=pyFileFixity -d -v

installdev:
	python setup.py develop --uninstall
	python setup.py develop

install:
	python setup.py install

build_cython:
	python setup.py build_ext --inplace

build:
	python -c "import shutil; shutil.rmtree('build', True)"
	python -c "import shutil; shutil.rmtree('dist', True)"
	python -c "import shutil; shutil.rmtree('pyFileFixity.egg-info', True)"
	python setup.py sdist --formats=gztar,zip bdist_wininst
	python setup.py sdist bdist_wheel

pypimeta:
	python setup.py register

pypi:
	twine upload dist/*

buildupload:
	@make testsetup
	@make build
	@make pypimeta
	@make pypi

none:
	# used for unit testing
