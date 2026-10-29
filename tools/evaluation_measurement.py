"""Pure measurement projection over existing receipts; never launches or judges.

Records bind observations to task, harness and instruction bytes. Counters keep
native meanings. Unknown usage/attempts are never zero; no billing or efficiency
claim is derived. Hashes bind supplied evidence, not authenticate its origin.
"""
from __future__ import annotations
import hashlib
import json
import math
import re

TOKEN_KEYS = ('input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_write_tokens',
              'reasoning_tokens', 'prompt_tokens', 'completion_tokens', 'total_tokens')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def counter(value):
    return value if type(value) is int and value >= 0 else None


def whole_job_readiness(records, manifest, expected_sha256):
    """Closed, explicitly attributed inventory; compare the SAME whole-job scope.

    Cold/setup/development remain visible. A reuse view needs frozen exclusion
    and reuse evidence; unknown recurring usage never becomes zero.
    """
    from fractions import Fraction
    gaps=[]
    if not isinstance(manifest,dict) or sha(expected_sha256) is None or digest(manifest)!=expected_sha256:
        return {'ready':False,'gaps':['frozen whole-job inventory missing or changed'],'overall_tokens':None}
    arms=manifest.get('arms',[])
    if not isinstance(arms,list) or not arms or len(set(arms))!=len(arms) or any(not isinstance(a,str) or not a for a in arms):
        return {'ready':False,'gaps':['explicit comparison arms required'],'overall_tokens':None}
    view=manifest.get('comparison_view')
    if view not in ('cold-start','recurring-reuse'):gaps.append('explicit cost comparison view required')
    if manifest.get('closed') is not True:gaps.append('whole-job inventory not closed')
    declared={}
    for call in manifest.get('calls',[]):
        if (not isinstance(call,dict) or not isinstance(call.get('call_id'),str) or not call['call_id']
                or call['call_id'] in declared or call.get('cost_class') not in ('recurring','one-time-setup','development')
                or not isinstance(call.get('run_id'),str) or not call['run_id']
                or call.get('target_arm') not in arms+['shared']):
            gaps.append('invalid/duplicate invocation or missing explicit target arm');continue
        declared[call['call_id']]=call
    if not declared:gaps.append('empty invocation inventory')
    stages=manifest.get('stages',{});covered=set()
    for stage in ('actor','retries','failures','support','review','coordinator','setup'):
        row=stages.get(stage,{});ids=row.get('call_ids')
        if not isinstance(ids,list) or any(not isinstance(i,str) or i not in declared for i in ids):
            gaps.append(stage+': invocation coverage missing');continue
        if not ids and sha(row.get('observed_zero_evidence_sha256')) is None:gaps.append(stage+': absence is not observed zero')
        covered.update(ids)
    if covered!=set(declared):gaps.append('inventory calls omitted from coverage')
    observed={}
    for row in records:
        account=row.get('workflow_accounting',{});ident=account.get('call_id')
        if ident not in declared or ident in observed:gaps.append('undeclared/duplicate recorded invocation');continue
        observed[ident]=row
        if row.get('record_sha256')!=digest({k:v for k,v in row.items() if k!='record_sha256'}):gaps.append(ident+': projection changed')
        if any(account.get(k)!=declared[ident].get(k) for k in ('run_id','target_arm','cost_class')):
            gaps.append(ident+': attribution mismatch')
    if set(observed)!=set(declared):gaps.append('required whole-job receipt missing')
    charges={arm:Fraction(0) for arm in arms};recurring={arm:Fraction(0) for arm in arms}
    classes={kind:[] for kind in ('recurring','one-time-setup','development')};excluded=[]
    for ident,row in observed.items():
        call=declared[ident];kind=call['cost_class'];usage=row.get('usage',{})
        total=counter(usage.get('tokens',{}).get('total_tokens'))
        complete=(total is not None and usage.get('coverage',{}).get('whole_system_complete') is True
            and counter(usage.get('provider_physical_attempt_count')) is not None and row.get('retries',{}).get('history_complete') is True)
        classes[kind].append(total if complete else None)
        exclude=view=='recurring-reuse' and kind!='recurring'
        if exclude:
            gaps.append(ident+': cost exclusions/reuse classification are not supported by this receipt contract; use cold-start accounting')
            if sha(call.get('exclusion_evidence_sha256')) is None or sha(call.get('reuse_evidence_sha256')) is None:
                gaps.append(ident+': setup/development exclusion not evidenced and reusable')
            excluded.append({'call_id':ident,'cost_class':kind,'tokens':total if complete else None})
        elif not complete:gaps.append(ident+': required usage/history incomplete')
        if call['target_arm']=='shared':
            allocation=manifest.get('shared_allocations',{}).get(ident,{})
            try:
                weights={arm:Fraction(*allocation['weights'][arm]) for arm in arms}
                if (set(allocation['weights'])!=set(arms) or any(w<0 for w in weights.values())
                        or sum(weights.values())!=1 or sha(allocation.get('review_evidence_sha256')) is None):raise ValueError()
            except (KeyError,TypeError,ValueError,ZeroDivisionError):
                gaps.append(ident+': reviewed shared allocation missing/invalid');continue
        else:weights={arm:Fraction(int(arm==call['target_arm'])) for arm in arms}
        if complete:
            for arm,weight in weights.items():
                if kind=='recurring':recurring[arm]+=weight*total
                if not exclude:charges[arm]+=weight*total
    totals={kind:sum(values) if None not in values else None for kind,values in classes.items()}
    # A partial/open inventory is not a zero-cost job. Retain individual raw
    # observations, but do not expose their subtotal as the required total.
    if gaps:
        totals={kind:None for kind in classes}
    rational=lambda values:{arm:{'numerator':v.numerator,'denominator':v.denominator} for arm,v in values.items()}
    return {'ready':not gaps,'gaps':sorted(set(gaps)),
            'overall_tokens':sum(totals.values()) if None not in totals.values() else None,
            'tokens_by_cost_class':totals,'comparison_view':view,
            'comparison_tokens_by_arm':rational(charges) if not gaps else None,
            'recurring_tokens_by_arm':rational(recurring) if not gaps else None,
            'excluded_setup_development':excluded,'execution_authenticated':False,
            'scope':'Closed attributed whole-job inventory; unknown excluded setup visible, no cold-total or origin authentication inferred'}


def seconds(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def sha(value):
    return value if isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) else None


