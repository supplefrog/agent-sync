"""Source-bound dependency coverage at the existing instruction publication seam."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import instruction_changes as changes
import sync_git


class DependencyReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.put('tools/example.py', 'old implementation\n')
        self.put('skills/example/SKILL.md', '# Example\nRead [tool](../../tools/example.py).\n')
        self.put('docs/router.md', 'Read [skill](../skills/example/SKILL.md).\n')
        for name in changes.CONTRACTS:
            self.put(name, 'Existing user intention.\n')
        self.git('init'); self.git('config', 'user.email', 'test@example.invalid'); self.git('config', 'user.name', 'Test')
        self.git('add', '.'); self.git('commit', '-m', 'baseline')
        self.put('tools/example.py', 'fixed implementation\n')
        self.paths = ['tools/example.py', 'evals/results/dependencies.json']

    def put(self, name, text):
        p = self.repo / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding='utf-8', newline='\n')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.DEVNULL)

    def record(self):
        _, _, affected = changes.reconciliation_scope(self.repo, self.repo, 'HEAD', self.paths)
        required = affected | changes.CONTRACTS
        row = {'artifacts': {}, 'obligations': [], 'requirement_change': False,
               'requirement_reason': 'Implementation repair preserves existing user intent.',
               'authority': 'Existing contract; no new preference inferred.', 'checks': 'Affected regression and nearby valid case.',
               'outcome_review': {'expected': 'Tool keeps its supported invocation.', 'observed': 'Local regression cases pass.', 'evidence': 'Fixture invocation and source coverage tests.', 'limitations': 'No model behavior measured.'}}
        for name in required:
            old = changes._before(self.repo, 'HEAD', name)
            new = (self.repo / name).read_bytes() if (self.repo / name).is_file() else None
            row['artifacts'][name] = {'before_sha256': changes._hash(old), 'after_sha256': changes._hash(new)}
            if name != 'tools/example.py':
                row['obligations'].append({'path': name, 'disposition': 'removed' if new is None else ('unchanged' if old == new else 'updated'),
                                          'reason': 'The supported invocation and user intent remain valid after this implementation repair.'})
        return row

    def run_check(self, row):
        self.put(self.paths[1], json.dumps({'change_reconciliation': [row]}))
        return changes._dependency_review(self.repo, self.repo, 'HEAD', self.paths, {})

    def test_transitive_guidance_and_unchanged_intent_are_bound(self):
        row = self.record()
        self.assertIn('docs/router.md', row['artifacts'])
        self.assertEqual(len(self.run_check(row)), 5)

    def test_missing_stale_or_undisposed_guidance_blocks(self):
        for mutation in ('missing', 'stale', 'disposition'):
            row = self.record()
            if mutation == 'missing': del row['artifacts']['skills/example/SKILL.md']
            if mutation == 'stale': row['artifacts']['skills/example/SKILL.md']['after_sha256'] = '0' * 64
            if mutation == 'disposition': row['obligations'] = []
            with self.subTest(mutation=mutation), self.assertRaises(sync_git.SyncBlocked): self.run_check(row)

    def test_removed_baseline_link_cannot_hide_consumer(self):
        self.put('skills/example/SKILL.md', '# Example\nNo link now.\n')
        row = self.record()
        self.assertIn('skills/example/SKILL.md', row['artifacts'])
        with self.assertRaisesRegex(sync_git.SyncBlocked, 'selected'): self.run_check(row)
        self.paths.append('skills/example/SKILL.md')
        self.run_check(self.record())

    def test_user_intent_change_requires_both_existing_contract_and_status(self):
        row = self.record(); row['requirement_change'] = True
        with self.assertRaisesRegex(sync_git.SyncBlocked, 'requirements and status'): self.run_check(row)
        for name in changes.CONTRACTS:
            self.put(name, 'User explicitly changed the required behavior.\n'); self.paths.append(name)
        row = self.record(); row['requirement_change'] = True; row['authority'] = 'Explicit user correction in this task.'
        self.run_check(row)

    def test_framework_requires_affected_owner_review(self):
        name = 'skills/instruction-authoring/SKILL.md'
        self.put(name, '# Authoring\nChanged conditional loading framework.\n'); self.paths.append(name)
        row = self.record()
        with self.assertRaisesRegex(sync_git.SyncBlocked, 'affected-owner'): self.run_check(row)
        row['framework_review'] = {'affected': ['skills/example/SKILL.md'], 'selection_reason': 'Tool invocation consumer.',
                                  'unaffected_reason': 'No new unrelated task method.', 'checks': 'Required load point inspected.'}
        self.run_check(row)

    def test_outcome_comparison_is_required(self):
        row = self.record(); del row['outcome_review']
        with self.assertRaisesRegex(sync_git.SyncBlocked, 'outcome evidence'): self.run_check(row)

    def test_unrelated_test_change_needs_no_record(self):
        self.put('tests/test_other.py', 'pass\n')
        self.assertEqual(changes._dependency_review(self.repo, self.repo, 'HEAD', ['tests/test_other.py'], {}), [])

    def test_skill_change_discovers_reverse_contract_or_guidance(self):
        self.put('skills/example/SKILL.md', '# Example\nChanged method.\n')
        self.paths.append('skills/example/SKILL.md')
        self.assertIn('docs/router.md', self.record()['artifacts'])

    def test_contract_change_identifies_its_skill_and_reverse_guidance(self):
        self.put('contracts/domain.json', '{"owner": "skills/example/SKILL.md"}')
        self.paths.append('contracts/domain.json')
        self.assertIn('skills/example/SKILL.md', self.record()['artifacts'])
        self.assertIn('docs/router.md', self.record()['artifacts'])

    def test_existing_publication_seam_blocks_missing_dependency_review(self):
        self.put('contracts/instruction-surfaces.json', '{"schema_version": 2, "surfaces": []}')
        with self.assertRaisesRegex(sync_git.SyncBlocked, 'bound dependency'):
            changes.check(self.repo, self.repo, 'HEAD', self.paths)
        self.run_check(self.record())
        self.assertTrue(changes.check(self.repo, self.repo, 'HEAD', self.paths))

    def test_deleting_intent_contract_cannot_disable_review(self):
        for name in changes.CONTRACTS:
            (self.repo / name).unlink()
        with self.assertRaisesRegex(sync_git.SyncBlocked, 'cannot be removed'):
            changes._dependency_review(self.repo, self.repo, 'HEAD', self.paths, {})
