#!/usr/bin/env python

import os
import fnmatch

class GlobDirectoryWalker:

    # a forward iterator that traverses a directory tree
    def __init__(self, directory, pattern="*"):
        self.stack = [directory]
        self.pattern = pattern
        self.files = []
        self.index = 0

    def __getitem__(self, index):
        while 1:
            try:
                file = self.files[self.index]
                self.index = self.index + 1
            except IndexError:
                # pop next directory from stack
                self.directory = self.stack.pop()
                self.files = os.listdir(self.directory)
                self.index = 0
            else:
                # got a filename
                fullname = os.path.join(self.directory, file)
                if os.path.isdir(fullname) and not os.path.islink(fullname):
                    self.stack.append(fullname)
                if fnmatch.fnmatch(file, self.pattern):
                    return fullname

def pycCleanup(directory,path,filext='pyc'):
    for filename in directory:
        if     filename[-3:] == filext:
            print '- ' + filename
            os.remove(path+os.sep+filename)
        elif os.path.isdir(path+os.sep+filename):
            pycCleanup(os.listdir(path+os.sep+filename),path+os.sep+filename)

def cleanup1(filext='pyc'):
    directory = os.listdir('.')
    print('Deleting .%s files recursively in %s.' % (filext, str(directory)))
    pycCleanup(directory,'.',filext)

def cleanup2(filext='pyc'):
    for file in GlobDirectoryWalker(".", "*."+filext):
        print file
        os.remove(file)

    print "After..."
    for file in GlobDirectoryWalker(".", "*."+filext):
        print file

if __name__ == '__main__':
    cleanup1()