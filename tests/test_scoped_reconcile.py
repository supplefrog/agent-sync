"""Integrated scoped publication and concurrent-work preservation."""
from pathlib import Path
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

import test_reconcile as fixtures
import test_sync_completion as completion


class ScopedReconcileTests(unittest.TestCase):
    setUp = completion.CompleteSyncTests.setUp
    fixture = completion.CompleteSyncTests.fixture
    git = completion.CompleteSyncTests.git
    setup_git = completion.CompleteSyncTests.setup_git
    run_sync = completion.CompleteSyncTests.run_sync

    def _hermes_inventory_fixture(self, root):
        repo, live, remote = self.setup_git(root)
        native = root / 'hermes'
        native.mkdir()
        policy = repo / 'recovery.json'
        recovery = self.reconcile.recovery
        inventory = repo / recovery.HERMES_INVENTORY
        inventory.parent.mkdir()
        inventory.write_text(json.dumps({'schema_version': 1, 'packages': [], 'native_plugins': {},
            'excluded_state': ['private state'], 'skill_selection': {}, 'plugin_selection': {}}))
        settings = native / 'config.json'
        settings.write_text('{"skills":{"disabled":[]},"plugins":{"enabled":[]}}')
        policy.write_text(json.dumps({'schema_version': 1, 'machine': 'test', 'public_safe': True,
            'hosts': {'hermes': {'artifacts': [{'id': 'settings', 'kind': 'config', 'format': 'json',
                'strategy': 'merge', 'source': 'config.json', 'snapshot': 'hosts/hermes/config.json',
                'include': ['skills', 'plugins']}]}}}))
        recovery.snapshot(policy, repo / 'recovery/current', {'hermes': native})
        self.git(repo, 'add', '.')
        self.git(repo, 'commit', '-m', 'reviewed capture baseline')
        self.git(repo, 'push', 'origin', 'main')
        settings.write_text('{"skills":{"disabled":["weekly-review"]},"plugins":{"enabled":["example"]}}')
        return repo, live, remote, native, inventory

    def _sync_hermes_inventory(self, repo, live, native):
        with patch.object(self.reconcile, '_run_checks', return_value=[]):
            return self.reconcile.complete_sync(repo, machine='test', skill_roots=[live],
                recovery_roots={'hermes': native}, recovery_artifacts=['hermes:settings'])

    def test_hermes_capture_publishes_generated_inventory_with_settings(self):
        for standalone in (False, True):
            with self.subTest(standalone=standalone), tempfile.TemporaryDirectory() as temp:
                repo, live, remote, native, inventory = self._hermes_inventory_fixture(Path(temp))
                recovery = self.reconcile.recovery
                if standalone:
                    recovery.snapshot(repo / 'recovery.json', repo / 'recovery/current',
                                      {'hermes': native}, artifacts=['hermes:settings'])
                report = self._sync_hermes_inventory(repo, live, native)
                self.assertEqual('synced', report['result'], report)
                published = json.loads(self.git(remote, 'show', 'main:' + recovery.HERMES_INVENTORY))
                self.assertEqual({'disabled': ['weekly-review']}, published['skill_selection'])
                self.assertEqual({'enabled': ['example']}, published['plugin_selection'])
                self.assertEqual(['private state'], published['excluded_state'])
                self.assertEqual(published, json.loads(inventory.read_bytes()))

    def test_hermes_capture_keeps_unselected_inventory_edits_out_of_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, native, inventory = self._hermes_inventory_fixture(Path(temp))
            recovery = self.reconcile.recovery
            recovery.snapshot(repo / 'recovery.json', repo / 'recovery/current',
                              {'hermes': native}, artifacts=['hermes:settings'])
            current = json.loads(inventory.read_bytes())
            current['excluded_state'].append('pending edit')
            inventory.write_text(json.dumps(current))
            old_head = self.git(remote, 'rev-parse', 'main')
            report = self._sync_hermes_inventory(repo, live, native)
            self.assertEqual('incomplete', report['result'], report)
            self.assertIn('Hermes inventory has unselected edits', report['reason'])
            self.assertEqual(current, json.loads(inventory.read_bytes()))
            self.assertEqual(old_head, self.git(remote, 'rev-parse', 'main'))

    def test_hermes_capture_rejects_a_missing_tracked_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, native, inventory = self._hermes_inventory_fixture(Path(temp))
            old_head = self.git(remote, 'rev-parse', 'main')
            snapshot = repo / 'recovery/current/hosts/hermes/config.json'
            before = snapshot.read_bytes()
            inventory.unlink()
            report = self._sync_hermes_inventory(repo, live, native)
            self.assertEqual('incomplete', report['result'], report)
            self.assertIn('required artifact is missing', report['reason'])
            self.assertEqual(before, snapshot.read_bytes())
            self.assertEqual(old_head, self.git(remote, 'rev-parse', 'main'))

    def test_hermes_capture_preserves_external_inventory_edit_during_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, native, inventory = self._hermes_inventory_fixture(Path(temp))
            recovery = self.reconcile.recovery
            old_head = self.git(remote, 'rev-parse', 'main')
            snapshot = repo / 'recovery/current/hosts/hermes/config.json'
            old_snapshot = snapshot.read_bytes()
            write = recovery._atomic_write
            def concurrent_edit(target, data):
                write(target, data)
                if target == inventory:
                    target.write_bytes(b'external edit')
            with patch.object(recovery, '_atomic_write', side_effect=concurrent_edit):
                report = self._sync_hermes_inventory(repo, live, native)
            self.assertEqual('incomplete', report['result'], report)
            self.assertEqual(b'external edit', inventory.read_bytes())
            self.assertEqual(old_snapshot, snapshot.read_bytes())
            self.assertEqual(old_head, self.git(remote, 'rev-parse', 'main'))

    def test_hermes_capture_never_publishes_inventory_edited_after_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, native, inventory = self._hermes_inventory_fixture(Path(temp))
            old_head = self.git(remote, 'rev-parse', 'main')
            sync = self.reconcile.sync
            def concurrent_edit(*args, **kwargs):
                report = sync(*args, **kwargs)
                self.assertEqual('applied', report['result'], report)
                inventory.write_bytes(b'external edit')
                return report
            with patch.object(self.reconcile, 'sync', side_effect=concurrent_edit):
                report = self._sync_hermes_inventory(repo, live, native)
            self.assertEqual('incomplete', report['result'], report)
            self.assertIn('Hermes inventory changed after capture', report['reason'])
            self.assertEqual(b'external edit', inventory.read_bytes())
            self.assertEqual(old_head, self.git(remote, 'rev-parse', 'main'))

    def test_hermes_capture_preserves_unchanged_inventory_identity_during_owner_update(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, _, native, inventory = self._hermes_inventory_fixture(Path(temp))
            recovery = self.reconcile.recovery
            recovery.snapshot(repo / 'recovery.json', repo / 'recovery/current',
                              {'hermes': native}, artifacts=['hermes:settings'])
            identity = self.fleet.path_identity(inventory)
            (repo / 'skills/kept/fixture.txt').write_text('reviewed content update\n')
            report = self.reconcile.sync(repo, machine='test', adopt=['kept'], skill_roots=[live],
                recovery_roots={'hermes': native}, recovery_artifacts=['hermes:settings'],
                scoped=True, check_commands=[], public_receipts=[])
            self.assertEqual('applied', report['result'], report)
            self.assertEqual(identity, self.fleet.path_identity(inventory))

    def extra_owner(self, repo, live):
        fixtures.write_skill(repo, 'other', 'baseline other')
        registry = json.loads((repo / 'registry.json').read_text())
        registry['skills'].append({'name': 'other', 'status': 'admitted'})
        (repo / 'registry.json').write_text(json.dumps(registry))
        self.fleet.render_snapshot(repo, repo / 'render/fleet')
        self.fleet.apply_snapshot(repo / 'render/fleet', live)
        self.git(repo, 'add', '.')
        self.git(repo, 'commit', '-m', 'other baseline')
        self.git(repo, 'push', 'origin', 'main')

    def binding_fixture(self, repo, live):
        self.extra_owner(repo, live)
        shutil.copyfile(fixtures.REPO / 'contracts/host-deltas.schema.json',
                        repo / 'contracts/host-deltas.schema.json')
        manifest = json.loads((repo / 'host-deltas.json').read_text())
        for name in ('kept', 'other'):
            relative = f'skills/{name}/' + ('fixture.txt' if name == 'kept' else 'SKILL.md')
            digest = self.fleet.sha256_file(repo / relative)
            manifest['entries'].append({
                'id': name, 'host': 'codex', 'category': 'native-skill',
                'owner': name, 'source_identity': 'repository:' + relative,
                'version_or_hash': 'sha256:' + digest, 'enablement': 'managed',
                'prerequisites': [], 'desired_state': 'installed', 'required': False,
                'restore': {'kind': 'repository', 'reference': relative},
                'readback': {'kind': 'file', 'path': relative, 'sha256': digest},
                'redaction': 'public-artifact'})
        (repo / 'host-deltas.json').write_text(json.dumps(manifest))
        self.git(repo, 'add', '.')
        self.git(repo, 'commit', '-m', 'binding baseline')
        self.git(repo, 'push', 'origin', 'main')
        return manifest

    def test_foreign_generated_hashes_survive_working_sync_without_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            baseline = self.binding_fixture(repo, live)
            selected = repo / 'skills/kept/fixture.txt'
            selected.write_text(selected.read_text() + '\nselected change\n')
            foreign = repo / 'skills/other/SKILL.md'
            foreign.write_text(foreign.read_text() + '\nforeign pending change\n')
            manifest = json.loads((repo / 'host-deltas.json').read_text())
            digest = self.fleet.sha256_file(foreign)
            manifest['entries'][1]['version_or_hash'] = 'sha256:' + digest
            manifest['entries'][1]['readback']['sha256'] = digest
            (repo / 'host-deltas.json').write_text(json.dumps(manifest))
            source_before = foreign.read_bytes()
            live_before = (live / 'other/SKILL.md').read_bytes()
            report = self.run_sync(repo, live, adopt=['kept'])
            self.assertEqual('synced', report['result'], report)
            working = json.loads((repo / 'host-deltas.json').read_text())
            published = json.loads(self.git(remote, 'show', 'main:host-deltas.json'))
            self.assertEqual(manifest['entries'][1], working['entries'][1])
            self.assertEqual(baseline['entries'][1], published['entries'][1])
            self.assertEqual(working['entries'][0], published['entries'][0])
            self.assertEqual('sha256:' + self.fleet.sha256_file(selected), published['entries'][0]['version_or_hash'])
            self.assertEqual(source_before, foreign.read_bytes())
            self.assertEqual(live_before, (live / 'other/SKILL.md').read_bytes())
            self.assertNotEqual(foreign.read_text().strip(), self.git(remote, 'show', 'main:skills/other/SKILL.md'))
            self.assertIn('host-deltas.json', report['pending_files'])
            self.assertEqual(selected.read_bytes(), (live / 'kept/fixture.txt').read_bytes())

    def test_projected_manifest_retry_keeps_foreign_hashes_unpublished(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            baseline = self.binding_fixture(repo, live)
            selected = repo / 'skills/kept/fixture.txt'
            selected.write_text(selected.read_text() + '\nselected change\n')
            foreign = repo / 'skills/other/SKILL.md'
            foreign.write_text(foreign.read_text() + '\nforeign change\n')
            manifest = json.loads((repo / 'host-deltas.json').read_text())
            manifest['entries'][1]['version_or_hash'] = 'sha256:' + self.fleet.sha256_file(foreign)
            (repo / 'host-deltas.json').write_text(json.dumps(manifest))
            hook = remote / 'hooks/pre-receive'
            hook.write_text('#!/bin/sh\nexit 1\n')
            report = self.run_sync(repo, live, adopt=['kept'])
            self.assertEqual('incomplete', report['result'], report)
            self.assertEqual('push', report['failed_step'], report)
            checked_commit = self.git(repo, 'rev-parse', 'HEAD')
            hook.unlink()
            report = self.run_sync(repo, live, adopt=['kept'])
            self.assertEqual('synced', report['result'], report)
            self.assertEqual(checked_commit, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(manifest['entries'][1], json.loads((repo / 'host-deltas.json').read_text())['entries'][1])
            self.assertEqual(baseline['entries'][1], json.loads(self.git(remote, 'show', 'main:host-deltas.json'))['entries'][1])

    def test_manifest_change_during_checks_still_blocks_before_deployment(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            self.binding_fixture(repo, live)
            selected = repo / 'skills/kept/fixture.txt'
            selected.write_text(selected.read_text() + '\nselected change\n')
            head = self.git(remote, 'rev-parse', 'main')
            original = (live / 'kept/fixture.txt').read_bytes()
            def check(*_):
                manifest = json.loads((repo / 'host-deltas.json').read_text())
                manifest['entries'][1]['version_or_hash'] = 'sha256:' + 'a' * 64
                (repo / 'host-deltas.json').write_text(json.dumps(manifest))
                return []
            with patch.object(self.reconcile, '_run_checks', side_effect=check):
                report = self.reconcile.complete_sync(repo, machine='test', recovery_roots={},
                    skill_roots=[live], adopt=['kept'])
            self.assertEqual('incomplete', report['result'], report)
            self.assertIn('selected files or agent owners changed', report['reason'])
            self.assertEqual(original, (live / 'kept/fixture.txt').read_bytes())
            self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual('sha256:' + 'a' * 64, json.loads((repo / 'host-deltas.json').read_text())['entries'][1]['version_or_hash'])

    def test_selected_readback_hash_change_requires_explicit_manifest_review(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            manifest = self.binding_fixture(repo, live)
            manifest['entries'][0]['readback']['sha256'] = 'a' * 64
            path = repo / 'host-deltas.json'
            path.write_text(json.dumps(manifest))
            working = path.read_bytes()
            head = self.git(remote, 'rev-parse', 'main')
            installed = (live / 'kept/fixture.txt').read_bytes()
            report = self.run_sync(repo, live, adopt=['kept'])
            self.assertEqual('incomplete', report['result'], report)
            self.assertIn('unselected host-delta fields differ', report['reason'])
            self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(installed, (live / 'kept/fixture.txt').read_bytes())
            self.assertEqual(working, path.read_bytes())

    def test_foreign_binding_policy_still_requires_review(self):
        for field in ('desired_state', 'readback-path'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                repo, live, remote = self.setup_git(Path(temp))
                manifest = self.binding_fixture(repo, live)
                selected = repo / 'skills/kept/fixture.txt'
                selected.write_text(selected.read_text() + '\nselected change\n')
                if field == 'readback-path':
                    manifest['entries'][1]['readback']['path'] = 'different/file.md'
                else:
                    manifest['entries'][1][field] = 'new policy'
                (repo / 'host-deltas.json').write_text(json.dumps(manifest))
                head = self.git(remote, 'rev-parse', 'main')
                original = (live / 'kept/fixture.txt').read_bytes()
                report = self.run_sync(repo, live, adopt=['kept'])
                self.assertEqual('incomplete', report['result'], report)
                self.assertIn('unselected host-delta fields differ', report['reason'])
                self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
                self.assertEqual(original, (live / 'kept/fixture.txt').read_bytes())

    def test_explicit_manifest_include_publishes_reviewed_foreign_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            manifest = self.binding_fixture(repo, live)
            selected = repo / 'skills/kept/fixture.txt'
            selected.write_text(selected.read_text() + '\nselected change\n')
            manifest['entries'][1]['desired_state'] = 'reviewed new policy'
            (repo / 'host-deltas.json').write_text(json.dumps(manifest))
            report = self.run_sync(repo, live, adopt=['kept'], include=['host-deltas.json'])
            self.assertEqual('synced', report['result'], report)
            published = json.loads(self.git(remote, 'show', 'main:host-deltas.json'))
            self.assertEqual(manifest['entries'][1], published['entries'][1])

    def test_selected_owner_completes_despite_unrelated_owner_conflict_and_staged_work(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            self.extra_owner(repo, live)
            selected = repo / 'skills/kept/fixture.txt'
            selected.write_text(selected.read_text() + '\nselected improvement\n')
            other_source = repo / 'skills/other/SKILL.md'
            other_live = live / 'other/SKILL.md'
            other_source.write_text(other_source.read_text() + '\ncanonical pending\n')
            other_live.write_text(other_live.read_text() + '\nlive conflicting pending\n')
            note = repo / 'private-unrelated.md'
            note.write_text('sk' + '-' + 'x' * 30)
            self.git(repo, 'add', 'private-unrelated.md')
            staged = self.git(repo, 'diff', '--cached', '--raw')
            source_before, live_before = other_source.read_bytes(), other_live.read_bytes()
            report = self.run_sync(repo, live, adopt=['kept'])
            self.assertEqual('incomplete', report['result'], report)
            self.assertIn('publication_verified', report, report)
            self.assertTrue(report['publication_verified'])
            self.assertFalse(report['rollout_verified'])
            self.assertEqual(source_before, other_source.read_bytes())
            self.assertEqual(live_before, other_live.read_bytes())
            self.assertEqual(staged, self.git(repo, 'diff', '--cached', '--raw'))
            self.assertEqual(selected.read_bytes(), (live / 'kept/fixture.txt').read_bytes())
            self.assertEqual(self.git(repo, 'rev-parse', 'HEAD'), self.git(remote, 'rev-parse', 'main'))
            self.assertNotIn('private-unrelated.md', self.git(remote, 'ls-tree', '-r', '--name-only', 'main').splitlines())
            self.assertEqual(['kept'], report['verified_owners'])
            self.assertTrue(report['pending_files'])

    def test_include_only_publishes_without_claiming_agent_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, _ = self.setup_git(Path(temp))
            (repo / 'notes.md').write_text('reviewed')
            selected = repo / 'skills/kept/fixture.txt'
            selected.write_text(selected.read_text() + '\nunrelated owner pending\n')
            original_live = (live / 'kept/fixture.txt').read_bytes()
            report = self.run_sync(repo, live, include=['notes.md'], source_only=True)
            self.assertEqual('published', report['result'], report)
            self.assertFalse(report['agents_verified'])
            self.assertEqual([], report['verified_owners'])
            self.assertEqual(original_live, (live / 'kept/fixture.txt').read_bytes())
            self.assertIn('skills/kept/fixture.txt', report['pending_files'])

    def test_selected_change_during_checks_stops_before_deployment(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            selected = repo / 'skills/kept/fixture.txt'
            selected.write_text(selected.read_text() + '\nrequested\n')
            original = (live / 'kept/fixture.txt').read_bytes()
            head = self.git(remote, 'rev-parse', 'main')
            def check(*_):
                selected.write_text(selected.read_text() + '\nconcurrent change\n')
                return []
            with patch.object(self.reconcile, '_run_checks', side_effect=check):
                report = self.reconcile.complete_sync(repo, machine='test', recovery_roots={},
                    skill_roots=[live], adopt=['kept'])
            self.assertEqual('incomplete', report['result'], report)
            self.assertEqual(original, (live / 'kept/fixture.txt').read_bytes())
            self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
            self.assertIn('concurrent change', selected.read_text())

    def test_unrelated_change_during_checks_is_preserved_and_not_published(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            (repo / 'notes.md').write_text('reviewed')
            def check(*_):
                (repo / 'new-unrelated.md').write_text('concurrent independent work')
                return []
            with patch.object(self.reconcile, '_run_checks', side_effect=check):
                report = self.reconcile.complete_sync(repo, machine='test', recovery_roots={},
                    skill_roots=[live], include=['notes.md'])
            self.assertEqual('synced', report['result'], report)
            self.assertEqual('concurrent independent work', (repo / 'new-unrelated.md').read_text())
            self.assertNotIn('new-unrelated.md', self.git(remote, 'ls-tree', '-r', '--name-only', 'main').splitlines())

    def test_failed_validation_does_not_restore_unwritten_canonical_or_recovery_files(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            selected = repo / 'skills/kept/SKILL.md'
            selected.write_text(selected.read_text() + '\nrequested\n')
            native = repo / 'recovery/current/hosts/hermes/config.json'
            native.parent.mkdir(parents=True, exist_ok=True)
            native.write_text('original native')
            def check(*_):
                selected.write_text(selected.read_text() + '\nconcurrent source\n')
                native.write_text('concurrent native')
                raise RuntimeError('failed acceptance')
            with patch.object(self.reconcile, '_run_checks', side_effect=check):
                report = self.reconcile.sync(repo, machine='test', adopt=['kept'],
                    recovery_roots={}, skill_roots=[live], check_commands=[], scoped=True)
            self.assertEqual('rejected', report['result'], report)
            self.assertIn('concurrent source', selected.read_text())
            self.assertEqual('concurrent native', native.read_text())

    def test_failed_postflight_preserves_concurrent_live_edit_and_retains_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            selected = repo / 'skills/kept/SKILL.md'
            selected.write_text(selected.read_text() + '\nrequested\n')
            def postflight(*_, **__):
                (live / 'kept/SKILL.md').write_text('concurrent live edit')
                return [{'name': 'kept', 'status': 'drift'}]
            with patch.object(self.reconcile.fleet, 'verify_snapshot', side_effect=postflight):
                report = self.reconcile.sync(repo, machine='test', adopt=['kept'],
                    recovery_roots={}, skill_roots=[live], check_commands=[], scoped=True)
            self.assertEqual('incomplete', report['result'], report)
            self.assertTrue(report['mutation_performed'])
            self.assertEqual('concurrent live edit', (live / 'kept/SKILL.md').read_text())
            self.assertTrue((repo / report['backup'] / 'outcome.json').is_file())

    def test_nested_render_edit_is_preserved_when_validation_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            selected = repo / 'skills/kept/SKILL.md'
            selected.write_text(selected.read_text() + '\nrequested\n')
            nested = repo / 'render/fleet/skills/kept/SKILL.md'
            def check(*_):
                nested.write_text('concurrent nested snapshot edit')
                raise RuntimeError('failed acceptance')
            with patch.object(self.reconcile, '_run_checks', side_effect=check):
                report = self.reconcile.sync(repo, machine='test', adopt=['kept'],
                    recovery_roots={}, skill_roots=[live], check_commands=[], scoped=True)
            self.assertEqual('incomplete', report['result'], report)
            self.assertEqual('concurrent nested snapshot edit', nested.read_text())
            self.assertTrue((repo / report['backup'] / 'snapshot').is_dir())

    def test_changed_snapshot_location_blocks_before_deployment(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, _ = self.setup_git(Path(temp))
            selected = repo / 'skills/kept/fixture.txt'
            selected.write_text(selected.read_text() + '\nrequested\n')
            original = (live / 'kept/fixture.txt').read_bytes()
            def check(*_):
                config = json.loads((repo / 'fleet.json').read_text())
                config['snapshot_root'] = 'render/new-location'
                (repo / 'fleet.json').write_text(json.dumps(config))
                return []
            with patch.object(self.reconcile, '_run_checks', side_effect=check):
                report = self.reconcile.complete_sync(repo, machine='test', recovery_roots={},
                    skill_roots=[live], adopt=['kept'])
            self.assertEqual('incomplete', report['result'], report)
            self.assertIn('dependency changed', report['reason'])
            self.assertEqual(original, (live / 'kept/fixture.txt').read_bytes())

    def test_live_adoption_does_not_overwrite_source_changed_during_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            target = repo / 'skills/kept'
            selected = target / 'SKILL.md'
            (live / 'kept/SKILL.md').write_text((live / 'kept/SKILL.md').read_text() + '\nrequested live edit\n')
            original_copy = self.reconcile._copy_optional
            def copy(source, destination):
                result = original_copy(source, destination)
                if source == target:
                    selected.write_text(selected.read_text() + '\nconcurrent source edit\n')
                return result
            with patch.object(self.reconcile, '_copy_optional', side_effect=copy):
                report = self.reconcile.sync(repo, machine='test', adopt=['kept'],
                    recovery_roots={}, skill_roots=[live], check_commands=[], scoped=True)
            self.assertEqual('rejected', report['result'], report)
            self.assertIn('concurrent source edit', selected.read_text())
            self.assertNotIn('requested live edit', selected.read_text())

    def test_rollback_preserves_unrelated_managed_state_added_during_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            selected = repo / 'skills/kept/SKILL.md'
            selected.write_text(selected.read_text() + '\nrequested\n')
            original = (live / 'kept/SKILL.md').read_bytes()
            marker = live / self.fleet.STATE_FILE
            def check(*_):
                state = json.loads(marker.read_text())
                state['skills']['other'] = {'sha256': 'a' * 64}
                marker.write_text(json.dumps(state))
                return []
            with patch.object(self.reconcile, '_run_checks', side_effect=check), patch.object(
                    self.reconcile.fleet, 'verify_snapshot', return_value=[{'name': 'kept', 'status': 'drift'}]):
                report = self.reconcile.sync(repo, machine='test', adopt=['kept'],
                    recovery_roots={}, skill_roots=[live], check_commands=[], scoped=True)
            self.assertEqual('rejected', report['result'], report)
            self.assertEqual({'sha256': 'a' * 64}, json.loads(marker.read_text())['skills']['other'])
            self.assertEqual(original, (live / 'kept/SKILL.md').read_bytes())

    def test_rollback_does_not_revert_live_content_it_did_not_write(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            selected = repo / 'skills/kept/SKILL.md'
            selected.write_text(selected.read_text() + '\nrequested\n')
            desired = selected.read_bytes()
            def check(*_):
                (live / 'kept/SKILL.md').write_bytes(desired)
                return []
            with patch.object(self.reconcile, '_run_checks', side_effect=check), patch.object(
                    self.reconcile.fleet, 'verify_snapshot', return_value=[{'name': 'kept', 'status': 'drift'}]):
                report = self.reconcile.sync(repo, machine='test', adopt=['kept'],
                    recovery_roots={}, skill_roots=[live], check_commands=[], scoped=True)
            self.assertEqual('rejected', report['result'], report)
            self.assertEqual(desired, (live / 'kept/SKILL.md').read_bytes())

    def test_selected_state_changed_after_backup_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            selected = repo / 'skills/kept/SKILL.md'
            selected.write_text(selected.read_text() + '\nrequested\n')
            marker = live / self.fleet.STATE_FILE
            original_live = (live / 'kept/SKILL.md').read_bytes()
            original_copy = self.reconcile._copy_optional
            def copy(source, destination):
                result = original_copy(source, destination)
                if destination.name == 'state-before-apply.json':
                    state = json.loads(marker.read_text())
                    state['skills']['kept']['concurrent_marker'] = 'writer-value'
                    marker.write_text(json.dumps(state))
                return result
            with patch.object(self.reconcile, '_copy_optional', side_effect=copy):
                report = self.reconcile.sync(repo, machine='test', adopt=['kept'],
                    recovery_roots={}, skill_roots=[live], check_commands=[], scoped=True)
            self.assertEqual('rejected', report['result'], report)
            self.assertEqual('writer-value', json.loads(marker.read_text())['skills']['kept']['concurrent_marker'])
            self.assertEqual(original_live, (live / 'kept/SKILL.md').read_bytes())

    def test_publication_only_does_not_consume_unrelated_dirty_fleet_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, _ = self.setup_git(Path(temp))
            (repo / 'notes.md').write_text('reviewed documentation')
            (repo / 'fleet.json').write_text('unfinished unrelated configuration')
            report = self.run_sync(repo, live, include=['notes.md'], source_only=True)
            self.assertEqual('published', report['result'], report)
            self.assertFalse(report['agents_verified'])
            self.assertFalse(report['installed_verified'])
            self.assertEqual('unfinished unrelated configuration', (repo / 'fleet.json').read_text())

    def test_retry_does_not_substitute_another_requested_owner_for_pending_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            (repo / 'notes.md').write_text('reviewed documentation')
            hook = remote / 'hooks/pre-receive'
            hook.write_text('#!/bin/sh\nexit 1\n')
            hook.chmod(0o755)
            self.assertEqual('incomplete', self.run_sync(repo, live, include=['notes.md'])['result'])
            hook.unlink()
            report = self.run_sync(repo, live, adopt=['kept'])
            self.assertEqual('incomplete', report['result'], report)
            self.assertIn('different owner selection', report['reason'])
            self.assertEqual('synced', self.run_sync(repo, live)['result'])


if __name__ == '__main__':
    unittest.main()
