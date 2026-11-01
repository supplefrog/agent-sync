"""Requested existing-owner edits through the real publication and rollout gate."""
from pathlib import Path
import json
import tempfile
import unittest

import test_reconcile as fixtures
import test_worktree_sync as ready_fixtures


class RequestedEditTests(unittest.TestCase):
    setUp = ready_fixtures.WorktreeSyncTests.setUp
    fixture = ready_fixtures.WorktreeSyncTests.fixture
    git = ready_fixtures.WorktreeSyncTests.git
    setup_git = ready_fixtures.WorktreeSyncTests.setup_git
    worker = ready_fixtures.WorktreeSyncTests.worker
    run_ready = ready_fixtures.WorktreeSyncTests.run_ready

    def prepare(self, root, metadata=False):
        repo, live, remote = self.setup_git(root)
        (repo / 'contracts/instruction-surfaces.json').write_text(json.dumps({'schema_version': 2, 'surfaces': []}))
        (repo / 'contracts/ownership.json').write_text(json.dumps({'capabilities': [{'id': 'kept', 'owner': 'skills/kept'}]}))
        registry = json.loads((repo / 'registry.json').read_bytes())
        next(r for r in registry['skills'] if r['name'] == 'kept')['license'] = 'MIT'
        (repo / 'registry.json').write_text(json.dumps(registry))
        if metadata:
            entry = repo / 'skills/kept/SKILL.md'
            entry.write_bytes(entry.read_bytes().replace(b'license: MIT',
                b'version: 1.0.0\ncompatibility: portable\nallowed-tools: Read\nlicense: MIT'))
        self.git(repo, 'add', '.')
        self.git(repo, 'commit', '-m', 'admitted owner baseline')
        self.git(repo, 'push', 'origin', 'main')
        base = self.git(repo, 'rev-parse', 'HEAD')
        worker = self.worker(repo, 'requested-edit-worker')
        before = self.fleet.directory_record(worker / 'skills/kept')
        entry = worker / 'skills/kept/SKILL.md'
        entry.write_bytes(entry.read_bytes() + b'\nKeep the explicitly selected question map with the project handoff.\n')
        if metadata:
            entry.write_bytes(entry.read_bytes().replace(b'version: 1.0.0\ncompatibility: portable\n',
                b'metadata:\n  version: 1.0.1\n  compatibility: portable\n'))
        after = self.fleet.directory_record(worker / 'skills/kept')
        files = {n: {'before_sha256': h, 'after_sha256': after['files'][n]} for n, h in before['files'].items()}
        acceptance = {'classification': 'requested-existing-instruction-edit', 'baseline_commit': base,
                      'license': 'MIT', 'before_package_sha256': before['sha256'], 'after_package_sha256': after['sha256'],
                      'files': files, 'runtime_activation': False, 'model_benefit_claim': False,
                      'deployment_checks_required': ['native-hermes-codex-omp-catalogue-body', 'repeat-sync-preserves-source']}
        row = {'owner': 'skills/kept', 'change_kind': 'requested-edit', 'basis': 'user-correction',
               'baseline_sufficient': False, 'deviation': 'User explicitly selected an existing-owner edit.',
               'evidence': 'Synthetic user selection fixture.', 'why_instruction': 'The selected behavior belongs to this skill.',
               'alternative': 'Unchanged baseline omits the selected behavior.', 'requested_edit_acceptance': acceptance,
               'artifacts': {'skills/kept/SKILL.md': files['SKILL.md']}}
        return repo, live, remote, worker, row

    def publish(self, worker, live, row, executable=False):
        receipt = worker / 'evals/results/requested-edit.json'
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps({'instruction_changes': [row]}))
        self.git(worker, 'add', '.')
        if executable:
            self.git(worker, 'update-index', '--chmod=+x', 'skills/kept/SKILL.md')
        self.git(worker, 'commit', '-m', 'explicit requested edit')
        return self.run_ready(fixtures.load_tool('worktree_sync'), worker, self.git(worker, 'rev-parse', 'HEAD'), live,
                              adopt=['kept'], include=['evals/results/requested-edit.json', 'registry.json'])

    def test_requested_edit_publishes_reads_back_and_repeats(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, worker, row = self.prepare(Path(temp), metadata=True)
            result = self.publish(worker, live, row)
            self.assertEqual('synced', result['result'], result)
            expected = (worker / 'skills/kept/SKILL.md').read_bytes()
            self.assertEqual(expected, (live / 'kept/SKILL.md').read_bytes())
            import subprocess
            self.assertEqual(expected, subprocess.check_output(['git', '-C', str(remote), 'show', 'main:skills/kept/SKILL.md']))
            head, before = self.git(remote, 'rev-parse', 'main'), fixtures.digest(live)
            repeated = fixtures.load_tool('worktree_sync').rollout_published(repo, head, machine='test')
            self.assertEqual('synced', repeated['result'], repeated)
            self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(before, fixtures.digest(live))

    def test_invalid_acceptance_does_not_mutate_remote_or_live(self):
        for failure in ('missing', 'null', 'empty', 'runtime', 'benefit', 'stale', 'files', 'baseline', 'license', 'claims'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                repo, live, remote, worker, row = self.prepare(Path(temp))
                acceptance = row['requested_edit_acceptance']
                if failure == 'missing': row.pop('requested_edit_acceptance')
                elif failure == 'null': row['requested_edit_acceptance'] = None
                elif failure == 'empty': row['requested_edit_acceptance'] = {}
                elif failure == 'runtime': acceptance['runtime_activation'] = True
                elif failure == 'benefit': acceptance['model_benefit_claim'] = True
                elif failure == 'stale': acceptance['after_package_sha256'] = 'a' * 64
                elif failure == 'files': acceptance['files'] = None
                elif failure == 'baseline': acceptance['baseline_commit'] = 'a' * 40
                elif failure == 'license': acceptance['license'] = 'Apache-2.0'
                elif failure == 'claims': row['behavior_measurements'] = []
                head, before = self.git(remote, 'rev-parse', 'main'), fixtures.digest(live)
                result = self.publish(worker, live, row)
                self.assertNotEqual('synced', result['result'], result)
                self.assertRegex(result.get('reason', ''), 'requested edit|behavioral-adoption')
                self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
                self.assertEqual(before, fixtures.digest(live))

    def test_ready_git_executable_mode_change_is_refused_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, worker, row = self.prepare(Path(temp))
            head, before = self.git(remote, 'rev-parse', 'main'), fixtures.digest(live)
            result = self.publish(worker, live, row, executable=True)
            self.assertNotEqual('synced', result['result'], result)
            self.assertIn('Git modes', result.get('reason', ''))
            self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(before, fixtures.digest(live))

    def advance(self, repo, live, registry=False, package=False, selected_registry=False):
        unrelated = self.worker(repo, 'independent-worker')
        name = 'skills/kept/fixture.txt' if package else 'a.md'
        (unrelated / name).write_bytes(b'Independent publication.\n')
        includes = [name]
        if registry or selected_registry:
            path = unrelated / 'registry.json'
            data = json.loads(path.read_bytes())
            selected = 'kept' if selected_registry else 'fleet-sync'
            next(r for r in data['skills'] if r['name'] == selected)['source'] = 'independent maintenance'
            path.write_text(json.dumps(data))
            includes.append('registry.json')
        self.git(unrelated, 'add', '.')
        self.git(unrelated, 'commit', '-m', 'independent publication')
        result = self.run_ready(fixtures.load_tool('worktree_sync'), unrelated,
                                self.git(unrelated, 'rev-parse', 'HEAD'), live, include=includes,
                                adopt=['kept'] if package else [])
        self.assertEqual('synced', result['result'], result)

    def test_reviewed_ancestor_survives_unrelated_publication_and_registry_maintenance(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, worker, row = self.prepare(Path(temp))
            self.advance(repo, live, registry=True)
            result = self.publish(worker, live, row)
            self.assertEqual('synced', result['result'], result)
            self.assertEqual((worker / 'skills/kept/SKILL.md').read_bytes(), (live / 'kept/SKILL.md').read_bytes())
            self.assertEqual('Independent publication.', self.git(remote, 'show', 'main:a.md'))
            registry = json.loads(self.git(remote, 'show', 'main:registry.json'))
            self.assertEqual('independent maintenance', next(r for r in registry['skills'] if r['name'] == 'fleet-sync')['source'])

    def test_invalid_or_drifted_reviewed_baselines_leave_remote_and_live_unchanged(self):
        for failure in ('invalid', 'tree', 'nonancestor', 'package-drift', 'selected-registry-drift'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                repo, live, remote, worker, row = self.prepare(Path(temp))
                acceptance = row['requested_edit_acceptance']
                baseline = acceptance['baseline_commit']
                if failure == 'invalid': acceptance['baseline_commit'] = 'a' * 40
                if failure == 'tree': acceptance['baseline_commit'] = self.git(repo, 'rev-parse', baseline + '^{tree}')
                if failure == 'nonancestor':
                    acceptance['baseline_commit'] = self.git(repo, 'commit-tree', baseline + '^{tree}', '-m', 'unrelated root')
                if failure == 'package-drift': self.advance(repo, live, package=True)
                if failure == 'selected-registry-drift': self.advance(repo, live, selected_registry=True)
                head, before = self.git(remote, 'rev-parse', 'main'), fixtures.digest(live)
                result = self.publish(worker, live, row)
                self.assertNotEqual('synced', result['result'], result)
                self.assertRegex(result.get('reason', ''), 'requested edit|bad file|valid object')
                self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
                self.assertEqual(before, fixtures.digest(live))

    def test_rebound_unsupported_changes_reject_before_remote_or_live_mutation(self):
        for failure in ('trigger', 'permission', 'license', 'name', 'compatibility', 'config', 'new-file', 'deleted-file', 'registry', 'owner'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                repo, live, remote, worker, row = self.prepare(Path(temp), metadata=True)
                entry = worker / 'skills/kept/SKILL.md'
                if failure in ('trigger', 'permission', 'license', 'name', 'compatibility'):
                    old, new = {'trigger': (b'Use when handling kept.', b'Use for every request.'),
                                'permission': (b'allowed-tools: Read', b'allowed-tools: Bash'),
                                'license': (b'license: MIT', b'license: Apache-2.0'),
                                'name': (b'name: kept', b'name: other'),
                                'compatibility': (b'compatibility: portable', b'compatibility: windows')}[failure]
                    entry.write_bytes(entry.read_bytes().replace(old, new))
                if failure == 'config': (worker / 'skills/kept/fixture.txt').write_text('changed runtime config')
                if failure == 'new-file': (worker / 'skills/kept/new.py').write_text('print(1)')
                if failure == 'deleted-file': (worker / 'skills/kept/fixture.txt').unlink()
                if failure == 'registry':
                    path = worker / 'registry.json'
                    path.write_bytes(path.read_bytes() + b'\n')
                if failure == 'owner': row['owner'] = 'skills/other'
                # Fresh hashes cannot authorize a forbidden transition.
                actual = self.fleet.directory_record(worker / 'skills/kept')
                row['requested_edit_acceptance']['after_package_sha256'] = actual['sha256']
                for relative, binding in row['requested_edit_acceptance']['files'].items():
                    binding['after_sha256'] = actual['files'].get(relative, 'absent')
                head, before = self.git(remote, 'rev-parse', 'main'), fixtures.digest(live)
                result = self.publish(worker, live, row)
                self.assertNotEqual('synced', result['result'], result)
                self.assertRegex(result.get('reason', ''), 'requested edit|architectural owner|bound necessity')
                self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
                self.assertEqual(before, fixtures.digest(live))


if __name__ == '__main__': unittest.main()
