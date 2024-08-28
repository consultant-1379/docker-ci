#!/bin/bash -e

#   This script checks if all components have been successfully installed in the cluster or not

CONDITION=0
ATTEMPTS=0

while [ $CONDITION -eq 0 ]; do

    if [ "`cmw-status app csiass comp node sg si siass su`" == "Status OK" ]; then
        RESULT="`cmw-repository-list | grep -v DEBUGINFO | grep NotUsed | wc -l`"
        if [ $RESULT -eq 0 ]; then
             CONDITION=1
             echo "Installation has been successful"
        else
             echo "Failure: Installation failed, please see detail by issuing cmw-repository-list"
             CONDITION=2
        fi
    else
        if [ $ATTEMPTS -eq 15 ]; then
             echo "Something is wrong with the target machines"
             CONDITION=2
        else
             ATTEMPTS=$(($ATTEMPTS+1))
             sleep 30
             export PATH="$PATH":/opt/coremw/bin
        fi
    fi
done


if [ $CONDITION -eq 2 ]; then
    false
fi
