"""Synthetic accounting/policy regressions, never live behavioral evidence."""
from fixture_workspace import configure
configure()
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import evaluation_measurement as m
from evaluation_evidence import outcome_efficiency, instruction_improvement, validate_report
import test_evaluation_evidence as fixtures
from test_evaluation_evidence import make_evaluation, attribute_fixture_judges


def seal(row):
    row['record_sha256'] = m.digest({k: v for k, v in row.items() if k != 'record_sha256'})
    return row


def record(total=45, arm='baseline'):
    context = {'host': 'hermes', 'case_id': 'task', 'arm': arm, 'role': arm,
               'trial': 0, 'attempt': 1, 'attempt_history_complete': True,
               'evidence_sha256': '9'*64, 'prerequisites_sha256': '8'*64,
               'host_version': 'synthetic-v1', 'task_sha256': '1'*64,
               'verifier_sha256': '2'*64, 'harness_sha256': '3'*64,
               'instruction_sha256': ('4' if arm == 'baseline' else '6')*64,
               'runtime_lane': 'synthetic-fixture', 'tool_policy': 'bounded',
               'context_policy': 'fresh',
               'route': {'model': 'fixture', 'provider': 'fixture', 'reasoning': 'medium'}}
    row = m.observation({'ok': True, 'execution_ok': True, 'operational_ok': True,
                         'output': 'answer', 'agent_observed_route': context['route']},
                        context, {'passed': True})
    # Deliberate synthetic certificate to test policy only. No native collector
    # or actual harness is claimed by these fixtures.
    row['usage'].update(source='synthetic-contract', token_semantics='synthetic-total',
                        provider_physical_attempt_count=1)
    row['usage']['tokens']['total_tokens'] = total
    row['usage']['coverage']['whole_system_complete'] = True
    row['harness']['effective_initial_tool_schema_sha256'] = '5'*64
    return seal(row)


