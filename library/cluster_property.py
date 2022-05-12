#!/usr/bin/python

# Copyright: (c) 2022, William Sheehan <willksheehan@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: cluster_property

short_description: sets and unsets cluster and node properties

version_added: "1.0"

description: 
    - sets or unsets specific properties for the cluster configuration or for specific nodes
    - for RHEL or SUSE operating systems 

options:
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
    state: present
    name: stonith-timeout
    value: 900
'''

from ansible.module_utils.basic import AnsibleModule
from distutils.spawn import find_executable
import platform


def run_module():
    
    # ==== Setup ====
    
    module_args = dict(
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

    os      = platform.dist()[0].lower()
    state   = module.params['state']
    node    = module.params['node']
    name    = module.params['name']
    value   = module.params['value']
    ctype   = "property" if node is None else "attribute"


    # ==== Command dictionary ====

    commands                                        = {}
    commands["redhat"]                              = {}
    commands["suse"]                                = {}
    commands["redhat"]["property" ]                 = {}
    commands["suse"  ]["property" ]                 = {}
    commands["redhat"]["attribute"]                 = {}
    commands["suse"  ]["attribute"]                 = {}
    commands["redhat"]["property" ]["set"]          = "pcs property set %s=%s" % (name, value)
    commands["suse"  ]["property" ]["set"]          = "crm configure property %s=%s" % (name, value)
    commands["redhat"]["attribute"]["set"]          = "pcs node attribute %s %s=%s" % (node, name, value)
    commands["suse"  ]["attribute"]["set"]          = "crm node attribute %s set %s %s" % (node, name, value)
    commands["redhat"]["property" ]["unset"]        = "pcs property unset %s" % name
    commands["suse"  ]["property" ]["unset"]        = "crm configure property"
    commands["redhat"]["attribute"]["unset"]        = "pcs node attribute %s %s=" % (node, name)
    commands["suse"  ]["attribute"]["unset"]        = "crm node attribute %s delete %s" % (node, name)
    commands["redhat"]["property" ]["get"]          = "pcs property list --all | grep %s | awk -F'[:]' '{print $2}' | tr -d '[:space:]'" % name # If the value contains spaces there will be an issue during equality comparison
    commands["suse"  ]["property" ]["get"]          = "crm configure get_property %s | tr -d '[:space:]'" % name
    commands["redhat"]["attribute"]["get"]          = "pcs node attribute --name %s | grep %s | awk -F'[=]' '{print $2}' | tr -d '[:space:]'" % (name, node)
    commands["suse"  ]["attribute"]["get"]          = "crm node show %s | grep %s | awk -F'[=]' '{print $2}' | tr -d '[:space:]'" % (node, name)
    commands["redhat"]["property" ]["check"]        = "pcs property show %s | grep %s" % (name, name)
    commands["suse"  ]["property" ]["check"]        = "crm configure show type:property | grep %s=" % name
    commands["redhat"]["attribute"]["check"]        = "pcs node attribute --name %s | grep %s" % (name, node)
    commands["suse"  ]["attribute"]["check"]        = "crm node attribute %s show %s" % (node, name)
    commands["redhat"]["property" ]["list"]         = "pcs property list"
    commands["suse"  ]["property" ]["list"]         = "crm configure show type:property"
    commands["redhat"]["attribute"]["list"]         = "pcs node attribute"
    commands["suse"  ]["attribute"]["list"]         = "crm configure show type:node"
    commands["redhat"]["property" ]["contains"]     = "%s: %s" % (name, value)
    commands["suse"  ]["property" ]["contains"]     = "%s=%s" % (name, value)
    commands["redhat"]["attribute"]["contains"]     = "%s=%s" % (name, value)
    commands["suse"  ]["attribute"]["contains"]     = "name=%s value=%s" % (name, value)


    # ==== Initial checks ====

    if os == "redhat" and find_executable('pcs') is None:
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
                result["error_message"] = err
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
                result["error_message"] = err
                result["command_used"] = cmd
                module.fail_json(msg="Failed to unset " + name, **result)


    # ==== Main code ====

    if state == "present":
        if get_property() != value:
            set_property()
        else:
            result["message"] += "No changes needed: %s is already set. " % ctype
    else:
        if check_property():
            unset_property()
        else:
            result["message"] += "No changes needed: %s is not currently set. " % ctype

    # Success
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()