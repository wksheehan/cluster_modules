#!/usr/bin/python

# Copyright: (c) 2022, William Sheehan <willksheehan@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
from operator import truediv
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
    resource_class:
        description:
            - the class of resource to configure
        choices: ['stonith', 'ocf',...]
        required: false
        type: str
    resource_provider:
        description:
            - the provider of resource to configure
        choices: ['heartbeat',...]
        required: false
        type: str
    resource_type:
        description:
            - the type of resource to configure (the resource agent)
        choices: ['azure-events', 'fence_azure_arm', 'IPaddr2',...]
        required: false
        type: str
    options:
        description:
            - the instance attributes, operations, and meta attributes for the resource
            - specify the exact list you wish to be present
            - the module will add or remove any extraneous parameters necessary
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
import xml.etree.ElementTree as ET
import uuid
import tempfile


def run_module():
    
    # ==== Setup ====
    
    module_args = dict(
        os=dict(required=True, choices=['RedHat', 'Suse']),
        state=dict(required=False, default="present", choices=['present', 'absent']),
        name=dict(required=True),
        resource_class=dict(required=False, default=""),
        resource_provider=dict(required=False, default=""),
        resource_type=dict(required=False),
        options=dict(required=False, default="")
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(
        changed=False
    )

    os                  = module.params['os']
    state               = module.params['state']
    name                = module.params['name']
    resource_class      = module.params['resource_class']
    resource_provider   = module.params['resource_provider']
    resource_type       = module.params['resource_type']
    options             = module.params['options']

    class_provider_type = format_class_provider_type()
    read_type           = "stonith" if resource_class == "stonith" else "resource"
    curr_cib_path       = "/var/lib/pacemaker/cib/cib.xml"
    new_cib_name        = "shadow-" + str(uuid.uuid4()) + ".xml"

# TODO:
# Clone creation (maybe separate module)
# Master slave configuration check
# Promotable status check
# Is the option string ever different for Suse vs RedHat 7 vs RedHat 8?


    # ==== Initial checks ====

    if find_executable('pcs') is None:
        module.fail_json(msg="'pcs' executable not found. Install 'pcs'.")
    if state == "present" and resource_type is None:
        module.fail_json(msg='Must specify resource_type when state is present' **result)
    rc, out, err = module.run_command(commands[os]["status"])
    if rc != 0:
        module.fail_json(msg="Cluster is not running on current node!", **result)


    # ==== Command dictionary ====

    commands                                        = {}
    commands["RedHat"]                              = {}
    commands["Suse"  ]                              = {}
    commands["Redhat"]["status"]                    = "pcs status"
    commands["Suse"  ]["status"]                    = "crm status"
    commands["Redhat"]["push_cib"]                  = "pcs cluster cib-push %s" # % new_cib_path
    commands["Suse"  ]["push_cib"]                  = "crm -c %s cib commit"    # % new_cib_path
    commands["RedHat"]["resource"]                  = {}
    commands["Suse"  ]["resource"]                  = {}
    commands["RedHat"]["resource"]["read"]          = f"pcs {read_type} config {name}" % (read_type, name)
    commands["Suse"  ]["resource"]["read"]          = f"crm config show {name}" 
    commands["RedHat"]["resource"]["create"]        = f"pcs {read_type} create {name} {class_provider_type} {options}"
    commands["Suse"  ]["resource"]["create"]        = f"crm configure primitive {name} {class_provider_type} {options}"
    commands["Redhat"]["resource"]["update"]        = f"pcs -f {new_cib_name} {read_type} create {name} {class_provider_type} {options}"
    commands["Suse"  ]["resource"]["update"]        = f"crm -F -c {new_cib_name} configure primitive {name} {class_provider_type} {options}"
    commands["RedHat"]["resource"]["delete"]        = f"pcs resource delete {name}"
    commands["Suse"  ]["resource"]["delete"]        = f"crm configure delete --force {name}"
    

    # ==== Functions ====
    
    # Formats the class:provider:type parameter for cluster creation
    def format_class_provider_type():
        class_provider_type = ""
        if resource_class is not None:
            class_provider_type += resource_class + ":" 
        if resource_provider is not None:
            class_provider_type += resource_provider + ":" 
        if resource_type is not None:
            class_provider_type += resource_type + ":"
        if resource_class or resource_provider or resource_type:
            class_provider_type = class_provider_type[:-1]
        return class_provider_type
    
    # Returns true if a resource with the given name exists
    def resource_exists():
        rc, out, err = module.run_command(commands[os]["resource"]["read"])
        if rc == 0:
            return True
        else:
            return False

    # Creates a new resource with the specified options
    def create_resource():
        result["changed"] = True
        if not module.check_mode:
            rc, out, err = module.run_command(commands[os]["resource"]["create"])
            if rc == 0:
                result["message"] += "Resource was successfully created. "
            else:
                result["changed"] = False
                module.fail_json(msg="Failed to create the resource", **result)
    
    # Deletes an existing resource
    def remove_resource():
        result["changed"] = True
        if not module.check_mode:
            rc, out, err = module.run_command(commands[os]["resource"]["delete"])
            if rc == 0:
                result["message"] += "Resource was successfully removed. "
            else:
                result["changed"] = False
                module.fail_json(msg="Failed to remove the resource", **result)

    # Updates an existing resource to match the configuration specified exactly
    def update_resource():
        # Make sure current cib exists
        if not os.path.isfile(curr_cib_path):
            module.fail_json(msg="Unable to find CIB file for existing resource", **result)

        if os == "Suse":
            # Create an empty shadow cib file
            rc, out, err = module.run_command("crm cib new %s empty" % new_cib_name)
            if rc != 0:
                module.fail_json(msg="Error creating shadow cib file before updating resource", **result)
        
        # Create the desired resource, without affecting the current cluster, by using temporary (shadow) cib file
        rc, out, err = module.run_command(commands[os]["resource"]["update"]) 
        if rc != 0:
            module.fail_json(msg="Error creating resource using the temporary (shadow) cib file", **result)
        
        new_cib_path = f"/var/lib/pacemaker/cib/{new_cib_name}" if os == "Suse" else f"./{new_cib_name}"

        # Get the current and new resource XML objects
        curr_cib        = ET.parse(curr_cib_path)
        new_cib         = ET.parse(new_cib_path)
        curr_resource   = curr_cib.getroot().find(f".//primitive[@id='{name}']")
        new_resource    = new_cib.getroot().find(f".//primitive[@id='{name}']")

        is_different    = compare_resources(curr_resource, new_resource)

        if is_different:
            result["changed"] = True
            if not module.check_mode:
                # Update the current resource to match the desired resource
                curr_resource.clear()
                curr_resource.text = new_resource.text
                curr_resource.tail = new_resource.tail
                curr_resource.tag = new_resource.tag
                curr_resource.attrib = new_resource.attrib
                curr_resource[:] = new_resource[:]
                # Write the new XML to shadow cib / temporary cib file
                updated_xml=ET.ElementTree(curr_cib.getroot())                                  # Get the updated xml
                updated_xml.write(new_cib_path)                                                 # Write the xml to the temporary (shadow) cib
                rc, out, err = module.run_command(commands[os]["push_cib"] % new_cib_path)   # Update the live cluster
                if rc == 0:
                    result["message"] += "Successfully updated the resource. "
                else:
                    result["changed"] = False
                    module.fail_json(msg="Failed to update the resource", **result)
        # No differences
        else:
            result["message"] += "No updates necessary: resource already configured as desired. "
    
    def compare_resources(resource1, resource2):
        print()


    # ==== Main code ====

    if state == "present":
        if resource_exists():
            update_resource()
        else:
            create_resource()
    else:
        if resource_exists():
            remove_resource()
        else:
            result["message"] += "No changes needed: resource does not exist. "

    # Success
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()