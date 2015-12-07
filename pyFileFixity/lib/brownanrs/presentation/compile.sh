#!/bin/bash
set -x
set -e
latex presentation.tex 
dvips -O 0.0,0.1 presentation.dvi 
ps2pdf presentation.ps
