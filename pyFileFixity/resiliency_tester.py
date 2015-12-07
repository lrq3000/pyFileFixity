#!/usr/bin/env python
#
# Resiliency tester
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
#=================================
#                 Resiliency Tester
#                by Stephen Larroque
#                      License: MIT
#              Creation date: 2015-11-28
#=================================
#

from __future__ import division

from pyFileFixity import __version__

# Include the lib folder in the python import path (so that packaged modules can be easily called, such as gooey which always call its submodules via gooey parent module)
import sys, os
thispathname = os.path.dirname(__file__)
sys.path.append(os.path.join(thispathname, 'lib'))

# Import necessary libraries
from lib._compat import _StringIO
import ConfigParser
import subprocess # to execute commands
import itertools
from lib.aux_funcs import recwalk, path2unix, fullpath, is_dir_or_file, is_dir, is_file, fullpath, copy_any, create_dir_if_not_exist, remove_if_exist
import lib.argparse as argparse
import datetime, time
import lib.tqdm as tqdm
#import operator # to get the max out of a dict
import csv # to process the database file from rfigc.py
import shlex # for string parsing as argv argument to main(), unnecessary otherwise
from lib.tee import Tee # Redirect print output to the terminal as well as in a log file
from collections import OrderedDict
#import pprint # Unnecessary, used only for debugging purposes



#***********************************
#     AUXILIARY FUNCTIONS
#***********************************

######## Config parsing and command execution ########

def parse_configfile(filepath):
    '''
    Parse a makefile to find commands and substitute variables. Expects a
    makefile with only aliases and a line return between each command.

    Returns a dict, with a list of commands for each alias.
    '''

    # -- Parsing the Makefile using ConfigParser
    # Adding a fake section to make the Makefile a valid Ini file
    ini_str = '[root]\n'
    if not hasattr(filepath, 'read'):
        fd = open(filepath, 'r')
    else:
        fd = filepath
    ini_str = ini_str + fd.read().replace('\t@', '\t').\
        replace('\t+', '\t').replace('\tmake ', '\t')
    if fd != filepath: fd.close()
    ini_fp = _StringIO(ini_str)
    # Parse using ConfigParser
    config = ConfigParser.RawConfigParser()
    config.readfp(ini_fp)
    # Fetch the list of aliases
    aliases = config.options('root')

    # -- Extracting commands for each alias
    commands = {}
    for alias in aliases:
        # strip the first line return, and then split by any line return
        commands[alias] = config.get('root', alias).lstrip('\n').split('\n')
    return commands

def get_filename_no_ext(filepath):
    return os.path.splitext(os.path.basename(filepath))[0]

def interpolate_dict(s, interp_args={}):
    # String interpolate the command to fill in the variables if necessary
    return s.format(**interp_args)

def execute_command(cmd, ptee=None, verbose=False):  # pragma: no cover
    # Parse string in a shell-like fashion
    # (incl quoted strings and comments)
    parsed_cmd = shlex.split(cmd, comments=True)
    # Execute command if not empty (ie, not just a comment)
    if parsed_cmd:
        if verbose:
            print("Running command: " + cmd)
        #if ptee: ptee.disable()
        if parsed_cmd[0].lower().startswith('python'):
            mod = import_module(get_filename_no_ext(parsed_cmd[1]))
            if mod and hasattr(mod, 'main'):
                mod.main(parsed_cmd[2:])
            else:
                return subprocess.check_call(parsed_cmd)
        else:
            # Launch the command and wait to finish (synchronized call)
            return subprocess.check_call(parsed_cmd)
        #if ptee: ptee.enable()

######## Diff functions ########

