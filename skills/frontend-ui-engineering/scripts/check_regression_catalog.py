"""Actual-catalog synthetic validator integration tests; no real UI truth is tested.

Writes a result JSON only when --output is supplied. Evidence metadata is mocked in memory:
synthetic-image.png is not an actual screenshot, and no capture is claimed.
Run: python -B check_regression_catalog.py [--skill PATH] [--output PATH]
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import patch


DEFAULT_SKILL = Path(__file__).resolve().parent.parent
SOURCE = 'a' * 64
LABEL = 'SYNTHETIC VALIDATOR TEST ONLY; mocked evidence metadata; no UI or image truth'


class FixturePath:
    """In-memory, deterministic subset of Path used for evidence availability only."""
    metadata = {'synthetic-image.png': 12, 'synthetic-source.txt': 12,
                'empty.png': 0}

    def __init__(self, value):
        self.path = value.path if isinstance(value, FixturePath) else PurePosixPath(str(value))

    def __truediv__(self, other):
        return FixturePath(self.path / FixturePath(other).path)

    def resolve(self):
        return self

    def is_absolute(self):
        return self.path.is_absolute()

    @property
    def parts(self):
        return self.path.parts

    @property
    def suffix(self):
        return self.path.suffix

    def is_relative_to(self, other):
        return self.path.is_relative_to(other.path)

    def is_file(self):
        return self.path.name in self.metadata

    def stat(self):
        return SimpleNamespace(st_size=self.metadata[self.path.name])


def independent_disposition(row, scope, features, selected):
    # Independent implementation of the documented applicability table.
    kind = row['class']
    if kind in ('tentative', 'project'):
        return kind
    if scope == 'workflow':
        return 'required'
    if kind == 'capability':
        return 'required' if row['id'] in selected else 'unselected'
    return ('required' if 'common' in row['features'] or
            any(tag in features for tag in row['features']) else 'not_applicable')


def fixture(catalog, scope='workflow', features=(), selected=()):
    contract = {'schema_version': 1, 'scope': scope, 'source_sha256': SOURCE,
                'features': list(features), 'selected': list(selected), 'requirements': []}
    observations = {'source_sha256': SOURCE, 'results': []}
    for row in catalog['requirements']:
        disposition = independent_disposition(row, scope, features, selected)
        entry = {'id': row['id'], 'disposition': disposition, 'cases': []}
        if disposition != 'required':
            entry['reason'] = LABEL + '; documented ' + disposition
        else:
            for index, suffix in enumerate(row['cases']):
                method = row['methods'][index % len(row['methods'])]
                context = {'viewport': {'width': 1280, 'height': 900},
                           'modality': 'synthetic-' + method,
                           'state': row['id'] + ':' + suffix,
                           'fixture': LABEL}
                entry['cases'].append({'id': suffix, 'method': method, 'context': context})
                observations['results'].append({
                    'requirement_id': row['id'], 'case_id': suffix,
                    'source_sha256': SOURCE, 'method': method, 'context': deepcopy(context),
                    'status': 'pass', 'evidence': ['synthetic-image.png' if method == 'rendered'
                                                 else 'synthetic-source.txt'], 'finding': LABEL})
        contract['requirements'].append(entry)
    return contract, observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill', type=Path, default=DEFAULT_SKILL)
    parser.add_argument('--output', type=Path,
                        default=None)
    args = parser.parse_args()
    skill = args.skill
    catalog_path = skill / 'references/regression-catalog.json'
    validator_path = skill / 'scripts/frontend_coverage.py'
    catalog_bytes = catalog_path.read_bytes()
    catalog = json.loads(catalog_bytes.decode('utf-8-sig'))
    validator_bytes = validator_path.read_bytes()
    spec = importlib.util.spec_from_file_location('actual_frontend_coverage', validator_path)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    tests = []

    def record(name, passed, **details):
        tests.append({'name': name, 'passed': bool(passed), **details})

    def check(name, contract, observations, ready=False, previous=None):
        with patch.object(validator, 'Path', FixturePath):
            report = validator.validate(catalog, contract, observations, '/synthetic-root', previous)
        record(name, report['ready'] is ready, expected_ready=ready, actual_ready=report['ready'],
               status=report['status'], blocking_checks=[c for c in report['checks']
                 + report['measurement_checks'] if c['status'] != 'pass'][:4])
        return report

    rows = catalog['requirements']
    record('actual-catalog-row-count', len(rows) == 75, actual=len(rows), expected=75)
    record('actual-catalog-unique-ids', len({r['id'] for r in rows}) == len(rows))
    retained_ids = {f'{prefix}{index:02d}' for prefix, last in
                    (('P', 12), ('V', 19), ('I', 22), ('R', 18), ('A', 4))
                    for index in range(1, last + 1)}
    record('retained-feedback-identities', {r['id'] for r in rows} == retained_ids)
    for row in rows:
        record('catalog-method-case-capacity:' + row['id'], len(row['methods']) <= len(row['cases']))
    base, observed = fixture(catalog)
    check('full-workflow-synthetic-observations', base, observed, ready=True)
    required = [e for e in base['requirements'] if e['disposition'] == 'required']

    # All catalog rows must be classified, including scoped and tentative rows.
    for index, row in enumerate(rows):
        contract = deepcopy(base)
        del contract['requirements'][index]
        check('omit-classification:' + row['id'], contract, observed)
        planned = validator.plan(catalog, 'workflow', SOURCE, [], [])
        entry = next(e for e in planned['contract']['requirements'] if e['id'] == row['id'])
        record('workflow-plan-classification:' + row['id'],
               entry['disposition'] == independent_disposition(row, 'workflow', [], []))
    record('unmeasured-plan-never-ready', planned['ready'] is False and planned['status'] == 'incomplete')

    # Every applicable suffix independently blocks readiness on omission/staleness.
    for entry in required:
        identifier = entry['id']
        for case in entry['cases']:
            suffix = case['id']
            tag = identifier + ':' + suffix
            ci = next(i for i, e in enumerate(base['requirements']) if e['id'] == identifier)
            ki = next(i for i, c in enumerate(entry['cases']) if c['id'] == suffix)
            oi = next(i for i, o in enumerate(observed['results'])
                      if (o['requirement_id'], o['case_id']) == (identifier, suffix))
            contract = deepcopy(base)
            del contract['requirements'][ci]['cases'][ki]
            check('omit-case:' + tag, contract, observed)
            observation = deepcopy(observed)
            del observation['results'][oi]
            check('omit-result:' + tag, base, observation)
            for field, value in (('source_sha256', 'b' * 64), ('method', 'human' if case['method'] != 'human' else 'source'),
                                 ('status', 'fail'), ('finding', ''), ('evidence', []),
                                 ('evidence', ['missing.png']), ('evidence', ['empty.png'])):
                observation = deepcopy(observed)
                observation['results'][oi][field] = value
                check('mutate-result-' + field + '-' + str(value) + ':' + tag, base, observation)
            for field, value in (('viewport', '320x900'), ('modality', 'different-input'),
                                 ('state', 'different-state'), ('fixture', 'different-fixture')):
                observation = deepcopy(observed)
                observation['results'][oi]['context'][field] = value
                check('mutate-result-context-' + field + ':' + tag, base, observation)
            if case['method'] == 'rendered':
                observation = deepcopy(observed)
                observation['results'][oi]['evidence'] = ['synthetic-source.txt']
                check('absent-rendered-image:' + tag, base, observation)
            # Matching new observations cannot silently rewrite inherited context/method.
            for field in ('context', 'method'):
                contract, observation = deepcopy(base), deepcopy(observed)
                value = (dict(case['context'], state='changed-inherited-state') if field == 'context'
                         else ('human' if case['method'] != 'human' else 'source'))
                contract['requirements'][ci]['cases'][ki][field] = value
                observation['results'][oi][field] = deepcopy(value)
                check('mutate-inherited-' + field + ':' + tag, contract, observation, previous=base)

    # Optional wants may remain unselected even if the corresponding feature tag exists.
    capabilities = [r['id'] for r in rows if r['class'] == 'capability']
    all_features = sorted({f for r in rows for f in r['features']})
    for features, label in (([], 'empty-product'), (all_features, 'all-features-unselected'),
                            (['reader', 'disclosure', 'contents-disclosure'], 'ordinary-reader-disclosure')):
        contract, observation = fixture(catalog, 'product', features)
        check(label + ':legitimate-product-scope', contract, observation, ready=True)
        for row, entry in zip(rows, contract['requirements']):
            record(label + ':classification:' + row['id'],
                   entry['disposition'] == validator.disposition(row, 'product', features, []))
        for identifier in capabilities:
            entry = next(e for e in contract['requirements'] if e['id'] == identifier)
            record(label + ':optional-absence:' + identifier,
                   entry['disposition'] == 'unselected' and not entry['cases'])
        if label == 'ordinary-reader-disclosure':
            for identifier in ('I04', 'I12', 'I13'):
                entry = next(e for e in contract['requirements'] if e['id'] == identifier)
                record(label + ':mechanism-not-forced:' + identifier,
                       entry['disposition'] == 'not_applicable' and not entry['cases'])
            for identifier in ('I01', 'I02', 'I03'):
                entry = next(e for e in contract['requirements'] if e['id'] == identifier)
                record(label + ':ordinary-mechanism-covered:' + identifier, entry['disposition'] == 'required')

    # Each selected want binds every case independently; previous wants cannot silently disappear.
    for identifier in capabilities:
        contract, observation = fixture(catalog, 'product', ['reader'], [identifier])
        check('selected-capability:' + identifier, contract, observation, ready=True)
        entry = next(e for e in contract['requirements'] if e['id'] == identifier)
        for case in entry['cases']:
            mutated = deepcopy(observation)
            mutated['results'] = [r for r in mutated['results']
                                 if (r['requirement_id'], r['case_id']) != (identifier, case['id'])]
            check('selected-capability-omit-result:' + identifier + ':' + case['id'], contract, mutated)
        dropped, remaining = fixture(catalog, 'product', ['reader'])
        check('drop-inherited-selected-capability:' + identifier, dropped, remaining, previous=contract)

    # Mechanism-specific tags activate exactly their conditional cases.
    for feature, identifier in (('combined-slide-zoom', 'I12'), ('masked-gallery', 'I13'),
                                ('native-image-generation', 'R07'), ('selector', 'V14')):
        contract, observation = fixture(catalog, 'product', ['reader', 'disclosure', feature])
        check('mechanism-enabled:' + feature, contract, observation, ready=True)
        entry = next(e for e in contract['requirements'] if e['id'] == identifier)
        record('mechanism-required:' + feature, entry['disposition'] == 'required')
        contract['requirements'] = [e for e in contract['requirements'] if e['id'] != identifier]
        check('mechanism-omit-classification:' + feature, contract, observation)

    # Legacy measurements remain supplementary and cannot replace missing rendered cases.
    contract, observation = deepcopy(base), deepcopy(observed)
    first = next(e for e in contract['requirements'] if e['disposition'] == 'required')['cases'][0]
    first['measurement_ids'] = ['synthetic-check']
    observation['measurements'] = {'status': 'pass', 'checks': [{'id': 'synthetic-check', 'status': 'pass'}]}
    check('linked-measurement-pass', contract, observation, ready=True)
    for mutation in ('omit-report', 'omit-check', 'nonapplicable-check', 'failed-check'):
        changed = deepcopy(observation)
        if mutation == 'omit-report':
            del changed['measurements']
        elif mutation == 'omit-check':
            changed['measurements']['checks'] = []
        elif mutation == 'nonapplicable-check':
            changed['measurements']['checks'][0]['evidence'] = {'applicable': False}
        else:
            changed['measurements']['status'] = 'fail'
            changed['measurements']['checks'][0]['status'] = 'fail'
        check('linked-measurement-' + mutation, contract, changed)

    report = {'evidence_level': LABEL, 'catalog_path': str(catalog_path),
              'catalog_sha256': hashlib.sha256(catalog_bytes).hexdigest(),
              'validator_path': str(validator_path),
              'validator_sha256': hashlib.sha256(validator_bytes).hexdigest(),
              'catalog_rows': len(rows), 'classes': dict(Counter(r['class'] for r in rows)),
              'workflow_required_rows': len(required),
              'workflow_required_cases': sum(len(e['cases']) for e in required),
              'tests_run': len(tests), 'passed': sum(t['passed'] for t in tests),
              'failed': sum(not t['passed'] for t in tests),
              'failures': [t for t in tests if not t['passed']], 'tests': tests,
              'limitations': ['Uses actual catalog and validator with synthetic observations.',
                              'Evidence file availability is mocked; no filesystem/image truth is established.',
                              'No browser, skill triggering, rendering, accessibility, taste or publication is tested.']}
    if args.output is not None:
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('evidence_level', 'catalog_rows', 'workflow_required_rows',
                                           'workflow_required_cases', 'tests_run', 'passed', 'failed', 'failures')}, indent=2))
    return 1 if report['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
