# An empty setup.py is required for retrocompatibility with older versions of pip that do not support pyproject.toml-only projects, especially to install in editable mode, see: https://github.com/pypa/setuptools/issues/2816

from setuptools import setup
setup()  # necessary to have at least a setup() call, otherwise setuptools will complaint with an exception: `AssertionError: Multiple .egg-info directories found\nerror: subprocess-exited-with-error`