def observed_usage(run, host):
    """Only documented producer locations, without summing overlapping buckets."""
    usage = run.get('native_usage')
    tokens = {key: None for key in TOKEN_KEYS}
    source, semantics, calls, complete = 'unavailable', 'unknown', None, None
    coverage = {}
    reconciliation = None
    if host == 'hermes' and isinstance(usage, dict) and usage.get('source') == 'native-Hermes-canonical-session-counters':
        values = usage.get('tokens', {})
        tokens = {key: counter(values.get(key)) for key in TOKEN_KEYS}
        source = usage['source']
        semantics = 'Hermes canonical: input excludes cache read/write; prompt and total overlap component buckets'
        calls = counter(usage.get('api_calls'))
        recorded = usage.get('coverage', {})
        complete = recorded.get('completed_response_usage_complete') if type(recorded.get('completed_response_usage_complete')) is bool else None
        coverage = {key: counter(recorded.get(key)) for key in ('session_completed_responses', 'completed_responses_with_usage', 'completed_responses_without_usage')}
        from evaluation_usage import reconcile_program_usage
        proof = reconcile_program_usage(usage)
        if (recorded.get('scope') == proof['scope'] and recorded.get('whole_system_complete') is True
                and run.get('catalog_evidence', {}).get('exact_catalog_verified') is True
                and run.get('model_launched') is True and proof['verified']):
            reconciliation = proof
    elif host == 'codex':
        terminals = [event for event in run.get('native_events', []) if isinstance(event, dict) and event.get('type') == 'turn.completed']
        values = terminals[0].get('usage', {}) if len(terminals) == 1 else None
        if isinstance(values, dict):
            for target, key in (('input_tokens', 'input_tokens'), ('output_tokens', 'output_tokens'), ('cache_read_tokens', 'cached_input_tokens'),
                                ('cache_write_tokens', 'cache_write_input_tokens'), ('reasoning_tokens', 'reasoning_output_tokens'), ('total_tokens', 'total_tokens')):
                tokens[target] = counter(values.get(key))
            source = 'native-Codex-turn-completed-usage'
            semantics = 'Codex native turn aggregate: cached input is a subset of input; other categories unknown'
            complete = tokens['input_tokens'] is not None and tokens['output_tokens'] is not None
        elif isinstance(run.get('tokens'), dict) and run['tokens'].get('source') == 'native-turn-completed-usage':
            values = run['tokens']
            for target, key in (('input_tokens', 'input'), ('output_tokens', 'output'), ('cache_read_tokens', 'cached_input')):
                tokens[target] = counter(values.get(key))
            source = 'native-Codex-turn-completed-usage'
            semantics = 'Codex native turn aggregate: cached input is a subset of input; other categories unknown'
            complete = tokens['input_tokens'] is not None and tokens['output_tokens'] is not None
    lifecycle = usage.get('lifecycle') if isinstance(usage, dict) else None
    if isinstance(lifecycle, dict) and lifecycle.get('source') == 'native-Hermes-lifecycle-hooks':
        from evaluation_usage import HOOKS
        events = []
        for event in lifecycle.get('events', [])[:512]:
            if not isinstance(event, dict) or event.get('hook') not in HOOKS:
                continue
            values = event.get('tokens') if isinstance(event.get('tokens'), dict) else {}
            events.append({'hook': event['hook'], 'request_sha256': sha(event.get('request_sha256')),
                           'retry_index': counter(event.get('retry_index')), 'seconds': seconds(event.get('seconds')),
                           'failed': event.get('failed') is True, 'usage_present': event.get('usage_present') is True,
                           'streaming': event.get('streaming') is True,
                           'tokens': {key: counter(values.get(key)) for key in TOKEN_KEYS}})
        http = lifecycle.get('native_http')
        http = ({'source': 'native-request-client-HTTPX-events',
                 **{key: counter(http.get(key)) for key in ('clients_hooked', 'unsupported_clients', 'dropped_events', 'observation_errors')},
                 'sdk_retry_limits': [counter(value) for value in http.get('sdk_retry_limits', [])[:512]],
                 'events': [{'phase': event['phase'], 'attempt': counter(event.get('attempt')),
                             'status': counter(event.get('status')), 'seconds': seconds(event.get('seconds'))}
                            for event in http.get('events', [])[:512]
                            if isinstance(event, dict) and event.get('phase') in ('request', 'response')]}
                if isinstance(http, dict) and http.get('source') == 'native-request-client-HTTPX-events' else None)
        exposure = [{'request_sha256': sha(e.get('request_sha256')), 'tool_schema_sha256': sha(e.get('tool_schema_sha256')),
                     'tool_count': counter(e.get('tool_count')),
                     'optional_body_present': e.get('optional_body_present') is True,
                     'terminal_contract_present': e.get('terminal_contract_present') is True}
                    for e in lifecycle.get('exposure_events', [])[:512] if isinstance(e,dict)]
        aux = lifecycle.get('auxiliary_dispatches')
        aux = {key: counter(aux.get(key)) for key in ('_relay_sync_completion','_relay_async_completion','_relay_sync_stream')} if isinstance(aux,dict) else None
        lifecycle = {'source': 'native-Hermes-lifecycle-hooks', 'events': events, 'native_http': http,
                     'exposure_events': exposure, 'auxiliary_dispatches': aux,
                     'dropped_events': counter(lifecycle.get('dropped_events')),
                     'provider_physical_attempts_verified': False, 'whole_system_complete': False}
    else:
        lifecycle = None
    if host == 'omp' and run.get('native_omp_stats_source') == 'get_session_stats' and isinstance(run.get('native_omp_stats'), dict):
        values = run['native_omp_stats'].get('tokens', {})
        if isinstance(values, dict):
            for target, key in (('input_tokens', 'input'), ('output_tokens', 'output'), ('reasoning_tokens', 'reasoning'),
                                ('cache_read_tokens', 'cacheRead'), ('cache_write_tokens', 'cacheWrite'), ('total_tokens', 'total')):
                tokens[target] = counter(values.get(key))
            source = 'native-OMP-get_session_stats'
            semantics = 'OMP native session/branch aggregate including some delegated usage; category inclusion and failed/aux coverage unverified'
    return {'source': source, 'tokens': tokens, 'token_semantics': semantics,
            'native_completed_response_count': calls, 'provider_physical_attempt_count': reconciliation['physical_attempt_count'] if reconciliation else None,
            'accounting_reconciliation': reconciliation,
            'lifecycle_observation': lifecycle if isinstance(lifecycle, dict) else None,
            'coverage': {**coverage, 'completed_response_usage_complete': complete,
                         'missing_token_fields': [key for key, value in tokens.items() if value is None],
                         'failed_attempts': 'observed-zero-in-scope' if reconciliation else 'unknown',
                         'auxiliary_models': 'observed-zero-central-dispatches' if reconciliation else 'unverified',
                         'scope': reconciliation['scope'] if reconciliation else 'incomplete-native-observation',
                         'whole_system_complete': reconciliation is not None}, 'billed_cost_usd': None}


