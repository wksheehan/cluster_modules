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
    
    # ==== Setup ====
    
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
        changed=False,
        message=""
    )

    os      = module.params['os']
    state   = module.params['state']
    node    = module.params['node']
    name    = module.params['name']
    value   = module.params['value']
    ctype   = "property" if node is None else "attribute"


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
    commands["RedHat"]["property" ]["get"]          = "pcs property list --all | grep %s | awk -F'[:]' '{print $2}' | tr -d '[:space:]'" % name # Good, but if the value contains spaces there will be an issue during equality comparison
    commands["Suse"  ]["property" ]["get"]          = "crm configure get_property %s" % name # GOOD
    commands["RedHat"]["attribute"]["get"]          = "pcs node attribute --name %s | grep %s | awk -F'[=]' '{print $2}' | tr -d '[:space:]'" % (name, node) # GOOD
    commands["Suse"  ]["attribute"]["get"]          = "crm node show %s | grep %s | awk -F'[=]' '{print $2}' | tr -d '[:space:]'" % (node, name) # GOOD
    commands["RedHat"]["property" ]["check"]        = "pcs property show %s | grep %s" % (name, name) # GOOD
    commands["Suse"  ]["property" ]["check"]        = "crm configure show type:property | grep %s=" % name # GOOD
    commands["RedHat"]["attribute"]["check"]        = "pcs node attribute --name %s | grep %s" % (name, node) # GOOD
    commands["Suse"  ]["attribute"]["check"]        = "crm node attribute %s show %s" % (node, name) # GOOD
    commands["RedHat"]["property" ]["list"]         = "pcs property list"
    commands["Suse"  ]["property" ]["list"]         = "crm configure show type:property"
    commands["RedHat"]["attribute"]["list"]         = "pcs node attribute"
    commands["Suse"  ]["attribute"]["list"]         = "crm configure show type:node"
    commands["RedHat"]["property" ]["contains"]     = "%s: %s" % (name, value)
    commands["Suse"  ]["property" ]["contains"]     = "%s=%s" % (name, value)
    commands["RedHat"]["attribute"]["contains"]     = "%s=%s" % (name, value)
    commands["Suse"  ]["attribute"]["contains"]     = "name=%s value=%s" % (name, value)


    # ==== Initial checks ====

    if os == "RedHat" and find_executable('pcs') is None:
        module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")
    if state == "present" and value is None:
        module.fail_json(msg="value parameter must be supplied when state is present")
    # Make sure we can communicate with pcs
    rc, out, err = module.run_command(commands[os][ctype]["list"])
    if rc != 0:
        module.fail_json(msg="Unable to retreive cluster properties or node attributes. Is the cluster running?", **result)


    # ==== Functions ====

    # Get the current property value
    def get_property():
        rc, out, err = module.run_command(commands[os][ctype]["get"], use_unsafe_shell=True)
        if rc != 0:
            return None
        else:
            return out
    
    # Check if a property value is set to something other than default
    def check_property():
        rc, out, err = module.run_command(commands[os][ctype]["check"], use_unsafe_shell=True)
        if rc == 0:
            return True
        else:
            return False
    
    def set_property():
        result["changed"] = True
        if not module.check_mode:
            cmd = commands[os][ctype]["set"]
            rc, out, err = module.run_command(cmd)
            if rc == 0:
                result["message"] += "Successfully set " + name + " to " + value
            else:
                result["changed"] = False
                result["stdout"] = out
                result["command_used"] = cmd
                module.fail_json(msg="Failed to set " + name + " to " + value, **result)

    def unset_property():
        result["changed"] = True
        if not module.check_mode:
            cmd = commands[os][ctype]["unset"]
            rc, out, err = module.run_command(cmd)
            if rc == 0:
                result["message"] += "Successfully unset " + name
            else:
                result["changed"] = False
                result["stdout"] = out
                result["command_used"] = cmd
                module.fail_json(msg="Failed to unset " + name, **result)

    # ==== Main code ====

    # Set property
    if state == "present":
        # Property is not set to desired value
        if get_property() != value:
            set_property()
        # Property is already set to correct value
        else:
            result["message"] += "No changes needed: %s is already set. " % ctype
    # Unset property
    else:
        # Property is set to something
        if check_property():
            unset_property()
        # Property is not currently set
        else:
            result["message"] += "No changes needed: %s is not currently set. " % ctype


    # Success
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()