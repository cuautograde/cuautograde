#!/usr/bin/env bash

# Author Dhruv Singhal (dhruv@singhal.me)

# This file will bootstrap the unit tests inside a docker container. Use it to
# set up any special environment the are not already baked into the docker
# image.

# Conventional/Example Docker Volumes:

# /autograder : This is the path to cuautograde directory, mounted as a
# read-only volume in the docker image.

# /tests : Another read-only volume that contains the tests to be run.

# /submission: The folder containing the students submission file. This volume
# is read-write so that the results and logs of the autograding can be
# collected.

# PYTHONPATH: These folders are added to the Python search path so that any
# modules can be referenced by name only.
export PYTHONPATH=/autograder:/tests:/submission

# You can do whatever setup you want here.
echo 'Running tests...'

# Invoke the autograder. Here, the autograder test module is test.py in /tests.
python -m runner test . -t 60 -v -r /submission/results.json -c /submission/log.txt
