"""Pinned imports through real ready integration; only fixture host checks mocked."""
from pathlib import Path
import copy
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
import test_reconcile as fixtures
import test_worktree_sync as ready_fixtures


class RequestedImportTests(unittest.TestCase):
    setUp = ready_fixtures.WorktreeSyncTests.setUp
    fixture = ready_fixtures.WorktreeSyncTests.fixture
    git = ready_fixtures.WorktreeSyncTests.git
    setup_git = ready_fixtures.WorktreeSyncTests.setup_git
    worker = ready_fixtures.WorktreeSyncTests.worker
    run_ready = ready_fixtures.WorktreeSyncTests.run_ready

    def prepare(self, root, insert_license=False):
        repo, live, remote = self.setup_git(root)
        index = repo / 'contracts/instruction-surfaces.json'
        index.write_text(json.dumps({'schema_version': 2, 'surfaces': []}))
        ownership = repo / 'contracts/ownership.json'
        ownership.write_text(json.dumps({'capabilities': [{'id': 'kept', 'owner': 'skills/kept'}]}))
        self.git(repo, 'add', '.')
        self.git(repo, 'commit', '-m', 'ownership baseline')
        self.git(repo, 'push', 'origin', 'main')
        upstream = root / 'upstream'
        fixtures.write_skill(upstream, 'requested', 'Requested instruction package.')
        entry = upstream / 'skills/requested/SKILL.md'
        original = entry.read_bytes().replace(b'\r\n', b'\n')
        if insert_license:
            original = original.replace(b'license: MIT\n', b'')
        entry.write_bytes(original)
        (upstream / 'LICENSE').write_text('MIT synthetic fixture license\n')
        self.git(upstream, 'init', '-b', 'main')
        self.git(upstream, 'config', 'core.autocrlf', 'false')
        self.git(upstream, 'config', 'user.name', 'Fixture')
        self.git(upstream, 'config', 'user.email', 'fixture@example.invalid')
        self.git(upstream, 'add', '.')
        self.git(upstream, 'commit', '-m', 'pinned upstream')
        pin = self.git(upstream, 'rev-parse', 'HEAD')
        self.git(repo, 'fetch', str(upstream), pin)
        worker = self.worker(repo, 'requested-worker')
        package = worker / 'skills/requested'
        import shutil
        shutil.copytree(upstream / 'skills/requested', package)
        shutil.copyfile(upstream / 'LICENSE', package / 'LICENSE')
        digest = lambda data: hashlib.sha256(data).hexdigest()
        files = {p.name: {'upstream_path': 'LICENSE' if p.name == 'LICENSE' else 'skills/requested/' + p.name,
                         'upstream_sha256': digest(p.read_bytes()), 'installed_sha256': digest(p.read_bytes()),
                         'transformation': 'identity'} for p in package.iterdir()}
        if insert_license:
            target = package / 'SKILL.md'
            target.write_bytes(original.replace(b'\n---\n', b'\nlicense: MIT\n---\n', 1))
            files['SKILL.md']['installed_sha256'] = digest(target.read_bytes())
            files['SKILL.md']['transformation'] = 'license-frontmatter'
        record = self.fleet.directory_record(package)
        acceptance = {'classification': 'requested-instruction-package', 'source_repository': 'https://github.com/example/source',
                      'source_commit': pin, 'source_path': 'skills/requested', 'license': 'MIT',
                      'package_sha256': record['sha256'], 'files': files, 'runtime_activation': False,
                      'model_benefit_claim': False,
                      'deployment_checks_required': ['native-hermes-codex-omp-catalogue-body', 'repeat-sync-preserves-source']}
        row = {'owner': 'skills/requested', 'change_kind': 'requested-import', 'basis': 'user-correction',
               'deviation': 'Explicitly requested new package.', 'evidence': 'Pinned upstream fixture.',
               'baseline_sufficient': False, 'why_instruction': 'User selected instruction package.',
               'alternative': 'Leaving package absent fails explicit request.', 'requested_import_acceptance': acceptance,
               'artifacts': {'skills/requested/SKILL.md': {'before_sha256': 'absent', 'after_sha256': files['SKILL.md']['installed_sha256']}}}
        registry = json.loads((worker / 'registry.json').read_bytes())
        registry['skills'].append({'name': 'requested', 'status': 'admitted', 'license': 'MIT',
                                  'source': acceptance['source_repository'] + '/tree/' + pin + '/skills/requested'})
        (worker / 'registry.json').write_text(json.dumps(registry))
        data = json.loads((worker / 'contracts/ownership.json').read_bytes())
        data['capabilities'].append({'id': 'requested', 'owner': 'skills/requested'})
        (worker / 'contracts/ownership.json').write_text(json.dumps(data))
        receipt = worker / 'evals/results/requested.json'
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps({'instruction_changes': [row]}))
        return repo, live, remote, worker, row

    def ready(self, worker, row):
        (worker / 'evals/results/requested.json').write_text(json.dumps({'instruction_changes': [row]}))
        self.git(worker, 'add', '.')
        self.git(worker, 'commit', '-m', 'requested package')
        return self.git(worker, 'rev-parse', 'HEAD')

    def run_import(self, worker, ready, live):
        adapter = fixtures.load_tool('worktree_sync')
        return self.run_ready(adapter, worker, ready, live, adopt=['requested'],
                              include=['registry.json', 'contracts/ownership.json', 'evals/results/requested.json'])

    def test_pinned_import_real_ready_sync_and_repeat(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, worker, row = self.prepare(Path(temp))
            ready = self.ready(worker, row)
            result = self.run_import(worker, ready, live)
            self.assertEqual('synced', result['result'], result)
            self.assertEqual((worker / 'skills/requested/SKILL.md').read_bytes(), (live / 'requested/SKILL.md').read_bytes())
            head = self.git(remote, 'rev-parse', 'main')
            published = Path(result['published_repo'])
            before_live = fixtures.digest(live)
            adapter = fixtures.load_tool('worktree_sync')
            repeat = adapter.rollout_published(repo, head, machine='test')
            self.assertEqual('synced', repeat['result'], repeat)
            self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(before_live, fixtures.digest(live))

    def test_source_contract_matrix_and_sole_license_transformation(self):
        import instruction_changes as changes
        import sync_git
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, worker, row = self.prepare(Path(temp), insert_license=True)
            paths = ['skills/requested/SKILL.md', 'skills/requested/LICENSE']
            base = self.git(repo, 'rev-parse', 'HEAD')
            eligible = lambda: changes.correction_eligibility(worker, repo, paths[0], 'skills/requested', row, base, paths, [])
            self.assertTrue(eligible()['eligible'])
            self.fleet.render_snapshot(worker, worker / 'render/fleet')
            state = self.reconcile._skill_state(worker, worker / 'render/fleet', [('test', live)], 'requested')
            self.assertEqual('review-required', state['mode'], 'a receipt alone cannot authorize live initial installation')
            accepted = copy.deepcopy(row)
            for key, value in [('source_commit', self.git(repo, 'rev-parse', accepted['requested_import_acceptance']['source_commit'] + '^{tree}')),
                               ('model_benefit_claim', True), ('files', {}), ('deployment_checks_required', []),
                               ('source_path', '../escape'), ('runtime_activation', None), ('files', None)]:
                row.clear(); row.update(copy.deepcopy(accepted))
                row['requested_import_acceptance'][key] = value
                with self.subTest(key=key), self.assertRaises((sync_git.SyncBlocked, RuntimeError)):
                    eligible()
            row.clear(); row.update(copy.deepcopy(accepted))
            (worker / 'skills/requested/extra.py').write_text('print("not instruction-only")')
            with self.assertRaises(sync_git.SyncBlocked): eligible()
            (worker / 'skills/requested/extra.py').unlink()
            transient = worker / 'skills/requested/__pycache__/extra.py'
            transient.parent.mkdir()
            transient.write_text('extra file')
            with self.assertRaises(sync_git.SyncBlocked): eligible()

    def test_contradictory_license_metadata_does_not_mutate_remote_or_live(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, worker, row = self.prepare(Path(temp))
            row['requested_import_acceptance']['license'] = 'Apache-2.0'
            registry_file = worker / 'registry.json'
            registry = json.loads(registry_file.read_bytes())
            next(item for item in registry['skills'] if item['name'] == 'requested')['license'] = 'Apache-2.0'
            registry_file.write_text(json.dumps(registry))
            before_remote = self.git(remote, 'rev-parse', 'main')
            before_live = fixtures.digest(live)
            result = self.run_import(worker, self.ready(worker, row), live)
            self.assertNotEqual('synced', result['result'], result)
            self.assertEqual(before_remote, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(before_live, fixtures.digest(live))

    def test_unbound_import_and_collision_do_not_mutate_remote_or_live(self):
        for failure in ('unbound', 'collision', 'runtime', 'source-bytes', 'lifecycle', 'malformed', 'null-acceptance', 'executable', 'intermediate-lifecycle'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                repo, live, remote, worker, row = self.prepare(Path(temp))
                if failure == 'unbound': row.pop('requested_import_acceptance')
                if failure == 'null-acceptance': row['requested_import_acceptance'] = None
                if failure == 'runtime': row['requested_import_acceptance']['runtime_activation'] = True
                if failure == 'source-bytes':
                    (worker / 'skills/requested/SKILL.md').write_text('unbound new bytes')
                if failure == 'collision':
                    (live / 'requested').mkdir()
                    (live / 'requested/local.txt').write_text('preserve unmanaged')
                if failure == 'lifecycle':
                    registry = json.loads((worker / 'registry.json').read_bytes())
                    registry['skills'][0]['status'] = 'retired'
                    (worker / 'registry.json').write_text(json.dumps(registry))
                if failure == 'intermediate-lifecycle':
                    registry_file = worker / 'registry.json'
                    original_registry = registry_file.read_bytes()
                    registry = json.loads(original_registry)
                    registry['skills'][0]['status'] = 'retired'
                    registry_file.write_text(json.dumps(registry))
                    self.git(worker, 'add', 'registry.json')
                    self.git(worker, 'commit', '-m', 'concealed retirement')
                    registry_file.write_bytes(original_registry)
                before_remote = self.git(remote, 'rev-parse', 'main')
                before_live = fixtures.digest(live)
                ready = self.ready(worker, row)
                if failure == 'executable':
                    self.git(worker, 'update-index', '--chmod=+x', 'skills/requested/SKILL.md')
                    self.git(worker, 'commit', '-m', 'executable mode')
                    ready = self.git(worker, 'rev-parse', 'HEAD')
                if failure == 'malformed':
                    (worker / 'evals/results/requested.json').write_text('[null]')
                    self.git(worker, 'add', '.')
                    self.git(worker, 'commit', '-m', 'malformed receipt')
                    ready = self.git(worker, 'rev-parse', 'HEAD')
                result = self.run_import(worker, ready, live)
                self.assertNotEqual('synced', result['result'], result)
                self.assertEqual(before_remote, self.git(remote, 'rev-parse', 'main'))
                self.assertEqual(before_live, fixtures.digest(live))

if __name__ == '__main__': unittest.main()
