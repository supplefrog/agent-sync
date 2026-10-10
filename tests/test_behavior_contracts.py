from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class BehaviorContractTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'contracts').mkdir()
        (root / 'skills/example').mkdir(parents=True)
        (root / 'skills/example/SKILL.md').write_text('example', encoding='utf-8')
        (root / 'contracts/surface-matrix.schema.json').write_bytes(
            (REPO / 'contracts/surface-matrix.schema.json').read_bytes())
        (root / 'contracts/ownership.schema.json').write_bytes(
            (REPO / 'contracts/ownership.schema.json').read_bytes())
        self.ownership = {'schema_version': 1, 'supported_hosts': ['codex', 'hermes'],
                          'retired_artifacts': [], 'capabilities': [{'id': 'example', 'owner': 'skills/example',
                          'status': 'admitted', 'selection_state': 'selected', 'selection_reason': 'fixture',
                          'selection_evidence': []}]}
        (root / 'contracts/ownership.json').write_text(json.dumps(self.ownership), encoding='utf-8')
        (root / 'registry.json').write_text(json.dumps({'skills': [{'name': 'example', 'status': 'admitted'}]}), encoding='utf-8')
        self.contract = {'id': 'example-outcome', 'scope': 'task-type',
                         'authority': {'status': 'inferred', 'reference': 'source intent, unconfirmed'},
                         'owners': ['skills/example'], 'hosts': ['codex', 'hermes'],
                         'trigger': 'Example task', 'desired_outcomes': ['Useful result'],
                         'undesired_outcomes': [], 'contraindications': [],
                         'acceptable_native_differences': [], 'checks': ['Read back result']}

    def run_cli(self, root, surface):
        path = root / 'contracts/surface-matrix.json'
        path.write_text(json.dumps(surface), encoding='utf-8')
        before = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in root.rglob('*') if p.is_file()}
        result = subprocess.run([sys.executable, '-B', str(REPO / 'tools/audit.py'),
                                 'behaviors', '--repo', str(root)], capture_output=True, text=True)
        after = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in root.rglob('*') if p.is_file()}
        self.assertEqual(before, after, 'read-only report must preserve fixture files')
        return result

    def test_legacy_missing_and_explicit_authority_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            for status in ('missing', 'inferred', 'user-confirmed'):
                surface = {}
                if status != 'missing':
                    contract = copy.deepcopy(self.contract)
                    contract['authority']['status'] = status
                    surface['behavior_contracts'] = [contract]
                result = self.run_cli(root, surface)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report['admitted_capabilities'][0]['contract_metadata'], status)
                self.assertFalse(report['promotion_authority'])
                self.assertFalse(report['inference_performed'])
                self.assertEqual(report['bindings']['contracts/surface-matrix.json'],
                                 hashlib.sha256((root / 'contracts/surface-matrix.json').read_bytes()).hexdigest())

    def test_system_contract_does_not_fill_domain_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            self.contract.update(scope='system')
            self.contract['authority']['status'] = 'user-confirmed'
            result = self.run_cli(root, {'behavior_contracts': [self.contract]})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['summary']['task_contract_missing'], 1)

    def test_invalid_metadata_rejects_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            cases = [None, [self.contract, self.contract]]
            for key, value in [('desired_outcomes', []), ('trigger', '  '),
                               ('contraindications', None), ('owners', ['../outside']),
                               ('owners', ['missing-owner']), ('hosts', ['unsupported'])]:
                contract = copy.deepcopy(self.contract)
                contract[key] = value
                cases.append([contract])
            contract = copy.deepcopy(self.contract)
            contract['authority'] = {'status': 'approved-by-agent', 'reference': 'assistant verdict'}
            cases.append([contract])
            for contracts in cases:
                with self.subTest(contracts=contracts):
                    result = self.run_cli(root, {'behavior_contracts': contracts})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('behavior contracts:', result.stderr)

    def test_corrupt_ownership_cannot_hide_or_inflate_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            original = copy.deepcopy(self.ownership)
            for mutation in ('duplicate', 'invalid-status', 'valid-status-disagrees', 'wrong-owner'):
                with self.subTest(mutation=mutation):
                    changed = copy.deepcopy(original)
                    item = changed['capabilities'][0]
                    if mutation == 'duplicate':
                        changed['capabilities'].append(copy.deepcopy(item))
                    elif mutation == 'invalid-status':
                        item['status'] = 'admited'
                    elif mutation == 'valid-status-disagrees':
                        item['status'] = 'retired'
                    else:
                        item['owner'] = 'skills/different'
                    (root / 'contracts/ownership.json').write_text(json.dumps(changed), encoding='utf-8')
                    result = self.run_cli(root, {})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('behavior coverage ownership:', result.stderr)


if __name__ == '__main__':
    unittest.main()
