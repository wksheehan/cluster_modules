#!/usr/bin/python

# Copyright: (c) 2022, William Sheehan <willksheehan@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)

from pkg_resources import require
__metaclass__ = type

DOCUMENTATION = r'''
---
module: cluster_auth

short_description: initializes a pacemaker cluster

version_added: "1.0"

description: 
    - creates or modifies (via add or remove) a cluster so that it contains exactly the specified node set
    - starts the cluster on all nodes
    - fails if not all nodes specified are online after 120 seconds
    - for RHEL or SUSE operating systems 

options:
    os:
        description:
            - the operating system
        required: true
        choices: ['RedHat', 'Suse']
        type: str
    version:
        description:
            - the operating system version
            - required when OS is RedHat
        required: false
        type: str
    state:
        description:
            - "present" creates or modifies the cluster
            - "absent" removes the entire cluster
        required: false
        default: present
        choices: ['present', 'absent']
        type: str
    sid:
        description:
            - the sid to be used in the naming of the cluster
        required: true
        type: str
    nodes:
        description:
            - the exact list of nodes desired to be in the cluster
            - any nodes currently in the cluster not specified here will be removed
            - any nodes not currently in the cluster specified here will be added
        required: true
        type: str
    tier:
        description:
            - the node tier, to be used in naming the cluster
        required: true
        type: str
    token:
        description:
            - the token used when setting up the cluster
        required: true
        type: str

author:
    - William Sheehan (@wksheehan)
'''

EXAMPLES = r'''
- name: Create a basic two node cluster for the hana node tier on RedHat 8
  cluster_init:
    os: RedHat
    version: 8
    state: present
    sid: SAP01
    nodes: node1 node2
    tier: hana
    token: {{ cluster_totem.token }}
'''

# RETURN = r'''
# # These are examples of possible return values, and in general should use other names for return values.
# # original_message:
# #     description: The original name param that was passed in.
# #     type: str
# #     returned: always
# #     sample: 'hello world'
# # message:
# #     description: The output message that the test module generates.
# #     type: str
# #     returned: always
# #     sample: 'goodbye'
# '''

from ansible.module_utils.basic import AnsibleModule
from distutils.spawn import find_executable
from time import sleep
import re
import socket

