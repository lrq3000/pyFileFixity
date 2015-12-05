#!/usr/bin/env python
#

import sys

class Tee(object):
    """ Redirect print output to the terminal as well as in a log file """

    def __init__(self, name=None, mode=None, nostdout=False):
        self.file = None
        self.nostdout = nostdout
        if not nostdout:
            self.__del__.im_func.stdout = sys.stdout
            self.stdout = self.__del__.im_func.stdout # The weakref proxy is to prevent Python, or yourself from deleting the self.files variable somehow (if it is deleted, then it will not affect the original file list). If it is not the case that this is being deleted even though there are more references to the variable, then you can remove the proxy encapsulation. http://stackoverflow.com/questions/865115/how-do-i-correctly-clean-up-a-python-object
            sys.stdout = self
        if name is not None and mode is not None:
            self.filename = name
            self.filemode = mode
            self.file = open(name, mode)

    def __del__(self):
        """ Restore stdout and close file when Tee is closed """
        self.flush() # commit all latest changes before exiting
        if not self.nostdout and hasattr(self.__del__.im_func, 'stdout'): sys.stdout = self.__del__.im_func.stdout
        if self.file: self.file.close()

    def write(self, data, end="\n", flush=True):
        """ Output data to stdout and/or file """
        if not self.nostdout:
            self.stdout.write(data+end)
        if self.file is not None:
            self.file.write(data+end)
        if flush:
            self.flush()

    def flush(self):
        """ Force commit changes to the file and stdout """
        if not self.nostdout:
            self.stdout.flush()
        if self.file is not None:
            self.file.flush()

    # def disable(self):
        # """ Temporarily disable Tee's redirection """
        # self.flush() # commit all latest changes before exiting
        # if not self.nostdout and hasattr(self, 'stdout'):
            # sys.stdout = self.stdout
            # self.stdout = None
        # if self.file:
            # self.file.close()
            # self.file = None

    # def enable(self):
        # """ Reenable Tee's redirection after being temporarily disabled """
        # if not self.nostdout and not self.stdout:
            # self.__del__.im_func.stdout = sys.stdout
            # self.stdout = self.__del__.im_func.stdout # The weakref proxy is to prevent Python, or yourself from deleting the self.files variable somehow (if it is deleted, then it will not affect the original file list). If it is not the case that this is being deleted even though there are more references to the variable, then you can remove the proxy encapsulation. http://stackoverflow.com/questions/865115/how-do-i-correctly-clean-up-a-python-object
            # sys.stdout = self
        # if not self.file and self.filename is not None and self.filemode is not None:
            # self.file = open(self.filename, self.filemode)
