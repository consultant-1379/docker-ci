#!/bin/bash
#
# This script works only when all cluster nodes are up.  If this is
# not the case, it will print an error.  Therefore the script catches
# the error and instructs running provisioner again later when nodes
# are up and running.
#

if [ -f /opt/coremw/sbin/cmw-cluster-resize ]; then
    /opt/coremw/sbin/cmw-cluster-resize
    if [ $? != 0 ]; then
        echo "Error: Resize failed" >&2
        exit 1
    fi
    /opt/coremw/bin/cmw-status node su comp
else
    echo "Coremw is not present in the cluster. Resize not required"
fi
