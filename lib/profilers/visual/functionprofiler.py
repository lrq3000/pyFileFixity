#!/usr/bin/env python
#

#
# TODO:
# - implement cProfile or yappi, or use threading.setProfile and sys.setProfile, or implement one's own multi-threaded profiler:
# http://code.google.com/p/yappi/
# http://code.activestate.com/recipes/465831-profiling-threads/
# http://effbot.org/librarybook/sys.htm
#
#
# CHANGELOG:
# 2014-18-08 - v0.5.1 - lrq3000
#   * force refresh (flush) stdout after printing
#   * fixed runsnakerun
# 2012-11-12 - v0.5.0 - lrq3000
#   * cleaned the functions a bit and added a no timeout mode
# 2010-09-22 - v0.4.3 - lrq3000
#   * added error handling if profile and pstats libraries can't be found
# 2010-09-17 - v0.4.2 - lrq3000
#   * added an automatic calibration prior to profiling
# 2010-09-17 - v0.4.1 - lrq3000
#   * fixed import bug
# 2010-09-16 - v0.4 - lrq3000
#    * fallback to profile instead of cProfile : even if this pure python implementation is much slower, it at least work with threads (cProfile, alias hotshot, is not compatible with multi-threaded applications at the moment)
# 2010-09-09 - v0.3 - lrq3000
#    * workaround for a bug with cProfile
# 2010-09-08 - v0.2 - lrq3000
#    * added the parsestats, browsegui and browsenogui functions
#    * centralized runprofile here
# 2010-09-06 - v0.1 - lrq3000
#    * Initial version.

__author__  = 'lrq3000'
__version__ = '0.5.0'


noprofiler = False
try:
	import profile, pstats # using profile and not cProfile because cProfile does not support multi-threaded applications.
except:
	noprofiler = True

import sys, os
pathname = os.path.dirname(sys.argv[0])
sys.path.append(os.path.join(pathname))

from kthread import *
from profilebrowser import *


def runprofile(mainfunction, output, timeout = 0, calibrate=False):
    '''
    Run the functions profiler and save the result
    If timeout is greater than 0, the profile will automatically stops after timeout seconds
    '''
    if noprofiler == True:
            print('ERROR: profiler and/or pstats library missing ! Please install it (probably package named python-profile) before running a profiling !')
            return False
    # This is the main function for profiling
    def _profile():
        profile.run(mainfunction, output)
    print('=> RUNNING FUNCTIONS PROFILER\n\n'); sys.stdout.flush();
    # Calibrate the profiler (only use this if the profiler produces some funny stuff, but calibration can also produce even more funny stuff with the latest cProfile of Python v2.7! So you should only enable calibration if necessary)
    if calibrate:
        print('Calibrating the profiler...'); sys.stdout.flush();
        cval = calibrateprofile()
        print('Calibration found value : %s' % cval); sys.stdout.flush();
    print('Initializing the profiler...'); sys.stdout.flush();
    # Run in timeout mode (if the function cannot ends by itself, this is the best mode: the function must ends for the profile to be saved)
    if timeout > 0:
        pthread = KThread(target=_profile) # we open the function with the profiler, in a special killable thread (see below why)
        print('Will now run the profiling and terminate it in %s seconds. Results will be saved in %s' % (str(timeout), str(output))); sys.stdout.flush();
        print('\nCountdown:'); sys.stdout.flush();
        for i in range(0,5):
                print(str(5-i))
                sys.stdout.flush()
                time.sleep(1)
        print('0\nStarting to profile...'); sys.stdout.flush();
        pthread.start() # starting the thread
        time.sleep(float(timeout)) # after this amount of seconds, the thread gets killed and the profiler will end its job
        print('\n\nFinishing the profile and saving to the file %s' % str(output)); sys.stdout.flush();
        pthread.kill() # we must end the main function in order for the profiler to output its results (if we didn't launch a thread and just closed the process, it would have done no result)
    # Run in full length mode (we run the function until it ends)
    else:
        print("Running the profiler, please wait until the process terminates by itself (if you forcequit before, the profile won't be saved)")
        _profile()
    print('=> Functions Profile done !')
    return True

def calibrateprofile():
    '''
    Calibrate the profiler (necessary to have non negative and more exact values)
    '''
    pr = profile.Profile()
    calib = []
    crepeat = 10
    for i in range(crepeat):
            calib.append(pr.calibrate(10000))
    final = sum(calib) / crepeat
    profile.Profile.bias = final # Apply computed bias to all Profile instances created hereafter
    return final

def parseprofile(profilelog, out):
    '''
    Parse a profile log and print the result on screen
    '''
    file = open(out, 'w') # opening the output file
    print('Opening the profile in %s...' % profilelog)
    p = pstats.Stats(profilelog, stream=file) # parsing the profile with pstats, and output everything to the file

    print('Generating the stats, please wait...')
    file.write("=== All stats:\n")
    p.strip_dirs().sort_stats(-1).print_stats()
    file.write("=== Cumulative time:\n")
    p.sort_stats('cumulative').print_stats(100)
    file.write("=== Time:\n")
    p.sort_stats('time').print_stats(100)
    file.write("=== Time + cumulative time:\n")
    p.sort_stats('time', 'cum').print_stats(.5, 'init')
    file.write("=== Callees:\n")
    p.print_callees()
    file.write("=== Callers:\n")
    p.print_callers()
    #p.print_callers(.5, 'init')
    #p.add('fooprof')
    file.close()
    print('Stats generated and saved to %s.' % out)
    print('Everything is done. Exiting')

def browseprofile(profilelog):
    '''
    Browse interactively a profile log in console
    '''
    print('Starting the pstats profile browser...\n')
    try:
            browser = ProfileBrowser(profilelog)
            print >> browser.stream, "Welcome to the profile statistics browser. Type help to get started."
            browser.cmdloop()
            print >> browser.stream, "Goodbye."
    except KeyboardInterrupt:
            pass

def browseprofilegui(profilelog):
    '''
    Browse interactively a profile log in GUI using RunSnakeRun and SquareMap
    '''
    from runsnakerun import runsnake # runsnakerun needs wxPython lib, if it's not available then we can pass if we don't want a GUI. RunSnakeRun is only used for GUI visualisation, not for profiling (and you can still use pstats for console browsing)
    app = runsnake.RunSnakeRunApp(0)
    app.OnInit(profilelog)
    #app.OnInit()
    app.MainLoop()
