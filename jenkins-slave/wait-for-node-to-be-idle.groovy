import hudson.model.*

// Get the node name. It should be the first argument to the script.
def nodeName = args[0]
def node = hudson.model.Hudson.instance.getComputer(nodeName)

if(node == null) {
    throw new IllegalArgumentException("The node '" + nodeName + "' could not be found.")
}

println("Waiting for the node to become idle...")
while(!node.isIdle()) {
    sleep(1000)
}

println("The node is idle")
