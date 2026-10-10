"""Instruction publication must have a bound architectural reason, not just valid bytes."""
from pathlib import Path
import hashlib
import json
import tempfile
import subprocess
import unittest

import test_worktree_sync as fixtures


class InstructionChangeTests(unittest.TestCase):
    setUp = fixtures.WorktreeSyncTests.setUp
    fixture = fixtures.WorktreeSyncTests.fixture
    git = fixtures.WorktreeSyncTests.git
    setup_git = fixtures.WorktreeSyncTests.setup_git
    adapter = fixtures.WorktreeSyncTests.adapter
    worker = fixtures.WorktreeSyncTests.worker
    commit = fixtures.WorktreeSyncTests.commit
    snapshot = fixtures.WorktreeSyncTests.snapshot

    # Reuse the real fixture, without importing another test suite into discovery.
    def setup_instructions(self, folder):
        repo, live, remote = self.setup_git(folder)
        index = repo / 'contracts/instruction-surfaces.json'
        index.write_text(json.dumps({'schema_version': 2, 'surfaces': [
            {'artifact': 'surfaces/core.md', 'owner': 'surfaces/core.md'}]}))
        (repo / 'surfaces').mkdir()
        (repo / 'surfaces/core.md').write_text('Baseline direction.\n')
        self.git(repo, 'add', '.')
        self.git(repo, 'commit', '-m', 'declare instruction architecture')
        self.git(repo, 'push', 'origin', 'main')
        (repo / 'surfaces/core.md').write_bytes(subprocess.check_output(['git', '-C', str(repo), 'show', 'HEAD:surfaces/core.md']))
        return repo, live, remote

    def test_ready_blocks_unjustified_instruction_before_deploy(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_instructions(Path(temporary))
            worker = self.worker(repo, 'instruction-worker')
            ready = self.commit(worker, 'surfaces/core.md', 'Always write another instruction.\n')
            before = self.snapshot(worker), self.git(remote, 'rev-parse', 'main')
            result = adapter.ready_plan(worker, ready, include=['surfaces/core.md'])
            self.assertEqual('review-required', result['result'], result)
            self.assertIn('instruction', result['reason'].lower())
            self.assertEqual(before, (self.snapshot(worker), self.git(remote, 'rev-parse', 'main')))
            self.assertFalse((repo / '.git' / 'agent-signal-integration-worktree').exists())

    def test_bound_correction_passes_but_sufficient_baseline_and_stale_receipts_block(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_instructions(Path(temporary))
            worker = self.worker(repo, 'instruction-worker')
            target = worker / 'surfaces/core.md'
            before = hashlib.sha256(subprocess.check_output(['git', '-C', str(worker), 'show', 'HEAD:surfaces/core.md'])).hexdigest()
            target.write_bytes(b'Judge requested outcomes; preserve necessary reads.\n')
            after = hashlib.sha256(target.read_bytes()).hexdigest()
            record = {'owner': 'surfaces/core.md', 'basis': 'user-correction',
                      'deviation': 'Old contract rejects useful outcomes merely for an optional unread skill.',
                      'evidence': 'Fixture user explicitly selected outcome-first acceptance.',
                      'baseline_sufficient': False,
                      'why_instruction': 'The incorrect policy is owned by this standing source.',
                      'alternative': 'A task-specific rule would leave the universal policy conflict.',
                      'artifacts': {'surfaces/core.md': {'before_sha256': before, 'after_sha256': after}}}
            receipt = worker / 'evals/results/instruction-test.json'
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({'instruction_changes': [record]}))
            self.git(worker, 'add', '.')
            self.git(worker, 'commit', '-m', 'bound instruction correction')
            ready = self.git(worker, 'rev-parse', 'HEAD')
            includes = ['surfaces/core.md', 'evals/results/instruction-test.json']
            result = adapter.ready_plan(worker, ready, include=includes)
            self.assertEqual('ready', result['result'], result)
            original = json.loads(json.dumps(record))
            for key, value in [('owner', 'skills/random'), ('basis', 'guess'),
                               ('evidence', ''), ('why_instruction', None),
                               ('baseline_sufficient', 'false')]:
                changed = json.loads(json.dumps(original))
                changed[key] = value
                ready = self.commit(worker, 'evals/results/instruction-test.json', json.dumps({'instruction_changes': [changed]}))
                snapshot = self.snapshot(worker), self.git(remote, 'rev-parse', 'main')
                result = adapter.ready_plan(worker, ready, include=includes)
                self.assertEqual('review-required', result['result'], (key, result))
                self.assertEqual(snapshot, (self.snapshot(worker), self.git(remote, 'rev-parse', 'main')))
            for rows in ([], [original, original], [None]):
                ready = self.commit(worker, 'evals/results/instruction-test.json', json.dumps({'instruction_changes': rows}))
                result = adapter.ready_plan(worker, ready, include=includes)
                self.assertEqual('review-required', result['result'], result)
            record['baseline_sufficient'] = True
            ready = self.commit(worker, 'evals/results/instruction-test.json', json.dumps({'instruction_changes': [record]}))
            result = adapter.ready_plan(worker, ready, include=includes)
            self.assertEqual('review-required', result['result'], result)
            self.assertIn('sufficient', result['reason'])
            record['baseline_sufficient'] = False
            record['artifacts']['surfaces/core.md']['after_sha256'] = '0' * 64
            ready = self.commit(worker, 'evals/results/instruction-test.json', json.dumps({'instruction_changes': [record]}))
            result = adapter.ready_plan(worker, ready, include=includes)
            self.assertEqual('review-required', result['result'], result)
            self.assertIn('bound', result['reason'])



    def test_random_instruction_file_rejects_and_ordinary_code_needs_no_instruction_record(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_instructions(Path(temporary))
            worker = self.worker(repo, 'instruction-worker')
            ready = self.commit(worker, 'tools/helper.py', 'value = 1\n')
            result = adapter.ready_plan(worker, ready, include=['tools/helper.py'])
            self.assertEqual('ready', result['result'], result)
            ready = self.commit(worker, 'random/AGENTS.md', 'Always add rules.\n')
            before = self.snapshot(worker), self.git(remote, 'rev-parse', 'main')
            result = adapter.ready_plan(worker, ready, include=['tools/helper.py', 'random/AGENTS.md'])
            self.assertEqual('review-required', result['result'], result)
            self.assertIn('unowned', result['reason'])
            self.assertEqual(before, (self.snapshot(worker), self.git(remote, 'rev-parse', 'main')))

    def test_shared_checkout_is_gated_before_publication(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_instructions(Path(temporary))
            (repo / 'surfaces/core.md').write_bytes(b'Unjustified new rule.\n')
            before = self.snapshot(repo), self.git(remote, 'rev-parse', 'main')
            result = adapter.reconcile.complete_sync(repo, machine='test', skill_roots=[live],
                         include=['surfaces/core.md'], capture_recovery=False, scoped=True)
            self.assertIn(result['result'], ('review-required', 'incomplete'), result)
            self.assertIn('instruction', result['reason'].lower())
            self.assertEqual(before, (self.snapshot(repo), self.git(remote, 'rev-parse', 'main')))

    def test_generated_copy_cannot_use_an_unchanged_source_as_exemption(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_instructions(Path(temporary))
            name = 'recovery/current/hosts/codex/AGENTS.md'
            target = repo / name
            target.parent.mkdir(parents=True)
            target.write_bytes(b'Hand-written generated instruction.\n')
            before = self.snapshot(repo), self.git(remote, 'rev-parse', 'main')
            result = adapter.reconcile.complete_sync(repo, machine='test', skill_roots=[live],
                         include=['surfaces/core.md', name], capture_recovery=False, scoped=True)
            self.assertIn(result['result'], ('review-required', 'incomplete'), result)
            self.assertIn('canonical source', result['reason'])
            self.assertEqual(before, (self.snapshot(repo), self.git(remote, 'rev-parse', 'main')))

    def test_broad_publication_is_also_gated_before_writes(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_instructions(Path(temporary))
            (repo / 'surfaces/core.md').write_bytes(b'Unjustified new standing rule.\n')
            before = self.snapshot(repo), self.git(remote, 'rev-parse', 'main')
            # Broader checks are outside this regression; only stub the plan's
            # unrelated inventory so the real publication branch is exercised.
            from unittest.mock import patch
            with patch.object(adapter.reconcile, 'plan', return_value={'findings': []}):
                result = adapter.reconcile.complete_sync(repo, machine='test', skill_roots=[live],
                    include=['surfaces/core.md'], capture_recovery=False, scoped=False)
            self.assertIn(result['result'], ('review-required', 'incomplete'), result)
            self.assertIn('instruction', result['reason'].lower())
            self.assertEqual(before, (self.snapshot(repo), self.git(remote, 'rev-parse', 'main')))

    def test_broad_live_origin_adoption_is_gated_before_other_agents_change(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_instructions(Path(temporary))
            owner = repo / 'contracts/ownership.json'
            owner.write_text(json.dumps({'capabilities': [{'id': 'kept', 'owner': 'skills/kept'}]}))
            self.git(repo, 'add', '.')
            self.git(repo, 'commit', '-m', 'declare skill owner')
            self.git(repo, 'push', 'origin', 'main')
            live_owner = live / 'kept/SKILL.md'
            live_owner.write_bytes(live_owner.read_bytes() + b'\nAlways add unnecessary rules.\n')
            before = self.snapshot(repo), live_owner.read_bytes(), self.git(remote, 'rev-parse', 'main')
            from unittest.mock import patch
            with patch.object(adapter.reconcile, 'plan', return_value={'findings': []}):
                result = adapter.reconcile.complete_sync(repo, machine='test', skill_roots=[live],
                    capture_recovery=False, scoped=False)
            self.assertIn(result['result'], ('review-required', 'incomplete'), result)
            self.assertIn('instruction', result['reason'].lower())
            self.assertEqual(before, (self.snapshot(repo), live_owner.read_bytes(), self.git(remote, 'rev-parse', 'main')))

    def test_sufficient_baseline_allows_pure_removal_but_not_a_disguised_rewrite(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_instructions(Path(temporary))
            worker = self.worker(repo, 'instruction-worker')
            target = worker / 'surfaces/core.md'
            before = hashlib.sha256(subprocess.check_output(['git', '-C', str(worker), 'show', 'HEAD:surfaces/core.md'])).hexdigest()
            target.write_bytes(b'')
            record = {'owner': 'surfaces/core.md', 'basis': 'user-correction',
                      'deviation': 'Redundant steering adds no value beyond the sufficient base model.',
                      'evidence': 'Fixture author selected deletion of redundant advice.',
                      'baseline_sufficient': True, 'change_kind': 'remove',
                      'why_instruction': 'Remove existing redundant text at its owner.',
                      'alternative': 'Adding more prose perpetuates the same deviation.',
                      'artifacts': {'surfaces/core.md': {'before_sha256': before, 'after_sha256': hashlib.sha256(b'').hexdigest()}}}
            receipt = worker / 'evals/results/instruction-test.json'
            receipt.parent.mkdir(parents=True)
            receipt.write_bytes(json.dumps({'instruction_changes': [record]}).encode())
            self.git(worker, 'add', '.')
            self.git(worker, 'commit', '-m', 'remove redundant instruction')
            includes = ['surfaces/core.md', 'evals/results/instruction-test.json']
            result = adapter.ready_plan(worker, self.git(worker, 'rev-parse', 'HEAD'), include=includes)
            self.assertEqual('ready', result['result'], result)
            target.write_bytes(b'A newly invented requirement.\n')
            record['artifacts']['surfaces/core.md']['after_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
            receipt.write_bytes(json.dumps({'instruction_changes': [record]}).encode())
            self.git(worker, 'add', '.')
            self.git(worker, 'commit', '-m', 'disguised instruction addition')
            result = adapter.ready_plan(worker, self.git(worker, 'rev-parse', 'HEAD'), include=includes)
            self.assertEqual('review-required', result['result'], result)
            self.assertIn('removal contains', result['reason'])