def observation(run, context, quality=None):
    """One logical invocation attempt, not both a retry wrapper and its child."""
    quality = quality or {}
    route = run.get('route_attestation', {})
    requested = route.get('requested') or run.get('requested_route') or context.get('route', {})
    observed = route.get('observed') or run.get('agent_observed_route') or {}
    output = run.get('output') if isinstance(run.get('output'), str) else run.get('final_response')
    execution = run.get('execution_ok', run.get('ok'))
    execution = execution if type(execution) is bool else None
    observed_quality = quality.get('passed') if type(quality.get('passed')) is bool else None
    checked_pass = observed_quality
    if execution is not True:
        checked_pass = None  # A runtime failure is not an artifact-quality verdict.
    result = {'schema_version': 1,
        'provenance': {'evidence_sha256': sha(context.get('evidence_sha256')),
                       'timestamp_utc': context.get('timestamp_utc'),
                       'execution_origin': 'recorded-receipt-not-authenticated'},
        'identity': {key: context.get(key) for key in ('case_id', 'arm', 'role', 'trial', 'attempt')},
        'revisions': {key: sha(context.get(key)) for key in
                      ('task_sha256', 'verifier_sha256', 'harness_sha256', 'instruction_sha256')},
        'harness': {key: context.get(key) for key in ('runtime_lane', 'tool_policy', 'context_policy')},
        'route': {'host': context.get('host'),
                  'requested': {key: requested.get(key) for key in ('model', 'provider', 'reasoning')},
                  'observed': {key: observed.get(key) for key in ('model', 'provider', 'reasoning')},
                  'version': context.get('host_version'), 'provider_resolved_identity_verified': False},
        'outcome': {'execution_ok': execution, 'operational_ok': run.get('operational_ok'),
                    'output_sha256': hashlib.sha256(output.encode()).hexdigest() if isinstance(output, str) else None,
                    'output_characters': len(output) if isinstance(output, str) else None,
                    'task_passed': checked_pass, 'quality_passed': observed_quality,
                    'quality_source': quality.get('source', 'not-evaluated'),
                    'quality_evidence_sha256': sha(quality.get('evidence_sha256'))},
        'elapsed': {'seconds': seconds(run.get('seconds', run.get('timings', {}).get('controller_total'))),
                    'scope': 'invocation wall time; may include runtime setup/cleanup; excludes controller retry delays'},
        'retries': {'logical_attempt_index': counter(context.get('attempt')),
                    'history_complete': context.get('attempt_history_complete') is True,
                    'provider_retries': None},
        'usage': observed_usage(run, context.get('host'))}
    result['trial_validity'] = trial_validity(run, context, result['outcome'])
    if isinstance(quality.get('dimensions'), dict):
        result['outcome']['assessment_dimensions'] = quality['dimensions']
    if isinstance(run.get('request_recording'), dict):
        recording = run['request_recording']
        result['request_recording'] = {key: sha(recording.get(key)) for key in
            ('manifest_sha256', 'run_binding_sha256', 'output_checks_sha256')}
        result['request_recording'].update(complete=recording.get('complete') is True,
            final_request_count=counter(recording.get('final_request_count')), execution_authenticated=False)
    accounting = run.get('workflow_accounting', context.get('workflow_accounting'))
    if isinstance(accounting, dict):
        # Optional explicit call/run linkage. No prompts, output or credentials.
        result['workflow_accounting'] = {k: accounting[k] for k in
            ('call_id','run_id','target_arm','required_call_ids','cost_class',
             'exclusion_evidence_sha256','reuse_evidence_sha256','supporting') if k in accounting}
    trace = (result['usage'].get('lifecycle_observation') or {}).get('exposure_events', [])
    result['harness']['effective_initial_tool_schema_sha256'] = (trace[0]['tool_schema_sha256']
        if trace and ((trace[0].get('tool_count') or 0)>0 and trace[0].get('terminal_contract_present') is True
                      or trace[0].get('tool_count')==0 and context.get('tool_policy')=='none'
                      and trace[0].get('tool_schema_sha256')==hashlib.sha256(b'[]').hexdigest()) else None)
    performance = run.get('performance') if isinstance(run.get('performance'), dict) else {}
    result['performance'] = {**{key: counter(performance.get(key)) for key in
                               ('workflow_retry_count', 'workflow_repair_count', 'human_intervention_count')},
                             'human_wait_seconds': seconds(performance.get('human_wait_seconds')),
                             'native_conversation_seconds': seconds(run.get('native_seconds')),
                             'workflow_elapsed_seconds': seconds(run.get('native_seconds')) if result['trial_validity']['status'] == 'valid' else None,
                             'elapsed': result['elapsed'], 'scope': 'Observed invocation only; missing friction metrics remain unknown'}
    result['record_sha256'] = digest(result)
    return result


def attribution_resolution(run, context):
    """Resolve causal-review bytes against this raw run and supplied sources.

    A digest alone grants no setup exclusion. Causal truth remains reviewed;
    tool friction cannot erase a later timeout or unknown usage.
    """
    review=run.get('failure_attribution') or {};raw=review.get('evidence_source')
    gaps=[];scope=None
    try:
        if not isinstance(raw,str) or hashlib.sha256(raw.encode()).hexdigest()!=review.get('evidence_sha256'):
            raise ValueError('causal evidence bytes missing/changed')
        evidence=json.loads(raw)
        raw_run={key:value for key,value in run.items() if key!='failure_attribution'}
        if evidence.get('run_sha256')!=digest(raw_run):gaps.append('causal review belongs to a different raw run')
        if evidence.get('failure_sha256')!=digest(run.get('failure',{})):gaps.append('causal review does not bind observed failure')
        scope=evidence.get('scope')
        if scope not in ('whole-trial','specific-tool-failure'):gaps.append('causal scope missing')
        if not isinstance(evidence.get('cause'),str) or not evidence['cause'].strip():gaps.append('causal explanation missing')
        sources=context.get('attribution_source_bytes',{})
        refs=evidence.get('supporting_sources')
        if not isinstance(refs,list) or not refs:raise ValueError('supporting causal observations required')
        for ref in refs:
            data=sources.get(ref.get('sha256'))
            if isinstance(data,str):data=data.encode()
            if (not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=ref.get('sha256')
                    or not isinstance(ref.get('excerpt'),str) or not ref['excerpt']
                    or ref['excerpt'] not in data.decode('utf-8',errors='replace')):
                gaps.append('causal observation unavailable/changed')
    except (ValueError,KeyError,TypeError,AttributeError) as error:gaps.append(str(error))
    return {'resolved':not gaps,'scope':scope,'gaps':sorted(set(gaps)),'causation_automatically_proven':False}


