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

    def _reviewed_inventory(self):
        policy = json.loads(self.policy.read_text())
        artifacts = policy['hosts']['hermes']['artifacts']
        artifacts[0]['include'].extend(['skills', 'plugins'])
        self.hermes = self.roots['hermes']
        (self.hermes / 'config.json').write_text(json.dumps({
            'model': 'old', 'skills': {'disabled': []}, 'plugins': {'enabled': []},
        }))
        for name in ('SKILL.md', 'old.md'):
            source = 'skills/example/' + name
            (self.hermes / source).parent.mkdir(parents=True, exist_ok=True)
            (self.hermes / source).write_bytes(b'---\nname: example\nlicense: MIT\n---\nSkill.\n' if name == 'SKILL.md' else b'Original.\n')
            artifacts.append({'id': 'example-' + name.lower().split('.')[0], 'kind': 'text',
                'source': source, 'snapshot': 'hermes/' + source, 'format': 'text',
                'strategy': 'replace-if-absent'})
        self.policy.write_text(json.dumps(policy))
        self.snapshot = self.root / 'recovery/current'
        inventory = self.root / 'recovery/hermes-local-inventory.json'
        inventory.parent.mkdir()
        inventory.write_text(json.dumps({'schema_version': 1, 'packages': [],
            'excluded_state': ['private state'], 'native_plugins': {}, 'skill_selection': {},
            'plugin_selection': {}}))
        recovery.snapshot(self.policy, self.snapshot, self.roots)
        return inventory

    def test_inventory_follows_only_selected_capture_and_rolls_back_with_snapshot(self):
        inventory = self._reviewed_inventory()
        roots = {'hermes': self.hermes}
        initial = json.loads(inventory.read_bytes())
        self.assertEqual(['SKILL.md', 'old.md'], [r['path'] for r in initial['packages'][0]['files']])
        self.assertEqual('MIT', initial['packages'][0]['declared_license'])
        live_file = self.hermes / 'skills/example/old.md'
        live_file.write_bytes(b'Updated with native line endings.\r\n')
        (self.hermes / 'skills/example/unreviewed.md').write_text('Ignore this file.')
        (self.hermes / 'config.json').write_text(json.dumps({
            'model': 'old', 'skills': {'disabled': ['example']}, 'plugins': {'enabled': ['demo']},
        }))
        recovery.snapshot(self.policy, self.snapshot, roots, artifacts=['hermes:example-old'])
        current = json.loads(inventory.read_bytes())
        self.assertEqual(initial['skill_selection'], current['skill_selection'])
        self.assertEqual(initial['plugin_selection'], current['plugin_selection'])
        self.assertEqual(initial['excluded_state'], current['excluded_state'])
        self.assertEqual([
            initial['packages'][0]['files'][0],
            {'path': 'old.md', 'sha256': recovery._sha256(live_file.read_bytes())},
        ], current['packages'][0]['files'])
        self.assertFalse(current['packages'][0]['disabled'])
        baseline = inventory.read_bytes()
        with patch.object(recovery, 'verify_snapshot', side_effect=recovery.RecoveryError('injected failure')):
            with self.assertRaisesRegex(recovery.RecoveryError, 'injected failure'):
                recovery.snapshot(self.policy, self.snapshot, roots, artifacts=['hermes:settings'])
        self.assertEqual(baseline, inventory.read_bytes())
        recovery.snapshot(self.policy, self.snapshot, roots, artifacts=['hermes:settings'])
        current = json.loads(inventory.read_bytes())
        self.assertEqual({'disabled': ['example']}, current['skill_selection'])
        self.assertEqual({'enabled': ['demo']}, current['plugin_selection'])
        self.assertTrue(current['packages'][0]['disabled'])
        self.assertEqual(initial['excluded_state'], current['excluded_state'])
        (self.hermes / 'skills/example/SKILL.md').write_text(
            '---\nname: new-example\nlicense: Apache-2.0\n---\nSkill.\n')
        (self.hermes / 'config.json').write_text(json.dumps({
            'model': 'old', 'skills': {'disabled': ['new-example']}, 'plugins': {'enabled': ['demo']},
        }))
        recovery.snapshot(self.policy, self.snapshot, roots, artifacts=['hermes:settings', 'hermes:example-skill'])
        current = json.loads(inventory.read_bytes())
        self.assertEqual('new-example', current['packages'][0]['name'])
        self.assertEqual('Apache-2.0', current['packages'][0]['declared_license'])
        self.assertTrue(current['packages'][0]['disabled'])

    def test_inventory_follows_reviewed_addition_and_full_policy_removal(self):
        inventory = self._reviewed_inventory()
        policy = json.loads(self.policy.read_text())
        old = policy['hosts']['hermes']['artifacts'][-1]
        new = dict(old, id='example-new', source='skills/example/new.md', snapshot='hermes/skills/example/new.md')
        (self.hermes / new['source']).write_text('Reviewed addition.\n')
        policy['hosts']['hermes']['artifacts'].append(new)
        self.policy.write_text(json.dumps(policy))
        recovery.snapshot(self.policy, self.snapshot, {'hermes': self.hermes}, artifacts=['hermes:example-new'])
        current = json.loads(inventory.read_bytes())
        self.assertEqual(['SKILL.md', 'old.md', 'new.md'], [r['path'] for r in current['packages'][0]['files']])
        policy['hosts']['hermes']['artifacts'].remove(old)
        self.policy.write_text(json.dumps(policy))
        baseline = inventory.read_bytes()
        snapshot_before = self._snapshot_bytes()
        write = recovery._atomic_write
        def fail_manifest(path, data):
            if path.name == 'manifest.json':
                raise OSError('manifest write failed')
            write(path, data)
        with patch.object(recovery, '_atomic_write', side_effect=fail_manifest):
            with self.assertRaisesRegex(OSError, 'manifest write failed'):
                recovery.snapshot(self.policy, self.snapshot, self.roots)
        self.assertEqual(baseline, inventory.read_bytes())
        self.assertEqual(snapshot_before, self._snapshot_bytes())
        recovery.snapshot(self.policy, self.snapshot, self.roots)
        current = json.loads(inventory.read_bytes())
        self.assertEqual(['SKILL.md', 'new.md'], [r['path'] for r in current['packages'][0]['files']])
        self.assertFalse((self.snapshot / old['snapshot']).exists())

    def test_inventory_readback_preserves_external_edit_during_manifest_write(self):
        inventory = self._reviewed_inventory()
        before = self._snapshot_bytes()
        write = recovery._atomic_write

        def concurrent_edit(target, data):
            write(target, data)
            if target.name == 'manifest.json':
                inventory.write_bytes(b'external edit')

        with patch.object(recovery, '_atomic_write', side_effect=concurrent_edit):
            with self.assertRaisesRegex(recovery.RecoveryError, 'inventory changed during capture readback'):
                recovery.snapshot(self.policy, self.snapshot, {'hermes': self.hermes}, artifacts=['hermes:settings'])
        self.assertEqual(b'external edit', inventory.read_bytes())
        self.assertEqual(before, self._snapshot_bytes())

    def test_full_capture_keeps_stale_file_edited_while_saving_rollback_data(self):
        inventory = self._reviewed_inventory()
        before = inventory.read_bytes()
        policy = json.loads(self.policy.read_text())
        reviewed = policy['hosts']['hermes']['artifacts'].pop()
        self.policy.write_text(json.dumps(policy))
        stale = self.snapshot / reviewed['snapshot']
        identity = recovery._file_identity

        def concurrent_edit(path):
            current = identity(path)
            if path == stale:
                path.write_bytes(b'external edit')
            return current

        with patch.object(recovery, '_file_identity', side_effect=concurrent_edit):
            with self.assertRaisesRegex(recovery.RecoveryError, 'changed while saving rollback data'):
                recovery.snapshot(self.policy, self.snapshot, self.roots)
        self.assertEqual(b'external edit', stale.read_bytes())
        self.assertEqual(before, inventory.read_bytes())

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