def diff_bytes_files(path1, path2, blocksize=65535, startpos1=0, startpos2=0):
    """ Compare two files byte-wise, and return the total number of differing bytes """
    diff_count = 0
    total_size = 0
    with open(path1, 'rb') as f1, open(path2, 'rb') as f2:
        buf1 = 1
        buf2 = 1
        f1.seek(startpos1)
        f2.seek(startpos2)
        while 1:
            buf1 = f1.read(blocksize)
            buf2 = f2.read(blocksize)
            if (buf1 and not buf2) or (buf2 and not buf1):
                # Reached end of file or the content is different, then add the rest of the other file as a difference
                size_remaining = 0
                if not buf2:
                    curpos = f1.tell()
                    size_remaining = f1.fstat(f1.fileno()).st_size - curpos - len(buf1)
                elif not buf1:
                    curpos = f2.tell()
                    size_remaining = f2.fstat(f2.fileno()).st_size - curpos - len(buf2)
                diff_count += size_remaining
                total_size += size_remaining
                break
            elif (not buf1 and not buf2):
                # End of file for both files
                break
            else:
                for char1, char2 in itertools.izip(buf1, buf2):
                    if char1 != char2:
                        diff_count += 1
                    total_size += 1
    return diff_count, total_size

def diff_bytes_dir(dir1, dir2):
    total_diff = 0
    total_size = 0
    for dirpath, filepath in recwalk(dir1):
        filepath1 = os.path.join(dirpath, filepath)
        relpath = os.path.relpath(filepath1, dir1)
        filepath2 = os.path.join(dir2, relpath)
        if not os.path.exists(filepath2):
            fsize = os.stat(filepath1).st_size
            total_diff += fsize
            total_size += fsize
        else:
            fdiff, fsize = diff_bytes_files(filepath1, filepath2)
            total_diff += fdiff
            total_size += fsize
    return total_diff, total_size

def diff_count_files(path1, path2, blocksize=65535, startpos1=0, startpos2=0):
    """ Return True if both files are identical, False otherwise """
    flag = True
    with open(path1, 'rb') as f1, open(path2, 'rb') as f2:
        buf1 = 1
        buf2 = 1
        f1.seek(startpos1)
        f2.seek(startpos2)
        while 1:
            buf1 = f1.read(blocksize)
            buf2 = f2.read(blocksize)
            if buf1 != buf2 or (buf1 and not buf2) or (buf2 and not buf1):
                # Reached end of file or the content is different, then return false
                flag = False
                break
            elif (not buf1 and not buf2):
                # End of file for both files
                break
    return flag
    #return filecmp.cmp(path1, path2, shallow=False)  # does not work on Travis

def diff_count_dir(dir1, dir2):
    diff_count = 0
    total_count = 0
    for dirpath, filepath in recwalk(dir1):
        filepath1 = os.path.join(dirpath, filepath)
        relpath = os.path.relpath(filepath1, dir1)
        filepath2 = os.path.join(dir2, relpath)
        if not os.path.exists(filepath2):
            diff_count += 1
        else:
            if not diff_count_files(filepath1, filepath2):
                diff_count += 1
        total_count += 1
    return diff_count, total_count

######## Stats functions ########

def compute_repair_power(new_error, old_error):
    if old_error != 0.0:
        return (1 - (new_error / old_error)) * 100
    else:
        return new_error

def compute_diff_stats(orig, dir1, dir2):
    stats = OrderedDict()
    stats["diff_bytes"] = diff_bytes_dir(orig, dir2)
    stats["diff_count"] = diff_count_dir(orig, dir2)
    stats["diff_bytes_prev"] = diff_bytes_dir(dir1, dir2)
    stats["diff_count_prev"] = diff_count_dir(dir1, dir2)
    stats["error"] = stats["diff_bytes"][0] / stats["diff_bytes"][1] * 100
    stats["repair_power"] = 0 # can only be defined when compared to the previous stage's stats
    return stats

