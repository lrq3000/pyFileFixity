#!/usr/bin/env python
#
# Easy Profiler
# Copyright (C) 2015 Larroque Stephen
#
# Licensed under the MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#------------------------------
#
# This script is similar to what has been done in a paper, albeit in a dumbed down version (since they could automatically check for corruption measures based on file format): Heydegger, Volker. "Analysing the impact of file formats on data integrity." Archiving Conference. Vol. 2008. No. 1. Society for Imaging Science and Technology, 2008.
# And another interesting paper by the same author: Heydegger, Volker. "Just one bit in a million: On the effects of data corruption in files." Research and Advanced Technology for Digital Libraries. Springer Berlin Heidelberg, 2009. 315-326.
# Errors are not evenly spread but rather block level (thus concentrated). Addis, Matthew, et al. "Reliable Audiovisual Archiving Using Unreliable Storage Technology and Services." (2009).
#

# Import necessary libraries
import lib.argparse as argparse
import os, sys


# Relative path to absolute
def fullpath(relpath):
    if (type(relpath) is object or type(relpath) is file):
        relpath = relpath.name
    return os.path.abspath(os.path.expanduser(relpath))


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    #==== COMMANDLINE PARSER ====

    #== Commandline description
    desc = '''Easy Profiler for pyFileFixity
Description: Provide an easy way to launch CPU/Memory profile with GUI support.
    '''
    ep = ''' '''

    #== Commandline arguments
    #-- Constructing the parser
    main_parser = argparse.ArgumentParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter)
    # Required arguments
    main_parser.add_argument('--script', metavar='script.py', type=str, nargs=1, required=True,
                        help='Path to the script to import and execute (the script must implement a main() function).')
    main_parser.add_argument('--profile_log', metavar='profile.log', type=str, nargs=1, required=False,
                        help='Path where to store the profile log.')
    main_parser.add_argument('--cpu', action='store_true', required=False, default=False,
                        help='CPU line-by-line profiler (pprofile.py).')
    main_parser.add_argument('--cpu_stack', action='store_true', required=False, default=False,
                        help='CPU stack (tree-like) profiler (pyinstrument.py).')
    main_parser.add_argument('--memory', action='store_true', required=False, default=False,
                        help='Memory line-by-line profiler (memory_profiler.py).')
    main_parser.add_argument('--gui', action='store_true', required=False, default=False,
                        help='GUI interface for the CPU line-by-line profiler (not ready for the memory profiler) using RunSnakeRun.')
    # Optional arguments

    #== Parsing the arguments
    args, args_rest = main_parser.parse_known_args(argv) # Storing all arguments to args

    #-- Set variables from arguments
    script = args.script[0]
    cpu = args.cpu
    memory = args.memory
    gui = args.gui
    cpu_stack = args.cpu_stack

    profile_log = None
    if args.profile_log:
        profile_log = fullpath(args.profile_log[0])
    
    if script.find('.') == -1:
        script = script + '.py'

    if not os.path.isfile(script):
        print("File does not exist: %s" % script)
    else:
        print("==== LAUNCHING PROFILING ====")
    
        scriptname = os.path.splitext(script)[0] # remove any extension to be able to import
        scriptmod = __import__(scriptname) # dynamic import

        if cpu:
            # Line-by-line CPU runtime profiling (pure python using pprofile)
            from lib.profilers.pprofile import pprofile
            # Load the profiler
            pprof = pprofile.Profile()
            # Launch experiment under the profiler
            args_rest = ' '.join(args_rest)
            with pprof:
                scriptmod.main(args_rest)
            # Print the result
            print("==> Profiling done.")
            if profile_log:
                pprof.dump_stats(profile_log)
            else:
                pprof.print_stats()
        elif memory:
            # Line-by-line memory profiler (pure python using memory_profiler)
            from lib.profilers.memory_profiler import memory_profiler
            # Load the memory profiler
            mprof = memory_profiler.LineProfiler()
            # Launch experiment under the memory profiler
            args_rest = ' '.join(args_rest)
            mpr = mprof(scriptmod.main)(args_rest)
            # Print results
            print("==> Profiling done.")
            if not mprof.code_map: # just to check that everything's alright
                print 'Error: the memory_profiler did not work! Please check that your are correctly calling mprof(func)(arguments)'
            else:
                if profile_log:
                    with open(profile_log, 'w') as pf:
                        memory_profiler.show_results(mprof, stream=pf)
                else:
                    print(memory_profiler.show_results(mprof, stream=None))
        elif gui:
            # Visual profiler with GUI (runsnakerun)
            # NOTE: you need wxPython to launch it
            from lib.profilers.visual.debug import runprofilerandshow
            if not profile_log: profile_log = 'profile.log' # a profile log is necessary to use the GUI because the profile will be generated separately, and then the GUI will read the file. File based communication is currently the only way to communicate with RunSnakeRun.
            args_rest = ' '.join(args_rest)
            runprofilerandshow('import '+scriptname+"\n"+scriptname+'.main', profile_log, argv=args_rest, calibrate=True)
            #runscriptprofilerandshow(script, profile_log, argv=args_rest, calibrate=True)
        elif cpu_stack:
            # Tree like cpu profiling
            from lib.profilers.pyinstrument import Profiler
            from lib.profilers.pyinstrument.profiler import SignalUnavailableError
            try:
                profiler = Profiler() # or if signal is not available on your system, use Profiler(use_signal=False), see below
            except SignalUnavailableError as e:
                profiler = Profiler(use_signal=False)
            profiler.start()
            scriptmod.main(args_rest)
            profiler.stop()
            print("==> Profiling done.")
            if profile_log:
                import codecs
                with codecs.open(profile_log, 'wb', encoding='utf8') as pf:
                    pf.write( profiler.output_text(unicode=True, color=True) )
            else:
                print(profiler.output_text(unicode=True, color=True))


# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":
    sys.exit(main())
