"""Public CLI keeps ready source publication separate from native maintenance."""
import contextlib
import io
import unittest
from unittest.mock import patch

import test_reconcile as fixtures
import worktree_sync


class WorktreeCliTests(unittest.TestCase):
    def setUp(self):
        self.reconcile = fixtures.load_tool('reconcile')

    def rejected(self, arguments):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as failure:
                self.reconcile.main(arguments)
        self.assertEqual(2, failure.exception.code)

    def test_scoped_source_requires_ready_or_explicit_legacy(self):
        with patch.object(self.reconcile, 'complete_sync') as deployment:
            self.rejected(['sync', '--include', 'README.md', '--no-capture-recovery'])
        deployment.assert_not_called()

    def test_ready_plan_dispatches_exact_commit_and_scope(self):
        with patch.object(worktree_sync, 'ready_plan', return_value={'result': 'ready'}) as operation:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, self.reconcile.main(['plan', '--ready', 'abc123', '--adopt', 'instruction-authoring', '--include', 'surfaces/core.md']))
        self.assertEqual('abc123', operation.call_args.args[1])
        self.assertEqual(['instruction-authoring'], operation.call_args.kwargs['adopt'])
        self.assertEqual(['surfaces/core.md'], operation.call_args.kwargs['include'])

    def test_ready_cannot_mix_native_or_broad_actions(self):
        with patch.object(worktree_sync, 'ready_sync') as operation:
            for arguments in (['--capture-artifact', 'codex:global-instructions'],
                              ['--reconcile-defaults'], ['--full'],
                              ['--capture-recovery'], ['--shared-checkout']):
                self.rejected(['sync', '--ready', 'abc123', '--include', 'README.md', *arguments])
        operation.assert_not_called()

    def test_explicit_legacy_and_native_capture_remain_available(self):
        with patch.object(self.reconcile, 'complete_sync', return_value={'result': 'synced'}) as operation:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, self.reconcile.main(['sync', '--shared-checkout', '--include', 'README.md', '--no-capture-recovery']))
                self.assertEqual(0, self.reconcile.main(['sync', '--capture-artifact', 'codex:global-instructions']))
        self.assertEqual(2, operation.call_count)


if __name__ == '__main__':
    unittest.main()
