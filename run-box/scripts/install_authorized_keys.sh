#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

#   This script creates and adds the authorized_keys
#   to both controllers in the cluster

TARGET_NODE1=$1
if [ -z "$TARGET_NODE1" ]; then
    echo "Usage: $0 target_node"
    echo "    target_node: IP address of target node to install authorized_keys file"
    exit
fi
TARGET_NODE2=`echo ${TARGET_NODE1%.*}.$(expr $(echo ${TARGET_NODE1} | cut -d '.' -f4) + 1)`
echo ${TARGET_NODE2}

if [ ! -r ~/.ssh ]; then
   mkdir -p ~/.ssh
fi
echo content of ~/.ssh
ls ~/.ssh/
sed -i '/<${TARGET_NODE1}>/d' "$(getent passwd `whoami` | cut -d: -f6)"/.ssh/known_hosts || true
sed -i '/<${TARGET_NODE2}>/d' "$(getent passwd `whoami` | cut -d: -f6)"/.ssh/known_hosts || true

rm -rf  ~/.ssh/id_rsa
ssh-keygen  -P '' -f ~/.ssh/id_rsa -t rsa
KEY="$(<~/.ssh/id_rsa.pub)"

create_ssh_dir()
{
IP=$1
expect <<END
set timeout 20
set password rootroot
spawn ssh root@$IP "mkdir -p ~/.ssh"
expect {
    "Password:" {
        send "\$password\r"
    }

    "yes/no)?" {
        send "yes\r"
        set timeout -1
        expect {
            "Password:" {
                send "\$password\r"
            }
            timemout {
                exit 1
            }
            eof {
                exit 1
            }
        }
    }

    timeout {
        exit 1
    }
    eof {
        exit 0
    }
}
expect {
    eof { exit 0 }
    timeout { exit 1 }
}
END

}

add_ssh_key()
{
IP=$1
expect <<END
set timeout 20
set password rootroot
spawn ssh root@$IP "echo '$KEY' > ~/.ssh/authorized_keys"
expect {
    "Password:" {
        send "\$password\r"
    }

    "yes/no)?" {
        send "yes\r"
        set timeout -1
        expect {
            "Password:" {
                send "\$password\r"
            }
            timemout {
                exit 1
            }
            eof {
                exit 1
            }
        }
    }

    timeout {
        exit 1
    }
    eof {
        exit 0
    }
}
expect {
    eof { exit 0 }
    timeout { exit 1 }
}
END
}

# Creation of SSH directory in node1
create_ssh_dir ${TARGET_NODE1}

# Creation of SSH directory in node2
create_ssh_dir ${TARGET_NODE2}

# Adding authorized key in node1
add_ssh_key ${TARGET_NODE1}

# Adding authorized key in node2
add_ssh_key ${TARGET_NODE2}
