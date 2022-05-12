#!/usr/bin/python

# Copyright: (c) 2022, William Sheehan <willksheehan@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: cluster_auth

short_description: authenticates nodes that will constitute a cluster

version_added: "1.0"

description: authenticates the user on one or more nodes to be used in a cluster on RHEL operating system 

options:
    version:
        description:
            - the operating system version
        required: true
        choices: ['7', '8']
        type: str
    nodes:
        description:
            - the nodes to authenticate or deauthenticate
            - a string of one or more nodes separated by spaces
        required: true
        type: str
    username:
        description:
            - the username of the cluster administrator
        required: false
        default: "hacluster"
        type: str
    password:
        description:
            - the password of the cluster administrator
        required: true
        type: str

author:
    - William Sheehan (@wksheehan)
'''

EXAMPLES = r'''
- name: Authenticate user hacluster on node1 for both the nodes in a two-node cluster (node1 and node2)
  cluster_auth:
    version: {{ ansible_distribution_major_version }}
    nodes: node1 node2
    username: hacluster
    password: testpass
'''

from ansible.module_utils.basic import AnsibleModule
from distutils.spawn import find_executable

def run_module():

    # ==== Setup ====

    module_args = dict(
        version=dict(required=True, choices=['7', '8']),
        nodes=dict(required=True),
        username=dict(required=False, default="hacluster"),
        password=dict(required=True, no_log=True)
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(
        changed=False,
        message=""
    )

    version     = module.params['version']
    nodes       = module.params['nodes']
    username    = module.params['username']
    password    = module.params['password']


    # ==== Initial checks ====
    
    if find_executable('pcs') is None:
        module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")
    
    
    # ==== Main code ====

    rc, out, err = module.run_command('pcs cluster pcsd-status %s' % nodes)

    if rc == 0:
        result["message"] = "Nodes %s are all online" % nodes
    else:
        result["changed"] = True
        if not module.check_mode:
            if version == "7":
                cmd = "pcs cluster auth %s -u %s -p %s" % (nodes, username, password)
            elif version == "8":
                cmd = "pcs host auth %s -u %s -p %s" % (nodes, username, password)
            else:
                module.fail_json(msg='Incorrect operating system version specified', **result)
            rc, out, err = module.run_command(cmd)
            if rc == 0:
                result["message"] = "Nodes were successfully authenticated"
            else:
                result["changed"] = False
                result["stdout"] = out
                result["error_message"] = err
                result["command_used"] = cmd
                module.fail_json(msg="Failed to authenticate to one or more nodes", **result)

    # Success
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()