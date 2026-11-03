"""Explicit preferences use source acceptance; autonomous claims retain measurement."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from fixture_workspace import configure

configure()

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import instruction_changes as changes
import sync_git


class UserPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.name = 'adapters/codex.json'
        self.receipt = 'evals/results/preference.json'
        self.old = {'host': 'codex', 'instructions': {'target': 'AGENTS.md',
                    'projection': {'sections': [{'label': 'OUTPUT', 'text': 'Be clear.'}]}},
                    'routing': {'permission': 'unchanged'}}
        self.new = copy.deepcopy(self.old)
        self.new['instructions']['projection']['sections'][0]['text'] += ' Use rich visuals.'
        self.baseline = {self.name: json.dumps(self.old).encode()}
        index = json.dumps({'schema_version': 2, 'surfaces': [
            {'artifact': 'surfaces/core.md', 'owner': 'surfaces/core.md'}]}).encode()
        self.baseline[changes.INDEX] = index
        self.put(changes.INDEX, index)
        self.put(self.name, json.dumps(self.new).encode())
        self.row = {'owner': self.name, 'basis': 'user-correction',
                    'change_kind': 'user-preference', 'baseline_sufficient': False,
                    'deviation': 'User selected rich visuals.', 'evidence': 'Explicit user request.',
                    'why_instruction': 'Save at the existing standing owner.',
                    'alternative': 'A chat-only instruction does not persist.',
                    'user_preference': {'request': 'Use rich visuals in my chats.',
                        'scope': 'Codex chat output', 'authority': 'explicit-user-request',
                        'protected_guarantees_unchanged': True}, 'artifacts': {}}
        patch = mock.patch.object(changes, '_before',
                                  side_effect=lambda repo, base, name: self.baseline.get(name))
        patch.start()
        self.addCleanup(patch.stop)

    def put(self, name, data):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def check(self):
        self.row['owner'] = self.row.get('owner', self.name)
        self.row['artifacts'] = {self.name: {
            'before_sha256': hashlib.sha256(self.baseline[self.name]).hexdigest(),
            'after_sha256': hashlib.sha256((self.repo / self.name).read_bytes()).hexdigest()}}
        self.put(self.receipt, json.dumps({'instruction_changes': [self.row]}).encode())
        return changes.check(self.repo, self.repo, 'base', [self.name, self.receipt])

    def test_explicit_output_preference_needs_no_measurements(self):
        with mock.patch.object(changes, 'measurement_eligibility',
                               side_effect=AssertionError('Explicit preference must not launch comparison')):
            self.assertTrue(self.check())

    def test_shared_standing_preference_qualifies(self):
        self.name = 'surfaces/core.md'
        self.row['owner'] = self.name
        self.baseline[self.name] = b'Owner\n<!-- agent-sync-standing -->\nBe clear.\n<!-- /agent-sync-standing -->\n'
        self.put(self.name, self.baseline[self.name].replace(b'Be clear.', b'Use diagrams when useful.'))
        self.assertTrue(self.check())

    def test_missing_or_nonexplicit_authority_rejected(self):
        for field, value in [('authority', 'agent-inference'), ('request', ''),
                             ('scope', ''), ('protected_guarantees_unchanged', False)]:
            with self.subTest(field=field):
                original = copy.deepcopy(self.row)
                self.row['user_preference'][field] = value
                with self.assertRaises(sync_git.SyncBlocked):
                    self.check()
                self.row = original
        del self.row['user_preference']
        with self.assertRaises(sync_git.SyncBlocked):
            self.check()

    def test_agent_proposal_cannot_use_preference_route(self):
        self.row['basis'] = 'observed-deviation'
        with self.assertRaises(sync_git.SyncBlocked):
            self.check()

    def test_adapter_runtime_or_target_change_rejected(self):
        for mutate in (lambda x: x['routing'].update(permission='new'),
                       lambda x: x['instructions'].update(target='another-file')):
            with self.subTest(mutate=mutate):
                data = copy.deepcopy(self.new)
                mutate(data)
                self.put(self.name, json.dumps(data).encode())
                with self.assertRaises(sync_git.SyncBlocked):
                    self.check()

    def test_ambiguous_json_and_nonprojection_type_changes_rejected(self):
        self.put(self.name, json.dumps(self.new).replace('"host": "codex"',
                 '"host": "other", "host": "codex"').encode())
        with self.assertRaises(sync_git.SyncBlocked):
            self.check()
        self.old['schema_version'] = 1
        self.baseline[self.name] = json.dumps(self.old).encode()
        self.new['schema_version'] = True
        self.put(self.name, json.dumps(self.new).encode())
        with self.assertRaises(sync_git.SyncBlocked):
            self.check()

    def test_core_outside_standing_change_rejected(self):
        self.name = 'surfaces/core.md'
        self.row['owner'] = self.name
        self.baseline[self.name] = b'Permission\n<!-- agent-sync-standing -->\nBe clear.\n<!-- /agent-sync-standing -->\n'
        self.put(self.name, self.baseline[self.name].replace(b'Permission', b'Changed permission'))
        with self.assertRaises(sync_git.SyncBlocked):
            self.check()

    def test_new_owner_or_executable_not_a_preference(self):
        self.name = 'tools/new.py'
        self.row['owner'] = self.name
        self.baseline[self.name] = b'old'
        self.put(self.name, b'new')
        with self.assertRaises(sync_git.SyncBlocked):
            changes.correction_eligibility(self.repo, self.repo, self.name, self.name,
                                           self.row, 'base', [self.name], [])

    def test_stale_binding_and_wrong_owner_still_rejected(self):
        self.check()
        path = self.repo / self.name
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(sync_git.SyncBlocked, 'not bound'):
            changes.check(self.repo, self.repo, 'base', [self.name, self.receipt])
        self.row['owner'] = 'surfaces/core.md'
        with self.assertRaisesRegex(sync_git.SyncBlocked, 'wrong architectural owner'):
            self.check()

    def test_behavior_claim_cannot_borrow_preference_route(self):
        self.row['task_contract'] = {'claim': 'Better answers'}
        with self.assertRaises(sync_git.SyncBlocked):
            self.check()

    def test_ordinary_prose_still_requires_measurement(self):
        self.row.pop('change_kind')
        self.row.pop('user_preference')
        self.row['basis'] = 'observed-deviation'
        with self.assertRaisesRegex(sync_git.SyncBlocked, 'instruction excluded'):
            self.check()


if __name__ == '__main__':
    unittest.main()
