"""Advisory authoring review shared by pre-edit review and reconciliation plan.

No model calls, candidate execution, writes, admission or publication authority.
Text overlap is a search hint; recorded comparisons are integrity checks, not
proof of authentic execution, natural discovery or full-stack behavior.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Sequence

import artifact_hash
import capability_intake
import fleet
import instruction_profile
import validate

OFFICIAL_GUIDANCE = [
    'https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra',
    'https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md#prompting-best-practices',
]
MAX_JSON_BYTES = 8_000_000

def _read_json_bytes(path: Path) -> tuple[bytes, dict[str, Any]]:
    if not path.is_file() or fleet.is_linklike_path(path):
        raise ValueError('evidence file must be a bounded regular file')
    with path.open('rb') as handle:
        raw = handle.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError('evidence file exceeds the bounded read limit')
    value = json.loads(raw.decode('utf-8'))
    if not isinstance(value, dict):
        raise ValueError('expected a JSON object')
    return raw, value

def _json(path: Path) -> dict[str, Any]:
    return _read_json_bytes(path)[1]

def _target(repo: Path, value: str) -> Path:
    requested = Path(value)
    if requested.is_absolute() or '..' in requested.parts:
        raise ValueError('target must be a repository-relative source path')
    path = repo / requested
    if not path.resolve().is_relative_to(repo) or fleet.is_linklike_path(path):
        raise ValueError('target escapes source ownership')
    return path

def _tokens(text: str) -> set[str]:
    ignored = {'use', 'when', 'for', 'the', 'and', 'with', 'from', 'that', 'this', 'only', 'not', 'work', 'task', 'skills', 'skill'}
    return {w for w in re.findall(r'[a-z][a-z0-9-]{2,}', text.lower()) if w not in ignored}

def _coverage(repo: Path, candidate: Path, baseline: Path | None,
              routes: list[dict[str, str]], reports: Sequence[Path], suites: Sequence[Path],
              *, strict_reports: bool = False, strict_suites: bool = False) -> dict[str, Any]:
    """Index exact model cells without weakening the existing per-model gate."""
    from evaluation_evidence import validate_report
    candidate_hash = artifact_hash.candidate_hash(candidate)
    baseline_hash = artifact_hash.candidate_hash(baseline) if baseline else None
    suite_index = {}
    diagnostics = {'unreadable_reports': 0, 'unreadable_suites': 0, 'non_comparative_records': 0}
    for path in suites:
        try:
            raw, suite = _read_json_bytes(path)
            suite_index[hashlib.sha256(raw).hexdigest()] = suite
        except (ValueError, OSError):
            if strict_suites:
                raise
            diagnostics['unreadable_suites'] += 1
    rows, observations = [], []
    for path in reports:
        try:
            report = _json(path)
        except (ValueError, OSError):
            if strict_reports:
                raise
            diagnostics['unreadable_reports'] += 1
            continue
        stack = report.get('effective_stack', {})
        if not isinstance(stack, dict) or not stack:
            diagnostics['non_comparative_records'] += 1
            continue
        artifacts = report.get('artifacts', {})
        if not isinstance(artifacts, dict):
            continue
        route = {k: stack.get(k) for k in ('model', 'provider', 'reasoning')}
        label = path.relative_to(repo).as_posix() if path.resolve().is_relative_to(repo) else 'supplied-report'
        row = {'report': label, 'host': report.get('agent'), **route,
               'candidate_matches': artifacts.get('candidate_sha256') == candidate_hash,
               'baseline_matches': baseline_hash is not None and artifacts.get('baseline_candidate_sha256') == baseline_hash}
        if not row['candidate_matches'] or not row['baseline_matches']:
            row['status'] = 'different-artifact-or-baseline'
        else:
            suite = suite_index.get(artifacts.get('suite_sha256'))
            if suite is None:
                row['status'] = 'independent-suite-missing'
            else:
                result = validate_report(report, suite)
                row.update(status='record-consistent' if not result['errors'] else 'invalid-record',
                           scope=result['scope'], decision=result['computed_decision'],
                           positive_sufficient=result['positive_decision_sufficient'],
                           evidence_complete=result['evidence_complete'],
                           operational_errors=result['operational_errors'],
                           limitations=result['limitations'], errors=result['errors'])
        observations.append(row)
    for route in routes:
        matched = [o for o in observations if all(o.get(k) == v for k, v in route.items())
                   and o.get('status') == 'record-consistent']
        rows.append({**route, 'status': 'recorded-text-comparison' if matched else 'missing-current-comparison',
                     'comparisons': matched,
                     'positive_decision_sufficient_in_record': any(o.get('positive_sufficient') is True for o in matched)})
    return {'required_routes': rows, 'observed_comparisons': observations,
            'candidate_sha256': candidate_hash, 'baseline_sha256': baseline_hash,
            'scan_diagnostics': diagnostics,
            'full_stack_behavior': 'not-established-by-this-review',
            'natural_skill_triggering': 'not-established-by-this-review',
            'limits': ['Uses the existing recorded-evidence validator; not execution authentication.',
                       'One existing eval_gate per exact model stack; mixed-model evidence is not pooled.',
                       'Callability and profile/structural receipts do not count as comparative quality.']}

def native_catalog_view(description: str, hosts: Sequence[str]) -> dict[str, Any]:
    """Source-derived hint only; verify the rendered catalog separately."""
    if 'hermes' not in hosts:
        return {'status':'not-requested'}
    import recovery
    path = recovery._default_roots()['hermes']/'hermes-agent/agent/skill_utils.py'
    if not path.is_file() or fleet.is_linklike_path(path):
        return {'status':'native-source-unavailable'}
    with path.open('rb') as handle:
        raw = handle.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        return {'status':'native-source-exceeds-read-limit'}
    match = re.search(r'^SKILL_PROMPT_DESC_LIMIT\s*=\s*(\d+)\s*$',raw.decode('utf-8'),re.MULTILINE)
    if not match or not 3 <= int(match.group(1)) <= 4096:
        return {'status':'native-limit-unresolved'}
    limit = int(match.group(1))
    visible = description[:limit-3]+'...' if len(description)>limit else description
    return {'status':'native-source-hint','hermes_description_limit':limit,
            'visible_description':visible,'truncated':len(description)>limit,
            'native_source_sha256':hashlib.sha256(raw).hexdigest(),
            'limit':'Source constant and single-line preview, not observed active-session rendering or trigger quality.'}

def review(repo: str | Path, target: str, *, candidate: str | Path | None = None,
           baseline: str | Path | None = None, hosts: Sequence[str] = (),
           models: Sequence[str] = (), reports: Sequence[str | Path] = (),
           suites: Sequence[str | Path] = (), reference_skills: Sequence[str | Path] = ()) -> dict[str, Any]:
    repo = Path(repo).resolve()
    source = _target(repo, target)
    proposed = Path(candidate).absolute() if candidate else source
    before = Path(baseline).absolute() if baseline else (source if candidate and source.is_file() else None)
    if not proposed.is_file() or fleet.is_linklike_path(proposed):
        raise ValueError('candidate must be a regular source file')
    if before is not None and (not before.is_file() or fleet.is_linklike_path(before)):
        raise ValueError('baseline must be a regular source file')
    text = proposed.read_text(encoding='utf-8')
    metadata, body = validate.frontmatter(text)
    parts = Path(target).parts
    registry = fleet.registry(repo)
    skill = parts[1] if len(parts) >= 3 and parts[0] == 'skills' else None
    owner = f'skills/{skill}' if skill else 'unresolved'
    owner_hosts = []
    if skill:
        finding = capability_intake.classify_fleet_action(
            {'name': skill, 'action': 'update' if source.is_file() else 'add'}, registry.get(skill),
            destination_id='authoring-review', checked=False)
    else:
        finding = {'owner': owner, 'disposition': 'review-required', 'route': 'cross-agent-surface-engineering',
                   'reason': 'Resolve the declared native/project source owner; advisory review grants no authority.'}
        contract = repo / 'contracts/instruction-surfaces.json'
        if contract.is_file():
            matches = [s for s in _json(contract).get('surfaces', []) if s.get('artifact') == target]
            if len(matches) == 1:
                owner = matches[0]['owner']; finding['owner'] = owner
                owner_hosts = [h for h in matches[0].get('hosts', []) if h in ('codex', 'hermes', 'omp')]
        policy_path = repo/'recovery.json'
        if owner == 'unresolved' and policy_path.is_file():
            policy = _json(policy_path)
            for host, data in policy.get('hosts', {}).items():
                for artifact in data.get('artifacts', []):
                    if 'recovery/current/'+artifact.get('snapshot', '') == target:
                        finding = capability_intake._classify_recovery_item(
                            {'host':host,'id':artifact['id'],'target':artifact['source']},artifact,conflict=False)
                        owner = finding['owner']
                        owner_hosts = [host]
    warnings = []
    if source.name == 'SKILL.md':
        intended_name = skill or source.parent.name
        warnings.extend(validate.validate_skill(proposed, expected_name=intended_name))
        if metadata.get('name') != intended_name:
            warnings.append('candidate frontmatter name differs from canonical target owner')
    peers = []
    query = _tokens(metadata.get('description', ''))
    for entry in (repo/'skills').glob('*/SKILL.md'):
        if entry.parent.name == skill or fleet.is_linklike_path(entry):
            continue
        meta, _ = validate.frontmatter(entry.read_text(encoding='utf-8'))
        other = _tokens(meta.get('description', ''))
        shared = query & other
        if len(shared) >= 2:
            peers.append({'owner': 'skills/'+entry.parent.name,
                          'shared_trigger_terms': sorted(shared),
                          'overlap_hint': round(len(shared)/len(query | other), 3)})
    peers.sort(key=lambda p: (-p['overlap_hint'], p['owner']))
    profile_path = instruction_profile.current_profile(repo)
    profile = _json(profile_path)
    required = []
    selected_hosts = list(hosts) or owner_hosts or list(profile['hosts'])
    for host in selected_hosts:
        if host not in profile['hosts']:
            raise ValueError('host has no current observation')
        settings = profile['hosts'][host]
        route = {'host': host, 'model': settings.get('model', profile['target']['model']),
                 'provider': settings.get('provider', profile['target']['provider']), 'reasoning': settings['reasoning']}
        required.append(route)
        for model in models:
            if model != route['model']:
                required.append({**route, 'model': model})
    report_paths = [Path(p).absolute() for p in reports] if reports else sorted((repo/'evals/results').glob('*.json'))
    suite_paths = [Path(p).absolute() for p in suites] if suites else sorted((repo/'evals').glob('*.json'))
    coverage = _coverage(repo, proposed, before, required, report_paths, suite_paths,
                         strict_reports=bool(reports), strict_suites=bool(suites))
    from useful_behavior import compare_sources
    behavior_review = compare_sources(proposed, reference_skills) if reference_skills else {
        'mode':'explicit-source-behavior-review','sources':[], 'automatic_semantic_verdict':False,
        'limit':'No existing/native skill was supplied; catalog overlap does not establish procedure preservation.'}
    return {'schema_version': 1, 'mode': 'advisory-authoring-review', 'target': target,
            'mutation_performed': False, 'inference_performed': False, 'admission_authority': False,
            'owner': owner, 'classification': finding, 'structural_findings': warnings,
            'catalog': {'description_characters': len(metadata.get('description', '')),
                        'entrypoint_bytes': len(text.encode()), 'entrypoint_lines': len(text.splitlines()),
                        'native_catalog_view': native_catalog_view(metadata.get('description', ''), selected_hosts),
                        'overlap_candidates': peers[:8],
                        'semantic_overlap': 'unresolved; token overlap is only a review shortlist'},
            'official_model_guidance': {'route': 'OpenAI Docs when available; current official pages otherwise',
                                        'requested_models': sorted({r['model'] for r in required}),
                                        'sources': OFFICIAL_GUIDANCE if any('astra' in r['model'].lower() for r in required) else [],
                                        'retrieval_status': 'model-specific links to consult; this command does not fetch documentation'},
            'measurement': coverage, 'useful_behavior_review': behavior_review,
            'profile_scope': 'Declared current-profile cells; live settings are not reverified here. --host narrows scope; added models inherit each host provider/reasoning.',
            'next_checks': ['Use the same review before editing and with plan --target after editing.',
                            'Preserve baseline bytes when a comparative behavior claim is intended.',
                            'Choose existing text or artifact lane only if it tests the claimed mechanism.',
                            'Full-stack/natural-discovery claims remain pending the native diagnostic.',
                            'Inspect shortlisted owners before deciding overlap, retirement or consolidation.',
                            'This optional review does not block editing or authorize deployment/publication.']}
