#!/usr/bin/env python
#

import sys

# Redirect print output to the terminal as well as in a log file
class Tee(object):
    def __init__(self, name=None, mode=None):
        self.file = None
        self.__del__.im_func.stdout = sys.stdout
        self.stdout = self.__del__.im_func.stdout # The weakref proxy is to prevent Python, or yourself from deleting the self.files variable somehow (if it is deleted, then it will not affect the original file list). If it is not the case that this is being deleted even though there are more references to the variable, then you can remove the proxy encapsulation. http://stackoverflow.com/questions/865115/how-do-i-correctly-clean-up-a-python-object
        if name is not None and mode is not None:
            self.file = open(name, mode)
            sys.stdout = self
    def __del__(self):
        if hasattr(self.__del__.im_func, 'stdout'): sys.stdout = self.__del__.im_func.stdout
        if self.file: self.file.close()
    def write(self, data):
        self.stdout.write(data+"\n")
        if self.file is not None:
            self.file.write(data+"\n")
            self.file.flush()
    def flush(self):
        self.stdout.flush()
        if self.file is not None:
            self.file.flush()
