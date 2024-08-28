#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

#   The script will perform the following actions:
#       1.  Download the components from artifactory using Artifactory Manager
#       2.  Generates the AIT repo with downloaded components

if [ $# -ne 2 ]; then
    echo "PATH TO THE AIT REPOSITORY AND CBA VERSION FILE NAME NEEDS TO BE PROVIDED"
    exit 1
fi

REPO=$1
VERSION_FILE=$2

function cleanup {
    rm -rf $REPO/{SWP_File,swp}
}
trap cleanup EXIT

# Generate the AIT repository
artifact_manager -cr -i $VERSION_FILE -o $REPO

(cd $REPO/swp ; cp DEPLOYMENT.working DEPLOYMENT.ready)
(cd $REPO ; ait-image-create swp swp)
chmod -R 755 $REPO
