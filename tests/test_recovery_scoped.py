from __future__ import annotations
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('recovery_scoped', ROOT / 'tools/recovery.py')
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


class ScopedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = self.root / 'policy.json'
        self.snapshot = self.root / 'snapshot'
        self.roots = {host: self.root / host for host in ('hermes', 'codex')}
        hosts = {}
        for host, root in self.roots.items():
            root.mkdir()
            (root / 'config.json').write_text(json.dumps({'model': 'old', 'private': 'keep'}))
            hosts[host] = {'artifacts': [{'id': 'settings', 'kind': 'config', 'format': 'json',
                'strategy': 'merge', 'source': 'config.json', 'snapshot': f'{host}/config.json', 'include': ['model']}]}
        self.policy.write_text(json.dumps({'schema_version': 1, 'machine': 'test', 'public_safe': True, 'hosts': hosts}))
        recovery.snapshot(self.policy, self.snapshot, self.roots)

    def _add_artifact(self, host='hermes', artifact_id='new'):
        policy = json.loads(self.policy.read_text())
        source = f'{artifact_id}.md'
        (self.roots[host] / source).write_text('Reviewed public text.\n')
        policy['hosts'][host]['artifacts'].append({
            'id': artifact_id, 'kind': 'text', 'format': 'text',
            'strategy': 'replace-if-absent', 'source': source, 'snapshot': f'{host}/{source}'})
        self.policy.write_text(json.dumps(policy))

    def _snapshot_bytes(self):
        return {path.relative_to(self.snapshot): path.read_bytes()
                for path in self.snapshot.rglob('*') if path.is_file()}

    def _assert_capture_rejected_without_mutation(self, selection, message):
        before = self._snapshot_bytes()
        with patch.object(recovery, '_atomic_write', wraps=recovery._atomic_write) as write:
            with self.assertRaisesRegex(recovery.RecoveryError, message):
                recovery.snapshot(self.policy, self.snapshot, self.roots, artifacts=selection)
            write.assert_not_called()
        self.assertEqual(before, self._snapshot_bytes())

    def test_additive_selected_capture_verifies_full_old_and_new_snapshot(self):
        prior = recovery.verify_snapshot(self.policy, self.snapshot)
        codex = (self.snapshot / 'codex/config.json').read_bytes()
        self._add_artifact()
        with self.assertRaisesRegex(recovery.RecoveryError, 'policy hash mismatch'):
            recovery.verify_snapshot(self.policy, self.snapshot)
        (self.roots['hermes'] / 'config.json').write_text('{"model":"new"}')
        result = recovery.snapshot(self.policy, self.snapshot,
            {'hermes': self.roots['hermes']}, artifacts=['hermes:settings', 'hermes:new'])
        self.assertEqual(result, recovery.verify_snapshot(self.policy, self.snapshot))
        self.assertEqual(3, len(result['artifacts']))
        self.assertEqual(codex, (self.snapshot / 'codex/config.json').read_bytes())
        prior_codex = next(item for item in prior['artifacts'] if item['host'] == 'codex')
        self.assertEqual(prior_codex, next(item for item in result['artifacts'] if item['host'] == 'codex'))
        self.assertEqual('new', json.loads((self.snapshot / 'hermes/config.json').read_text())['model'])
        self.assertEqual('Reviewed public text.\n', (self.snapshot / 'hermes/new.md').read_text())

    def test_additive_unselected_artifact_refused_without_mutation(self):
        self._add_artifact()
        self._assert_capture_rejected_without_mutation(['hermes:settings'], 'explicitly selected')

    def test_additive_mixed_unselected_addition_refused_without_mutation(self):
        self._add_artifact()
        self._add_artifact('codex', 'unselected')
        self._assert_capture_rejected_without_mutation(['hermes:new'], 'explicitly selected')

    def test_additive_policy_metadata_change_refused_without_mutation(self):
        self._add_artifact()
        policy = json.loads(self.policy.read_text())
        policy['machine'] = 'changed'
        self.policy.write_text(json.dumps(policy))
        self._assert_capture_rejected_without_mutation(['hermes:new'], 'policy hash mismatch')

    def test_additive_existing_artifact_metadata_change_refused_without_mutation(self):
        self._add_artifact()
        policy = json.loads(self.policy.read_text())
        policy['hosts']['hermes']['artifacts'][0]['include'] = ['private']
        self.policy.write_text(json.dumps(policy))
        self._assert_capture_rejected_without_mutation(['hermes:settings', 'hermes:new'], 'policy hash mismatch')

    def test_additive_artifact_removal_refused_without_mutation(self):
        self._add_artifact()
        policy = json.loads(self.policy.read_text())
        policy['hosts']['hermes']['artifacts'].pop(0)
        self.policy.write_text(json.dumps(policy))
        self._assert_capture_rejected_without_mutation(['hermes:new'], 'explicitly selected')

    def test_additive_unselected_snapshot_corruption_refused_without_mutation(self):
        self._add_artifact()
        (self.snapshot / 'codex/config.json').write_text('{}')
        self._assert_capture_rejected_without_mutation(['hermes:new'], 'hash mismatch')

    def test_additive_full_postverification_failure_rolls_back(self):
        before = self._snapshot_bytes()
        self._add_artifact()
        with patch.object(recovery, 'verify_snapshot', side_effect=recovery.RecoveryError('postverify failure')):
            with self.assertRaisesRegex(recovery.RecoveryError, 'postverify failure'):
                recovery.snapshot(self.policy, self.snapshot, self.roots, artifacts=['hermes:new'])
        self.assertEqual(before, self._snapshot_bytes())

    def test_scoped_capture_preserves_other_record_and_content(self):
        manifest = recovery.verify_snapshot(self.policy, self.snapshot)
        codex = (self.snapshot / 'codex/config.json').read_bytes()
        (self.roots['hermes'] / 'config.json').write_text('{"model":"new"}')
        result = recovery.snapshot(self.policy, self.snapshot, {'hermes': self.roots['hermes']}, artifacts=['hermes:settings'])
        self.assertEqual(codex, (self.snapshot / 'codex/config.json').read_bytes())
        self.assertEqual(manifest['artifacts'][0], result['artifacts'][0])
        recovery.verify_snapshot(self.policy, self.snapshot)

    def test_unselected_corruption_prevents_scoped_capture(self):
        (self.snapshot / 'codex/config.json').write_text('{}')
        with self.assertRaisesRegex(recovery.RecoveryError, 'hash mismatch'):
            recovery.snapshot(self.policy, self.snapshot, {'hermes': self.roots['hermes']}, artifacts=['hermes:settings'])

    def test_snapshot_failure_restores_valid_existing_snapshot(self):
        before = {path: path.read_bytes() for path in self.snapshot.rglob('*') if path.is_file()}
        (self.roots['hermes'] / 'config.json').write_text('{"model":"new"}')
        write = recovery._atomic_write
        def fail(path, data):
            if path.name == 'manifest.json':
                raise OSError('injected manifest failure')
            write(path, data)
        with patch.object(recovery, '_atomic_write', side_effect=fail), self.assertRaises(OSError):
            recovery.snapshot(self.policy, self.snapshot, self.roots, artifacts=['hermes:settings'])
        self.assertEqual(before, {path: path.read_bytes() for path in self.snapshot.rglob('*') if path.is_file()})
        recovery.verify_snapshot(self.policy, self.snapshot)

    def test_capture_source_race_prevents_output(self):
        target = self.roots['hermes'] / 'config.json'
        before = (self.snapshot / 'manifest.json').read_bytes()
        read = recovery._read_config
        def race(path, fmt):
            config = read(path, fmt)
            if path == target:
                target.write_text('{"model":"concurrent"}')
            return config
        with patch.object(recovery, '_read_config', side_effect=race), self.assertRaisesRegex(recovery.RecoveryError, 'changed during read'):
            recovery.snapshot(self.policy, self.snapshot, self.roots, artifacts=['hermes:settings'])
        self.assertEqual(before, (self.snapshot / 'manifest.json').read_bytes())

    def test_selection_exact_nonempty_unique(self):
        for artifacts in ([], ['hermes:settings'] * 2, ['hermes:*'], ['hermes:../config.json'], ['codex:new']):
            with self.subTest(artifacts=artifacts), self.assertRaises(recovery.RecoveryError):
                recovery.restore(self.policy, self.snapshot, self.roots, artifacts=artifacts)

    def test_selected_restore_requires_only_selected_root_preserves_private(self):
        target = self.roots['hermes'] / 'config.json'
        target.write_text('{"model":"changed","private":"keep"}')
        with patch.object(recovery, '_atomic_write', wraps=recovery._atomic_write) as write:
            recovery.restore(self.policy, self.snapshot, {'hermes': self.roots['hermes']}, artifacts=['hermes:settings'])
            write.assert_not_called()
        recovery.restore(self.policy, self.snapshot, {'hermes': self.roots['hermes']}, artifacts=['hermes:settings'], apply=True)
        self.assertEqual(json.loads(target.read_text()), {'model': 'old', 'private': 'keep'})

    def test_preflight_race_preserves_newer_edit(self):
        target = self.roots['hermes'] / 'config.json'
        target.write_text('{"model":"changed","private":"keep"}')
        serialize = recovery._serialize_config
        def race(value, fmt):
            data = serialize(value, fmt)
            target.write_text('{"model":"concurrent","private":"new"}')
            return data
        with patch.object(recovery, '_serialize_config', side_effect=race), self.assertRaisesRegex(recovery.RecoveryError, 'changed during preflight'):
            recovery.restore(self.policy, self.snapshot, self.roots, artifacts=['hermes:settings'], apply=True)
        self.assertEqual(json.loads(target.read_text())['private'], 'new')

    def test_rollback_does_not_overwrite_concurrent_edit(self):
        for root in self.roots.values():
            (root / 'config.json').write_text('{"model":"changed"}')
        first = self.roots['codex'] / 'config.json'
        second = self.roots['hermes'] / 'config.json'
        write = recovery._atomic_write
        def fail(target, data):
            if target == second:
                first.write_text('{"model":"concurrent"}')
                raise OSError('injected')
            return write(target, data)
        with patch.object(recovery, '_atomic_write', side_effect=fail), self.assertRaisesRegex(recovery.RecoveryError, 'rollback conflicts preserved at') as caught:
            recovery.restore(self.policy, self.snapshot, self.roots, apply=True)
        self.assertEqual(json.loads(first.read_text())['model'], 'concurrent')
        backup = Path(str(caught.exception).split('preserved at ', 1)[1])
        self.assertTrue((backup / '0.original').is_file())
        for file in backup.iterdir():
            file.unlink()
        backup.rmdir()


if __name__ == '__main__':
    unittest.main()
