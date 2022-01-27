#!/usr/bin/python

# (c) 2018-2022, NetApp, Inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = '''
module: na_ontap_volume_clone
short_description: NetApp ONTAP manage volume clones.
extends_documentation_fragment:
    - netapp.ontap.netapp.na_ontap
version_added: 2.6.0
author: NetApp Ansible Team (@carchi8py) <ng-ansibleteam@netapp.com>
description:
- Create NetApp ONTAP volume clones.
- A FlexClone License is required to use this module
options:
  state:
    description:
    - Whether volume clone should be created.
    choices: ['present']
    type: str
    default: 'present'
  parent_volume:
    description:
    - The parent volume of the volume clone being created.
    required: true
    type: str
  name:
    description:
    - The name of the volume clone being created.
    required: true
    type: str
    aliases:
    - volume
  vserver:
    description:
    - Vserver in which the volume clone should be created.
    required: true
    type: str
  parent_snapshot:
    description:
    - Parent snapshot in which volume clone is created off.
    type: str
  parent_vserver:
    description:
    - Vserver of parent volume in which clone is created off.
    type: str
  qos_policy_group_name:
    description:
    - The qos-policy-group-name which should be set for volume clone.
    type: str
  space_reserve:
    description:
    - The space_reserve setting which should be used for the volume clone.
    choices: ['volume', 'none']
    type: str
  volume_type:
    description:
    - The volume-type setting which should be used for the volume clone.
    choices: ['rw', 'dp']
    type: str
  junction_path:
    version_added: 2.8.0
    description:
    - Junction path of the volume.
    type: str
  uid:
    version_added: 2.9.0
    description:
    - The UNIX user ID for the clone volume.
    type: int
  gid:
    version_added: 2.9.0
    description:
    - The UNIX group ID for the clone volume.
    type: int
  split:
    version_added: '20.2.0'
    description:
    - Split clone volume from parent volume.
    type: bool
