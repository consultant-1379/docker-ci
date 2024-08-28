#!/usr/bin/env python
#
#   This script performs AIT local installation on target
#
#   Prerequisites:
#       *   The AIT repository has been created and is accessible from the script
#       *   The DEPOLYEMENT.ready file is present in the AIT repository
#
#   The script will perform the following actions:
#       1.  scp the AIT repository to the target
#       2.  Install AIT_TA rpm on SC-1
#       3.  scp the AIT repository to the target
#       4.  create ait-repo.conf file
#       5.  Check the status of ait_ta
#               a.   If it has not started, start the installation process
#       6.  Monitor the installation process until completion
#
#

import os
import time
import sys, getopt
from subprocess import *
from paramiko import *


## HELPER FUNCTIONS
def print_output(output):
    """
        Helper function to print the output of the ssh.exec_command function
    """
    out = output.read().splitlines()
    for line in out:
        print(line)

def remote_copy(sshClient, local, remote):
    """
        Helper function to transfer a file to a remote target
    """
    print("Remote function SWP file copy from path %s." % local)
    print("Remote function SWP file copy to remote path %s." % remote)
    sftp = sshClient.open_sftp()
    sftp.put(local, remote)
    sftp.close()


def getAitRpm(path):
    """
        Helper function to get ait-ta rpm file
    """
    cmd = "ls " + path
    p = Popen(cmd, stdout=PIPE, stderr=STDOUT, shell=True)
    out = p.stdout.read().splitlines()
    for line in out:
        if "ait-ta-cxp" in line:
            return line.strip()

def monitor(ip):
    """
        Helper function to start ait-installation monitor to monitor
        AIT installation progress on the target
    """
    cmd = [ "ait-installation-monitor",
            "--snapshot-state",
            "--no-var-log-messages",
            "--target",
            "root:rootroot@" + ip ]
    p = Popen(cmd, stdout=PIPE, stderr=STDOUT)

    counter = 0
    loop = 0
    counter_complete = 100
    while counter < 60: # 10 min timeout
        output = p.communicate()[0]

        if "AIT-TA Status: NOT RUNNING" in output:
            counter = counter + 1

        elif "AIT-TA Status: RUNNING" in output:
            counter = 0

        if "COMPLETE" in output:
            counter = counter_complete

        if "Cannot currently login" in output:
            print("Cannot currently login - maybe in a reboot")

        else:
            print(output)

        loop = loop + 1
        sys.stdout.flush()
        time.sleep(10)
        p = Popen(cmd, stdout=PIPE, stderr=STDOUT)

    if counter == counter_complete:
        # Successful installation
        return 0
    else:
        return -1

def waitFor(sshClient, path, fileName):
    """
        Helper function to wait for the file with fileName gets created
        under path on the target machine
    """
    stdin,stdout,stderr = sshClient.exec_command("ls -R " + path)
    out = stdout.read().splitlines()
    while fileName not in out:
        stdin,stdout,stderr = sshClient.exec_command("ls -R " + path)
        out = stdout.read().splitlines()

def editDeployment(sshClient, path):
    """
        Helper function to set the DEPLOYMENT.ready file to match cluster size
    """
    # Inner function to fetch the number of nodes for a specific type
    # from /cluster/etc/cluster.conf file
    def getSize(node):
        cmd = "grep -c -e 'node [0-9] " + node + "' /cluster/etc/cluster.conf"
        stdin,stdout,stderr = sshClient.exec_command(cmd)
        out = stdout.read().splitlines()
        for line in out:
            if line.isdigit():
                return line

    # editing for the SC
    number = getSize("control")
    cmd = "sed -i 's/SCs=[0-9]*/SCs=" + number + "/g' " + path + "DEPLOYMENT.ready"
    sshClient.exec_command(cmd)

    # editing for the PL
    number = getSize("payload")
    cmd = "sed -i 's/PLs=[0-9]*/PLs=" + number + "/g' " + path + "DEPLOYMENT.ready"
    sshClient.exec_command(cmd)

def usage():
    """
        Helper function to print the usage of the script
    """
    print(__file__ + " [OPTIONS]... -i [IP] -p [PATH]\n")
    print("Options:")
    print("-h, --help:")
    print("\tThis help message\n")
    print("-i, --ip=<ip address>:")
    print("\tIP address of the target\n")
    print("-p,--path=<path to AIT image>:")
    print("\tAIT wanted configuration to install on the target\n")


## Main part
def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hi:p:", ["help, ip, path"])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()

        elif opt in ("-i", "--ip"):
            ip = arg

        elif opt in ("-p", "--path"):
            path = arg

    config = path.split("/")[-1].replace(".tgz","")
    ait_path = "/opt/dxtools/"
    target_repo = "/home/ait/repo/" + config
    home_ait = "/home/ait/repo/"
    ait_ta_bin = "/opt/ait/etc/init.d/ait_ta"

    # Initializing the SSH protocol
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    ssh.connect(ip, username='root', password='rootroot')

    # Part 1. scp the AIT-TA rpm file to the target
    ait_rpm = getAitRpm(ait_path + "agent_setup/non_exec/")
    local = str(ait_path + "agent_setup/non_exec/" + ait_rpm)
    remote = "/cluster/rpms/" + ait_rpm
    remote_copy(ssh, local, remote)

    # Part 2. Install AIT_TA rpm on SC-1
    stdin,stdout,stderr = ssh.exec_command("cluster rpm -a " + ait_rpm + " -n 1")
    print_output(stdout)

    stdin,stdout,stderr = ssh.exec_command("cluster rpm -A -n 1")
    print_output(stdout)

    stdin,stdout,stderr = ssh.exec_command("cluster rpm -l -n 1")
    print_output(stdout)

    # Part 3. scp the AIT repository to the target.
    ssh.exec_command("mkdir -p " + home_ait)
    remote = home_ait + config + ".tgz"
    remote_copy(ssh, path, remote)

    # untaring ait image
    ssh.exec_command("cd " + home_ait + " ; tar -zxf " + config + ".tgz")
    waitFor(ssh, home_ait, "chsum.md5")

    # untaring compressed archive from ait image
    ssh.exec_command("cd " + home_ait + " ; tar -zxf " + config + ".tgz")
    waitFor(ssh, home_ait + config, "DEPLOYMENT.ready")

    # edit DEPLOYMENT.ready file
    editDeployment(ssh, home_ait + config + "/")

    # Part 4. Create ait-repo.conf file
    ssh.exec_command("echo file://" + target_repo + " > /home/ait/ait-repo.conf")

    # Part 5. Check AIT_TA status
    stdin,stdout,stderr = ssh.exec_command(ait_ta_bin + " status")
    out = stdout.read().splitlines()
    for line in out:
        print(line)
        if "AIT-TA is not running" in line:
            # If it has not started, start the installation process
            print("starting AIT-TA")
            cmd = ait_ta_bin + " start"
            ssh.exec_command(cmd)
            time.sleep(1)
            break

    # closing ssh connection
    ssh.close()

    # 6. Monitor the installation process until completion
    ret = monitor(ip)
    if ret < 0:
        # Failure
        print("ERROR: The AIT installation failed, check the logs for more details")
        os._exit(1)
    else:
        print("SUCCESSFUL INSTALLATION")
        os._exit(0)

if __name__ == "__main__":
    main(sys.argv[1:])
