
- hosts: localhost
  become: yes
  become_user: root
  name: "Node standby / online testing"
  tasks:
    - name: "Set the nodes list per OS"
      ansible.builtin.set_fact:
        node1: "x0rapp00leb7"
        node2: "x0rapp01leb7"
      when: ansible_os_family == "RedHat"
    
    - name: "Set the nodes list per OS"
      ansible.builtin.set_fact:
        node1: "x00app00l650"
        node2: "x00app01l650"
      when: ansible_os_family == "Suse"

    - name: "Ensure nodes on standby"
      node_online:
        online: "false"
        node: "{{ item.name }}"
        loop:
        - { name: "{{node1}}" }
        - { name: "{{node2}}" }
      register: resultobj
      
    - name: "Ensure nodes on standby: Output"
      debug:
        msg: '{{ resultobj }}'
    
    - name: "Ensure nodes on standby idempotence"
      node_online:
        online: "false"
        node: "{{ item.name }}"
        loop:
        - { name: "{{node1}}" }
        - { name: "{{node2}}" }
      register: resultobj
      
    - name: "Ensure nodes on standby idempotence: Output"
      debug:
        msg: '{{ resultobj }}'
    
    - name: "Bring nodes online"
      node_online:
        online: "true"
        node: "{{ item.name }}"
        loop:
        - { name: "{{node1}}" }
        - { name: "{{node2}}" }
      register: resultobj
      
    - name: "Bring nodes online: Output"
      debug:
        msg: '{{ resultobj }}'
   
    - name: "Bring nodes online idempotence"
      node_online:
        online: "true"
        node: "{{ item.name }}"
        loop:
        - { name: "{{node1}}" }
        - { name: "{{node2}}" }
      register: resultobj
      
    - name: "Bring nodes online idempotence: Output"
      debug:
        msg: '{{ resultobj }}'