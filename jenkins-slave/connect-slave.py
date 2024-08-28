#!/usr/bin/env python

# Steps necessary to connect the node:
# 1) Write slave.xml
# 2) wget JENKINS_URL:JENKINS_PORT/jnlpJars/jenkins-cli.jar
# 3) java -jar jenkins-cli.jar -s JENKINS_URL:JENKINS_PORT/ create-node slave-1 < slave.xml
# 4) wget JENKINS_URL:JENKINS_PORT/jnlpJars/slave.jar
# 5) java -jar slave.jar -jnlpUrl JENKINS_URL:JENKINS_PORT/computer/slave-1/slave-agent.jnlp


# Includes
import argparse
import os
import sys
import traceback
import signal
import time
import subprocess
import uuid
import socket
import re
import urlparse
import xml.etree.cElementTree as xmlWriter
import ntpath
from shutil import copy


def debug(msg):
    sys.stdout.write(msg+"\n")
    sys.stdout.flush()

# Define input arguments
parser = argparse.ArgumentParser(description='Connect a Jenkins machine as a slave to a Jenkins master')

mandatoryArgs = parser.add_argument_group('Mandatory arguments')
mandatoryArgs.add_argument('--url', action="store", dest="url", default=False, required=True)
mandatoryArgs.add_argument('--label', action="store", dest="label", default=False, required=True)
mandatoryArgs.add_argument('--vault-pass', action="store", dest="vaultPass", default=False, required=False)

parser.add_argument('--tunnel', action="store", dest="tunnel", default=False)
parser.add_argument('--predownloaded-jars', action="store_true", default=False, dest="preDownloadedJars")

# Parse input arguments
args = parser.parse_args()
jenkinsUrl = args.url
tunnel = args.tunnel
label = args.label
preDownloadedJars = args.preDownloadedJars
debug("Jenkins Url: " + jenkinsUrl)

# Resolve the Jenkins Master hostname to an ip
# Remove https://, http:// and leading slashes
domain = jenkinsUrl.replace("https://","").replace("http://","").replace("/","")
# Remove the port if it's set
domain = re.sub(":.*", "", domain)
debug("Trying to resolve the domain '" + domain + "' to an IP.")
ip = socket.gethostbyname(domain)
debug("Resolved Jenkins Url IP: " + ip)

# Add the IP to the no_proxy range so the traffic is routed correctly
os.environ["no_proxy"] = os.environ["no_proxy"] + "," + ip

# Create a unique node name
hostname = socket.gethostname()
uniqueId = uuid.uuid1()
uniqueString = str(uniqueId.time_low)
nodeName = label + "-" + hostname + "-" + uniqueString

# This variable should be true if the node configuration has been created successfully
nodeConfigurationCreated = False

# This is the slave subprocess
slaveProcess = None

if args.vaultPass:
    # Decrypt the identity file to use for Jenkins connect
    identityFile = os.environ.get("IDENTITY")
    filename = ntpath.basename(identityFile)
    tmpFile = "/tmp/" + filename
    copy(identityFile,tmpFile)
    sys.stdout.flush()
    identity = ["-i", tmpFile]
    decryptCommand = ["ansible-vault", "decrypt", tmpFile, "--vault-password-file", args.vaultPass]

    try:
        debug("Decrypting the identity file")
        subprocess.check_call(decryptCommand, stderr=subprocess.STDOUT)
    except:
        traceback.print_exc(file=sys.stdout)
        raise
else:
    identity = []

def getScriptPath():
    return os.path.dirname(os.path.realpath(sys.argv[0])) + "/"

# Create the initial commands to be used during the execution
cliJarLocation = "/tmp/jenkins-cli.jar"
slaveJarLocation = "/tmp/slave.jar"
jenkinsCliCommand = [ "java", "-jar", cliJarLocation, "-s", jenkinsUrl] + identity
jenkinsSlaveCommand = [ "java", "-jar", slaveJarLocation]

# Register interruption handler
# At script shutdown the node configuration should be deleted.
def cleanup(signum = None, frame = None):

    if nodeConfigurationCreated:

        offlineNodeCommand = jenkinsCliCommand + ["offline-node", nodeName ]
        waitScript = getScriptPath() +  "wait-for-node-to-be-idle.groovy"
        waitForSlaveToBecomeIdleCommand = jenkinsCliCommand + ["groovy", waitScript, nodeName ]
        deleteSlaveCommand = jenkinsCliCommand + ["delete-node", nodeName ]

        debug("Setting the node offline")
        subprocess.check_call(offlineNodeCommand, stderr=subprocess.STDOUT)

        debug("Waiting for the node to become idle")
        subprocess.check_call(waitForSlaveToBecomeIdleCommand, stderr=subprocess.STDOUT)

        if slaveProcess:
            debug("Terminating the slave process")
            slaveProcess.kill()

        debug("Deleting the slave configuration")
        subprocess.check_call(deleteSlaveCommand, stderr=subprocess.STDOUT)

        debug("Done")

    sys.exit(0)