def compute_all_diff_stats(commands, origpath, tamperdir, repairdir, finalrepairdir):
    stats = OrderedDict() # keep order just to more easily print the stats aftewards

    # compute diff for each steps:
    # - origpath/tampered
    stats["tamper"] = compute_diff_stats(origpath, origpath, tamperdir)

    # - tampered/result0,1,... in loop
    indir = tamperdir
    for i in xrange(len(commands["repair"])):
        outdir = "%s%i" % (repairdir, i)
        stats["repair%i"%i] = compute_diff_stats(origpath, indir, outdir)
        if i == 0:
            stats["repair0"]["repair_power"] = compute_repair_power(stats["repair0"]["error"], stats["tamper"]["error"])
        else:
            stats["repair%i"%i]["repair_power"] = compute_repair_power(stats["repair%i"%i]["error"], stats["repair%i"%(i-1)]["error"])
        indir = outdir

    # - final diff origpath/tampered + tampered/finalresult
    stats["final"] = compute_diff_stats(origpath, origpath, finalrepairdir)
    stats["final"]["repair_power"] = compute_repair_power(stats["final"]["error"], stats["tamper"]["error"])

    return stats

def pretty_print_stats(stat):  # pragma: no cover
    out = ''
    for key, value in stat.iteritems():
        if key == 'diff_bytes':
            out += "\t- Differing bytes from original: %i/%i\n" % (value[0], value[1])
        elif key == 'diff_bytes_prev':
            out += "\t- Differing bytes from previous stage: %i/%i\n" % (value[0], value[1])
        elif key == 'diff_count':
            out += "\t- Differing files from original: %i/%i\n" % (value[0], value[1])
        elif key == 'diff_count_prev':
            out += "\t- Differing files from previous stage: %i/%i\n" % (value[0], value[1])
        elif key == 'error':
            out += "\t- Error rate (from original): %g\n" % value
        elif key == 'repair_power':
            out += "\t- Repair power (from original): %g\n" % value
        else:
            out += "\t- %s: %s\n" % (key, value)
    return out

def stats_running_average(stats, new_stats, weight):
    """ Compute the running average between two stats dictionaries """
    def running_average(old, new, weight):
        return (old*weight + new) / (weight+1)

    nstats = {}
    for stage in stats.iterkeys():
        if stage in new_stats:
            nstats[stage] = {}
            for key in stats[stage].iterkeys():
                if key in new_stats[stage]:
                    # List
                    if isinstance(stats[stage][key], (list, tuple)):
                        nstats[stage][key] = [running_average(x, y, weight) for x,y in itertools.izip(stats[stage][key], new_stats[stage][key])]
                        #nstats[stage][key] = [[x, y] for x,y in itertools.izip(stats[stage][key], new_stats[stage][key])]

                    # Scalar
                    elif not hasattr(stats[stage][key], '__len__') and (not isinstance(stats[stage][key], basestring)):
                        nstats[stage][key] = running_average(stats[stage][key], new_stats[stage][key], weight)

    return nstats

######## Helper functions (importing, path construction, etc.) ########

def import_module(module_name):  # pragma: no cover
    ''' Reliable import, courtesy of Armin Ronacher '''
    try:
        __import__(module_name)
    except ImportError:
        exc_type, exc_value, tb_root = sys.exc_info()
        tb = tb_root
        while tb is not None:
            if tb.tb_frame.f_globals.get('__name__') == module_name:
                raise exc_type, exc_value, tb_root
            tb = tb.tb_next
        return None
    return sys.modules[module_name]

def get_dbfile(dbdir, id):
    return fullpath(os.path.join(dbdir, 'db%i' % id))


#***********************************
#        GUI AUX FUNCTIONS
#***********************************

# Try to import Gooey for GUI display, but manage exception so that we replace the Gooey decorator by a dummy function that will just return the main function as-is, thus keeping the compatibility with command-line usage
try:  # pragma: no cover
    import lib.gooey as gooey
except ImportError as exc:
    # Define a dummy replacement function for Gooey to stay compatible with command-line usage
    class gooey(object):  # pragma: no cover
        def Gooey(func):
            return func
    # If --gui was specified, then there's a problem
    if len(sys.argv) > 1 and sys.argv[1] == '--gui':  # pragma: no cover
        print('ERROR: --gui specified but an error happened with lib/gooey, cannot load the GUI (however you can still use this script in commandline). Check that lib/gooey exists and that you have wxpython installed. Here is the error: ')
        raise(exc)