class OutcomeEfficiencyTests(unittest.TestCase):
    def check(self, before=None, after=None):
        return outcome_efficiency(before or [record()], after or [record(35, 'candidate')])

    def test_oracle_preflight_is_recomputed_and_missing_new_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            item = make_evaluation(Path(temp))
            self.assertEqual(validate_report(item['report'], item['suite'])['errors'], [])
            for alteration in ('missing', 'forged'):
                report=copy.deepcopy(item['report'])
                if alteration == 'missing': report.pop('oracle_preflight')
                else: report['oracle_preflight']['controls'][0]['deterministic_pass']=False
                self.assertIn('oracle preflight receipt mismatch', validate_report(report,item['suite'])['errors'])

    def test_equal_quality_equal_or_lower_tokens_eligible_without_live_proof(self):
        for total in (35, 45):
            result = self.check(after=[record(total, 'candidate')])
            self.assertTrue(result['eligible'], result)
            self.assertFalse(result['execution_authenticated'])
            self.assertFalse(result['behavioral_proof'])

    def test_worse_quality_lower_tokens_rejected(self):
        after = record(10, 'candidate'); after['outcome']['quality_passed'] = False
        self.assertFalse(self.check(after=[seal(after)])['eligible'])

    def test_quality_pass_cannot_trade_for_more_tokens(self):
        self.assertFalse(self.check(after=[record(46, 'candidate')])['eligible'])

    def test_missing_usage_route_harness_and_attribution_rejected(self):
        for field in ('usage', 'route', 'harness', 'attribution', 'source'):
            after = record(10, 'candidate')
            if field == 'usage': after['usage']['coverage']['whole_system_complete'] = False
            if field == 'route': after['route']['observed']['model'] = 'other'
            if field == 'harness': after['revisions']['harness_sha256'] = '7'*64
            if field == 'attribution': after['trial_validity']['status'] = 'unresolved'
            if field == 'source': after['provenance']['evidence_sha256'] = None
            with self.subTest(field=field):
                self.assertFalse(self.check(after=[seal(after)])['eligible'])

    def test_retry_charged_once_and_conflicting_duplicate_rejected(self):
        retry = record(30, 'candidate'); retry['identity']['attempt'] = 0
        retry['outcome']['execution_ok'] = False; seal(retry)
        after = record(20, 'candidate')
        result = self.check(after=[retry, after, copy.deepcopy(after)])
        # Duplicate task records are ambiguous, never extra evidence.
        self.assertFalse(result['eligible'])
        result = self.check(after=[retry, after])
        self.assertFalse(result['eligible'])  # 30 + 20 > baseline 45

    def test_support_charged_once_and_conflicting_duplicate_rejected(self):
        after = record(20, 'candidate'); support = copy.deepcopy(after)
        support['identity'].update(arm='judge', role='judge-0')
        support['workflow_accounting'] = {'target_arm': 'candidate', 'call_id': 'judge'}
        seal(support)
        result = self.check(after=[after, support, copy.deepcopy(support)])
        self.assertTrue(result['eligible'], result)  # 20 + 20, not 60
        conflict = copy.deepcopy(support); conflict['usage']['tokens']['total_tokens'] = 21
        self.assertFalse(self.check(after=[after, support, seal(conflict)])['eligible'])

    def test_shared_judge_attribution_is_required_even_if_accounting_claims_success(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = make_evaluation(Path(temp), outcome='tie')
            report, suite = fixture['report'], fixture['suite']
            with mock.patch('evaluation_evidence.outcome_efficiency', return_value={'errors': []}):
                errors = instruction_improvement(report, suite,
                    suite_sha256=report['artifacts']['suite_sha256'],
                    harness_sha256=report['artifacts']['harness_sha256'],
                    route={'host': report['agent'], **{k: report['effective_stack'][k]
                           for k in ('model', 'provider', 'reasoning')}})
            self.assertIn('shared judge needs explicit target arm; no guessed allocation', errors)

    def test_ledger_only_accounting_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = make_evaluation(Path(temp), outcome='tie')
            report, suite = fixture['report'], fixture['suite']
            attribute_fixture_judges(report)
            self.assertEqual(validate_report(report, suite)['errors'], [])
            judge = next(e for e in report['attempt_ledger'] if str(e.get('role', '')).startswith('judge'))
            judge['workflow_accounting']['target_arm'] = 'baseline'
            self.assertIn('attempt ledger contradicts paired result history', validate_report(report, suite)['errors'])

    def test_legacy_tie_and_win_use_efficiency_policy_after_real_quality_recompute(self):
        for outcome, total, eligible in (('tie', 35, True), ('tie', 45, False),
                                         ('win', 35, True), ('win', 45, True), ('win', 50, False)):
            with self.subTest(outcome=outcome, total=total), tempfile.TemporaryDirectory() as temp:
                fixture = make_evaluation(Path(temp), outcome=outcome)
                report, suite = fixture['report'], fixture['suite']
                attribute_fixture_judges(report)
                # Isolate accounting from fake transport; raw receipts without
                # complete usage are separately rejected in eligibility tests.
                rows = []
                for result in report['results']:
                    for side, tokens in (('baseline', 45), ('candidate', total)):
                        row = record(tokens, side)
                        row['identity'].update(case_id=result['id'], trial=result['trial'])
                        rows.append(seal(row))
                with mock.patch.object(m, 'inline_records', return_value=rows):
                    errors = instruction_improvement(report, suite,
                        suite_sha256=report['artifacts']['suite_sha256'],
                        harness_sha256=report['artifacts']['harness_sha256'],
                        route={'host': report['agent'], **{k: report['effective_stack'][k]
                               for k in ('model', 'provider', 'reasoning')}})
                self.assertEqual(not errors, eligible, errors)


class SequentialCoverageTests(unittest.TestCase):
    """Real report/stopping recomputation; only usage is a synthetic projection."""
    def setUp(self):
        self.enterContext(mock.patch('subprocess.Popen', side_effect=AssertionError('no child/model calls')))

    def fixture(self, minimum=1, maximum=2, version=2):
        original_loader = fixtures.load_evaluator
        def loader():
            evaluator = original_loader()
            main = evaluator.main
            def bounded_main():
                sys.argv[sys.argv.index('--min-trials') + 1] = str(minimum)
                sys.argv[sys.argv.index('--max-trials') + 1] = str(maximum)
                return main()
            evaluator.main = bounded_main
            return evaluator
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        with mock.patch.object(fixtures, 'load_evaluator', side_effect=loader):
            fixture = fixtures.make_evaluation(root, version=version, outcome='tie')
        report, suite = fixture['report'], fixture['suite']
        attribute_fixture_judges(report)
        rows = []
        for result in report['results']:
            for side, total in (('baseline', 45), ('candidate', 35)):
                row = record(total, side)
                row['identity'].update(case_id=result['id'], trial=result['trial'])
                rows.append(seal(row))
        return report, suite, rows

    def errors(self, report, suite, rows):
        with mock.patch.object(m, 'inline_records', return_value=rows):
            return instruction_improvement(report, suite,
                suite_sha256=report['artifacts']['suite_sha256'],
                harness_sha256=report['artifacts']['harness_sha256'],
                route={'host': report['agent'], **{key: report['effective_stack'][key]
                       for key in ('model', 'provider', 'reasoning')}})

    def test_complete_sequential_tie_above_minimum_is_eligible(self):
        for maximum in (2, 3):
            with self.subTest(maximum=maximum):
                # max=3 stops at two because the remaining declared run budget
                # cannot reserve another complete trial; the validator checks it.
                report, suite, rows = self.fixture(maximum=maximum)
                checked = validate_report(report, suite)
                self.assertEqual(checked['errors'], [])
                self.assertEqual(len(checked['computed_summary']['trial_scores']), 2)
                self.assertEqual(report['decision_rule']['min_trials'], 1)
                self.assertEqual(report['decision']['decision'], 'inconclusive')
                self.assertEqual(self.errors(report, suite, rows), [])

    def test_inconclusive_equal_cost_is_not_improvement_or_retirement(self):
        report, suite, rows = self.fixture()
        for row in rows:
            row['usage']['tokens']['total_tokens'] = 45
            seal(row)
        before = copy.deepcopy(report)
        errors = self.errors(report, suite, rows)
        self.assertTrue(any('noninferiority is not improvement' in e for e in errors), errors)
        self.assertEqual(report, before)
        self.assertEqual(report['decision']['decision'], 'inconclusive')

    def test_unknown_accounting_cannot_supply_a_token_gain(self):
        report, suite, rows = self.fixture()
        for row in rows:
            if row['identity']['arm'] == 'candidate':
                row['usage']['tokens']['total_tokens'] = None
                seal(row)
        errors = self.errors(report, suite, rows)
        self.assertTrue(any('noninferiority is not improvement' in e for e in errors), errors)
        self.assertTrue(any('usage' in e or 'tokens' in e for e in errors), errors)

    def test_below_minimum_complete_trials_rejected(self):
        report, suite, rows = self.fixture(minimum=1, maximum=1)
        self.assertEqual(validate_report(report, suite)['errors'], [])
        report['decision_rule'].update(min_trials=2, max_trials=2)
        self.assertIn('no sufficient full-suite outcome comparison', self.errors(report, suite, rows))

    def test_extra_trials_after_declared_terminal_stop_rejected(self):
        report, suite, rows = self.fixture()
        report['decision_rule']['max_trials'] = 1
        checked = validate_report(report, suite)
        self.assertIn('observations continue after a terminal decision', checked['errors'])
        self.assertTrue(self.errors(report, suite, rows))

    def test_mismatched_projected_arms_or_trial_ids_rejected(self):
        report, suite, rows = self.fixture()
        for field, value in (('arm', 'baseline'), ('trial', 7)):
            changed = copy.deepcopy(rows)
            row = next(row for row in changed if row['identity']['arm'] == 'candidate')
            row['identity'][field] = value
            seal(row)
            with self.subTest(field=field):
                self.assertTrue(self.errors(report, suite, changed))
        changed_report = copy.deepcopy(report)
        changed_report['results'][-1]['trial'] = 7
        self.assertTrue(self.errors(changed_report, suite, rows))

    def test_incomplete_case_coverage_and_required_stability_trials_rejected(self):
        for version, missing in ((2, 1), (3, 4)):
            report, suite, rows = self.fixture(minimum=2, maximum=2, version=version)
            report['results'] = report['results'][:-missing]
            with self.subTest(version=version):
                self.assertIn('no sufficient full-suite outcome comparison', self.errors(report, suite, rows))


if __name__ == '__main__':
    unittest.main()