def trial_validity(run, context, outcome):
    """Attribute only documented setup boundaries or evidence-linked review.

    A one-time workflow setup exemption needs fresh-run reuse evidence. No
    exception text, timing guess, or folder name establishes attribution.
    """
    scenario = context.get('benchmark_scenario', 'steady-state')
    if scenario not in ('steady-state', 'cold-start'): scenario = 'unknown'
    review = run.get('failure_attribution') if isinstance(run.get('failure_attribution'), dict) else {}
    evidence = sha(review.get('evidence_sha256'))
    resolution=attribution_resolution(run,context) if review else {'resolved':False,'scope':None,'gaps':['no causal review']}
    category = review.get('category') if resolution['resolved'] else None
    reuse = sha(review.get('reuse_evidence_sha256'))
    failure = run.get('failure') if isinstance(run.get('failure'), dict) else {}
    contract = run.get('runtime_contract') if isinstance(run.get('runtime_contract'), dict) else {}
    prelaunch_setup = (run.get('model_launched') is False and failure.get('source') == 'runtime-control' and failure.get('kind') == 'isolation'
                       and contract.get('phase') in ('setup', 'preflight'))
    if scenario == 'unknown':
        status, reason, category = 'unresolved', 'benchmark scenario unavailable', 'unknown'
    elif prelaunch_setup or (category == 'evaluator-setup' and resolution['scope']=='whole-trial' and run.get('model_launched') is False):
        status, reason = 'invalid-setup', 'evaluator/tool prerequisites failed; not workflow performance'
        if prelaunch_setup: evidence = digest({'failure': failure, 'phase': contract.get('phase'), 'operation': contract.get('setup_operation')})
        category = 'evaluator-setup'
    elif category == 'evaluator-setup':
        status,reason,category='unresolved','specific tool defect or postlaunch attribution does not erase incomplete trial','partially-supported-tool-defect'
    elif run.get('blocked_requests') and category not in ('workflow', 'one-time-workflow-setup'):
        status, reason, category = 'unresolved', 'tool-guard rejection observed; workflow versus evaluator causation not established', 'unknown'
        evidence = digest({'blocked_request_count': len(run['blocked_requests'])})
    elif category == 'one-time-workflow-setup' and scenario == 'steady-state':
        status, reason = (('one-time-setup', 'reusable setup excluded from steady-state; fresh-run reuse evidence supplied')
                          if reuse and isinstance(review.get('reuse_evidence_source'),str) and hashlib.sha256(review['reuse_evidence_source'].encode()).hexdigest()==reuse
                          else ('unresolved', 'one-time setup claimed without resolved fresh-run reuse evidence'))
    elif category in ('workflow', 'one-time-workflow-setup'):
        status, reason = 'valid', 'evidence-linked workflow effort/failure; cold-start setup included when explicitly selected'
    elif outcome.get('execution_ok') is True and outcome.get('operational_ok') is True:
        status, reason = 'valid', 'completed task execution; quality bar assessed separately'
        category = 'workflow'
    else:
        status, reason = 'unresolved', 'failure attribution not established; neither workflow charge nor setup exemption'
        category = 'unknown'
    return {'status': status, 'category': category, 'reason': reason, 'evidence_sha256': evidence,
            'benchmark_scenario': scenario, 'reuse_evidence_sha256': reuse,
            'prerequisites_sha256': sha(context.get('prerequisites_sha256')),'causal_review':resolution}


def measurement_sources(report, source_bytes=None):
    """Explicit bounded hash-addressed evidence; source integrity, not causation."""
    import base64
    sources=dict(source_bytes or {})
    bundle=report.get('measurement_source_bundle')
    if bundle is not None:
        if not isinstance(bundle,dict) or set(bundle)!= {'version','encoding','files'} or bundle['version']!=1 or bundle['encoding']!='base64' or not isinstance(bundle['files'],dict):
            raise ValueError('Malformed measurement source bundle')
        if len(bundle['files'])>512 or any(not isinstance(v,str) for v in bundle['files'].values()) or sum(len(v) for v in bundle['files'].values())>12*1024*1024:
            raise ValueError('Encoded measurement source bounds exceeded')
        for key,value in bundle['files'].items():
            if not isinstance(value,str):raise ValueError('Invalid measurement source encoding')
            data=base64.b64decode(value,validate=True)
            if key in sources and sources[key]!=data:raise ValueError('Conflicting measurement evidence')
            sources[key]=data
    if len(sources)>512 or any(not isinstance(v,bytes) for v in sources.values()) or sum(map(len,sources.values()))>8*1024*1024:
        raise ValueError('Measurement sources exceed bounded byte contract')
    if any(sha(k) is None or hashlib.sha256(v).hexdigest()!=k for k,v in sources.items()):
        raise ValueError('Measurement source hash mismatch')
    return sources


