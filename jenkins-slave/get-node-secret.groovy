import hudson.model.*

// Get the node name. It should be the first argument to the script.
def nodeName = args[0]

// Return the secret of the node.
println hudson.model.Hudson.instance.getComputer(nodeName).getJnlpMac()
