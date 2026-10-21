"""Check architectural ownership and bound necessity before instruction publication.

This validates evidence records, not semantic benefit or human authenticity.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
import subprocess

import sync_git
import validate

INDEX = 'contracts/instruction-surfaces.json'
GENERATED = {'recovery/current/hosts/codex/AGENTS.md',
             'recovery/current/hosts/hermes/SOUL.md',
             'recovery/current/hosts/omp/AGENTS.md'}
ADAPTERS = {'adapters/codex.json', 'adapters/hermes.json', 'adapters/omp.json'}


def is_instruction_source(name):
    path = Path(name)
    return ((name.startswith('skills/') and path.suffix.lower() == '.md') or
            name == 'surfaces/core.md' or name in ADAPTERS or
            path.name.upper() in {'AGENTS.MD', 'SOUL.MD', 'RULES.MD', 'SKILL.MD'})


def _before(repo, base, name):
    # Read raw blobs: Windows newline conversion must not weaken the binding.
    result = subprocess.run(['git', '-C', str(repo), 'show', base + ':' + name],
                            capture_output=True)
    if result.returncode:
        # Absence is distinct from an invalid revision or failed Git operation.
        entry = subprocess.run(['git', '-C', str(repo), 'ls-tree', '-z', base, '--', name],
                               capture_output=True)
        if entry.returncode or entry.stdout:
            raise sync_git.SyncBlocked('cannot read instruction baseline: ' + name)
        return None
    return result.stdout


def _hash(data):
    return hashlib.sha256(data).hexdigest() if data is not None else 'absent'


CONTRACTS = {'docs/system-requirements.md', 'docs/requirement-status.md'}


def _preference_data_only(old, new, row):
    """Recognize role-selector data, never standing prose or native-default mapping."""
    if old is None or new is None:
        return False
    start, end = b"<!-- agent-sync-preferences -->", b"<!-- /agent-sync-preferences -->"
    def parts(data):
        if data.count(start) != 1 or data.count(end) != 1:
            return None
        prefix, block = data.split(start)
        block, suffix = block.split(end)
        match = re.fullmatch(rb"\s*```json\s*\r?\n(.*?)\r?\n```\s*", block, re.S)
        if match is None:
            return None
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate preference key")
                result[key] = value
            return result
        return prefix, suffix, json.loads(match[1], object_pairs_hook=unique)
    try:
        before, after = parts(old), parts(new)
        roles = row.get('preference_roles')
        if (before is None or after is None or before[:2] != after[:2]
                or not isinstance(roles, list) or not roles
                or any(not isinstance(role, str) for role in roles)
                or len(roles) != len(set(roles))):
            return False
        left, right = before[2], after[2]
        if not isinstance(left, dict) or not isinstance(right, dict):
            return False
        old_roles, new_roles = left.get('roles'), right.get('roles')
        if not isinstance(old_roles, dict) or not isinstance(new_roles, dict):
            return False
        old_other = json.dumps({k:v for k,v in left.items() if k != 'roles'}, sort_keys=True, allow_nan=False)
        new_other = json.dumps({k:v for k,v in right.items() if k != 'roles'}, sort_keys=True, allow_nan=False)
        if old_other != new_other:
            return False
        # Preserve all existing roles; coordinator is the sole supported addition.
        if not set(old_roles) <= set(new_roles) or set(new_roles) - set(old_roles) - {'coordinator'}:
            return False
        changed = {k for k in new_roles if k not in old_roles or old_roles[k] != new_roles[k]}
        if changed != set(roles) or not changed <= (set(old_roles) | {'coordinator'}):
            return False
        for role in changed:
            value = new_roles[role]
            if (not isinstance(value, dict) or set(value) != {'model', 'reasoning'}
                    or not isinstance(value['model'], str)
                    or not re.fullmatch(r'[a-z0-9][a-z0-9._-]+', value['model'])
                    or value['reasoning'] not in {'none','minimal','low','medium','high','xhigh','max','ultra'}):
                return False
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def correction_eligibility(candidate, source, name, owner, row, base, paths, reconciliations):
    """Narrow reviewed correction routes after necessity/dependency validation.

    Record validation does not authenticate authority or prove semantic scope.
    Other instruction adoption still uses the measured-evidence gate.
    """
    old = _before(source, base, name)
    path = candidate / name
    new = path.read_bytes() if path.is_file() else None
    kind = row.get('change_kind', 'add-or-change')
    reason = None
    if (kind == 'add-or-change' and row.get('basis') == 'mechanical-maintenance'
            and old is not None and new is not None
            and old.replace(b'\r\n', b'\n') == new.replace(b'\r\n', b'\n')):
        reason = 'content-identical line-ending repair'
    elif (kind == 'add-or-change' and name == owner == 'surfaces/core.md'
            and row.get('basis') == 'user-correction' and _preference_data_only(old, new, row)):
        reason = 'explicit user model-selector data; standing instructions unchanged'
    elif kind == 'contract-correction':
        sections = {'skills/instruction-authoring/SKILL.md': 'Evaluation discipline',
                    'skills/instruction-authoring/references/change-review.md': 'Publication necessity record'}
        if (row.get('basis') != 'user-correction' or owner != 'skills/instruction-authoring'
                or name not in sections or old is None or new is None):
            raise sync_git.SyncBlocked('contract correction requires the existing explicit authoring owner')
        def outside_section(data):
            text = data.decode('utf-8').replace('\r\n', '\n')
            heading = '## ' + sections[name] + '\n'
            if text.count(heading) != 1:
                raise sync_git.SyncBlocked('contract correction has no unique authoring contract section')
            prefix, section = text.split(heading, 1)
            _, delimiter, suffix = section.partition('\n## ')
            return prefix, delimiter + suffix
        if outside_section(old) != outside_section(new):
            raise sync_git.SyncBlocked('contract correction changes instructions outside its contract section')
        matching = [r for r in reconciliations if r.get('requirement_change') is True
                    and {name, *CONTRACTS} <= set(r.get('artifacts', {}))]
        if (len(matching) != 1 or not CONTRACTS <= set(paths)
                or any(_before(source, base, n) == (candidate / n).read_bytes() for n in CONTRACTS)):
            raise sync_git.SyncBlocked('contract correction requires selected, changed, bound intent and status')
        reason = 'reviewed explicit authoring contract correction'
    if reason is None:
        return None
    if 'behavior_measurements' in row or 'task_contract' in row:
        raise sync_git.SyncBlocked('correction cannot substitute for a behavioral-adoption claim')
    return {'eligible': True, 'reason': reason + '; no behavioral improvement claimed',
            'behavioral_proof': False, 'approval_authenticated': False}


def measurement_eligibility(candidate, source, name, owner, row, base):
    """Exclude changed instructions lacking matching measured improvement.

    Unchanged deployed instructions are not reclassified. Records establish
    consistency and coverage, not authenticity or semantic task adequacy.
    """
    import artifact_hash
    import instruction_profile
    from evaluation_evidence import instruction_improvement
    try:
        profile_raw = instruction_profile.current_profile(candidate).read_bytes()
        profile = json.loads(profile_raw)
        hosts = set(profile['hosts'])
        if owner.startswith('recovery:'):
            hosts &= {owner.split(':')[1]}
        elif name in ADAPTERS:
            hosts &= {Path(name).stem}
        records = row.get('behavior_measurements')
        contract = row.get('task_contract')
        if not hosts or not isinstance(records, list) or not isinstance(contract, dict):
            raise ValueError('missing behavioral measurements or task contract')
        if not isinstance(contract.get('claim'), str) or not contract['claim'].strip():
            raise ValueError('missing intended behavioral outcome')
        harness = artifact_hash.harness_hash(candidate / 'tools/eval.py')
        seen = set()
        for measurement in records:
            if measurement.get('profile_sha256') != _hash(profile_raw):
                raise ValueError('measurement current-profile binding is outdated or missing')
            def read(key):
                relative = sync_git.safe_path(candidate, measurement[key])
                if not relative.startswith('evals/'):
                    raise ValueError('measurement must use existing evals records')
                path = candidate / relative
                if path.is_symlink() or path.stat().st_size > 8_000_000:
                    raise ValueError('measurement must be a bounded regular file')
                raw = path.read_bytes()
                if _hash(raw) != measurement[key + '_sha256']:
                    raise ValueError('measurement record bytes mismatch')
                return json.loads(raw)
            report, suite = read('report'), read('suite')
            if report.get('kind') == 'native-skill-study':
                # Inspect the bound raw plan/report without treating a leaf
                # study as a legacy admission suite or granting it authority.
                from evaluation_evidence import validate_artifact_evidence
                diagnostic = validate_artifact_evidence(report, suite)
                return {'eligible': False, 'reason': 'instruction excluded: native artifact evidence remains diagnostic only',
                        'artifact_evidence': {key: diagnostic[key] for key in
                            ('consistent', 'source_bytes_complete', 'source_gaps', 'runtime_gaps', 'errors',
                             'admission', 'execution_authenticated', 'admission_blockers')}}
            host = report.get('agent')
            if host not in hosts or host in seen:
                raise ValueError('missing, duplicate or unexpected measurement host')
            seen.add(host)
            suite_hash = measurement['suite_sha256']
            if (contract.get('suite_sha256') != suite_hash or suite.get('claim') != contract['claim']
                    or contract.get('comparison_requirements') != suite.get('comparison_requirements')):
                raise ValueError('measurement task contract mismatch')
            settings = profile['hosts'][host]
            route = {'host': host, **{key: settings.get(key, profile['target'].get(key))
                                     for key in ('model', 'provider', 'reasoning')}}
            errors = instruction_improvement(report, suite, suite_sha256=suite_hash,
                                             harness_sha256=harness, route=route)
            if errors:
                raise ValueError('; '.join(errors))
            if Path(name).name == 'SKILL.md' and report['artifacts']['candidate_sha256'] != artifact_hash.freeze_candidate(candidate / name)['package_sha256']:
                raise ValueError('measurement skill package is outdated or mismatched')
            binding = row['artifacts'][name]
            for side, digest in (('baseline', binding['before_sha256']), ('candidate', binding['after_sha256'])):
                snapshot = report.get('input_snapshot', {}).get(side) or {}
                if digest == 'absent':
                    if snapshot:
                        raise ValueError('measurement baseline does not represent absent instruction')
                elif digest not in snapshot.get('files', {}).values():
                    raise ValueError('measurement instruction bytes mismatch')
                data = (_before(source, base, name) if side == 'baseline' else
                        ((candidate / name).read_bytes() if (candidate / name).is_file() else None))
                if data and data.decode('utf-8').strip() not in snapshot.get('prompt_text', ''):
                    raise ValueError('instruction body was not in measured prompt')
            new = (candidate / name).read_text(encoding='utf-8') if (candidate / name).is_file() else ''
            if new and new.strip() not in report['input_snapshot']['candidate']['prompt_text']:
                raise ValueError('changed instruction body was not in measured prompt')
        if seen != hosts:
            raise ValueError('missing measured improvement for current target hosts: ' + ', '.join(sorted(hosts - seen)))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, instruction_profile.ProfileError) as exc:
        return {'eligible': False, 'reason': 'instruction excluded: ' + str(exc)}
    return {'eligible': True, 'reason': 'source-bound outcome/accounting checks cover current target routes; '
            'claim coverage, practical benefit and retention require owner review'}


def reconciliation_scope(candidate, source, base, paths):
    """Discover exact reverse references; this is coverage, not semantic analysis."""
    names = set(subprocess.check_output(
        ['git', '-C', str(source), 'ls-tree', '-r', '--name-only', base], text=True).splitlines()) | set(paths)
    guidance = {n for n in names if (n.endswith('.md') and n.startswith(('skills/', 'docs/', 'adapters/'))) or
                (n.startswith('contracts/') and n.endswith(('.json', '.md')))}
    changed = {n for n in paths if _before(source, base, n) !=
               ((candidate / n).read_bytes() if (candidate / n).is_file() else None)}
    executables = {n for n in changed if n.startswith(('tools/', 'integrations/')) or
                   (n.startswith('skills/') and '/scripts/' in n)}
    # Batch baseline reads; avoid a subprocess per edge on every graph walk.
    ordered = sorted(guidance)
    result = subprocess.run(['git', '-C', str(source), 'cat-file', '--batch'],
                            input=''.join(base + ':' + n + '\n' for n in ordered).encode(),
                            capture_output=True, check=True)
    raw, offset, graph = result.stdout, 0, {}
    for name in ordered:
        end = raw.index(b'\n', offset)
        header = raw[offset:end].split()
        offset = end + 1
        if header[-1] == b'missing':
            old = b''
        else:
            size = int(header[-1]); old = raw[offset:offset + size]; offset += size + 1
        new = (candidate / name).read_bytes() if (candidate / name).is_file() else b''
        links = set()
        for data in (old, new):
            text = data.decode('utf-8')
            links.update(re.findall(r'(?<![\w/.-])((?:tools|integrations|skills|docs|adapters)/[\w./-]+)', text))
            for link in validate.local_links(text):
                try:
                    links.add((candidate / name).parent.joinpath(link.split('#', 1)[0]).resolve().relative_to(candidate.resolve()).as_posix())
                except ValueError:
                    pass
        graph[name] = links
    contract_sources = {n for n in changed if n.startswith('contracts/')}
    affected = set(executables) | contract_sources | {n for n in changed if n.startswith('skills/') and n.endswith('.md')} | (changed & CONTRACTS)
    while True:
        more = ({name for name, links in graph.items() if links & affected} |
                {target for name in contract_sources for target in graph.get(name, ()) if target in guidance}) - affected
        if not more:
            break
        affected.update(more)
    return changed, executables, affected


def _dependency_review(candidate, source, base, paths, instruction_paths):
    # Legacy fixtures/repos without this intent owner keep their migration boundary.
    if not any(_before(source, base, n) is not None or (candidate / n).is_file() for n in CONTRACTS):
        return []
    if any(not (candidate / name).is_file() for name in CONTRACTS):
        raise sync_git.SyncBlocked('existing intent contract and status cannot be removed')
    changed, executables, affected = reconciliation_scope(candidate, source, base, paths)
    if not executables and not instruction_paths and not (changed & CONTRACTS) and not any(n.startswith('contracts/') for n in changed) and not any(n.startswith('skills/') and n.endswith('.md') for n in changed):
        return []
    required = affected | set(instruction_paths) | CONTRACTS
    records = []
    for name in sorted(paths):
        if name.startswith('evals/results/') and name.endswith('.json') and (candidate / name).is_file():
            value = json.loads((candidate / name).read_bytes())
            rows = value.get('change_reconciliation', []) if isinstance(value, dict) else []
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise sync_git.SyncBlocked('invalid change reconciliation record: ' + name)
            records.extend((name, row) for row in rows)
    framework_changed = any(n.startswith('skills/instruction-authoring/') and n.endswith('.md') for n in changed)
    if framework_changed:
        reviews = [row.get('framework_review') for _, row in records if 'framework_review' in row]
        if len(reviews) != 1 or not isinstance(reviews[0], dict):
            raise sync_git.SyncBlocked('authoring framework change requires one affected-owner assessment')
        review = reviews[0]
        if any(not isinstance(review.get(k), str) or not review[k].strip() for k in ('selection_reason', 'unaffected_reason', 'checks')) or not isinstance(review.get('affected'), list) or not review['affected']:
            raise sync_git.SyncBlocked('authoring framework assessment is incomplete')
        for name in review['affected']:
            if not isinstance(name, str) or sync_git.safe_path(candidate, name) != name or not name.startswith(('skills/', 'contracts/', 'docs/')):
                raise sync_git.SyncBlocked('invalid framework dependency address')
            required.add(name)
    used = []
    for name in sorted(required):
        matches = [(receipt, row) for receipt, row in records if isinstance(row.get('artifacts'), dict) and name in row['artifacts']]
        if len(matches) != 1:
            raise sync_git.SyncBlocked('change reconciliation requires one bound dependency record: ' + name)
        receipt, row = matches[0]
        old = _before(source, base, name)
        new = (candidate / name).read_bytes() if (candidate / name).is_file() else None
        if row['artifacts'][name] != {'before_sha256': _hash(old), 'after_sha256': _hash(new)}:
            raise sync_git.SyncBlocked('change reconciliation has stale dependency bytes: ' + name)
        if not isinstance(row.get('requirement_change'), bool) or any(
                not isinstance(row.get(key), str) or not row[key].strip()
                for key in ('requirement_reason', 'authority', 'checks')):
            raise sync_git.SyncBlocked('change reconciliation requires intent assessment and checks: ' + name)
        outcome = row.get('outcome_review')
        if not isinstance(outcome, dict) or any(not isinstance(outcome.get(k), str) or not outcome[k].strip() for k in ('expected', 'observed', 'evidence', 'limitations')):
            raise sync_git.SyncBlocked('change reconciliation requires expected/observed outcome evidence: ' + name)
        if old is None and new is None:
            raise sync_git.SyncBlocked('dependency address does not exist: ' + name)
        if row['requirement_change'] and not CONTRACTS <= (changed & set(paths)):
            raise sync_git.SyncBlocked('changed user intent requires selected requirements and status updates')
        if name not in executables:
            obligations = row.get('obligations', [])
            matches = [o for o in obligations if isinstance(o, dict) and o.get('path') == name] if isinstance(obligations, list) else []
            expected = 'removed' if new is None else ('updated' if old != new else 'unchanged')
            if len(matches) != 1 or matches[0].get('disposition') != expected or not isinstance(matches[0].get('reason'), str) or not matches[0]['reason'].strip():
                raise sync_git.SyncBlocked('change reconciliation omits dependency disposition: ' + name)
            if old != new and name not in paths:
                raise sync_git.SyncBlocked('changed dependency must be selected for publication: ' + name)
        used.append({'path': name, 'receipt': receipt, 'check': 'dependency-coverage'})
    return used


def _loading_review(candidate, source, base, owner, row, changed):
    """Validate the declared map and load graph, not its semantic completeness."""
    if not owner.startswith('skills/'):
        return
    if 'restructured' in row and not isinstance(row['restructured'], bool):
        raise sync_git.SyncBlocked('instruction restructuring declaration must be boolean: ' + owner)
    entry = owner + '/SKILL.md'
    old_entry = _before(source, base, entry)
    current = candidate / entry
    new_entry = current.read_bytes() if current.is_file() else None
    reasons = []
    if entry in changed and new_entry is not None:
        reasons.extend(validate.loading_signals(new_entry.decode('utf-8'),
                       old_entry.decode('utf-8') if old_entry is not None else None)['review_reasons'])
    for name in changed:
        old = _before(source, base, name)
        path = candidate / name
        new = path.read_bytes() if path.is_file() else None
        if old is not None and new is None:
            reasons.append('removed instruction file')
        if validate.local_links((old or b'').decode('utf-8')) != validate.local_links((new or b'').decode('utf-8')):
            reasons.append('changed local reference routes')
    if row.get('restructured') is True:
        reasons.append('declared workflow restructuring')
    review = row.get('loading_review')
    if not reasons and review is None:
        return
    if not isinstance(review, dict) or any(not isinstance(review.get(key), str) or not review[key].strip()
                                          for key in ('entrypoint_reason', 'checks')):
        raise sync_git.SyncBlocked('instruction change requires a loading review: ' + owner + ' (' + '; '.join(sorted(set(reasons))) + ')')
    rows = review.get('obligations')
    if not isinstance(rows, list) or not rows or any(not isinstance(item, dict) for item in rows):
        raise sync_git.SyncBlocked('loading review requires an obligation map: ' + owner)

    def address(value):
        if not isinstance(value, str) or not value.startswith(owner + '/') or '\\' in value:
            raise sync_git.SyncBlocked('loading review address is outside its owner: ' + str(value))
        name, _, fragment = value.partition('#')
        if sync_git.safe_path(candidate, name) != name:
            raise sync_git.SyncBlocked('loading review requires exact source addresses: ' + value)
        return name, fragment

    # Follow local Markdown links, including nested routers; mere existence is
    # insufficient. References outside this package remain with their owners.
    reachable, pending = set(), [entry] if new_entry is not None else []
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        path = candidate / name
        if not path.is_file():
            continue
        reachable.add(name)
        if path.suffix.lower() != '.md':
            continue
        for link in validate.local_links(path.read_text(encoding='utf-8')):
            destination = (path.parent / link.split('#', 1)[0]).resolve()
            try:
                destination.relative_to((candidate / owner).resolve())
                relative = destination.relative_to(candidate.resolve()).as_posix()
            except ValueError:
                continue
            if relative not in reachable:
                pending.append(relative)
    covered_before, covered_after = set(), set()
    for item in rows:
        if (any(not isinstance(item.get(key), str) or not item[key].strip()
                for key in ('obligation', 'applies_when', 'load_when', 'reason'))
                or not isinstance(item.get('required'), bool)
                or item.get('disposition') not in {'preserved', 'changed', 'added', 'removed'}):
            raise sync_git.SyncBlocked('loading review has incomplete obligation conditions: ' + owner)
        for side in ('before', 'after'):
            values = item.get(side)
            if not isinstance(values, list) or (not values and item['disposition'] != ('added' if side == 'before' else 'removed')):
                raise sync_git.SyncBlocked('loading review has no ' + side + ' obligation address: ' + owner)
            for value in values:
                name, fragment = address(value)
                data = _before(source, base, name) if side == 'before' else ((candidate / name).read_bytes() if (candidate / name).is_file() else None)
                if data is None:
                    raise sync_git.SyncBlocked('loading review address does not exist in ' + side + ': ' + value)
                if fragment:
                    # Addresses use literal heading text, avoiding platform slug conventions.
                    headings = {line.lstrip('#').strip() for line in data.decode('utf-8').splitlines() if line.startswith('#')}
                    if fragment not in headings:
                        raise sync_git.SyncBlocked('loading review heading does not exist: ' + value)
                if side == 'after' and name not in reachable:
                    raise sync_git.SyncBlocked('loading review destination is not reachable from entrypoint: ' + value)
                (covered_before if side == 'before' else covered_after).add(name)
    for name in changed:
        if _before(source, base, name) is not None and name not in covered_before:
            raise sync_git.SyncBlocked('loading review omits changed baseline source: ' + name)
        if (candidate / name).is_file() and name not in covered_after:
            raise sync_git.SyncBlocked('loading review omits changed destination source: ' + name)


def check(candidate: Path, source: Path, base: str, paths):
    paths = set(paths)
    old_index = _before(source, base, INDEX)
    current = candidate / INDEX
    before = json.loads(old_index) if old_index is not None else {}
    after = json.loads(current.read_bytes()) if current.is_file() else {}
    # V1 inventories predate declared standing-source ownership. Preserve that
    # migration boundary; a V2 baseline cannot evade this check by deleting it.
    if max(before.get('schema_version', 0), after.get('schema_version', 0)) < 2:
        for name in paths:
            path = candidate / name
            instruction = is_instruction_source(name)
            if instruction and _before(source, base, name) != (path.read_bytes() if path.is_file() else None):
                raise sync_git.SyncBlocked('changed instruction excluded: migrate ownership/evidence before qualification: ' + name)
        return []
    if after.get('schema_version') != 2:
        raise sync_git.SyncBlocked('instruction ownership index cannot be removed or downgraded')
    owners = {}
    for row in before.get('surfaces', []) + after.get('surfaces', []):
        name, owner = row.get('artifact'), row.get('owner')
        if name and owner and name not in GENERATED and row.get('model_sensitive') is not False:
            if name in owners and owners[name] != owner:
                raise sync_git.SyncBlocked('conflicting instruction source ownership: ' + name)
            owners[name] = owner
    capability_owners = {}
    ownership = candidate / 'contracts/ownership.json'
    if ownership.is_file():
        for row in json.loads(ownership.read_bytes()).get('capabilities', []):
            capability_owners[row['id']] = row['owner']
    native_owners = {}
    policy = candidate / 'recovery.json'
    if policy.is_file():
        for host, spec in json.loads(policy.read_bytes()).get('hosts', {}).items():
            for row in spec.get('artifacts', []):
                native_owners['recovery/current/' + row['snapshot']] = 'recovery:' + host + ':' + row['id']
    source_changes = set()
    for source_name in {'surfaces/core.md', *ADAPTERS}:
        if source_name in paths:
            source_path = candidate / source_name
            new_source = source_path.read_bytes() if source_path.is_file() else None
            if _before(source, base, source_name) != new_source:
                source_changes.add(source_name)
    required = {}
    for name in paths:
        path = candidate / name
        if name in GENERATED:
            host_adapter = 'adapters/' + Path(name).parts[3] + '.json'
            if not ({'surfaces/core.md', host_adapter} & source_changes):
                if _before(source, base, name) != (path.read_bytes() if path.is_file() else None):
                    raise sync_git.SyncBlocked('generated instruction edit requires its canonical source: ' + name)
            continue
        owner = None
        parts = Path(name).parts
        if len(parts) >= 3 and parts[0] == 'skills' and path.suffix.lower() == '.md':
            owner = capability_owners.get(parts[1])
            if owner != 'skills/' + parts[1]:
                raise sync_git.SyncBlocked('unowned instruction capability: ' + name)
        elif name in owners or name.startswith('surfaces/') or name in ADAPTERS:
            owner = owners.get(name, name if name.startswith('adapters/') else None)
            if not owner:
                raise sync_git.SyncBlocked('unowned standing instruction source: ' + name)
        elif path.name.upper() in {'AGENTS.MD', 'SOUL.MD', 'RULES.MD', 'SKILL.MD'}:
            owner = native_owners.get(name, owners.get(name))
            if not owner:
                raise sync_git.SyncBlocked('unowned instruction source: ' + name)
        if owner:
            old = _before(source, base, name)
            new = path.read_bytes() if path.is_file() else None
            if old != new:
                required[name] = (owner, _hash(old), _hash(new))
    dependencies = _dependency_review(candidate, source, base, paths, required)
    if not required:
        return dependencies
    records = []
    reconciliation_records = []
    for name in sorted(paths):
        if name.startswith('evals/results/') and name.endswith('.json') and (candidate / name).is_file():
            value = json.loads((candidate / name).read_bytes())
            if isinstance(value, dict):
                reconciliation_records.extend(value.get('change_reconciliation', []))
            if isinstance(value, dict) and 'instruction_changes' in value:
                rows = value['instruction_changes']
                if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                    raise sync_git.SyncBlocked('invalid instruction change evidence: ' + name)
                records.extend((name, row) for row in rows)
    used = []
    loading_rows = {}
    measurement_rows = []
    for name, (owner, old_hash, new_hash) in sorted(required.items()):
        matches = [(receipt, row) for receipt, row in records
                   if isinstance(row.get('artifacts'), dict) and name in row['artifacts']]
        if len(matches) != 1:
            raise sync_git.SyncBlocked('instruction change requires one bound necessity record: ' + name)
        receipt, row = matches[0]
        if row.get('owner') != owner:
            raise sync_git.SyncBlocked('instruction change has the wrong architectural owner: ' + name)
        binding = row['artifacts'][name]
        if binding != {'before_sha256': old_hash, 'after_sha256': new_hash}:
            raise sync_git.SyncBlocked('instruction necessity record is not bound to changed bytes: ' + name)
        kind = row.get('change_kind', 'add-or-change')
        if kind not in {'add-or-change', 'remove', 'contract-correction'}:
            raise sync_git.SyncBlocked('invalid instruction change kind: ' + name)
        if kind == 'remove':
            old_data = _before(source, base, name)
            new_data = (candidate / name).read_bytes() if (candidate / name).is_file() else b''
            old_lines = iter((old_data or b'').decode('utf-8').splitlines())
            if any(not any(old_line == line for old_line in old_lines)
                   for line in new_data.decode('utf-8').splitlines()):
                raise sync_git.SyncBlocked('instruction removal contains added or rewritten content: ' + name)
            if not isinstance(row.get('baseline_sufficient'), bool):
                raise sync_git.SyncBlocked('instruction removal has no baseline assessment: ' + name)
        elif row.get('baseline_sufficient') is not False:
            raise sync_git.SyncBlocked('instruction change rejected: baseline is sufficient or unassessed: ' + name)
        if row.get('basis') not in {'user-correction', 'observed-deviation', 'mechanical-maintenance'}:
            raise sync_git.SyncBlocked('instruction change has no supported basis: ' + name)
        if any(not isinstance(row.get(key), str) or not row[key].strip()
               for key in ('deviation', 'evidence', 'why_instruction', 'alternative')):
            raise sync_git.SyncBlocked('instruction change has incomplete architectural reasoning: ' + name)
        measurement_rows.append((name, owner, row))
        used.append({'path': name, 'owner': owner, 'receipt': receipt})
        rows, changed = loading_rows.setdefault(owner, ({}, set()))
        rows[id(row)] = row
        changed.add(name)
    for owner, (rows, changed) in loading_rows.items():
        if not owner.startswith('skills/'):
            continue
        if any('restructured' in row and not isinstance(row['restructured'], bool) for row in rows.values()):
            raise sync_git.SyncBlocked('instruction restructuring declaration must be boolean: ' + owner)
        reviews = [row['loading_review'] for row in rows.values() if 'loading_review' in row]
        if len(reviews) > 1:
            raise sync_git.SyncBlocked('loading review requires one owner-level map: ' + owner)
        assessment = {'restructured': any(row.get('restructured') is True for row in rows.values())}
        if reviews:
            assessment['loading_review'] = reviews[0]
        _loading_review(candidate, source, base, owner, assessment, changed)
    for name, owner, row in measurement_rows:
        eligibility = correction_eligibility(candidate, source, name, owner, row, base, paths, reconciliation_records)
        if eligibility is None:
            eligibility = measurement_eligibility(candidate, source, name, owner, row, base)
        if not eligibility['eligible']:
            raise sync_git.SyncBlocked(eligibility['reason'] + ': ' + name)
    return used + dependencies