def inline_records(report, *, source_bytes=None):
    """Use the canonical attempt ledger once, including interrupted orphan runs."""
    sources=measurement_sources(report,source_bytes)
    stack, artifacts = report.get('effective_stack', {}), report.get('artifacts', {})
    try:
        suite = json.loads(report.get('input_snapshot', {}).get('suite_source', '{}'))
    except (ValueError, TypeError):
        suite = {}
    cases = {row.get('id'): row for row in suite.get('cases', [])}
    rows = {(row.get('trial'), row.get('id')): row for row in report.get('results', [])}
    complete_history = (bool(report.get('attempt_ledger')) and counter(report.get('run_count')) == len(report['attempt_ledger']))
    ledger = list(report.get('attempt_ledger', []))
    records = []
    # Historical reports without a ledger remain usable but cannot claim history.
    if not ledger:
        for row in rows.values():
            for role in ('baseline', 'candidate'):
                run = row.get(role, {})
                for attempt in run.get('attempts') or [run]:
                    ledger.append({'trial': row.get('trial'), 'case_id': row.get('id'), 'role': role, **attempt})
            for i, judge in enumerate(row.get('judgments', [])):
                run = judge.get('run', {})
                for attempt in run.get('attempts') or [run]:
                    ledger.append({'trial': row.get('trial'), 'case_id': row.get('id'), 'role': 'judge-'+str(i), **attempt})
    evidence = digest({key: value for key, value in report.items() if key not in ('measurements', 'measurement_status')})
    last = {}
    sequences = {}
    for entry in ledger:
        key = (entry.get('trial'), entry.get('case_id'), entry.get('role'))
        last[key] = entry.get('attempt')
        sequences.setdefault(key, []).append(entry.get('attempt'))
    complete_history = complete_history and all(values == list(range(1, len(values)+1)) for values in sequences.values())
    for entry in ledger:
        role, case_id = entry.get('role'), entry.get('case_id')
        key = (entry.get('trial'), case_id, role)
        row = rows.get(key[:2], {})
        judge = isinstance(role, str) and role.startswith('judge')
        side = 'candidate' if role == 'candidate' else 'baseline'
        instruction = artifacts.get('candidate_sha256' if side == 'candidate' else 'baseline_candidate_sha256') if not judge else None
        quality = {'source': 'not-evaluated'}
        if not judge and row and entry.get('attempt') == last[key]:
            quality = {'passed': row.get('hard_pass', {}).get(side), 'source': 'existing-evaluator-hard-pass',
                       'evidence_sha256': digest({'deterministic': row.get('deterministic'), 'hard_pass': row.get('hard_pass'),
                                                 'judge_errors': row.get('judge_errors'), 'winner': row.get('winner')})}
            if row.get('judge_errors'):
                quality['passed'] = None
        route = {key: stack.get(('judge_' if judge else '')+key, stack.get(key)) for key in ('model', 'provider', 'reasoning')}
        context = {'evidence_sha256': evidence, 'attribution_source_bytes':sources, 'timestamp_utc': report.get('timestamp_utc'),
                   'case_id': case_id, 'arm': side if not judge else 'judge', 'role': role,
                   'trial': entry.get('trial'), 'attempt': entry.get('attempt'),
                   'attempt_history_complete': complete_history,
                   'task_sha256': digest(cases[case_id]) if case_id in cases else None,
                   'verifier_sha256': artifacts.get('suite_sha256'), 'harness_sha256': artifacts.get('harness_sha256'),
                   'instruction_sha256': instruction, 'host': report.get('judge_agent' if judge else 'agent'),
                   'host_version': report.get('judge_version' if judge else 'agent_version'), 'route': route,
                   'runtime_lane': stack.get('runtime_lane'), 'tool_policy': stack.get('tool_policy'), 'context_policy': stack.get('context_policy')}
        context.update(benchmark_scenario=cases.get(case_id, {}).get('benchmark_scenario', 'steady-state'),
                       prerequisites_sha256=cases.get(case_id, {}).get('prerequisites_sha256'))
        records.append(observation(entry, context, quality))
    for item in report.get('supporting_receipts',[]):
        run=item['run'];identity=item['identity'];account=item['workflow_accounting']
        records.append(observation({**run,'workflow_accounting':{**account,'supporting':True}},
            {'evidence_sha256':digest(run),'attribution_source_bytes':sources,'timestamp_utc':report.get('timestamp_utc'),
             'case_id':identity.get('case_id'),'trial':identity.get('trial'),'attempt':identity.get('attempt',1),
             'role':identity['role'],'arm':'support','host':item['host'],'host_version':item['host_version'],
             'route':item['route'],'attempt_history_complete':item.get('attempt_history_complete') is True},
            {'source':'supporting-native-receipt; not task-quality verdict'}))
    return records


def artifact_records(report, plan, *, source_bytes=None):
    """Project the existing independently checked artifact pilot; no new judge."""
    records = []
    completed={}
    if isinstance(report.get('completed_review'),dict) and source_bytes is not None:
        from evaluation_evidence import completed_artifact_decision
        completed=completed_artifact_decision(report,report['completed_review'],source_bytes)
    cases = {case['id']: case for case in plan['spec']['cases']}
    for row in report.get('results', []):
        case = cases.get(row['case'], {})
        native = row.get('native', {})
        checked = row.get('oracle', {})
        passed = (row.get('oracle_exit_code') == 0 and type(checked.get('passed')) is int and checked['passed'] > 0
                  and type(checked.get('failed')) is int and checked['failed'] == 0 and checked.get('failures') == []) if checked else None
        frozen = plan.get('candidate_snapshots', {}).get(row['arm'])
        spec = plan['spec']
        harness = {key: plan.get(key) for key in ('controller_sha256', 'worker_sha256', 'native_hermes_worker_sha256', 'runtime_sha256', 'measurement_sha256', 'usage_observer_sha256')}
        harness['common_catalog'] = sorted(frame['package_sha256'] for frame in plan.get('common_catalog_snapshots', {}).values())
        harness['instruction_exposure'] = spec.get('instruction_exposure', 'native-discovery')
        if spec.get('terminal_backend'): harness['terminal_backend'] = spec['terminal_backend']
        instruction = frozen.get('package_sha256') if frozen else digest({'optional_skill': 'absent', 'minimum_permitted_harness': harness})
        cleanup = native.get('cleanup', {})
        operational = (cleanup.get('state_removed') is True and not cleanup.get('errors') and not native.get('worker_cleanup_errors')) if cleanup else row.get('isolated_runtime_removed')
        recording = ({'request_recording': row.get('request_recording') or {'complete': False}}
                     if spec.get('request_recording_parent') else {})
        dimensions = row.get('outcome_assessment') or {
            'runtime_completed':native.get('ok',row.get('worker_ok')),
            'deterministic_invariants_passed':passed,
            'semantic_adequacy':{'status':'pending','passed':None},
            'comparative_preference':{'status':'not-assessed','winner':None},
            'projection_note':'New conservative projection; original legacy records remain unchanged'}
        # Oracle success is necessary evidence, never a substantive artifact review.
        full_quality = False if passed is False else None
        final_review=completed.get('deliveries',{}).get(row['id'],{})
        if completed.get('source_bound_current_quality') and final_review.get('task_passed') is not None:
            full_quality=final_review['task_passed']
            dimensions={**dimensions,'semantic_adequacy':{'status':'completed-packet-review','passed':final_review['reviewed_artifact_adequate']},
                'comparative_preference':completed.get('quality_disposition'),'task_passed':full_quality}
        runtime_completed = dimensions.get('runtime_completed', native.get('ok', row.get('worker_ok')))
        records.append(observation({**native, **recording, 'execution_ok': runtime_completed,
                                    'operational_ok': operational, 'seconds': row.get('seconds_including_verification')},
            {'case_id': row['case'], 'arm': row['arm'], 'role': 'worker', 'trial': 0, 'attempt': 1,
             'timestamp_utc': report.get('timestamp_utc'),
             'attempt_history_complete': True, 'task_sha256': digest({'prompt': case.get('prompt'), 'source_tree': plan.get('case_source_trees', {}).get(row['case'])}),
             'verifier_sha256': plan.get('oracle_sha256'), 'harness_sha256': digest(harness),
             'instruction_sha256': instruction,
             'host': spec.get('agent', 'hermes'), 'host_version': native.get('host_version'),
             'route': {key: spec.get(key) for key in ('model','provider','reasoning')},
             'runtime_lane': plan.get('kind'), 'tool_policy': 'native-study-request-gate' if plan.get('kind') in ('native-skill-study','native-runtime-smoke') else 'routed-native-child', 'context_policy': 'fresh-runtime-per-output',
             'benchmark_scenario': case.get('benchmark_scenario', 'steady-state'),
             'prerequisites_sha256': case.get('prerequisites_sha256'),
             'evidence_sha256': digest(row),'attribution_source_bytes':source_bytes or {}},
            {'passed': full_quality, 'source': 'packet-bound-substantive-review' if full_quality is not None and completed.get('ready') else 'artifact-oracle-invariants; substantive-review-pending',
             'dimensions':dimensions,'evidence_sha256':report.get('completed_review',{}).get('review_sha256')
                if completed.get('ready') and full_quality is not None else digest(checked) if checked else None}))
    return records


