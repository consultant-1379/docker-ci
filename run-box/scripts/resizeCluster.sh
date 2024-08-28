#!/bin/bash

set -o errexit
set -o pipefail

# Script performs resize of the cluster with user provided input after validation

function myHelp () {
# Script used to resize the cluster.
cat <<-END
Usage:
------
   -h | --help
    Display this help

    Syntax: ./resize clusterSize
    Example: ./resize 2+2
END
}

declare -x FILENAME=/cluster/etc/cluster.conf

NEW_NODE_LIST=$1

if [ $# -ne 1 ]; then
    echo "Error: Provide cluster size"
    myHelp
    exit 1
fi
NODE_REGEX="^[0-9][+][0-9]+$"
if [[ ! $NEW_NODE_LIST =~ $NODE_REGEX ]]; then
    echo "Error: Invalid format for cluster size"
    myHelp
    exit 1
fi

declare -x SCALEOUT
declare -x OLD_NODE_COUNT=$(grep -c -e 'node [0-9]' $FILENAME)
declare -x CURRENT_NODE_COUNT
declare -x NODE_COUNT_DIFFERENCE

NEW_PL_NODE_COUNT=$(echo $NEW_NODE_LIST| cut -d'+' -f 2)
CURRENT_NODE_COUNT=$(grep -c -e 'node [0-9]' $FILENAME)
CURRENT_PL_NODE_COUNT=$(grep -c -e 'PL-[0-9]' $FILENAME)

echo "Total Payloads present in current system:  $CURRENT_PL_NODE_COUNT"
echo "New payload count requested for scaling: $NEW_PL_NODE_COUNT"

# Check if operation is scalein or SCALEOUT
if [ $NEW_PL_NODE_COUNT -eq $CURRENT_PL_NODE_COUNT ]; then
    echo "New cluster size is same as old cluster size"
    exit 1
elif [ $NEW_PL_NODE_COUNT -gt $CURRENT_PL_NODE_COUNT ]; then
    SCALEOUT=true
    NODE_COUNT_DIFFERENCE=$(expr $NEW_PL_NODE_COUNT - $CURRENT_PL_NODE_COUNT)
else
    SCALEOUT=false
    NODE_COUNT_DIFFERENCE=$(expr $CURRENT_PL_NODE_COUNT - $NEW_PL_NODE_COUNT)
fi

echo "Node count difference $NODE_COUNT_DIFFERENCE"

if [ "$SCALEOUT" = true ]; then
    echo "Scale-out operation in progress"
else
    echo "Scale-in operation in progress"
fi

# Function to add payload in cluster.conf file
# Ex: node 3 payload PL-3
function payload() {
    CURRENT_NODE_COUNT=$1
    NEW_PL_NUMBER=$(expr $CURRENT_NODE_COUNT + 1 )
    PATTERN="node $CURRENT_NODE_COUNT payload PL-$CURRENT_NODE_COUNT"
    if [ $CURRENT_PL_NODE_COUNT -eq 0 ]; then
        PATTERN="node $CURRENT_NODE_COUNT control SC-2"
    fi

    NEW_PATTERN="node $NEW_PL_NUMBER payload PL-$NEW_PL_NUMBER"
    # If scaleout is true new paylode node information will be added
    # else existing payload information will be deleted
    if [ "$SCALEOUT" = true ]; then
        sed -i "/$PATTERN/a $NEW_PATTERN" $FILENAME
        if [ $? -ne 0 ]; then
            echo "Error: SCALEOUT operation failed while adding new payload information"
            exit 1
        fi
    else
        if [ $CURRENT_PL_NODE_COUNT -ne 0 ]; then
            sed -i "/$PATTERN/d" $FILENAME
            if [ $? -ne 0 ]; then
                echo "Error: Scalein operation failed while adding new payload information"
                exit 1
            fi
        fi
    fi
}

# Function to add eth interface in cluster.conf file
# Ex: interface 3 eth0 MACaddress
function interface() {
    CURRENT_NODE_COUNT=$1
    NEW_PL_NUMBER=$(expr $(echo $CURRENT_NODE_COUNT) + 1 )
    LAST_NODE_ETH_MAC1=$(grep -e "interface $CURRENT_NODE_COUNT eth0 ethernet" $FILENAME  | cut -d' ' -f5 | cut -d ':' -f5)
    MAC=$(expr $LAST_NODE_ETH_MAC1 + 1 )
    MAC_DIGIT_COUNT=$(expr $(echo ${#MAC}))

    if [ $MAC_DIGIT_COUNT -eq 1 ]; then MAC=$(echo "0"$MAC);fi;

    PATTERN="interface $CURRENT_NODE_COUNT eth0 ethernet"
    NEW_PATTERN="interface $NEW_PL_NUMBER eth0 ethernet 02:00:00:0f:$MAC:01"

    # If scaleout is true new paylode node eth interface information will be added
    # else existing payload eth interface information will be deleted
    if [ "$SCALEOUT" = true ]; then
        sed -i "/$PATTERN/a $NEW_PATTERN" $FILENAME
        if [ $? -ne 0 ]; then
            echo "Error: SCALEOUT operation failedi while adding new eth MAC1 interface information"
            exit 1
        fi
    else
        if [ $CURRENT_PL_NODE_COUNT -ne 0 ]; then
            sed -i "/$PATTERN/d" $FILENAME
            if [ $? -ne 0 ]; then
                echo "Error: Scalein operation failed while adding new eth MAC1 interface information"
                exit 1
            fi
        fi
    fi

    PATTERN="interface $CURRENT_NODE_COUNT eth1 ethernet"
    NEW_PATTERN="interface $NEW_PL_NUMBER eth1 ethernet 02:00:00:0f:$MAC:02"

    # If scaleout is true new paylode node eth interface information will be added
    # else existing payload eth interface information will be deleted
    if [ "$SCALEOUT" = true ]; then
        sed -i "/$PATTERN/a $NEW_PATTERN" $FILENAME
        if [ $? -ne 0 ]; then
            echo "Error: SCALEOUT operation failed while adding new eth MAC2 interface information"
            exit 1
        fi
    else
        if [ $CURRENT_PL_NODE_COUNT -ne 0 ]; then
            sed -i "/$PATTERN/d" $FILENAME
            if [ $? -ne 0 ]; then
                echo "Error: Scalein operation failed while adding new eth MAC2 interface information"
                exit 1
            fi
        fi
    fi
}

# Function to add nbi in cluster.conf file
function nbi() {
    CURRENT_NODE_COUNT=$1
    LAST_NODE_IP=$(grep -e "ip $CURRENT_NODE_COUNT eth0 nbi" $FILENAME | cut -d' ' -f5 | cut -d '.' -f4)
    PATTERN="ip $CURRENT_NODE_COUNT eth0 nbi"

    NEW_PL_NUMBER=$(expr $CURRENT_NODE_COUNT + 1 )
    NEW_PL_IP=$(echo 10.0.2.$(expr $LAST_NODE_IP + 1 ))

    NEW_PATTERN="ip $NEW_PL_NUMBER eth0 nbi $NEW_PL_IP"

    # If scaleout is true new paylode node nbi information will be added
    # else existing payload nbi information will be deleted
    if [ "$SCALEOUT" = true ]; then
        sed -i "/$PATTERN/a $NEW_PATTERN" $FILENAME
        if [ $? -ne 0 ]; then
            echo "Error: SCALEOUT operation failedi while adding new nbi information"
            exit 1
        fi
    else
        if [ $CURRENT_PL_NODE_COUNT -ne 0 ]; then
            sed -i "/$PATTERN/d" $FILENAME
            if [ $? -ne 0 ]; then
                echo "Error: Scalein operation failed while adding new nbi information"
                exit 1
            fi
        fi
    fi
}

# Function to reload the cluster
function reloadClusterConf() {
    /opt/lde/lde-config/cluster2imm.py /cluster/etc/cluster.conf /cluster/etc/lde-config.xml
    cluster config --reload --all &> /dev/null
    if [ $? -eq 0 ]; then
        echo "Cluster.conf has been reloaded successfully"
    else
        echo "Error: Failed to reload Cluster.conf"
        exit 1
    fi
}


# Based on the number of payloads diference iterate through the loop to add payload configuration in cluster.conf file
for (( i=1; i <= $NODE_COUNT_DIFFERENCE; ++i ))
do
    echo "Execution on new payload node: $i"
    CURRENT_NODE_COUNT=$(grep -c -e 'node [0-9]' $FILENAME)
    payload $CURRENT_NODE_COUNT
    interface $CURRENT_NODE_COUNT
    nbi $CURRENT_NODE_COUNT
done

# Sleep has been added to update the cluster configuration and wait until new changes gets reflected
sleep 5s
reloadClusterConf
sleep 5s

# Based on the number of payloads diference iterate through the loop to add new payload rpm
if [ "$SCALEOUT" = true ]; then
    PL=$(expr $OLD_NODE_COUNT + 1 )
    for (( i=1; i <= $NODE_COUNT_DIFFERENCE; ++i ))
    do
        cd /cluster/rpms
        LDE_PRESENT=$(find /cluster/rpms -name "ldews-payload*.rpm" | wc -l)

        if [ -f /cluster/nodes/$PL/etc/rpm.conf ]; then
            echo "Payload rpm is already present. RPM is being upgraded for node $PL"
            cluster rpm --upgrade ldews-payload*.rpm --node $PL
        else
            echo "Payload rpm is not present. RPM is being added for node $PL"
            cluster rpm --add ldews-payload*.rpm --node $PL
        fi

        if [ $? -eq 0 ]; then
           echo "Payload rpm has been added successfully for node $PL"
        else
           echo "Error: Failed to add payload rpm for node $PL"
        fi
        PL=$(expr $PL + 1)
    done
fi
