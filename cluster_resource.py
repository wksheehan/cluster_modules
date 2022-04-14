#!/usr/bin/python

# Copyright: (c) 2022, William Sheehan <willksheehan@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: cluster_auth

short_description: authenticates pacemaker to nodes in a cluster

version_added: "1.0"

description: authenticates nodes in a pacemaker cluster for either RHEL or SUSE operating systems 

options:
    os:
        description:
            - the operating system
        required: true
        choices: ['RedHat', 'Suse']
        type: str
    state:
        description:
            - "present" authenticates the node
            - "absent" removes the authentication
        required: false
        default: present
        choices: ['present', 'absent']
        type: str
    node:
        description:
            - the node to authenticate or deauthenticate
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
- name: Authenticate user hacluster on node1 for both the nodes in a two-node cluster (node1 and node2) on RedHat
  cluster_auth:
    os: RedHat
    state: present
    node: node1 node2
    username: hacluster
    password: testpass

- name: Deauthenticate node1 on RedHat
  cluster_auth:
    os: RedHat
    state: absent
    node: node1
    password: testpass
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


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        os=dict(required=True, choices=['RedHat', 'Suse']),
        state=dict(required=False, default="present", choices=['present', 'absent']),
        node=dict(required=True),
        username=dict(required=False, default="hacluster"),
        password=dict(required=True, no_log=True)
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(
        changed=False
    )

    # ADD CHECK MODE SUPPORT
    if module.check_mode:
        module.exit_json(**result)

    # FAILURE STATEMENT
    # module.fail_json(msg='FAILURE MESSAGE', **result)

    # SUCCESS STATEMENT
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()