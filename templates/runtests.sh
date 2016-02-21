#!/usr/bin/env bash

# Author: Dhruv Singhal (dhruv@singhal.me)

# This is a sample script to run all the tests.

# This is the file that CMS produces, containing student code.
SUBMISSION_FILE="$1"

# This is the location where the student submissions are extracted, and which
# will contain the results of autograding.
DEST="$2"

# This is the path to the CSV from CMS into which the grades are entered.
CSV_FILE="$3"

# First extract student submissions. The submissions will be extracted such that
# the actual files are in a folder $DEST/<group NetIDs>/, after repeatedly
# extracting any nested zips.
python cuautograde/extract.py -s "$SUBMISSION_FILE" -d "$DEST" -e

# Mount the docker volumes as explained in docker.sh and run the bootstrap
# script.
for d in $DEST/* ; do
    echo "Processing $d"
    docker run -v "$d":/submission -v $(pwd):/tests:ro -v $(realpath ../../modules/cuautograde):/autograder:ro dhruvs/cs4670 sh /tests/docker.sh
done

# Finally all the results to the CMS grade and comment script.
python cuautograde/analysis.py "$DEST" -c "$CSV_FILE"
