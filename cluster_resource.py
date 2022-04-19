#!/usr/bin/python

# Copyright: (c) 2022, William Sheehan <willksheehan@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: cluster_resource

short_description: configures a cluster resource

version_added: "1.0"

description: 
    - configures a cluster resource
    - for RHEL or SUSE operating systems 

options:
    os:
        description:
            - the operating system
        required: true
        choices: ['RedHat', 'Suse']
        type: str
    state:
        description:
            - 'present' ensures the resource is exists
            - 'absent' ensures the resource doesn't exist
        required: false
        default: present
        choices: ['present', 'absent']
        type: str
    name:
        description:
            - the name of the cluster resource
        required: true
        type: str
    resource_type:
        description:
            - the type of resource to configure
        required: false
        type: str
    options:
        description:
            - additional options to include when configuring the resource
        required: false
        type: str
author:
    - William Sheehan (@wksheehan)
'''

EXAMPLES = r'''
- name: Create a stonith resource
  cluster_resource:
    os: RedHat
    state: present
    name: my_stonith_resource
    resource-type: stonith
'''

from ansible.module_utils.basic import AnsibleModule
from distutils.spawn import find_executable


def run_module():
    
    # ==== Setup ====
    
    module_args = dict(
        os=dict(required=True, choices=['RedHat', 'Suse']),
        state=dict(required=False, default="present", choices=['present', 'absent']),
        name=dict(required=True),
        resource_type=dict(required=False),
        options=dict(required=False)
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(
        changed=False
    )

    os              = module.params['os']
    state           = module.params['state']
    name            = module.params['name']
    resource_type   = module.params['resource_type']
    options         = module.params['options']
    #ctype           = "property" if node is None else "attribute"


    # ==== Command dictionary ====

    commands                                        = {}
    commands["RedHat"]                              = {}
    commands["Suse"]                                = {}
    commands["RedHat"]["property" ]                 = {}
    commands["Suse"  ]["property" ]                 = {}
    commands["RedHat"]["attribute"]                 = {}
    commands["Suse"  ]["attribute"]                 = {}
    commands["RedHat"]["property" ]["set"]          = "pcs property set %s=%s" % (name, value)
    commands["Suse"  ]["property" ]["set"]          = "crm configure property %s=%s" % (name, value)
    commands["RedHat"]["attribute"]["set"]          = "pcs node attribute %s %s=%s" % (node, name, value)
    commands["Suse"  ]["attribute"]["set"]          = "crm node attribute %s set %s %s" % (node, name, value)
    commands["RedHat"]["property" ]["unset"]        = "pcs property unset %s" % name
    commands["Suse"  ]["property" ]["unset"]        = "crm configure property"
    commands["RedHat"]["attribute"]["unset"]        = "pcs node attribute %s %s=" % (node, name)
    commands["Suse"  ]["attribute"]["unset"]        = "crm node attribute %s delete %s" % (node, name)
    commands["RedHat"]["property" ]["show"]         = "pcs property show %s | grep %s" % (name, name)
    commands["Suse"  ]["property" ]["show"]         = "crm configure show type:property | grep %s=" % name
    commands["RedHat"]["attribute"]["show"]         = "pcs node attribute --name %s | grep %s" % (name, node)
    commands["Suse"  ]["attribute"]["show"]         = "crm node attribute %s show %s" % (node, name)
    commands["RedHat"]["property" ]["list"]         = "pcs property list"
    commands["Suse"  ]["property" ]["list"]         = "crm configure show type:property"
    commands["RedHat"]["attribute"]["list"]         = "pcs node attribute"
    commands["Suse"  ]["attribute"]["list"]         = "crm configure show type:node"
    commands["RedHat"]["property" ]["contains"]     = "%s: %s" % (name, value)
    commands["Suse"  ]["property" ]["contains"]     = "%s=%s" % (name, value)
    commands["RedHat"]["attribute"]["contains"]     = "%s=%s" % (name, value)
    commands["Suse"  ]["attribute"]["contains"]     = "name=%s value=%s" % (name, value)


    # ==== Initial checks ====

    if find_executable('pcs') is None:
        module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")


    # ==== Functions ====


    # ==== Main code ====

    # Configure resource
    if state == "present":
        print('x')
    # Remove resource
    else:
        print('x')

    # SUCCESS STATEMENT
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()