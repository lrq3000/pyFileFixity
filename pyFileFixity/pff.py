#!/usr/bin/env python
#
# Main script entry point for pyFileFixity, provides an interface with subcommands
# Copyright (C) 2023 Stephen Karl Larroque
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
#     pyFileFixity Main Subcommands Facade API
#                by Stephen Larroque
#                       License: MIT
#              Creation date: 2023-08-04
#=================================
# Inspired by Adam Johnson's template for a script with subcommands: https://adamj.eu/tech/2021/10/15/a-python-script-template-with-sub-commands-and-type-hints/
#

from __future__ import annotations

# Import tools for argument parsing and typing
import argparse
from collections.abc import Sequence
import sys

# Include the lib folder in the python import path to be able to do relative imports
# DEPRECATED: unnecessary since PEP328, but need to use the "from .a import x" form, not "import .x" https://fortierq.github.io/python-import/ -- but note that editable mode is very fine and accepted nowadays, a subsequent PEP fixed the issue!
#import os, sys
#thispathname = os.path.dirname(__file__)
#sys.path.append(os.path.join(thispathname))

# Import all pyFileFixity subcommands tools
from .rfigc import main as rfigc_main
from .header_ecc import main as hecc_main
#from .structural_adaptive_ecc import main as saecc_main
#from .repair_ecc import main as recc_main
#from .filetamper import main as filetamper_main
#from .replication_repair import main as replication_repair_main
#from .resiliency_tester import main as resiliency_tester_main
#from .ecc_speedtest import main as ecc_speedtest_main

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Add sub-commands
    rfigc_parser = subparsers.add_parser("hash", aliases=["rfigc"], help="Check files integrity fast by hash, size, modification date or by data structure integrity.", add_help=False)  # disable help, so that we can redefine it and propagate as an argument downstream to the called module
    rfigc_parser.add_argument('-h', '--help', action='store_true')  # redefine help argument so that we can pass it downstream to submodules' argparse parsers

    header_ecc_parser = subparsers.add_parser("header", aliases=["header_ecc", "hecc"], help="Protect files headers with error correction codes", add_help=False)
    header_ecc_parser.add_argument('-h', '--help', action='store_true')

    # Parse known arguments, but we have almost none, this is done on purpose so that we can pass all arguments (except helps) downstream for submodules to handle with their own Argparse
    args, args_remainder = parser.parse_known_args(argv)
    #print(type(args_remainder))  # DEBUGLINE
    #print(args)  # DEBUGLINE

    if len(sys.argv) >= 2:
        # Prepare subarguments
        subargs = []
        if args.help is True:
            # Manage custom case of manually propagating --help to downstream module, we prepend to the string of the remainder of arguments
            subargs.append("--help")
        # Add the rest of the arguments, so that the downstream module can handle them with their own Argparse parser
        subargs.extend(args_remainder)  # args_remainder is a list, so we can extend subargs with it

        fullcommand = "pff.py " + args.subcommand

        if args.subcommand == "hash" or args.subcommand == "rfigc":
            return rfigc_main(argv=subargs, command=fullcommand)
        elif args.subcommand == "header" or args.subcommand == "header_ecc" or args.subcommand == "hecc":
            return hecc_main(argv=subargs, command=fullcommand)
        else:
            # Unreachable
            raise NotImplementedError(
                f"Command {args.command} is not implemented (dev forgot!).",
            )


def subcommand1(string: str) -> int:
    # Implement behaviour

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
