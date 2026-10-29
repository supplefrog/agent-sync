"""File-free audit/admission binding and ready-diagnostic controls only."""
from pathlib import Path
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import instruction_changes as changes
import audit
import worktree_sync as sync


class BytePath:
    def __init__(self, data, name=''):
        self.data, self.name = data, name
    def __truediv__(self, name):
        name = str(name)
        return BytePath(self.data, self.name+'/'+name if self.name else name)
    def read_bytes(self):
        return self.data[self.name]
    def is_file(self):
        return self.name in self.data


class BoundIntegrationReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = {}
        for name in (changes.INDEX, 'registry.json', changes.NATIVE_LEARNING_OWNER+'/PUBLIC-FILES.json'):
            cls.template[name] = (ROOT/name).read_bytes()
        manifest = json.loads(cls.template[changes.NATIVE_LEARNING_OWNER+'/PUBLIC-FILES.json'])
        for item in manifest['files']:
            name = changes.NATIVE_LEARNING_OWNER+'/'+item['path']
            cls.template[name] = (ROOT/name).read_bytes()
        for row in json.loads(cls.template['registry.json'])['skills']:
            name = 'skills/'+row['name']+'/SKILL.md'
            if (ROOT/name).is_file(): cls.template[name] = (ROOT/name).read_bytes()

    def setUp(self):
        self.data = dict(self.template)
        self.unsafe = set()
        self.path_calls = []

    def path(self, repo, name):
        self.path_calls.append(name)
        if name in self.unsafe:
            raise changes.sync_git.SyncBlocked('linked or unsafe publication path')
        if name.startswith('/') or '\\' in name or '..' in name.split('/'):
            raise changes.sync_git.SyncBlocked('nonexact publication path')
        return name

    def call(self, name=None):
        with patch.object(changes.sync_git, 'safe_path', side_effect=self.path):
            return changes.native_learning_source_reference(BytePath(self.data), name or changes.NATIVE_LEARNING_REFERENCE)

    def index_change(self, mutate):
        index = json.loads(self.data[changes.INDEX]);mutate(index)
        self.data[changes.INDEX] = json.dumps(index).encode()

    def test_exact_source_reference_allowed_and_all_member_paths_checked(self):
        self.assertTrue(self.call())
        self.assertIn(changes.NATIVE_LEARNING_REFERENCE, self.path_calls)
        self.assertIn(changes.INDEX, self.path_calls)
        self.assertIn('registry.json', self.path_calls)
        self.assertGreaterEqual(len(self.path_calls), 92)

    def test_arbitrary_integration_stays_rejected(self):
        self.assertFalse(self.call('integrations/other/SKILL.md'))
        with patch.object(changes.sync_git, 'safe_path', side_effect=self.path):
            self.assertIn('outside canonical skills tree', audit._integration_reference_error(BytePath(self.data), 'integrations/other/SKILL.md'))

    def test_unindexed_source_rejected(self):
        self.data[changes.INDEX] = b'{"surfaces":[]}'
        self.assertFalse(self.call())

    def test_self_indexed_arbitrary_reference_cannot_borrow_case(self):
        self.index_change(lambda value: value['surfaces'].append({'artifact':'integrations/other/SKILL.md','status':'reference'}))
        self.assertFalse(self.call('integrations/other/SKILL.md'))
        self.assertFalse(self.call())

    def test_duplicate_declaration_rejected(self):
        self.index_change(lambda value: value['surfaces'].append(next(row for row in value['surfaces'] if row.get('artifact')==changes.NATIVE_LEARNING_REFERENCE)))
        self.assertFalse(self.call())

    def test_wrong_owner_rejected(self):
        self.index_change(lambda value: next(row for row in value['surfaces'] if row.get('artifact')==changes.NATIVE_LEARNING_REFERENCE).update(owner='skills/unrelated'))
        self.assertFalse(self.call())

    def test_global_or_active_classification_rejected(self):
        for field, value in [('scope','global'),('status','active'),('backup','effective'),('assembly_order',1)]:
            with self.subTest(field=field):
                self.data = dict(self.template)
                self.index_change(lambda index: next(row for row in index['surfaces'] if row.get('artifact')==changes.NATIVE_LEARNING_REFERENCE).update({field:value}))
                self.assertFalse(self.call())

    def test_member_change_rejected(self):
        self.data[changes.NATIVE_LEARNING_REFERENCE] += b' changed'
        self.assertFalse(self.call())

    def test_other_package_member_change_rejected(self):
        manifest = json.loads(self.data[changes.NATIVE_LEARNING_OWNER+'/PUBLIC-FILES.json'])
        other = next(item['path'] for item in manifest['files'] if not item['path'].endswith('SKILL.md'))
        self.data[changes.NATIVE_LEARNING_OWNER+'/'+other] += b' changed'
        self.assertFalse(self.call())

    def test_rehashed_or_missing_manifest_rejected(self):
        name = changes.NATIVE_LEARNING_OWNER+'/PUBLIC-FILES.json'
        self.data[name] += b' '
        self.assertFalse(self.call())
        del self.data[name]
        self.assertFalse(self.call())

    def test_existing_path_boundary_failure_rejected(self):
        for name in [changes.INDEX,changes.NATIVE_LEARNING_REFERENCE,changes.NATIVE_LEARNING_OWNER+'/PUBLIC-FILES.json']:
            with self.subTest(path=name):
                self.unsafe={name};self.assertFalse(self.call())

    def test_named_global_registration_rejected(self):
        registry=json.loads(self.data['registry.json']);registry['skills'].append({'name':'hermes-native-learning','status':'admitted'})
        self.data['registry.json']=json.dumps(registry).encode()
        self.assertFalse(self.call())

    def test_registered_different_name_global_copy_rejected(self):
        registry=json.loads(self.data['registry.json']);registry['skills'].append({'name':'duplicate-reference','status':'admitted'})
        self.data['registry.json']=json.dumps(registry).encode()
        self.data['skills/duplicate-reference/SKILL.md']=self.data[changes.NATIVE_LEARNING_REFERENCE].replace(b'\n',b'\r\n')
        self.assertFalse(self.call())

    def test_unregistered_named_global_copy_rejected(self):
        self.data['skills/hermes-native-learning/SKILL.md']=self.data[changes.NATIVE_LEARNING_REFERENCE]
        self.assertFalse(self.call())

    def test_audit_router_skips_only_the_bound_reference(self):
        with patch.object(changes.sync_git, 'safe_path', side_effect=self.path):
            self.assertIsNone(audit._integration_reference_error(BytePath(self.data), changes.NATIVE_LEARNING_REFERENCE))
        self.data[changes.NATIVE_LEARNING_REFERENCE] += b'changed'
        with patch.object(changes.sync_git, 'safe_path', side_effect=self.path):
            self.assertIn('outside canonical skills tree', audit._integration_reference_error(BytePath(self.data), changes.NATIVE_LEARNING_REFERENCE))