def run_module():
    module_args = dict(
        os=dict(required=True, choices=['RedHat', 'Suse']),
        version=dict(required=False),
        state=dict(required=False, default="present", choices=['present', 'absent']),
        sid=dict(required=True),
        nodes=dict(required=True),
        tier=dict(required=True, choices=['hana', 'scs', 'db2']),
        token=dict(required=True)
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(
        changed=False,
        message=""
    )

    # Capture inputs
    os = module.params['os']
    version = module.params['version']
    state = module.params['state']
    sid = module.params['sid']
    nodes = module.params['nodes']
    nodes_set = set(nodes.split())
    tier = module.params['tier']
    token = module.params['token']
    prefix = tier if tier != "hana" else "hdb"
    hostnode = socket.gethostname()

    # Initial checks
    if find_executable('pcs') is None:
        module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")
    if os == "RedHat" and version is None:
        module.fail_json(msg="OS version must be specified when using RedHat")
    if os == "Suse":
        version = "all"

    # Dictionary of commands to run
    commands                                    = {}
    commands["RedHat"]                          = {}
    commands["RedHat"]["7"]                     = {}
    commands["RedHat"]["8"]                     = {}
    commands["RedHat"]["7"]["setup"]            = "pcs cluster setup --name %s_cluster %s --token %s" % (sid, nodes, token)
    commands["RedHat"]["8"]["setup"]            = "pcs cluster setup %s_cluster %s totem token=%s" % (sid, nodes, token)
    commands["RedHat"]["7"]["destroy"]          = "pcs cluster destroy"
    commands["RedHat"]["8"]["destroy"]          = "pcs cluster destroy"
    commands["RedHat"]["7"]["add"]              = "pcs cluster node add "
    commands["RedHat"]["8"]["add"]              = "pcs cluster node add "
    commands["RedHat"]["7"]["remove"]           = "pcs cluster node remove "
    commands["RedHat"]["8"]["remove"]           = "pcs cluster node remove "
    commands["RedHat"]["7"]["start"]            = "pcs cluster start --all"
    commands["RedHat"]["8"]["start"]            = "pcs cluster start --all"
    commands["RedHat"]["7"]["stop"]             = "pcs cluster stop --all"
    commands["RedHat"]["8"]["stop"]             = "pcs cluster stop --all"
    commands["RedHat"]["7"]["status"]           = "pcs status"
    commands["RedHat"]["8"]["status"]           = "pcs status"
    commands["RedHat"]["7"]["online"]           = "pcs status | grep '^Online:'"
    commands["RedHat"]["8"]["online"]           = "pcs status | grep '^  \* Online:'"
    commands["Suse"]                            = {}
    commands["Suse"]["all"]                     = {}
    commands["Suse"]["ha"]["setup"]             = "ha-cluster-init -y --name '%s_%s' --interface eth0 --no-overwrite-sshkey" % (prefix, sid)
    commands["Suse"]["ha"]["add"]               = "ha-cluster-join -y -c %s --interface eth0" % nodes
    commands["Suse"]["crm"]["setup"]            = "crm cluster init -y --name '%s_%s' --interface eth0 --nodes '%s'" % (prefix, sid, nodes)
    commands["Suse"]["crm"]["add"]              = "crm cluster add -y %s" # can only add one node at a time
    commands["Suse"]["crm"]["remove_host"]      = "crm cluster remove -y -c %s %s --force" # % (hostnode, nodes_to_remove)
    commands["Suse"]["crm"]["remove_some"]      = "crm cluster remove -y %s" 
    commands["Suse"]["crm"]["start"]            = "crm cluster start" 
    commands["Suse"]["crm"]["stop"]             = "crm cluster stop" 
    commands["Suse"]["all"]["status"]           = "crm status"
    commands["Suse"]["all"]["online"]           = "crm status | grep 'Online:'"

    #############################
    ######### FUNCTIONS #########
    #############################

    # Start a cluster on all configured nodes
    def start_cluster():
        rc, out, err = module.run_command(commands[os][version]["start"])
        if rc != 0:
            result["changed"] = False
            module.fail_json(msg="Error starting the cluster", **result)
    
    # Stop a cluster on all configured nodes
    def stop_cluster():
        rc, out, err = module.run_command(commands[os][version]["stop"])
        if rc == 0:
            result["message"] += "Successfully stopped the cluster. "
        else:
            result["changed"] = False
            module.fail_json(msg="Error stopping the cluster", **result)

    # Get list of existing nodes in the cluster configuration
    def get_nodes():
        corosync_conf = open('corosync.conf', 'r')
        node_names = re.compile(r"ring0_addr\s*:\s*([\w.-]+)\s*", re.M)
        return node_names.findall(corosync_conf.read())

    # Get set of nodes that are online
    def get_nodes_online():
        seconds = 0
        nodes_online = set()
        start_cluster()
        while seconds < 120:
            # String containing which nodes are online
            rc, out, err = module.run_command(commands[os][version]["online"])
            # See which nodes are online
            for node in nodes_set:
                if node in out:
                    nodes_online.add(node)
            # All nodes online
            if len(nodes_online) == len(nodes_set):
                break
            # Atleast one node not online
            sleep(10)
            seconds += 10
        return nodes_online

    #############################
    ######### MAIN CODE #########
    #############################

    # Check if cluster configuration exists
    corosync_conf_exists = os.path.isfile('/etc/corosync/corosync.conf')

    # ALWAYS ENSURE CLUSTER IS STARTED BEFORE DOING THINGS
    # Suse
    if os == "Suse":
        # Create or modify the cluster
        if state == "present":
            # No existing cluster, set up new one
            if not corosync_conf_exists:
                result["changed"] = True
                if not module.check_mode:
                    # Current node initiates the cluster
                    if hostnode == nodes:
                        rc, out, err = module.run_command(commands[os][version]["setup"])
                        if rc != 0:
                            result["changed"] = False
                            module.fail_json(msg="Failed to set up the cluster", **result)
                        result["message"] += "Successfully set up the cluster. "
                    # Different node initiated the cluster
                    else:
                        rc, out, err = module.run_command(commands[os][version]["add"])
                        if rc != 0:
                            result["changed"] = False
                            module.fail_json(msg="Failed to set up the cluster", **result)
                        result["message"] += "Successfully added node %s to the cluster. " % hostnode
            # Existing clutser detected
            else:
                # Ensure current node is in the cluster configuration
                print()
        # Remove the cluster
        else:
            # Get all nodes in the cluster 
            # Make sure host node is the last one to be removed otherwise it can't remove the other nodes in the system
            nodes_to_remove = set()
            if hostnode in nodes_to_remove:
                nodes_to_remove -= hostnode
                cmd = commands[os][version]["remove_host"] % (hostnode, nodes_to_remove)
            else:
                cmd = commands[os][version]["remove_some"] % nodes_to_remove

    # RedHat
    else:
        # Create or modify the cluster
        if state == "present":
            # No existing cluster, set up a new one
            if not corosync_conf_exists:
                result["changed"] = True
                if not module.check_mode:
                    rc, out, err = module.run_command(commands[os][version]["setup"])
                    if rc != 0:
                        result["changed"] = False
                        module.fail_json(msg="Failed to set up the cluster", **result)
                    result["message"] += "Successfully set up the cluster. "
            # Existing cluster detected
            else:
                # Get the difference in nodes
                existing_nodes = set(get_nodes())
                nodes_to_add = nodes_set - existing_nodes
                nodes_to_remove = existing_nodes - nodes_set
                # Add any missing nodes
                if len(nodes_to_add) > 0:
                    result["changed"] = True
                    nodes_to_add = " ".join(nodes_to_add)
                    start_cluster()
                    if not module.check_mode:
                        rc, out, err = module.run_command(commands[os][version]["add"] + nodes_to_add)
                        if rc == 0:
                            result["message"] += "Successfully added the following nodes to the cluster: " + nodes_to_add + ". "
                        else:
                            result["changed"] = False
                            module.fail_json(msg="Failed to add the following nodes to the cluster: " + nodes_to_add, **result)
                # Remove any extra nodes
                if len(nodes_to_remove) > 0:
                    # Warn that all nodes in cluster will be removed
                    if len(nodes_to_remove) == len(existing_nodes):
                        module.fail_json(msg="No nodes will be left in the cluster. If you intend to destroy the whole cluster, re-run the module with state = absent", **result)
                    else:
                        result["changed"] = True
                        nodes_to_remove = " ".join(nodes_to_remove)
                        stop_cluster()
                        if not module.check_mode:
                            rc, out, err = module.run_command(commands[os][version]["remove"] + nodes_to_remove)
                            if rc == 0:
                                result["message"] += "Successfully removed the following nodes from the cluster: " + nodes_to_remove + ". "
                            else:
                                result["changed"] = False
                                module.fail_json(msg="Failed to remove the following nodes to the cluster: " + nodes_to_remove, **result)
                # No difference, nothing to do
                if len(nodes_to_add) == 0 and len(nodes_to_remove) == 0:
                    result["message"] += "No changes needed: cluster is already set up with the nodes specified. "
            # ensure cluster is started and all nodes online
            nodes_online = get_nodes_online()
            result["online_nodes"] = nodes_online
            # Some nodes not online, failure
            if len(nodes_online) != len(nodes_set):
                module.fail_json(msg="The following nodes are not online: " + " ".join(nodes_set - nodes_online), **result)
        # Remove the cluster (state == absent)
        else:
            # Cluster detected, destroy it
            if corosync_conf_exists:
                result["changed"] = True
                if not module.check_mode:
                    rc, out, err = module.run_command(commands[os][version]["destroy"])
                    if rc == 0:
                        result["message"] += "Succesfully destroyed the cluster. "
                    else:
                        module.fail_json(msg="Failed to destroy the cluster", **result)
            # No existing cluster, nothing to do
            else:
                result["message"] += "No changes needed: no clusters were detected. "

    # Success
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()