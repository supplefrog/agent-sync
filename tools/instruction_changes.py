"""Check architectural ownership and bound necessity before instruction publication.

This validates evidence records, not semantic benefit or human authenticity.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import sync_git

INDEX = 'contracts/instruction-surfaces.json'
GENERATED = {'recovery/current/hosts/codex/AGENTS.md',
             'recovery/current/hosts/hermes/SOUL.md'}


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


def check(candidate: Path, source: Path, base: str, paths):
    paths = set(paths)
    old_index = _before(source, base, INDEX)
    current = candidate / INDEX
    before = json.loads(old_index) if old_index is not None else {}
    after = json.loads(current.read_bytes()) if current.is_file() else {}
    # V1 inventories predate declared standing-source ownership. Preserve that
    # migration boundary; a V2 baseline cannot evade this check by deleting it.
    if max(before.get('schema_version', 0), after.get('schema_version', 0)) < 2:
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
    for source_name in ('surfaces/core.md', 'adapters/codex.json', 'adapters/hermes.json'):
        if source_name in paths:
            source_path = candidate / source_name
            new_source = source_path.read_bytes() if source_path.is_file() else None
            if _before(source, base, source_name) != new_source:
                source_changes.add(source_name)
    required = {}
    for name in paths:
        path = candidate / name
        if name in GENERATED:
            host_adapter = 'adapters/codex.json' if '/codex/' in name else 'adapters/hermes.json'
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
        elif name in owners or name.startswith('surfaces/') or name in {'adapters/codex.json', 'adapters/hermes.json'}:
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
    if not required:
        return []
    records = []
    for name in sorted(paths):
        if name.startswith('evals/results/') and name.endswith('.json') and (candidate / name).is_file():
            value = json.loads((candidate / name).read_bytes())
            if isinstance(value, dict) and 'instruction_changes' in value:
                rows = value['instruction_changes']
                if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                    raise sync_git.SyncBlocked('invalid instruction change evidence: ' + name)
                records.extend((name, row) for row in rows)
    used = []
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
        if kind not in {'add-or-change', 'remove'}:
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
        used.append({'path': name, 'owner': owner, 'receipt': receipt})
    return used