def _auxiliary(row):
    identity = row.get('identity', {})
    accounting = row.get('workflow_accounting', {})
    return (accounting.get('supporting') is True or accounting.get('cost_class') in ('development','one-time-setup')
            or identity.get('arm') == 'judge'
            or str(identity.get('role', '')).split('-')[0] in ('judge','parent','coordinator','support'))


def workflow_usage(row, records=()):
    """Sum recurring disjoint invocations once; never guess missing linkage.

    A leaf without linked stages retains its legacy isolated-invocation scope.
    Producers of multi-call workflows declare required_call_ids on the output.
    call_id identifies an invocation, not an aggregate which overlaps children.
    """
    ident = row.get('identity', {})
    account = row.get('workflow_accounting', {})
    run_id = account.get('run_id')
    arm = ident.get('arm')
    relevant, gaps, excluded = [], [], []
    candidates = list(records) or [row]
    if not any(other is row for other in candidates): candidates.append(row)
    arms = {r.get('identity', {}).get('arm') for r in candidates if not _auxiliary(r)
            and all(r.get('identity', {}).get(k)==ident.get(k) for k in ('case_id','trial'))}
    for other in candidates:
        oi = other.get('identity', {}); oa = other.get('workflow_accounting', {})
        if not all(oi.get(k)==ident.get(k) for k in ('case_id','trial')): continue
        if run_id and oa.get('run_id') != run_id:
            if oi.get('arm')==arm or oa.get('target_arm')==arm:
                gaps.append('related call missing or different workflow run linkage')
            continue
        target = oa.get('target_arm', oi.get('arm'))
        if target == 'judge':
            if len(arms)!=1:
                gaps.append('shared supporting call needs explicit target arm; no guessed allocation')
                continue
            target = next(iter(arms))
        if target != arm: continue
        relevant.append(other)
    unique = {}
    for other in relevant:
        oi=other.get('identity', {}); oa=other.get('workflow_accounting', {})
        call = oa.get('call_id') or digest([oi.get(k) for k in ('case_id','trial','arm','role','attempt')])
        if not isinstance(call,str) or not call:
            gaps.append('invalid invocation identity');continue
        if call in unique:
            if digest(unique[call])!=digest(other): gaps.append('conflicting duplicate invocation')
            continue
        unique[call]=other
    required = account.get('required_call_ids', [])
    if not isinstance(required,list) or any(not isinstance(k,str) or not k for k in required):
        gaps.append('invalid required invocation manifest')
    elif set(required)-set(unique): gaps.append('required workflow invocation missing')
    included = []
    for call,other in unique.items():
        oa=other.get('workflow_accounting', {}); cost=oa.get('cost_class','recurring')
        if cost not in ('recurring','development','one-time-setup'):
            gaps.append('unknown invocation cost classification');continue
        separate = cost=='development' or (cost=='one-time-setup' and row.get('trial_validity',{}).get('benchmark_scenario')!='cold-start')
        if separate:
            if (sha(oa.get('exclusion_evidence_sha256')) is None or
                    cost=='one-time-setup' and sha(oa.get('reuse_evidence_sha256')) is None):
                gaps.append('development/setup exclusion lacks evidence and verified reuse')
            excluded.append({'call_id':call,'cost_class':cost,'usage':other.get('usage',{})})
            continue
        usage=other.get('usage', {})
        if (counter(usage.get('tokens',{}).get('total_tokens')) is None
                or usage.get('coverage',{}).get('whole_system_complete') is not True
                or counter(usage.get('provider_physical_attempt_count')) is None
                or other.get('retries',{}).get('history_complete') is not True):
            gaps.append('related retry/supporting call has incomplete usage; cannot omit it from a qualifying run')
        if (usage.get('source')!=row.get('usage',{}).get('source') or
                usage.get('token_semantics')!=row.get('usage',{}).get('token_semantics')):
            gaps.append('workflow token semantics differ or are unavailable')
        included.append((call,other))
    tokens = {key: (sum(r['usage']['tokens'][key] for _,r in included)
                   if included and all(counter(r.get('usage',{}).get('tokens',{}).get(key)) is not None for _,r in included) else None)
              for key in TOKEN_KEYS}
    attempts=[counter(r.get('usage',{}).get('provider_physical_attempt_count')) for _,r in included]
    if gaps:
        tokens={key:None for key in TOKEN_KEYS}
    return {'tokens':tokens,'gaps':sorted(set(gaps)),'included_call_ids':[c for c,_ in included],
            'logical_invocation_count':len(included),
              'physical_attempt_count':sum(attempts) if not gaps and attempts and None not in attempts else None,
            'call_observations':[{'call_id':c,'native_seconds':r.get('performance',{}).get('native_conversation_seconds'),
                                  'physical_attempts':r.get('usage',{}).get('provider_physical_attempt_count')} for c,r in included],
            'excluded_calls':excluded,'scope':'Recurring task-model invocations, deduplicated; evidenced development/one-time setup separate',
            'source':row.get('usage',{}).get('source'),'token_semantics':row.get('usage',{}).get('token_semantics')}


