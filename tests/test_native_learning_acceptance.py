"""Proposed scoped consumer controls; source preparation does not execute them."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
V3_BASELINE = '6c40eca7f39f89c9f44dc1f7eb728f139ba31856'
sys.path.insert(0, str(ROOT / 'tools'))
import instruction_changes as gate


class MemoryPath:
    def __init__(self, data, name=''):
        self.data, self.name = data, name
    def __truediv__(self, name):
        return MemoryPath(self.data, str(name))
    def read_bytes(self):
        return self.data[self.name]
    def is_file(self):
        return self.name in self.data


class NativeLearningSourceAcceptance(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads(subprocess.check_output(['git', '-C', str(ROOT), 'show', V3_BASELINE + ':evals/results/native-learning-source-binding.json']))
        self.row = copy.deepcopy(self.receipt['instruction_changes'][0])
        self.records = copy.deepcopy(self.receipt['change_reconciliation'])
        self.paths = self.receipt['selected_paths']
        self.data = {name: subprocess.check_output(['git', '-C', str(ROOT), 'show', V3_BASELINE + ':' + name]) for name in self.paths}
        self.index_before = subprocess.check_output(['git', '-C', str(ROOT), 'show', self.receipt['base'] + ':' + gate.INDEX])
        self.before = {gate.INDEX: self.index_before}
        for name in gate.CONTRACTS:
            self.before[name] = subprocess.check_output(['git', '-C', str(ROOT), 'show', self.receipt['base'] + ':' + name])
        self.name = next(iter(self.row['artifacts']))

    def call(self):
        with patch.object(gate, '_before', side_effect=lambda source, base, name: self.before.get(name)):
            return gate.correction_eligibility(MemoryPath(self.data), None, self.name,
                self.row['owner'], self.row, self.receipt['base'], self.paths, self.records)

    def test_exact_source_does_not_authenticate_or_activate(self):
        result = self.call()
        self.assertTrue(result['eligible'])
        self.assertFalse(result['approval_authenticated'])
        self.assertFalse(result['behavioral_proof'])

    def test_missing_package_selection_rejected(self):
        self.paths = [name for name in self.paths if not name.endswith('/PUBLIC-FILES.json')]
        with self.assertRaises(gate.sync_git.SyncBlocked): self.call()

    def test_package_substitution_rejected(self):
        self.data[self.name] += b'changed'
        with self.assertRaises(gate.sync_git.SyncBlocked): self.call()

    def test_wrong_index_rejected(self):
        self.data[gate.INDEX] += b' '
        with self.assertRaises(gate.sync_git.SyncBlocked): self.call()

    def test_existing_instruction_baseline_rejected(self):
        self.before[self.name] = b'prior source'
        with self.assertRaises(gate.sync_git.SyncBlocked): self.call()

    def test_rehashed_unrelated_intent_rejected(self):
        target = sorted(gate.CONTRACTS)[0]
        self.data[target] += b' unrelated policy'
        self.records[0]['artifacts'][target]['after_sha256'] = gate._hash(self.data[target])
        with self.assertRaises(gate.sync_git.SyncBlocked): self.call()

    def test_forged_source_binding_rejected(self):
        self.records[0]['artifacts'][self.name]['after_sha256'] = '0' * 64
        with self.assertRaises(gate.sync_git.SyncBlocked): self.call()

    def test_missing_intent_binding_rejected(self):
        del self.records[0]['artifacts'][gate.INDEX]
        with self.assertRaises(gate.sync_git.SyncBlocked): self.call()

    def test_activation_claim_rejected(self):
        self.row['native_learning_acceptance']['activation'] = 'authorized'
        with self.assertRaises(gate.sync_git.SyncBlocked): self.call()

    def test_behavioral_evidence_cannot_borrow_source_route(self):
        self.row['behavior_measurements'] = []
        with self.assertRaises(gate.sync_git.SyncBlocked): self.call()

    def test_other_owner_not_admitted(self):
        self.row['owner'] = 'skills/unrelated'
        self.assertIsNone(self.call())


class NativeLearningMaintainedReference(unittest.TestCase):
    """Closed source recognition, not new instruction or activation authority."""
    def setUp(self):
        prefix = gate.NATIVE_LEARNING_OWNER
        manifest = json.loads((ROOT / prefix / 'PUBLIC-FILES.json').read_bytes())
        self.data = {prefix + '/' + item['path']: (ROOT / prefix / item['path']).read_bytes()
                     for item in manifest['files']}
        self.data[prefix + '/PUBLIC-FILES.json'] = (ROOT / prefix / 'PUBLIC-FILES.json').read_bytes()
        for name in (gate.INDEX, 'registry.json'):
            self.data[name] = (ROOT / name).read_bytes()
        self.name = gate.NATIVE_LEARNING_REFERENCE

    def call(self, name=None):
        # Filesystem path safety has its own controls; these exercise source binding.
        with patch.object(gate.sync_git, 'safe_path', side_effect=lambda repo, name: name):
            return gate.native_learning_source_reference(MemoryPath(self.data), name or self.name)

    def test_exact_maintained_package(self):
        raw = self.data[gate.NATIVE_LEARNING_OWNER + '/PUBLIC-FILES.json']
        self.assertEqual('34a1446acd8dd9ad5f3039a5d9d2b6220d2f1f083adeee6101b102dc3151c084',
                         hashlib.sha256(raw).hexdigest())
        manifest = json.loads(raw)
        self.assertEqual((117, 118, 117), (manifest['fileCount'], manifest['publicationFileCount'], len(manifest['files'])))
        self.assertTrue(self.call())

    def test_changed_non_entrypoint_member_rejected(self):
        # Count and entrypoint are still exact; every other member must bind too.
        self.data[gate.NATIVE_LEARNING_OWNER + '/LICENSE'] += b' changed'
        self.assertFalse(self.call())

    def test_registered_alias_copy_rejected(self):
        registry = json.loads(self.data['registry.json'])
        alias = 'skills/' + registry['skills'][0]['name'] + '/SKILL.md'
        self.data[alias] = self.data[self.name].replace(b'\n', b'\r\n')
        self.assertFalse(self.call())

    def test_changed_reference_rejected(self):
        self.data[self.name] += b' changed'
        self.assertFalse(self.call())

    def test_missing_reference_rejected(self):
        del self.data[self.name]
        self.assertFalse(self.call())

    def test_unknown_manifest_rejected(self):
        self.data[gate.NATIVE_LEARNING_OWNER + '/PUBLIC-FILES.json'] += b' '
        self.assertFalse(self.call())

    def test_changed_index_rejected(self):
        self.data[gate.INDEX] += b' '
        self.assertFalse(self.call())

    def test_global_copy_rejected(self):
        self.data['skills/hermes-native-learning/SKILL.md'] = self.data[self.name]
        self.assertFalse(self.call())

    def test_other_entrypoint_rejected(self):
        self.assertFalse(self.call(gate.NATIVE_LEARNING_OWNER + '/docs/T3-INTEGRATION.md'))


if __name__ == '__main__':
    unittest.main()