for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
    signal.signal(sig, cleanup)



###################
# Write slave.xml #
###################
slave = xmlWriter.Element("slave")
xmlWriter.SubElement(slave, "remoteFS").text = "/tmp/."
xmlWriter.SubElement(slave, "numExecutors").text = "1"
xmlWriter.SubElement(slave, "mode").text = "NORMAL"
xmlWriter.SubElement(slave, "retentionStrategy", { "class":"hudson.slaves.RetentionStrategy$Always" })
xmlWriter.SubElement(slave, "label").text = label
xmlWriter.SubElement(slave, "nodeProperties")

launcher = xmlWriter.SubElement(slave, "launcher", { "class":"hudson.slaves.JNLPLauncher" })
if tunnel:
    xmlWriter.SubElement(launcher, "tunnel").text = tunnel

tree = xmlWriter.ElementTree(slave)
tree.write("/tmp/slave.xml")

debug("slave.xml written to /tmp/slave.xml")


############################
# Download jenkins-cli.jar #
############################
# Download the jenkins-cli.jar file and save it locally under /tmp/
# Example command:
# wget -P /tmp/ http://com-docker-2.com.k2.ericsson.se:8080//jnlpJars/jenkins-cli.jar

if not preDownloadedJars:
    jenkinsCliUrl = urlparse.urljoin(jenkinsUrl, "jnlpJars/jenkins-cli.jar")
    command = [ "wget", "--quiet", "-O", cliJarLocation, jenkinsCliUrl ]

    debug("Downloading jenkins-cli.jar from '" + jenkinsCliUrl + "'")
    subprocess.check_call(command, stderr=subprocess.STDOUT)


#############################
# Create node configuration #
#############################
# Example command:
# java -jar /tmp/jenkins-cli.jar -s http://com-docker-2.com.k2.ericsson.se:8080/ create-node slave-1 < /tmp/slave.xml

# Create node configuration
debug("Creating node configuration for node '" + nodeName + "'")
command = jenkinsCliCommand + ["create-node", nodeName ]

try:
    slavexml = open("/tmp/slave.xml")
    subprocess.check_call(command, stdin=slavexml, stderr=subprocess.STDOUT)
    debug("Node configuration created")
except:
    traceback.print_exc(file=sys.stdout)
    raise
else:
    slavexml.close()

nodeConfigurationCreated = True


######################
# Download slave.jar #
######################
# Example command:
# wget http://com-docker-2.com.k2.ericsson.se:8080/jnlpJars/slave.jar

if not preDownloadedJars:
    jenkinsSlaveUrl = urlparse.urljoin(jenkinsUrl, "jnlpJars/slave.jar")
    command = [ "wget", "--quiet", "-O", slaveJarLocation, jenkinsSlaveUrl ]

    debug("Downloading slave.jar from '" + jenkinsSlaveUrl + "'")
    subprocess.check_call(command, stderr=subprocess.STDOUT)


####################
# Connect the node #
####################
# Example command:
# java -jar slave.jar -jnlpUrl http://com-docker-2.com.k2.ericsson.se:8080/computer/slave-1/slave-agent.jnlp

debug("Getting the secret of node: '" + nodeName + "'")
secretScript = getScriptPath() +  "get-node-secret.groovy"
command = jenkinsCliCommand + ["groovy", secretScript, nodeName]
secret = subprocess.check_output(command, stderr=subprocess.STDOUT)

trailingStr = "computer/" + nodeName + "/slave-agent.jnlp"
jnlpUrl = urlparse.urljoin(jenkinsUrl, trailingStr)
command = jenkinsSlaveCommand + ["-jnlpUrl", jnlpUrl, "-secret", secret]

try:
    # We dont want the subprocess to terminate on SIGTERM, so we set the signal handler for SIGTERM to no-handler.
    # The child process will inherit the signal handler from the main process
    default_handler = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)

    debug("Connecting slave '" + nodeName + "'to master using jnlpUrl '" + jnlpUrl + "'")
    slaveProcess = subprocess.Popen(command,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE
                                    )

    # Restore the signal handler for the main process
    signal.signal(signal.SIGTERM, default_handler)

    debug("Slave process started")
    slaveProcess.wait()
    for line in slaveProcess.stdout:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    for line in slaveProcess.stderr:
        sys.stdout.write(line+"\n")
        sys.stdout.flush()

    debug("slave process exited")

except subprocess.CalledProcessError:
    raise