class ReadyFailureDetails(unittest.TestCase):
    def failure(self):
        return sync.reconcile.CheckFailure({'command':'python audit.py check --structural','exit_code':1,
            'diagnostic':'skill entrypoint outside canonical skills tree: integrations/other/SKILL.md',
            'local_log':'.staging/check-failures/example.json'},['python validate.py'])

    def test_ready_plan_keeps_structured_failure_and_completed_checks(self):
        with patch.object(sync,'_qualify',side_effect=self.failure()):
            result=sync.ready_plan(ROOT,'synthetic')
        self.assertEqual(result['result'],'review-required')
        self.assertEqual(result['check_failure']['exit_code'],1)
        self.assertIn('outside canonical skills tree',result['check_failure']['diagnostic'])
        self.assertEqual(result['completed_checks'],['python validate.py'])
        self.assertIn('temporary candidate',result['check_failure']['local_log_scope'])

    def test_ready_sync_keeps_failure_before_any_live_action(self):
        with patch.object(sync,'_primary',return_value=(ROOT,ROOT)), \
                patch.object(sync.sync_git,'git',return_value='synthetic'), \
                patch.object(sync,'_read',return_value=None), \
                patch.object(sync,'_qualify',side_effect=self.failure()), \
                patch.object(sync,'_begin_published_successor') as begin:
            result=sync.ready_sync(ROOT,'synthetic')
        self.assertEqual(result['result'],'incomplete')
        self.assertEqual(result['check_failure']['exit_code'],1)
        self.assertEqual(result['completed_checks'],['python validate.py'])
        begin.assert_not_called()

    def test_existing_sanitizer_applies_and_unsafe_log_pointer_omitted(self):
        detail=self.failure();detail.detail['diagnostic']='failure at '+str(ROOT/'private-evidence.json')
        detail.detail['local_log']=str(ROOT/'private-evidence.json')
        result=sync._ready_check_failure(detail,ROOT)
        self.assertNotIn(str(ROOT),result['check_failure']['diagnostic'])
        self.assertNotIn('local_log',result['check_failure'])


if __name__=='__main__':
    unittest.main()
