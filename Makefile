# Makefile like config file for py-make
# To use: `pip install py-make`
# then calle `pymake <command>`
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
# CRITICAL NOTE: if you get a "FileNotFoundError" exception when trying to call @+python or @+make, then it is because you used spaces instead of a hard TAB character to indent! TODO: bugfix this. It happens only for @+ commands and for those after the first command (if the @+ command with spaces as indentation is the first and only statement in a command, it works!)

help:
	@+make -p

alltests:
	@+make testcoverage
	@+make testsetup

all:
	@make alltests
	@make build

prebuildclean:
	@+python -c "import shutil; shutil.rmtree('build', True)"
	@+python -c "import shutil; shutil.rmtree('dist', True)"
	@+python -c "import shutil; shutil.rmtree('pyFileFixity.egg-info', True)"  # very important to delete egg-info before any new build or pip install, otherwise may cause an error that multiple egg-info folders are present, or it may build using old definitions

coverclean:
	@+python -c "import os; os.remove('.coverage') if os.path.exists('.coverage') else None"
	@+python -c "import shutil; shutil.rmtree('__pycache__', True)"
	@+python -c "import shutil; shutil.rmtree('tests/__pycache__', True)"

test:
	#tox --skip-missing-interpreters
    pytest

testnose:
    # Only for Py2
	nosetests pyFileFixity/tests/ -d -v

testpyproject:
	validate-pyproject pyproject.toml -v

testsetuppost:
	twine check "dist/*"
	rstcheck README.rst

testcoverage:
	@+make coverclean
	#nosetests pyFileFixity/tests/ --with-coverage --cover-package=pyFileFixity -d -v  # Py2 only
	coverage run --branch -m pytest pyFileFixity -v
	coverage report -m

installdev:
	@+make prebuildclean
	# Should work for both Py2 and Py3, --editable option and isolation builds work with both pyproject.toml and setup.cfg
	@+python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple --upgrade --editable .[test,testmeta] --verbose --use-pep517

installdevpy2:
	@+make prebuildclean
	@+python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple --upgrade --editable .[test] --verbose --use-pep517

install:
	@+make prebuildclean
	@+python -m pip install --upgrade . --verbose --use-pep517

build:
	# requires `pip install build`
	@+make prebuildclean
	@+make testpyproject
	@+python -sBm build  # do NOT use the -w flag, otherwise only the wheel will be built, but we need sdist for source distros such as Debian and Gentoo!
	@+make testsetuppost

buildpy2:
	# Py2 only
	# requires `pip install build`
	@+make prebuildclean
	@+python -sBm build  # do NOT use the -w flag, otherwise only the wheel will be built, but we need sdist for source distros such as Debian and Gentoo!
	@+make testsetuppost

buildwheelhouse:
	cibuildwheel --platform auto

upload:
	twine upload dist/*

buildupload:
	@+make testsetup
	@+make build
	@+make pypimeta
	@+make pypi
