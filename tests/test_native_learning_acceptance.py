"""Proposed scoped consumer controls; source preparation does not execute them."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
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
        self.receipt = json.loads((ROOT / 'evals/results/native-learning-source-binding.json').read_bytes())
        self.row = copy.deepcopy(self.receipt['instruction_changes'][0])
        self.records = copy.deepcopy(self.receipt['change_reconciliation'])
        self.paths = self.receipt['selected_paths']
        self.data = {name: (ROOT / name).read_bytes() for name in self.paths}
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


if __name__ == '__main__':
    unittest.main()
