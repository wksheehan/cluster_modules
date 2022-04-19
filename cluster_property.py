#!/usr/bin/python

# Copyright: (c) 2022, William Sheehan <willksheehan@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: cluster_auth

short_description: sets and unsets both cluster and node properties

version_added: "1.0"

description: 
    - sets or unsets specific properties for the cluster configuration or for specific nodes
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
            - "present" ensures the property is set
            - "absent" ensures the property is unset
        required: false
        default: present
        choices: ['present', 'absent']
        type: str
    node:
        description:
            - the node for setting or unsetting node-specific properties
            - if specified, will set/unset a node-specific attribute
            - if absent, will set/unset a cluster property
        required: false
        type: str
    name:
        description:
            - the name of the attribute or property to set or unset
        required: true
        type: str
    value:
        description:
            - the value of the attribute to set
            - not needed when unsetting (state=absent)
        required: false
        type: str
author:
    - William Sheehan (@wksheehan)
'''

EXAMPLES = r'''
- name: Set stonith-timeout property to 900
  cluster_property:
    os: RedHat
    state: present
    name: stonith-timeout
    value: 900
'''

from ansible.module_utils.basic import AnsibleModule
from distutils.spawn import find_executable


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        os=dict(required=True, choices=['RedHat', 'Suse']),
        state=dict(required=False, default="present", choices=['present', 'absent']),
        node=dict(required=False),
        name=dict(required=True),
        value=dict(required=False)
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(
        changed=False
    )

    # Capture input
    os = module.params['os']
    state = module.params['state']
    node = module.params['node']
    name = module.params['name']
    value = module.params['value']
    type = "property" if node is None else "attribute"

    # Dictionary of commands to run
    commands                                        = {}
    commands["RedHat"]                              = {}
    commands["RedHat"]["property"]                  = {}
    commands["RedHat"]["property"]["set"]           = "pcs property set %s=%s" % (name, value)
    commands["RedHat"]["property"]["unset"]         = "pcs property unset %s" % name
    commands["RedHat"]["property"]["show"]          = "pcs property show %s | grep %s" % (name, name)
    commands["RedHat"]["property"]["list"]          = "pcs property list"
    commands["RedHat"]["property"]["contains"]      = "%s: %s" % (name, value)
    commands["RedHat"]["attribute"]                 = {}
    commands["RedHat"]["attribute"]["set"]          = "pcs node attribute %s %s=%s" % (node, name, value)
    commands["RedHat"]["attribute"]["unset"]        = "pcs node attribute %s %s=" % (node, name)
    commands["RedHat"]["attribute"]["show"]         = "pcs node attribute --name %s | grep %s" % (name, node)
    commands["RedHat"]["attribute"]["list"]         = "pcs node attribute"
    commands["RedHat"]["attribute"]["contains"]     = "%s=%s" % (name, value)
    commands["Suse"]                                = {}
    commands["Suse"]["property"]                    = {}
    commands["Suse"]["property"]["set"]             = "crm configure property %s=%s" % (name, value)
    commands["Suse"]["property"]["unset"]           = "crm configure property"
    commands["Suse"]["property"]["show"]            = "crm configure show type:property | grep %s=" % name
    commands["Suse"]["property"]["list"]            = "crm configure show type:property"
    commands["Suse"]["property"]["contains"]        = "%s=%s" % (name, value)
    commands["Suse"]["attribute"]                   = {}
    commands["Suse"]["attribute"]["set"]            = "crm node attribute %s set %s %s" % (node, name, value)
    commands["Suse"]["attribute"]["unset"]          = "crm node attribute %s delete %s" % (node, name)
    commands["Suse"]["attribute"]["show"]           = "crm node attribute %s show %s" % (node, name)
    commands["Suse"]["attribute"]["list"]           = "crm configure show type:node"
    commands["Suse"]["attribute"]["contains"]       = "name=%s value=%s" % (name, value)

    # Initial checks
    if find_executable('pcs') is None:
        module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")
    if state == "present" and value is None:
        module.fail_json(msg="value parameter must be supplied when state is present")
    # Make sure we can communicate with pcs
    rc, out, err = module.run_command(commands[os][type]["list"])
    if rc != 0:
        module.fail_json(msg="Unable to retreive cluster properties or node attributes. Is the cluster running?", **result)

    ### Functions ###

    # Check if a property or attribute (specified via 'type' parameter) is already set to desired value
    def already_set():
        rc, out, err = module.run_command(commands[os][type]["show"])
        if rc != 0:
            return False
        else:
            return commands[os][type]["contains"] in out
    
    ### Main code ###

    # Set property
    if state == "present":
        if not already_set():
            result["changed"] = True
            if not module.check_mode:
                rc, out, err = module.run_command(commands[os][type]["set"])
                if rc == 0:
                    result["message"] += "Successfully set " + name + " to " + value
                else:
                    result["changed"] = False
                    module.fail_json(msg="Failed to set " + name + " to " + value, **result)
        # Property already set
        else:
            result["message"] += "No changes needed: node attribute is already set. "
    # Unset property
    else:
        rc, out, err = module.run_command(commands[os][type]["show"])
        # Property is already set to some value
        if rc == 0:
            result["changed"] = True
            if not module.check_mode:
                rc, out, err = module.run_command(commands[os][type]["unset"])
                if rc == 0:
                    result["message"] += "Successfully unset " + name
                else:
                    result["changed"] = False
                    module.fail_json(msg="Failed to unset " + name, **result)
        # Property is not currently set
        else:
            result["message"] += "No changes needed: node attribute is not currently set. "


    # SUCCESS STATEMENT
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()