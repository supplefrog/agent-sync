"""Instruction publication must have a bound architectural reason, not just valid bytes."""
from pathlib import Path
import hashlib
import json
import tempfile
import subprocess
import unittest

import test_worktree_sync as fixtures


class InstructionChangeTests(unittest.TestCase):
    def test_later_restructuring_declaration_is_checked_with_unchanged_routes(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_instructions(Path(temporary))
            entry, detail = 'skills/kept/SKILL.md', 'skills/kept/references/protocol.md'
            (repo / 'contracts/ownership.json').write_text(json.dumps({'capabilities': [{'id': 'kept', 'owner': 'skills/kept'}]}))
            (repo / entry).write_bytes((repo / entry).read_bytes() + b'\nFor release read [protocol](references/protocol.md).\n')
            (repo / detail).parent.mkdir()
            (repo / detail).write_bytes(b'Required release procedure.\n')
            self.git(repo, 'add', '.')
            self.git(repo, 'commit', '-m', 'existing release route')
            self.git(repo, 'push', 'origin', 'main')
            worker = self.worker(repo, 'stable-route-worker')
            rows = []
            for name in (entry, detail):
                old = subprocess.check_output(['git', '-C', str(worker), 'show', 'HEAD:' + name])
                (worker / name).write_bytes(old + b'\nClarified existing procedure.\n')
                rows.append({'owner': 'skills/kept', 'basis': 'mechanical-maintenance',
                    'deviation': 'Substantial semantic restructuring with stable link topology.', 'evidence': 'Fixture current source.',
                    'baseline_sufficient': False, 'why_instruction': 'Existing instruction owner.', 'alternative': 'Keep existing wording.',
                    'artifacts': {name: {'before_sha256': hashlib.sha256(old).hexdigest(),
                                         'after_sha256': hashlib.sha256((worker / name).read_bytes()).hexdigest()}}})
            rows[1]['restructured'] = True
            receipt_name = 'evals/results/stable-route.json'
            receipt = worker / receipt_name
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({'instruction_changes': rows}))
            self.git(worker, 'add', '.')
            self.git(worker, 'commit', '-m', 'stable links later declaration')
            includes = [entry, detail, receipt_name]
            before = self.snapshot(worker), (live / 'kept/SKILL.md').read_bytes(), self.git(remote, 'rev-parse', 'main')
            result = adapter.ready_plan(worker, self.git(worker, 'rev-parse', 'HEAD'), include=includes)
            self.assertEqual('review-required', result['result'], result)
            self.assertIn('declared workflow restructuring', result['reason'])
            self.assertEqual(before, (self.snapshot(worker), (live / 'kept/SKILL.md').read_bytes(), self.git(remote, 'rev-parse', 'main')))
            rows[1]['loading_review'] = {'entrypoint_reason': 'Keep common routing inline.',
                'checks': 'Source route and required conditions inspected; no natural triggering claim.',
                'obligations': [{'obligation': 'Required release procedure', 'required': True, 'applies_when': 'Release',
                    'before': [entry, detail], 'after': [entry, detail], 'disposition': 'preserved',
                    'load_when': 'Before release', 'reason': 'Keep the existing required route.'}]}
            ready = self.commit(worker, receipt_name, json.dumps({'instruction_changes': rows}))
            self.assertEqual('ready', adapter.ready_plan(worker, ready, include=includes)['result'])

    def test_loading_review_blocks_dense_entrypoint_and_accepts_required_workflow(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_instructions(Path(temporary))
            owner = repo / 'contracts/ownership.json'
            owner.write_text(json.dumps({'capabilities': [{'id': 'kept', 'owner': 'skills/kept'}]}))
            self.git(repo, 'add', '.')
            self.git(repo, 'commit', '-m', 'declare skill owner')
            self.git(repo, 'push', 'origin', 'main')
            worker = self.worker(repo, 'loading-worker')
            name = 'skills/kept/SKILL.md'
            target = worker / name
            old = subprocess.check_output(['git', '-C', str(worker), 'show', 'HEAD:' + name])
            # The reported failure class: extensive prose hidden in few lines.
            target.write_bytes(old + ('\n' + 'required procedure ' * 2000 + '\n').encode())
            record = {'owner': 'skills/kept', 'basis': 'observed-deviation',
                      'deviation': 'Dense common entrypoint bypasses line-only review.',
                      'evidence': 'Reported 139-line frontend body exceeded 32 KB.',
                      'baseline_sufficient': False, 'why_instruction': 'Repair existing loading policy.',
                      'alternative': 'A hard size ceiling rejects legitimate required procedures.',
                      'artifacts': {name: {'before_sha256': hashlib.sha256(old).hexdigest(),
                                           'after_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}}}
            receipt_name = 'evals/results/loading-test.json'
            receipt = worker / receipt_name
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({'instruction_changes': [record]}))
            self.git(worker, 'add', '.')
            self.git(worker, 'commit', '-m', 'dense entrypoint')
            includes = [name, receipt_name]
            before = self.snapshot(worker), (live / 'kept/SKILL.md').read_bytes(), self.git(remote, 'rev-parse', 'main')
            result = adapter.ready_plan(worker, self.git(worker, 'rev-parse', 'HEAD'), include=includes)
            self.assertEqual('review-required', result['result'], result)
            self.assertIn('loading review', result['reason'])
            self.assertEqual(before, (self.snapshot(worker), (live / 'kept/SKILL.md').read_bytes(), self.git(remote, 'rev-parse', 'main')))
            record['loading_review'] = {
                'entrypoint_reason': 'All cases need this substantial compulsory protocol.',
                'checks': 'Source inspection verifies a shared required procedure; no natural-routing claim.',
                'obligations': [{'obligation': 'Required common procedure', 'applies_when': 'Every kept task',
                    'required': True, 'before': [name], 'after': [name], 'disposition': 'preserved',
                    'load_when': 'Read entrypoint before execution', 'reason': 'All modes share the protocol.'}]}
            ready = self.commit(worker, receipt_name, json.dumps({'instruction_changes': [record]}))
            result = adapter.ready_plan(worker, ready, include=includes)
            self.assertEqual('ready', result['result'], result)
            # The same justified required workflow remains valid over 500 lines.
            target.write_bytes(old + b'\n' + b'Required step.\n' * 501)
            record['artifacts'][name]['after_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
            receipt.write_text(json.dumps({'instruction_changes': [record]}))
            self.git(worker, 'add', '.')
            self.git(worker, 'commit', '-m', 'valid multi-line compulsory protocol')
            self.assertEqual('ready', adapter.ready_plan(worker, self.git(worker, 'rev-parse', 'HEAD'), include=includes)['result'])

    def test_reference_move_requires_reachable_obligation_map(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_instructions(Path(temporary))
            (repo / 'contracts/ownership.json').write_text(json.dumps({'capabilities': [{'id': 'kept', 'owner': 'skills/kept'}]}))
            self.git(repo, 'add', '.')
            self.git(repo, 'commit', '-m', 'declare skill owner')
            self.git(repo, 'push', 'origin', 'main')
            worker = self.worker(repo, 'route-worker')
            name, reference = 'skills/kept/SKILL.md', 'skills/kept/references/required.md'
            old = subprocess.check_output(['git', '-C', str(worker), 'show', 'HEAD:' + name])
            (worker / name).write_bytes(old + b'\nFor release, read [required protocol](references/required.md).\n')
            ref = worker / reference
            ref.parent.mkdir()
            ref.write_bytes(b'Required release protocol.\n')
            record = {'owner': 'skills/kept', 'basis': 'mechanical-maintenance',
                'deviation': 'Move a required release protocol into conditional detail.', 'evidence': 'Fixture source route.',
                'baseline_sufficient': False, 'why_instruction': 'Keep requirement at its owner.', 'alternative': 'Always load every mode.',
                'artifacts': {name: {'before_sha256': hashlib.sha256(old).hexdigest(), 'after_sha256': hashlib.sha256((worker / name).read_bytes()).hexdigest()},
                              reference: {'before_sha256': 'absent', 'after_sha256': hashlib.sha256(ref.read_bytes()).hexdigest()}}}
            receipt_name = 'evals/results/route-test.json'
            receipt = worker / receipt_name
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({'instruction_changes': [record]}))
            self.git(worker, 'add', '.')
            self.git(worker, 'commit', '-m', 'move required procedure')
            includes = [name, reference, receipt_name]
            result = adapter.ready_plan(worker, self.git(worker, 'rev-parse', 'HEAD'), include=includes)
            self.assertEqual('review-required', result['result'], result)
            record['loading_review'] = {'entrypoint_reason': 'Common trigger; release detail is conditional.',
                'checks': 'Release reaches required reference; ordinary repair stays at entrypoint. Static checks only.',
                'obligations': [{'obligation': 'Release protocol', 'applies_when': 'Release', 'required': True,
                    'before': [name], 'after': [name, reference], 'disposition': 'preserved',
                    'load_when': 'Before release', 'reason': 'Only release uses this procedure.'}]}
            for mutation in (None, {}, {'required': 'true'}, {'after': ['skills/kept/references/missing.md']},
                             {'after': ['../escape.md']}, {'before': [reference]}, {'applies_when': ''}):
                changed = json.loads(json.dumps(record))
                if mutation == {}:
                    changed['loading_review']['obligations'] = []
                elif mutation is not None:
                    changed['loading_review']['obligations'][0].update(mutation)
                ready = self.commit(worker, receipt_name, json.dumps({'instruction_changes': [changed]}))
                result = adapter.ready_plan(worker, ready, include=includes)
                self.assertEqual('ready' if mutation is None else 'review-required', result['result'], (mutation, result))
            # Separate necessity rows must not hide a later restructuring flag.
            first, second = json.loads(json.dumps(record)), json.loads(json.dumps(record))
            first['artifacts'] = {name: record['artifacts'][name]}
            second['artifacts'] = {reference: record['artifacts'][reference]}
            first.pop('loading_review')
            second.pop('loading_review')
            second['restructured'] = True
            ready = self.commit(worker, receipt_name, json.dumps({'instruction_changes': [first, second]}))
            self.assertEqual('review-required', adapter.ready_plan(worker, ready, include=includes)['result'])
            second['loading_review'] = record['loading_review']
            ready = self.commit(worker, receipt_name, json.dumps({'instruction_changes': [first, second]}))
            self.assertEqual('ready', adapter.ready_plan(worker, ready, include=includes)['result'])
            # An existing but unlinked file cannot count as loaded preservation.
            orphan = worker / 'skills/kept/references/orphan.md'
            orphan.write_bytes(b'Unreachable protocol.\n')
            record['artifacts']['skills/kept/references/orphan.md'] = {
                'before_sha256': 'absent', 'after_sha256': hashlib.sha256(orphan.read_bytes()).hexdigest()}
            record['loading_review']['obligations'][0]['after'] = [name, reference, 'skills/kept/references/orphan.md']
            receipt.write_text(json.dumps({'instruction_changes': [record]}))
            self.git(worker, 'add', '.')
            self.git(worker, 'commit', '-m', 'unreachable destination')
            result = adapter.ready_plan(worker, self.git(worker, 'rev-parse', 'HEAD'), include=includes + ['skills/kept/references/orphan.md'])
            self.assertEqual('review-required', result['result'], result)
            self.assertIn('reachable', result['reason'])

    def test_omp_generated_overlay_requires_its_canonical_source(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
        import instruction_changes
        import sync_git
        with tempfile.TemporaryDirectory() as temporary:
            repo, _, _ = self.setup_instructions(Path(temporary))
            name = 'recovery/current/hosts/omp/AGENTS.md'
            target = repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('An unowned replacement for shared preferences.\n')
            with self.assertRaisesRegex(sync_git.SyncBlocked, 'generated instruction edit requires its canonical source'):
                instruction_changes.check(repo, repo, 'HEAD', [name])

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
