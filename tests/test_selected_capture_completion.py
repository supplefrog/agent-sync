"""Selected native capture integrated with real temporary Git publication."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

import test_reconcile as fixtures
import test_sync_completion as completion


class SelectedCaptureCompletionTests(unittest.TestCase):
    setUp = completion.CompleteSyncTests.setUp
    fixture = completion.CompleteSyncTests.fixture
    git = completion.CompleteSyncTests.git
    setup_git = completion.CompleteSyncTests.setup_git

    def native_fixture(self, root, *, legacy_binding=False):
        repo, live, remote = self.setup_git(root)
        self.git(repo, 'config', 'core.autocrlf', 'false')
        (repo / '.gitattributes').write_text('* -text\n')
        (repo / '.gitignore').write_text('render/\n.agent-signal-path-*.lock\n')
        roots = {host: root / host for host in ('hermes', 'codex')}
        hosts = {}
        for host, directory in roots.items():
            directory.mkdir()
            (directory / 'config.json').write_text('{"model":"old","private":"preserve"}')
            hosts[host] = {'artifacts': [{'id': 'settings', 'kind': 'config', 'format': 'json',
                'strategy': 'merge', 'source': 'config.json',
                'snapshot': f'hosts/{host}/config.json', 'include': ['model']}]}
        (repo / 'recovery.json').write_text(json.dumps({'schema_version': 1,
            'machine': 'test', 'public_safe': True, 'hosts': hosts}))
        manifest = self.reconcile.recovery.snapshot(repo / 'recovery.json', repo / 'recovery/current', roots)
        source = json.loads((fixtures.REPO / 'host-deltas.json').read_text())
        entry = next(item for item in source['entries'] if item['id'] == 'hermes-settings')
        record = next(item for item in manifest['artifacts'] if item['host'] == 'hermes')
        entry['version_or_hash'] = 'sha256:' + (self.fleet.sha256_file(repo / 'recovery/current/manifest.json')
                                                  if legacy_binding else record['sha256'])
        self.fleet.atomic_json(repo / 'host-deltas.json', {'schema_version': 1,
            'machine': 'test', 'public_safe': True, 'entries': [entry], 'exclusions': []})
        self.git(repo, 'add', '.')
        self.git(repo, 'commit', '-m', 'native baseline')
        self.git(repo, 'push', 'origin', 'main')
        return repo, live, remote, roots

    def capture(self, repo, live, roots, *, artifacts=('hermes:settings',), **kwargs):
        # The fixture has no application validators. Git, capture, identity
        # checks, metadata binding, and publication remain real.
        with patch.object(self.reconcile, '_run_checks', return_value=['fixture checks']):
            return self.reconcile.complete_sync(repo, machine='test', recovery_roots=roots,
                skill_roots=[live], recovery_artifacts=list(artifacts), **kwargs)

    def test_selected_capture_completes_and_preserves_unselected_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, roots = self.native_fixture(Path(temp), legacy_binding=True)
            untouched = repo / 'recovery/current/hosts/codex/config.json'
            before = untouched.read_bytes()
            (roots['hermes'] / 'config.json').write_text('{"model":"new","private":"preserve"}')
            report = self.capture(repo, live, {'hermes': roots['hermes']})
            self.assertEqual('synced', report['result'], report)
            self.assertTrue(report['capture_verified'])
            self.assertEqual(['hermes:settings'], report['verified_recovery_artifacts'])
            self.assertIsNone(report['measurements']['billed_cost_usd'])
            self.assertGreater(report['measurements']['total_seconds'], 0)
            self.assertEqual(before, untouched.read_bytes())
            published = json.loads(self.git(remote, 'show', 'main:recovery/current/hosts/hermes/config.json'))
            self.assertEqual({'model': 'new'}, published)
            self.assertEqual(self.git(repo, 'rev-parse', 'HEAD'), self.git(remote, 'rev-parse', 'main'))
            self.reconcile.recovery.verify_snapshot(repo / 'recovery.json', repo / 'recovery/current')
            self.reconcile.host_deltas.load_manifest(repo / 'host-deltas.json', repo)

    def test_implicit_host_delta_capture_preserves_unreviewed_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, roots = self.native_fixture(Path(temp))
            path = repo / 'host-deltas.json'
            manifest = json.loads(path.read_text())
            manifest['entries'][0]['desired_state'] = 'Unrelated pending metadata'
            self.fleet.atomic_json(path, manifest)
            dirty = path.read_bytes()
            snapshot = (repo / 'recovery/current/hosts/hermes/config.json').read_bytes()
            head = self.git(remote, 'rev-parse', 'main')
            (roots['hermes'] / 'config.json').write_text('{"model":"new"}')
            report = self.capture(repo, live, roots)
            self.assertNotEqual('synced', report['result'], report)
            self.assertEqual(dirty, path.read_bytes())
            self.assertEqual(snapshot, (repo / 'recovery/current/hosts/hermes/config.json').read_bytes())
            self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(head, self.git(repo, 'rev-parse', 'HEAD'))

    def test_implicit_manifest_capture_preserves_unselected_record_and_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, roots = self.native_fixture(Path(temp))
            path = repo / 'recovery/current/manifest.json'
            unselected = repo / 'recovery/current/hosts/codex/config.json'
            data = b'{"model":"unrelated pending capture"}\n'
            unselected.write_bytes(data)
            manifest = json.loads(path.read_text())
            record = next(item for item in manifest['artifacts'] if item['host'] == 'codex')
            record.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
            self.fleet.atomic_json(path, manifest)
            dirty = path.read_bytes()
            snapshot = (repo / 'recovery/current/hosts/hermes/config.json').read_bytes()
            head = self.git(remote, 'rev-parse', 'main')
            (roots['hermes'] / 'config.json').write_text('{"model":"new"}')
            report = self.capture(repo, live, roots)
            self.assertNotEqual('synced', report['result'], report)
            self.assertEqual(dirty, path.read_bytes())
            self.assertEqual(data, unselected.read_bytes())
            self.assertEqual(snapshot, (repo / 'recovery/current/hosts/hermes/config.json').read_bytes())
            self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(head, self.git(repo, 'rev-parse', 'HEAD'))

    def test_reviewed_exact_host_delta_include_remains_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, roots = self.native_fixture(Path(temp))
            path = repo / 'host-deltas.json'
            manifest = json.loads(path.read_text())
            manifest['entries'][0]['desired_state'] = 'Reviewed metadata'
            self.fleet.atomic_json(path, manifest)
            (roots['hermes'] / 'config.json').write_text('{"model":"new"}')
            report = self.capture(repo, live, roots, include=['host-deltas.json'])
            self.assertEqual('synced', report['result'], report)
            published = json.loads(self.git(remote, 'show', 'main:host-deltas.json'))
            self.assertEqual('Reviewed metadata', published['entries'][0]['desired_state'])

    def test_pending_retry_rejects_different_artifact_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, roots = self.native_fixture(Path(temp))
            (roots['hermes'] / 'config.json').write_text('{"model":"new"}')
            hook = remote / 'hooks/pre-receive'
            hook.write_text('#!/bin/sh\nexit 1\n')
            hook.chmod(0o755)
            report = self.capture(repo, live, roots)
            self.assertEqual('incomplete', report['result'], report)
            self.assertEqual('push', report['failed_step'], report)
            head = self.git(repo, 'rev-parse', 'HEAD')
            remote_head = self.git(remote, 'rev-parse', 'main')
            hook.unlink()
            rejected = self.capture(repo, live, roots, artifacts=['codex:settings'])
            self.assertNotEqual('synced', rejected['result'], rejected)
            self.assertIn('different recovery artifact selection', rejected['reason'])
            self.assertEqual(head, self.git(repo, 'rev-parse', 'HEAD'))
            self.assertEqual(remote_head, self.git(remote, 'rev-parse', 'main'))
            (roots['hermes'] / 'config.json').write_text('{"model":"concurrent"}')
            drifted = self.capture(repo, live, roots)
            self.assertNotEqual('synced', drifted['result'], drifted)
            self.assertIn('selected native recovery changed after capture', drifted['reason'])
            self.assertEqual(remote_head, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual('concurrent', json.loads((roots['hermes'] / 'config.json').read_text())['model'])
            (roots['hermes'] / 'config.json').write_text('{"model":"new"}')
            resumed = self.capture(repo, live, roots)
            self.assertEqual('synced', resumed['result'], resumed)
            self.assertEqual(head, self.git(repo, 'rev-parse', 'HEAD'))
            self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))

    def test_explicit_artifact_conflicts_do_not_broaden_or_mutate(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, roots = self.native_fixture(Path(temp))
            original = (repo / 'recovery/current/manifest.json').read_bytes()
            for options in ({'scoped': False}, {'capture_recovery': False}):
                with self.subTest(options=options):
                    result = self.capture(repo, live, roots, **options)
                    self.assertEqual('review-required', result['result'], result)
                    self.assertEqual(original, (repo / 'recovery/current/manifest.json').read_bytes())

    def test_migration_is_rolled_back_if_snapshot_replacement_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, roots = self.native_fixture(Path(temp), legacy_binding=True)
            metadata = repo / 'host-deltas.json'
            original = metadata.read_bytes()
            snapshot = (repo / 'recovery/current/manifest.json').read_bytes()
            (roots['hermes'] / 'config.json').write_text('{"model":"new"}')
            with patch.object(self.reconcile, '_replace_tree', side_effect=RuntimeError('injected snapshot failure')):
                result = self.reconcile.sync(repo, machine='test', recovery_roots=roots,
                    recovery_artifacts=['hermes:settings'], capture_recovery=True,
                    scoped=True, check_commands=[])
            self.assertEqual('rejected', result['result'], result)
            self.assertEqual(original, metadata.read_bytes())
            self.assertEqual(snapshot, (repo / 'recovery/current/manifest.json').read_bytes())

    def test_binding_update_preserves_intervening_metadata_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, roots = self.native_fixture(Path(temp))
            metadata = repo / 'host-deltas.json'
            tool = self.reconcile.host_deltas
            original = tool._load_manifest_unbound
            saved = []
            def intervening(path, directory):
                value = original(path, directory)
                changed = json.loads(metadata.read_text())
                changed['entries'][0]['desired_state'] = 'Concurrent edit'
                self.fleet.atomic_json(metadata, changed)
                saved.append(metadata.read_bytes())
                return value
            with patch.object(tool, '_load_manifest_unbound', side_effect=intervening):
                with self.assertRaisesRegex(RuntimeError, 'changed before binding update'):
                    tool.refresh_bindings(metadata, repo, source_identities=['recovery-artifact:hermes:settings'])
            self.assertEqual(saved[-1], metadata.read_bytes())


if __name__ == '__main__':
    unittest.main()
