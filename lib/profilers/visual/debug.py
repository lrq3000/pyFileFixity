#!/usr/bin/env python

import os, sys, time

# add current script path libs
#pathname = os.path.dirname(sys.argv[0])
#sys.path.insert(0, os.path.join(pathname, 'lib', 'debug'))

pathname = os.path.dirname(os.path.realpath(__file__))
#sys.path.append(os.path.join(pathname, 'lib', 'debug'))
sys.path.append(pathname)

# import functools, used to preserve the correct func.__name__
import functools

# import some functions profiler functions and GUI
import functionprofiler
# Note: as an alternative, you can also use pyprof2calltree and kcachegrind to get a lot more informations and interactive call graph

# import profilehooks lib
from profilehooks import profile

# import memory profiler line by line
from memory_profiler import profile as memoryprofile_linebyline


#### NON DECORATOR FUNCTIONS ####
#################################

def startmemorytracker():
    from pympler import tracker
    tr = tracker.SummaryTracker()
    return tr

def runprofilerandshow(funcname, profilepath, argv='', *args, **kwargs):
    '''
    Run a functions profiler and show it in a GUI visualisation using RunSnakeRun
    Note: can also use calibration for more exact results
    '''
    functionprofiler.runprofile(funcname+'(\''+argv+'\')', profilepath, *args, **kwargs)
    print 'Showing profile (windows should open in the background)'; sys.stdout.flush();
    functionprofiler.browseprofilegui(profilepath)




#### DECORATOR FUNCTIONS ####
#############################

# @profile: use profilehooks to profile functions
# @profileit: profile using python's profile (works with threads)
# @showprofile: show the functions profile in a nice GUI using RunSnakeRun (alternative: using the generated profile log files you can use pyprof2calltree and kcachegrind to get a lot more informations and interactive call graph)
# @memorytrack: use Pympler to track and show memory usage (only console, no GUI)
#@callgraph: save the call graph in text format and image (if GraphViz is available, more specifically the dot program)
#@profile_linebyline: profile a function with line by line CPU consumption (using line_profiler, need to install it because it is compiled in C)
#@memoryprofile_linebyline: memory profile a function with line by line memory consumption (using memory_profiler, needs psutils on Windows)

# eg:
# @showprofile
# @profileit
# def func(): ...

def memorytrack(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from pympler import tracker
        tr = tracker.SummaryTracker()
        func(*args, **kwargs)
        tr.print_diff()
    return wrapper

def profileit(func):
    import profile
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        #datafn = func.__name__ + ".profile" # Name the data file sensibly
        datafn = 'profile.log'
        prof = profile.Profile()
        retval = prof.runcall(func, *args, **kwargs)
        prof.dump_stats(datafn)
        return retval

    return wrapper

def profileit_log(log):
    import profile
    def inner(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            prof = profile.Profile()
            retval = prof.runcall(func, *args, **kwargs)
            # Note use of name from outer scope
            prof.dump_stats(log)
            return retval
        return wrapper
    return inner

def showprofile(func):
    profilepath = 'profile.log'
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func(*args, **kwargs)
        functionprofiler.browseprofilegui(profilepath)
    return wrapper

def callgraph(func):
    ''' Makes a call graph
    Note: be sure to install GraphViz prior to printing the dot graph!
    '''
    import pycallgraph
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        pycallgraph.start_trace()
        func(*args, **kwargs)
        pycallgraph.save_dot('callgraph.log')
        pycallgraph.make_dot_graph('callgraph.png')
        #pycallgraph.make_dot_graph('callgraph.jpg', format='jpg', tool='neato')
    return wrapper

def profile_linebyline(func):
    import line_profiler
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        prof = line_profiler.LineProfiler()
        val = prof(func)(*args, **kwargs)
        prof.print_stats()
        return val
    return wrapper


# Some debug testing here
if __name__ == '__main__':

    @showprofile
    @profileit
    #@memorytrack
    #@callgraph
    #@profile
    #@memoryprofile_linebyline
    #@profile_linebyline
    def testcaptcha():
        import captchagenerator

        captcha = captchagenerator.CaptchaGenerator(True, True, debugPng=True, debug=False, nbElem=10, modelsPath='bammodels', windowWidth='320', windowHeight='240')

        #captcha.renderCaptcha('solmasks', 'solmasks')
        captcha.renderCaptchaMulti(4, 'solmasks', 'solmasks')

        #time.sleep(20)

    #@memoryprofile_linebyline
    #@profile_linebyline
    def test_1():
        a = [1] * (10 ** 6)
        b = [2] * (2 * 10 ** 7)
        del b

        for i in range(2):
            a = [1] * (10 ** 6)
            b = [2] * (2 * 10 ** 7)
            del b
        return a

    # Test 1
    #runprofilerandshow('testcaptcha', 'profile.log')

    # Test 2
    testcaptcha()

    # Test 3
    #test_1()