def conditional_decorator(flag, dec):  # pragma: no cover
    def decorate(fn):
        if flag:
            return dec(fn)
        else:
            return fn
    return decorate

def check_gui_arg():  # pragma: no cover
    '''Check that the --gui argument was passed, and if true, we remove the --gui option and replace by --gui_launched so that Gooey does not loop infinitely'''
    if len(sys.argv) > 1 and sys.argv[1] == '--gui':
        # DEPRECATED since Gooey automatically supply a --ignore-gooey argument when calling back the script for processing
        #sys.argv[1] = '--gui_launched' # CRITICAL: need to remove/replace the --gui argument, else it will stay in memory and when Gooey will call the script again, it will be stuck in an infinite loop calling back and forth between this script and Gooey. Thus, we need to remove this argument, but we also need to be aware that Gooey was called so that we can call gooey.GooeyParser() instead of argparse.ArgumentParser() (for better fields management like checkboxes for boolean arguments). To solve both issues, we replace the argument --gui by another internal argument --gui_launched.
        return True
    else:
        return False

def AutoGooey(fn):  # pragma: no cover
    '''Automatically show a Gooey GUI if --gui is passed as the first argument, else it will just run the function as normal'''
    if check_gui_arg():
        return gooey.Gooey(fn)
    else:
        return fn



#***********************************
#                       MAIN
#***********************************