def quality_eligibility(row):
    """Use the existing execution, cleanup and task-quality verdicts as the bar."""
    outcome = row.get('outcome', {})
    reasons = []
    if row.get('trial_validity', {}).get('status') != 'valid': reasons.append('trial invalid, one-time setup, or attribution unresolved')
    if _auxiliary(row): reasons.append('supporting call, not an independently qualified task output')
    if isinstance(row.get('request_recording'), dict) and row['request_recording'].get('complete') is not True:
        reasons.append('required prompt/request recording or output-check binding incomplete')
    if outcome.get('execution_ok') is not True: reasons.append('execution not successful')
    if outcome.get('operational_ok') is not True: reasons.append('cleanup not successful or unverified')
    provenance = outcome.get('assessment_dimensions', {}).get('execution_provenance', {})
    if provenance.get('required') is True and provenance.get('final_artifact_program_linked') is not True:
        reasons.append('executed program bytes not linked to final artifact')
    if outcome.get('quality_passed') is False or outcome.get('task_passed') is False:
        reasons.append('task output below quality bar')
    elif outcome.get('quality_passed') is not True or outcome.get('task_passed') is not True:
        reasons.append('successful task-quality verdict unavailable')
    return {'eligible': not reasons, 'reasons': reasons}


def reliability_summary(records):
    """Retain attempts and denominators; judge calls are not task-output trials."""
    workers = [row for row in records if not _auxiliary(row)]
    supporting={}
    for row in records:
        if not _auxiliary(row):continue
        identity=row.get('identity',{});account=row.get('workflow_accounting',{})
        key=digest([identity.get(k) for k in ('case_id','trial','arm')]+[account.get('run_id'),
            account.get('call_id') or [identity.get('role'),identity.get('attempt')]])
        supporting.setdefault(key,row)
    groups = {}
    for row in workers:
        identity = row.get('identity', {})
        groups.setdefault(tuple(identity.get(k) for k in ('case_id', 'trial', 'arm', 'role')), []).append(row)
    qualified, ambiguous, valid, invalid, setup, unresolved, quality_passed = 0, 0, 0, 0, 0, 0, 0
    for rows in groups.values():
        attempts = [counter(row.get('identity', {}).get('attempt')) for row in rows]
        if None in attempts or len(set(attempts)) != len(attempts):
            ambiguous += 1
        else:
            terminal = rows[attempts.index(max(attempts))]
            status = terminal.get('trial_validity', {}).get('status')
            quality_passed += terminal.get('outcome', {}).get('task_passed') is True
            valid += status == 'valid'
            invalid += status == 'invalid-setup'
            setup += status == 'one-time-setup'
            unresolved += status not in ('valid', 'invalid-setup', 'one-time-setup')
            qualified += quality_eligibility(terminal)['eligible']
    excluded = [{'record': row.get('record_sha256'), 'identity': row.get('identity'),
                 'reasons': quality_eligibility(row)['reasons'], 'trial_validity': row.get('trial_validity'),
                 'performance': row.get('performance')} for row in workers if not quality_eligibility(row)['eligible']]
    return {'task_run_count': len(groups), 'quality_qualified_run_count': qualified,
            'observed_quality_passed_run_count': quality_passed,
            'valid_task_run_count': valid, 'invalid_setup_run_count': invalid,
            'one_time_setup_run_count': setup, 'unresolved_run_count': unresolved,
            'nonqualified_valid_run_count': valid-qualified, 'ambiguous_terminal_run_count': ambiguous,
            'quality_success_rate': qualified/valid if valid and not ambiguous else None,
            'worker_attempt_count': len(workers), 'excluded_attempts': excluded,
            'supporting_call_count': len(supporting),
            'supporting_observation_count':len(records)-len(workers),
            'supporting_execution_failure_count': sum(row.get('outcome', {}).get('execution_ok') is False for row in supporting.values()),
            'denominator': 'Unique case/trial/arm/role valid task runs; invalid setup and verified one-time setup separate; unresolved attribution visible; all attempts retained'}


def precise_usage_gaps(row, records=()):
    """No failure exclusion may erase a retry/judge inside a qualifying run."""
    usage = row.get('usage', {})
    gaps = []
    if usage.get('source') in (None, 'unavailable') or counter(usage.get('tokens', {}).get('total_tokens')) is None:
        gaps.append('complete overall token total unavailable')
    if usage.get('coverage', {}).get('whole_system_complete') is not True:
        gaps.append('overall token coverage unavailable (physical attempts/auxiliary models)')
    if counter(usage.get('provider_physical_attempt_count')) is None:
        gaps.append('physical attempt count unavailable')
    if row.get('retries', {}).get('history_complete') is not True:
        gaps.append('logical invocation history incomplete')
    if row.get('trial_validity', {}).get('prerequisites_sha256') is None:
        gaps.append('equivalent prerequisites evidence unavailable')
    if sha(row.get('harness', {}).get('effective_initial_tool_schema_sha256')) is None:
        gaps.append('effective initial tool schema evidence unavailable')
    route = row.get('route', {})
    if route.get('version') is None or any(route.get('requested', {}).get(key) is None
            or route.get('observed', {}).get(key) != route.get('requested', {}).get(key)
            for key in ('model', 'provider', 'reasoning')):
        gaps.append('effective native route/version evidence incomplete')
    return gaps + workflow_usage(row, records)['gaps']


