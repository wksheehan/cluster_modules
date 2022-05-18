#!/usr/bin/python

# Copyright: (c) 2022, William Sheehan <willksheehan@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cluster_colocation

short_description: manages cluster colocation constraints

version_added: "1.0"

description: 
    - creates, deletes, modifies cluster colocation constraints
    - for RHEL or SUSE operating systems 

options:
    state:
        description:
            - "present" ensures the colocation constraint exists
            - "absent" ensures the colocatino contraint does not exist
        required: false
        default: present
        choices: ['present', 'absent']
        type: str
    name:
        description:
            - the id of the colocation constraint
        required: false
        default: 'colocation-{source_resource}-{target_resource}-{score}'
        type: str
    source_resource:
        description:
            - the colocation source
            - if the constraint cannot be satisfied, the cluster may decide not to allow the resource to run at all
        required: true
        type: str
    target_resource:
        description:
            - the colocation target, or 'with resource'
            - the cluster will decide where to put this resource first and then decide where to put the source resource
        required: true
        type: str
    source_role:
        description:
            - the role of the source resource
        choices: ['Master', 'Slave', 'Started', 'Stopped']
        required: false
        type: str
    target_role:
        description:
            - the role of the target resource
        choices: ['Master', 'Slave', 'Started', 'Stopped']
        required: false
        type: str
    score:
        description:
            - the constraint score
            - positive values indicate the resource should run on the same node
            - negative values indicate the resources should not run on the same node
            - 'INFINITY' indicates that the source_resource must run on the same node as the target_resource
            - '-INFINITY' indicates that the source_resource must not run on the same node as the target_resource
        required: false
        default: 'INFINITY'
        type: str
author:
    - William Sheehan (@wksheehan)
'''

EXAMPLES = r'''
- name: colocate resource1 with master role of resource2 (resource2-master) with a score of 4000
  cluster_colocation:
    state: present
    source_resource: 'resource1'
    target_resource: 'resource2-master'
    target_role: 'master'
    score: 4000
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.helper_functions import get_os_name, get_os_version, execute_command
from distutils.spawn import find_executable
import xml.etree.ElementTree as ET


def run_module():
    
    # ==== SETUP ====
    
    module_args = dict(
        state=dict(required=False, default="present", choices=["present", "absent"]),
        name=dict(required=False),
        source_resource=dict(required=True),
        target_resource=dict(required=True),
        source_role=dict(required=False, default="Started", choices=["Master", "Slave", "Started", "Stopped"]),
        target_role=dict(required=False, default="Started", choices=["Master", "Slave", "Started", "Stopped"]),
        score=dict(required=False, default="INFINITY")
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(
        changed=False,
        message=""
    )

    os                  = get_os_name(module, result)
    version             = get_os_version(module, result)
    state               = module.params['state']
    name                = module.params['name']
    source_resource     = module.params['node']
    target_resource     = module.params['target_resource']
    source_role         = module.params['source_role']
    target_role         = module.params['target_role']
    score               = module.params['score']    
    
    if os == "Suse":
        version = "all"
    if name is None:
        name = f"colocation-{source_resource}-{target_resource}-{score}"


    # ==== COMMAND DICTIONARY ====

    commands                                        = {}
    commands["RedHat"]                              = {}
    commands["Suse"  ]                              = {}
    commands["RedHat"]["status"]                    = "pcs status"
    commands["Suse"  ]["status"]                    = "crm status"
    commands["RedHat"]["7"  ]                       = {}
    commands["RedHat"]["8"  ]                       = {}
    commands["Suse"  ]["all"]                       = {}
    commands["RedHat"]["7"  ]["read"]               = f"pcs constraint colocation show --full | grep id:{name}"
    commands["RedHat"]["8"  ]["read"]               = f"pcs constraint colocation show --full | grep id:{name}"
    commands["Suse"  ]["all"]["read"]               = f"crm configure show type:colocation | grep {name}"
    commands["RedHat"]["7"  ]["create"]             = f"pcs constraint colocation add {source_role} {source_resource} with {target_role} {target_resource} {score} id={name}"
    commands["RedHat"]["8"  ]["create"]             = f"pcs constraint colocation add {source_role} {source_resource} with {target_role} {target_resource} {score} id={name}"
    commands["Suse"  ]["all"]["create"]             = f"colocation {name} {score}: {source_resource}:{source_role} {target_resource}:{target_role}"
    commands["RedHat"]["7"  ]["delete"]             = f"pcs constraint colocation remove {source_resource} {target_resource}"
    commands["RedHat"]["8"  ]["delete"]             = f"pcs constraint colocation remove {source_resource} {target_resource}"
    commands["Suse"  ]["all"]["delete"]             = f"crm configure delete --force {name}"

    # ==== INITIAL CHECKS ====

    if os == "RedHat" and find_executable('pcs') is None:
        module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")
    # Make sure we can communicate with the cluster
    rc, out, err = module.run_command(commands[os]["status"])
    if rc != 0:
        module.fail_json(msg="Cluster is not running on current node!", **result)


    # ==== FUNCTIONS ====

    def constraint_exists():
        rc, out, err = module.run_command(commands[os][version]["read"], use_unsafe_shell=True)
        return rc == 0
    
    def create_constraint():
        result["changed"] = True
        if not module.check_mode:
            cmd = commands[os][version]["create"]
            execute_command(module, result, cmd, 
                            f"Successfully created constraint {name}. "  
                            f"Failed to create constraint {name}")

    def delete_constraint():
        result["changed"] = True
        if not module.check_mode:
            cmd = commands[os][version]["delete"]
            execute_command(module, result, cmd, 
                            f"Successfully deleted constraint {name}. ",
                            f"Failed to delete constraint {name}")
    
    def update_constraint():
        if not compare_constraints():
            result["changed"] = True
            if not module.check_mode:
                delete_constraint()
                create_constraint()
        else:
            result["message"] += "No updates necessary: constraint already configured as desired. "

    # Compare existing resource constraint against desired resource constraint
    # Returns True if the constraints are equivalent, False if they are different
    def compare_constraints():
         cib = ET.parse("/var/lib/pacemaker/cib/cib.xml")
         curr_constraint = cib.getroot().find(f".//rsc_colocation[@id='{name}']")
         
         if curr_constraint == None:
             module.fail_json(msg="Could not find constraint in the cib file", **result)

         constraint_attributes = curr_constraint.attrib

         return (
                constraint_attributes.get("rsc") == source_resource and
                constraint_attributes.get("rsc-role", "Started") == source_role and
                constraint_attributes.get("with-rsc") == target_resource and
                constraint_attributes.get("with-rsc-role", "Started") == target_role and
                constraint_attributes.get("score", "INFINITY") == score
         )


    # ==== MAIN CODE ====

    if state == "present":
        if constraint_exists():
            update_constraint()
        else:
            create_constraint()
    else:
        if constraint_exists():
            delete_constraint()
        else:
            result["message"] += "No changes needed: constraint does not exist " % name

    # Success
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()