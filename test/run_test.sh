#!/bin/bash

export PYTHONPATH=../src:$PYTHONPATH

rm -f -r ../src./__pycache__
rm -f -r __pycache__

if [[ "$1" == "" ]]; then
    python3 -m unittest discover -f -v -s . -p '*_test.py'
else
    python3 -m unittest discover -f -v -s . -p "$1_test.py"
fi