'''

EXAMPLES = """
    - name: create volume clone
      na_ontap_volume_clone:
        state: present
        username: "{{ netapp username }}"
        password: "{{ netapp password }}"
        hostname: "{{ netapp hostname }}"
        vserver: vs_hack
        parent_volume: normal_volume
        name: clone_volume_7
        space_reserve: none
        parent_snapshot: backup1
        junction_path: /clone_volume_7
        uid: 1
        gid: 1
"""

RETURN = """
"""

import traceback
from ansible.module_utils.basic import AnsibleModule
import ansible_collections.netapp.ontap.plugins.module_utils.netapp as netapp_utils
from ansible_collections.netapp.ontap.plugins.module_utils.netapp_module import NetAppModule
from ansible_collections.netapp.ontap.plugins.module_utils.netapp import OntapRestAPI
from ansible_collections.netapp.ontap.plugins.module_utils import rest_generic
from ansible.module_utils._text import to_native

HAS_NETAPP_LIB = netapp_utils.has_netapp_lib()


class NetAppONTAPVolumeClone:
    """
        Creates a volume clone
    """

    def __init__(self):
        """
            Initialize the NetAppOntapVolumeClone class
        """
        self.argument_spec = netapp_utils.na_ontap_host_argument_spec()
        self.argument_spec.update(dict(
            state=dict(required=False, type='str', choices=['present'], default='present'),
            parent_volume=dict(required=True, type='str'),
            name=dict(required=True, type='str', aliases=["volume"]),
            vserver=dict(required=True, type='str'),
            parent_snapshot=dict(required=False, type='str', default=None),
            parent_vserver=dict(required=False, type='str', default=None),
            qos_policy_group_name=dict(required=False, type='str', default=None),
            space_reserve=dict(required=False, type='str', choices=['volume', 'none'], default=None),
            volume_type=dict(required=False, type='str', choices=['rw', 'dp']),
            junction_path=dict(required=False, type='str', default=None),
            uid=dict(required=False, type='int'),
            gid=dict(required=False, type='int'),
            split=dict(required=False, type='bool', default=None),
        ))

        self.module = AnsibleModule(
            argument_spec=self.argument_spec,
            supports_check_mode=True,
            required_together=[
                ['uid', 'gid']
            ],
            mutually_exclusive=[
                ('junction_path', 'parent_vserver'),
                ('uid', 'parent_vserver'),
                ('gid', 'parent_vserver')
            ]
        )

        self.na_helper = NetAppModule()
        self.parameters = self.na_helper.set_parameters(self.module.params)
        self.rest_api = OntapRestAPI(self.module)
        unsupported_rest_properties = ['space_reserve']
        self.use_rest = self.rest_api.is_rest_supported_properties(self.parameters, unsupported_rest_properties)
        if not self.use_rest:
            if HAS_NETAPP_LIB is False:
                self.module.fail_json(msg="the python NetApp-Lib module is required")
            elif self.parameters.get('parent_vserver'):
                # use cluster ZAPI, as vserver ZAPI does not support parent-vserser for create
                self.create_server = netapp_utils.setup_na_ontap_zapi(module=self.module)
                # keep vserver for ems log and clone-get
                self.vserver = netapp_utils.setup_na_ontap_zapi(module=self.module, vserver=self.parameters['vserver'])
            else:
                self.vserver = netapp_utils.setup_na_ontap_zapi(module=self.module, vserver=self.parameters['vserver'])
                self.create_server = self.vserver

    def create_volume_clone(self):
        """
        Creates a new volume clone
        """
        if self.use_rest:
            return self.create_volume_clone_rest()
        clone_obj = netapp_utils.zapi.NaElement('volume-clone-create')
        clone_obj.add_new_child("parent-volume", self.parameters['parent_volume'])
        clone_obj.add_new_child("volume", self.parameters['name'])
        if self.parameters.get('qos_policy_group_name'):
            clone_obj.add_new_child("qos-policy-group-name", self.parameters['qos_policy_group_name'])
        if self.parameters.get('space_reserve'):
            clone_obj.add_new_child("space-reserve", self.parameters['space_reserve'])
        if self.parameters.get('parent_snapshot'):
            clone_obj.add_new_child("parent-snapshot", self.parameters['parent_snapshot'])
        if self.parameters.get('parent_vserver'):
            clone_obj.add_new_child("parent-vserver", self.parameters['parent_vserver'])
            clone_obj.add_new_child("vserver", self.parameters['vserver'])
        if self.parameters.get('volume_type'):
            clone_obj.add_new_child("volume-type", self.parameters['volume_type'])
        if self.parameters.get('junction_path'):
            clone_obj.add_new_child("junction-path", self.parameters['junction_path'])
        if self.parameters.get('uid'):
            clone_obj.add_new_child("uid", str(self.parameters['uid']))
            clone_obj.add_new_child("gid", str(self.parameters['gid']))
        try:
            self.create_server.invoke_successfully(clone_obj, True)
        except netapp_utils.zapi.NaApiError as exc:
            self.module.fail_json(msg='Error creating volume clone: %s: %s' %
                                      (self.parameters['name'], to_native(exc)), exception=traceback.format_exc())
        if 'split' in self.parameters and self.parameters['split']:
            self.start_volume_clone_split()

    def modify_volume_clone(self):
        """
        Modify an existing volume clone
        """
        if 'split' in self.parameters and self.parameters['split']:
            self.start_volume_clone_split()

    def start_volume_clone_split(self):
        """
        Starts a volume clone split
        """
        if self.use_rest:
            return self.start_volume_clone_split_rest()
        clone_obj = netapp_utils.zapi.NaElement('volume-clone-split-start')
        clone_obj.add_new_child("volume", self.parameters['name'])
        try:
            self.vserver.invoke_successfully(clone_obj, True)
        except netapp_utils.zapi.NaApiError as exc:
            self.module.fail_json(msg='Error starting volume clone split: %s: %s' %
                                      (self.parameters['name'], to_native(exc)), exception=traceback.format_exc())

    def get_volume_clone(self):
        if self.use_rest:
            return self.get_volume_clone_rest()
        clone_obj = netapp_utils.zapi.NaElement('volume-clone-get')
        clone_obj.add_new_child("volume", self.parameters['name'])
        current = None
        try:
            results = self.vserver.invoke_successfully(clone_obj, True)
            if results.get_child_by_name('attributes'):
                attributes = results.get_child_by_name('attributes')
                info = attributes.get_child_by_name('volume-clone-info')
                current = {}
                # Check if clone is currently splitting. Whilst a split is in
                # progress, these attributes are present in 'volume-clone-info':
                # block-percentage-complete, blocks-scanned & blocks-updated.
                if info.get_child_by_name('block-percentage-complete') or \
                        info.get_child_by_name('blocks-scanned') or \
                        info.get_child_by_name('blocks-updated'):
                    current["split"] = True
                else:
                    # Clone hasn't been split.
                    current["split"] = False
            return current
        except netapp_utils.zapi.NaApiError as error:
            # Error 15661 denotes a volume clone not being found.
            if to_native(error.code) != "15661":
                self.module.fail_json(msg='Error fetching volume clone information %s: %s' %
                                          (self.parameters['name'], to_native(error)), exception=traceback.format_exc())
        return None

    def get_volume_clone_rest(self):
        api = 'storage/volumes'
        params = {'name': self.parameters['name'],
                  'svm.name': self.parameters['vserver'],
                  'clone.is_flexclone': True,
                  'fields': 'uuid,'
                            'clone.parent_volume.name,'
                            'qos.policy.name,'
                            'clone.parent_snapshot.name,'
                            'clone.parent_svm.name,'
                            'nas.path,'
                            'nas.uid,'
                            'nas.gid'}
        record, error = rest_generic.get_one_record(self.rest_api, api, params)
        if error:
            self.module.fail_json(msg='Error getting volume clone %s: %s' % (self.parameters['name'], to_native(error)),
                                  exception=traceback.format_exc())
        if record:
            return self.format_get_volume_clone_rest(record)
        return record

    def format_get_volume_clone_rest(self, record):
        return {
            'name': record.get('name', None),
            'uuid': record.get('uuid', None),
            'parent_volume': self.na_helper.safe_get(record, ['clone', 'parent_volume', 'name']),
            'vserver': self.na_helper.safe_get(record, ['svm', 'name']),
            'qos_policy_group_name': self.na_helper.safe_get(record, ['qos', 'policy', 'name']),
            'parent_snapshot': self.na_helper.safe_get(record, ['clone', 'parent_snapshot', 'name']),
            'parent_vserver': self.na_helper.safe_get(record, ['clone', 'parent_svm', 'name']),
            'volume_type': record.get('type', None),
            'junction_path': self.na_helper.safe_get(record, ['nas', 'path']),
            'uid': self.na_helper.safe_get(record, ['nas', 'uid']),
            'gid': self.na_helper.safe_get(record, ['nas', 'gid']),
            'split': False
        }

    def create_volume_clone_rest(self):
        api = 'storage/volumes'
        body = {'name': self.parameters['name'],
                'clone.parent_volume.name': self.parameters['parent_volume'],
                "clone.is_flexclone": True,
                "svm.name": self.parameters['vserver']}
        if self.parameters.get('qos_policy_group_name'):
            body['qos.policy.name'] = self.parameters['qos_policy_group_name']
        if self.parameters.get('parent_snapshot'):
            body['clone.parent_snapshot.name'] = self.parameters['parent_snapshot']
        if self.parameters.get('parent_vserver'):
            body['clone.parent_svm.name'] = self.parameters['parent_vserver']
        if self.parameters.get('volume_type'):
            body['type'] = self.parameters['volume_type']
        if self.parameters.get('junction_path'):
            body['nas.path'] = self.parameters['junction_path']
        if self.parameters.get('uid'):
            body['nas.uid'] = self.parameters['uid']
        if self.parameters.get('gid'):
            body['nas.gid'] = self.parameters['gid']
        dummy, error = rest_generic.post_async(self.rest_api, api, body, job_timeout=120)
        if error:
            self.module.fail_json(
                msg='Error creating volume clone %s: %s' % (self.parameters['name'], to_native(error)),
                exception=traceback.format_exc())

    def start_volume_clone_split_rest(self):
        api = 'storage/volumes'
        body = {'clone.split_initiated': True}
        dummy, error = rest_generic.patch_async(self.rest_api, api, self.parameters['uuid'], body, job_timeout=120)
        if error:
            self.module.fail_json(msg='Error starting volume clone split %s: %s' % (self.parameters['name'],
                                                                                    to_native(error)),
                                  exception=traceback.format_exc())

    def apply(self):
        """
        Run Module based on playbook
        """
        if not self.use_rest:
            netapp_utils.ems_log_event("na_ontap_volume_clone", self.vserver)
        current = self.get_volume_clone()
        if self.use_rest and current:
            self.parameters['uuid'] = current['uuid']
        modify = None
        cd_action = self.na_helper.get_cd_action(current, self.parameters)
        if cd_action is None and self.parameters['state'] == 'present':
            modify = self.na_helper.get_modified_attributes(current, self.parameters)
        if self.na_helper.changed and not self.module.check_mode:
            if cd_action == 'create':
                self.create_volume_clone()
            if modify:
                self.modify_volume_clone()
        self.module.exit_json(changed=self.na_helper.changed)


def main():
    """
    Creates the NetApp Ontap Volume Clone object and runs the correct play task
    """
    obj = NetAppONTAPVolumeClone()
    obj.apply()


if __name__ == '__main__':
    main()