#@conditional_decorator(check_gui_arg(), gooey.Gooey) # alternative to AutoGooey which also correctly works
@AutoGooey
def main(argv=None):
    if argv is None: # if argv is empty, fetch from the commandline
        argv = sys.argv[1:]
    elif isinstance(argv, basestring): # else if argv is supplied but it's a simple string, we need to parse it to a list of arguments before handing to argparse or any other argument parser
        argv = shlex.split(argv) # Parse string just like argv using shlex

    #==== COMMANDLINE PARSER ====

    #== Commandline description
    desc = '''Resiliency Tester
Description: Given a directory and a configuration file (containing the commands to execute before and after file tampering), this script will generate a testing tree, where the files will be corrupted randomly and then the supplied repair commands will be executed, and repair stats will be computed at each step (for each stage and repair commands).

The testing process works in stages:
1- Before_tamper stage: Run preparatory commands before tampering (useful to generate ecc/database files).
2- Tamper stage: Tamper the files and/or databases.
3- After_tamper stage: Run after tampering commands, aka preparatory commands before repair stage.
4- Repair stage: Run repair commands, each repair command reusing the files generated (partially repaired) by the previous stage. This is indeed your repair workchain that you define here.
5- Statistics are generated for each stage.

Note that the original files are never tampered, we tamper only the copy we did inside the test folder.
Also note that the test folder will not be removed at the end, so that you can see for yourself the files resulting of each stage, and eventually use other tools to compute additional stats.
    '''
    ep = '''Use --gui as the first argument to use with a GUI (via Gooey).
'''

    #== Commandline arguments
    #-- Constructing the parser
    # Use GooeyParser if we want the GUI because it will provide better widgets
    if len(argv) > 0 and (argv[0] == '--gui' and not '--ignore-gooey' in argv):  # pragma: no cover
        # Initialize the Gooey parser
        main_parser = gooey.GooeyParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter)
        # Define Gooey widget types explicitly (because type auto-detection doesn't work quite well)
        widget_dir = {"widget": "DirChooser"}
        widget_filesave = {"widget": "FileSaver"}
        widget_file = {"widget": "FileChooser"}
        widget_text = {"widget": "TextField"}
        widget_multidir = {"widget": "MultiDirChooser"}
    else: # Else in command-line usage, use the standard argparse
        # Delete the special argument to avoid unrecognized argument error in argparse
        if '--ignore-gooey' in argv[0]: argv.remove('--ignore-gooey') # this argument is automatically fed by Gooey when the user clicks on Start
        # Initialize the normal argparse parser
        main_parser = argparse.ArgumentParser(add_help=True, description=desc, epilog=ep, formatter_class=argparse.RawTextHelpFormatter)
        # Define dummy dict to keep compatibile with command-line usage
        widget_dir = {}
        widget_filesave = {}
        widget_file = {}
        widget_text = {}
        widget_multidir = {}

    # Required arguments
    main_parser.add_argument('-i', '--input', metavar='"/path/to/original/files/"', type=is_dir_or_file, nargs=1, required=True,
                        help='Specify the path to the directory containing the sample data.', **widget_dir)
    main_parser.add_argument('-o', '--output', metavar='/test/folder/', nargs=1, required=True,
                        help='Path to the test folder that will be created to store temporary test files.', **widget_dir)
    main_parser.add_argument('-c', '--config', metavar='/some/folder/config.txt', type=str, nargs=1, required=True, #type=argparse.FileType('rt')
                        help='Path to the configuration file (containing the commands to execute, Makefile format). Possible entries: before_tamper, tamper, after_tamper, repair. Note that you can use a few special tags to trigger string interpolation: {inputdir}, {dbdir}, {outputdir}.', **widget_file)

    # Optional arguments
    main_parser.add_argument('-p', '--parallel', action='store_true', required=False,
                        help='If true, repair commands will be run on the tampered files, not on the previous repair results. Useful if you want to try different strategies/commands/programs. By default, false, thus the repair commands will take advantage of the results of previous repair commands.')
    main_parser.add_argument('-m', '--multiple', metavar=1, type=int, default=1, required=False,
                        help='Run multiple times the resiliency test, and average the stats.', **widget_text)

    # Optional general arguments
    main_parser.add_argument('-l', '--log', metavar='/some/folder/filename.log', type=str, nargs=1, required=False,
                        help='Path to the log file. (Output will be piped to both the stdout and the log file)', **widget_filesave)
    main_parser.add_argument('-f', '--force', action='store_true', required=False, default=False,
                        help='Force overwriting the output folder even if it already exists.')
    main_parser.add_argument('-v', '--verbose', action='store_true', required=False, default=False,
                        help='Verbose mode (show more output).')
    main_parser.add_argument('--silent', action='store_true', required=False, default=False,
                        help='No console output (but if --log specified, the log will still be saved in the specified file).')

    #== Parsing the arguments
    args = main_parser.parse_args(argv) # Storing all arguments to args

    #-- Set variables from arguments
    origpath = fullpath(args.input[0]) # path to the input directory (where the original, sample data is)
    outputpath = fullpath(args.output[0])
    configfile = fullpath(args.config[0])
    parallel = args.parallel
    multiple = args.multiple
    force = args.force
    verbose = args.verbose
    silent = args.silent

    #if os.path.isfile(inputpath): # if inputpath is a single file (instead of a folder), then define the rootfolderpath as the parent directory (for correct relative path generation, else it will also truncate the filename!)
        #rootfolderpath = os.path.dirname(inputpath)

    # -- Checking arguments
    if not os.path.isdir(origpath):
        raise NameError("Input path needs to be a directory!")

    if not os.path.exists(configfile):
        raise NameError("Please provide a configuration file in order to run a test!")
    else:
        commands = parse_configfile(configfile)

    if os.path.exists(outputpath) and not force:
        raise NameError("Specified test folder (output path) %s already exists! Use --force to overwrite this directory." % outputpath)
    else:
        remove_if_exist(outputpath)

    if multiple < 1:
        multiple = 1

    # -- Configure the log file if enabled (ptee.write() will write to both stdout/console and to the log file)
    if args.log:
        ptee = Tee(args.log[0], 'a', nostdout=silent)
        sys.stderr = Tee(args.log[0], 'a', nostdout=silent)
    else:
        ptee = Tee(nostdout=silent)

    # == PROCESSING BRANCHING == #

    # == Main branch
    ptee.write("====================================")
    ptee.write("Resiliency tester, started on %s" % datetime.datetime.now().isoformat())
    ptee.write("====================================")
    
    ptee.write("Testing folder %s into test folder %s for %i run(s)." % (origpath, outputpath, multiple))

    fstats = {}
    for m in xrange(multiple):
        run_nb = m + 1

        ptee.write("===== Resiliency tester: starting run %i =====" % run_nb)

        # -- Define directories tree for this test run
        # testpath is the basepath for the current run
        # Generate a specific subdirectory for the current run
        testpath = os.path.join(outputpath, "run%i" % run_nb)
        dbdir = fullpath(os.path.join(testpath, "db"))
        origdbdir = fullpath(os.path.join(testpath, "origdb"))
        tamperdir = fullpath(os.path.join(testpath, "tampered"))
        repairdir = fullpath(os.path.join(testpath, "repair"))

        # == START TEST RUN
        # Create test folder
        create_dir_if_not_exist(testpath)

        # Before tampering
        ptee.write("=== BEFORE TAMPERING ===")
        create_dir_if_not_exist(dbdir)
        for i, cmd in enumerate(commands["before_tamper"]):
            scmd = interpolate_dict(cmd, interp_args={"inputdir": origpath, "dbdir": dbdir})
            ptee.write("Executing command: %s" % scmd)
            execute_command(scmd, ptee=ptee)
        copy_any(dbdir, origdbdir) # make a copy because we may tamper the db files

        # Tampering
        ptee.write("=== TAMPERING ===")
        copy_any(origpath, tamperdir)
        for i, cmd in enumerate(commands["tamper"]):
            scmd = interpolate_dict(cmd, interp_args={"inputdir": tamperdir, "dbdir": dbdir})
            ptee.write("- RTEST: Executing command: %s" % scmd)
            execute_command(scmd, ptee=ptee)

        # After tampering
        ptee.write("=== AFTER TAMPERING ===")
        for i, cmd in enumerate(commands["after_tamper"]):
            scmd = interpolate_dict(cmd, interp_args={"inputdir": tamperdir, "dbdir": dbdir})
            ptee.write("- RTEST: Executing command: %s" % scmd)
            execute_command(scmd, ptee=ptee)

        # Repairing
        ptee.write("=== REPAIRING ===")
        indir = tamperdir
        finalrepairdir = ''
        for i, cmd in enumerate(commands["repair"]):
            outdir = "%s%i" % (repairdir, i)
            scmd = interpolate_dict(cmd, interp_args={"inputdir": indir, "dbdir": dbdir, "outputdir": outdir})
            ptee.write("- RTEST: Executing command: %s" % scmd)
            create_dir_if_not_exist(outdir)
            execute_command(scmd, ptee=ptee)
            copy_any(indir, outdir, only_missing=True) # copy the files that did not need any repair (or could not be repaired at all!)
            finalrepairdir = outdir
            # If parallel, do not reuse the previous repair resulting files, repair from the tampered files directly
            if not parallel: indir = outdir

        # Stats
        stats = compute_all_diff_stats(commands, origpath, tamperdir, repairdir, finalrepairdir)
        ptee.write("========== Resiliency tester results for run %i ==========" % run_nb)
        for key, stat in stats.iteritems():
            ptee.write("=> Stage: %s" % key)
            ptee.write(pretty_print_stats(stat))

        if run_nb == 1:
            fstats = stats
        else:
            fstats = stats_running_average(fstats, stats, run_nb-1)

    ptee.write("============================")
    ptee.write("RESILIENCY TESTER FINAL AVERAGED RESULTS OVER %i RUNS" % multiple)
    ptee.write("============================")
    for key, stat in fstats.iteritems():
        ptee.write("=> Stage: %s" % key)
        ptee.write(pretty_print_stats(stat))

    # Shutting down
    del ptee
    # Completely repair all the files? Return OK
    if stats["final"]["error"] == 0:
        return 0
    else:
        return 1

# Calling main function if the script is directly called (not imported as a library in another program)
if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
