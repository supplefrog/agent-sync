"""Integrated scoped publication and concurrent-work preservation."""
from pathlib import Path
import json
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

    def test_selected_owner_completes_despite_unrelated_owner_conflict_and_staged_work(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            self.extra_owner(repo, live)
            selected = repo / 'skills/kept/SKILL.md'
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
            self.assertEqual('synced', report['result'], report)
            self.assertEqual(source_before, other_source.read_bytes())
            self.assertEqual(live_before, other_live.read_bytes())
            self.assertEqual(staged, self.git(repo, 'diff', '--cached', '--raw'))
            self.assertEqual(selected.read_bytes(), (live / 'kept/SKILL.md').read_bytes())
            self.assertEqual(self.git(repo, 'rev-parse', 'HEAD'), self.git(remote, 'rev-parse', 'main'))
            self.assertNotIn('private-unrelated.md', self.git(remote, 'ls-tree', '-r', '--name-only', 'main').splitlines())
            self.assertEqual(['kept'], report['verified_owners'])
            self.assertTrue(report['pending_files'])

    def test_include_only_publishes_without_claiming_agent_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, _ = self.setup_git(Path(temp))
            (repo / 'notes.md').write_text('reviewed')
            selected = repo / 'skills/kept/SKILL.md'
            selected.write_text(selected.read_text() + '\nunrelated owner pending\n')
            original_live = (live / 'kept/SKILL.md').read_bytes()
            report = self.run_sync(repo, live, include=['notes.md'])
            self.assertEqual('synced', report['result'], report)
            self.assertFalse(report['agents_verified'])
            self.assertEqual([], report['verified_owners'])
            self.assertEqual(original_live, (live / 'kept/SKILL.md').read_bytes())
            self.assertIn('skills/kept/SKILL.md', report['pending_files'])

    def test_selected_change_during_checks_stops_before_deployment(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            selected = repo / 'skills/kept/SKILL.md'
            selected.write_text(selected.read_text() + '\nrequested\n')
            original = (live / 'kept/SKILL.md').read_bytes()
            head = self.git(remote, 'rev-parse', 'main')
            def check(*_):
                selected.write_text(selected.read_text() + '\nconcurrent change\n')
                return []
            with patch.object(self.reconcile, '_run_checks', side_effect=check):
                report = self.reconcile.complete_sync(repo, machine='test', recovery_roots={},
                    skill_roots=[live], adopt=['kept'])
            self.assertEqual('incomplete', report['result'], report)
            self.assertEqual(original, (live / 'kept/SKILL.md').read_bytes())
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
            selected = repo / 'skills/kept/SKILL.md'
            selected.write_text(selected.read_text() + '\nrequested\n')
            original = (live / 'kept/SKILL.md').read_bytes()
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
            self.assertEqual(original, (live / 'kept/SKILL.md').read_bytes())

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
            report = self.run_sync(repo, live, include=['notes.md'])
            self.assertEqual('synced', report['result'], report)
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
