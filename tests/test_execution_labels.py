"""Real producer/consumer policy checks with only inference substituted."""
import contextlib
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import test_evaluator_core as core
import test_evaluation_evidence as evidence


class ExecutionLabelTests(unittest.TestCase):
    def test_unsupported_labels_rejected_before_candidate_freeze(self):
        for args in (['--prompt-assembly', 'natural-discovery'],
                     ['--context-policy', 'resumed-conversation'],
                     ['--prompt-assembly', 'isolated-anonymous-artifact-v3']):
            with self.subTest(args=args), tempfile.TemporaryDirectory() as temp:
                with mock.patch.object(core.evaluator, 'freeze_candidate', side_effect=AssertionError('reached candidate freeze')) as freeze:
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                        core.EvaluatorCoreTests().run_v2_main(Path(temp), extra_args=args)
                self.assertEqual(error.exception.code, 2)
                freeze.assert_not_called()
                self.assertFalse((Path(temp)/'report.json').exists())

    def test_actual_inline_study_still_reaches_production_report(self):
        with tempfile.TemporaryDirectory() as temp:
            code, report, *_ = core.EvaluatorCoreTests().run_v2_main(Path(temp))
            self.assertEqual(report['status'], 'complete')
            self.assertEqual(report['effective_stack']['prompt_assembly'], 'isolated-explicit-artifact-v2')
            self.assertEqual(report['effective_stack']['context_policy'], 'fresh-session-per-output')

    def test_consumer_rejects_relabeling_a_real_producer_report(self):
        for version in (2, 3):
            with tempfile.TemporaryDirectory() as temp:
                data = evidence.make_evaluation(Path(temp), version=version)
                self.assertEqual(evidence.validate_report(data['report'], data['suite'])['errors'], [])
                for key, value in (('prompt_assembly', 'natural-discovery'), ('context_policy', 'resumed-conversation')):
                    report = copy.deepcopy(data['report'])
                    report['effective_stack'][key] = value
                    checked = evidence.validate_report(report, data['suite'])
                    with self.subTest(version=version, key=key):
                        self.assertTrue(checked['errors'])
                        self.assertTrue(any(key in error for error in checked['errors']), checked['errors'])


if __name__ == '__main__': unittest.main()