def compare_records(before, after, *, changed='instruction'):
    """Describe matched task observations over time; no selection/admission rule.

    Model comparisons pin instructions/harness. Instruction comparisons pin the
    requested route/harness. Missing controls, duplicates and telemetry produce
    explicit unavailable results instead of an efficiency verdict.
    """
    if changed not in ('instruction', 'model'):
        raise ValueError('comparison must name instruction or model as changed')
    def key(row):
        identity, rev = row['identity'], row['revisions']
        controls = [rev.get(k) for k in ('task_sha256', 'verifier_sha256', 'harness_sha256')]
        if any(v is None for v in controls): return None
        validity = row.get('trial_validity', {})
        controls.extend([validity.get('benchmark_scenario'), validity.get('prerequisites_sha256')])
        if changed == 'model':
            if rev.get('instruction_sha256') is None: return None
            controls.extend([rev['instruction_sha256'], row['route']['requested'].get('provider'), row['route']['requested'].get('reasoning')])
        else: controls.append(row['route']['requested'])
        role = identity.get('role')
        if changed == 'instruction' and role in ('baseline', 'candidate', 'worker'):
            role = 'worker'
        return digest([identity.get('case_id'), role, identity.get('trial'), row['harness'], row['route'].get('host'), row['route'].get('version'), *controls])
    def index(rows):
        groups = {}
        for row in rows:
            if _auxiliary(row): continue
            ident = key(row)
            groups.setdefault(ident, []).append(row)
        for ident, group in groups.items():
            attempts=[counter(r.get('identity',{}).get('attempt')) for r in group]
            if len(group)>1 and None not in attempts and len(set(attempts))==len(attempts):
                groups[ident]=[group[attempts.index(max(attempts))]]
        return groups
    left, right = index(before), index(after)
    pairs, unmatched = [], []
    for ident in sorted(set(left) | set(right), key=str):
        a, b = left.get(ident, []), right.get(ident, [])
        if ident is None or len(a) != 1 or len(b) != 1:
            unmatched.append({'match_key': ident, 'before_count': len(a), 'after_count': len(b), 'reason': 'missing-controls, unmatched task, retries or duplicate trials'})
            continue
        a, b = a[0], b[0]
        semantic_match = a['usage']['source'] == b['usage']['source'] and a['usage']['token_semantics'] == b['usage']['token_semantics'] and a['usage']['source'] != 'unavailable'
        eligible_a, eligible_b = quality_eligibility(a), quality_eligibility(b)
        precision_a = precise_usage_gaps(a, before) if eligible_a['eligible'] else []
        precision_b = precise_usage_gaps(b, after) if eligible_b['eligible'] else []
        precise = eligible_a['eligible'] and eligible_b['eligible'] and not precision_a and not precision_b and semantic_match
        total_a, total_b = workflow_usage(a,before), workflow_usage(b,after)
        token_delta = {k: total_b['tokens'][k] - total_a['tokens'][k]
                       if precise and total_a['tokens'][k] is not None and total_b['tokens'][k] is not None else None for k in TOKEN_KEYS}
        elapsed_a, elapsed_b = a.get('performance', {}).get('workflow_elapsed_seconds'), b.get('performance', {}).get('workflow_elapsed_seconds')
        # Independent stage wall times may overlap; do not label a leaf clock
        # as the full workflow's elapsed time or silently add concurrent clocks.
        if len(total_a['included_call_ids'])>1 or len(total_b['included_call_ids'])>1:
            elapsed_a=elapsed_b=None
        pairs.append({'case_id': a['identity'].get('case_id'), 'before': a['record_sha256'], 'after': b['record_sha256'],
                      'route': {'before': a['route'], 'after': b['route']},
                      'task_passed': {'before': a['outcome']['task_passed'], 'after': b['outcome']['task_passed']},
                      'quality_eligibility': {'before': eligible_a, 'after': eligible_b},
                      'precise_usage_gaps': {'before': precision_a, 'after': precision_b},
                      'conditional_efficiency_eligible': precise,
                      'seconds_delta_after_minus_before': elapsed_b - elapsed_a if eligible_a['eligible'] and eligible_b['eligible'] and elapsed_a is not None and elapsed_b is not None else None,
                      'performance': {'before': a.get('performance'), 'after': b.get('performance')},
                      'token_delta_after_minus_before': token_delta,
                      'workflow_usage': {'before':total_a,'after':total_b},
                      'unobserved_controls': ['native host version'] if a['route'].get('version') is None else [],
                      'whole_system_efficiency_verdict': None})
    def cases(rows, qualified=False):
        return sorted({str(row.get('identity', {}).get('case_id')) for row in rows if not _auxiliary(row)
                       and (not qualified or quality_eligibility(row)['eligible'])})
    qualified_keys_a = {key(row) for row in before if quality_eligibility(row)['eligible']}
    qualified_keys_b = {key(row) for row in after if quality_eligibility(row)['eligible']}
    return {'schema_version': 1, 'changed': changed, 'pairs': pairs, 'unmatched': unmatched,
            'reliability': {'before': reliability_summary(before), 'after': reliability_summary(after)},
            'conditional_efficiency': {'scope': 'Recorded case-scoped usage; separate closed whole-job attribution required for overall efficiency',
                'eligible_pair_count': sum(pair['conditional_efficiency_eligible'] for pair in pairs),
                'eligible_case_ids': sorted({pair['case_id'] for pair in pairs if pair['conditional_efficiency_eligible']}),
                'observed_case_ids': {'before': cases(before), 'after': cases(after)},
                'quality_qualified_case_ids': {'before': cases(before, True), 'after': cases(after, True)},
                'equivalent_case_coverage': not unmatched and cases(before) == cases(after)
                    and None not in qualified_keys_a and qualified_keys_a == qualified_keys_b
                    and all(row.get('trial_validity', {}).get('status') == 'valid' for row in before+after if not _auxiliary(row))},
            'admission': False, 'limits': ['Descriptive task-specific observations, not execution authentication or a statistical quality verdict.',
                                         'No physical-attempt, auxiliary-model, dollar-cost or whole-system efficiency claim.']}


def acceptance_readiness(records):
    """Readiness for conditional efficiency; failures remain reliability evidence.

    A standalone failed/below-bar run need not have usage. Every call inside a
    qualifying run still needs accounting. This is not an all-attempt cost gate.
    """
    gaps = []
    if not records:
        gaps.append('no observed execution records')
    qualified = [row for row in records if quality_eligibility(row)['eligible']]
    if records and not qualified: gaps.append('no quality-qualified task output')
    if any(row.get('trial_validity', {}).get('status') == 'unresolved' for row in records if not _auxiliary(row)):
        gaps.append('unresolved trial attribution remains; not charged to workflow or forgiven as setup')
    reliability = reliability_summary(records)
    if reliability['ambiguous_terminal_run_count']:
        gaps.append('ambiguous terminal attempt identity')
    for row in qualified:
        identity = row.get('record_sha256')
        gaps.extend(f'{identity}: {gap}' for gap in precise_usage_gaps(row, records))
    return {'ready': not gaps, 'gaps': gaps, 'quality_qualified_count': len(qualified),
            'reliability': reliability,
            'scope': 'Conditional on quality-qualified outputs; excludes failed/below-bar runs from efficiency, not reliability; no all-attempt cost or improvement verdict'}


def attach_measurements(report, plan=None, *, source_bytes=None):
    """Measurement errors cannot prevent export of original execution evidence."""
    try:
        if plan is None and source_bytes is not None:
            import base64
            sources=measurement_sources(report,source_bytes)
            report['measurement_source_bundle']={'version':1,'encoding':'base64','files':{k:base64.b64encode(v).decode('ascii') for k,v in sources.items()}}
        records = inline_records(report,source_bytes=source_bytes) if plan is None else artifact_records(report, plan,source_bytes=source_bytes)
        report['measurements'] = records
        report['measurement_status'] = {'projection_ok': True, 'acceptance': acceptance_readiness(records)}
    except Exception as exc:
        report['measurements'] = []
        report['measurement_status'] = {'projection_ok': False, 'error_type': type(exc).__name__,
                                        'acceptance': {'ready': False, 'gaps': ['measurement projection failed']}}
