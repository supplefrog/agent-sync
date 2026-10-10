"""Read-only behavior-contract coverage; metadata never proves quality or authority."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

import jsonschema


def validate_contracts(repo: Path, surface: dict) -> list[str]:
    if 'behavior_contracts' not in surface:
        return []
    contracts = surface.get('behavior_contracts', [])
    schema = json.loads((repo / 'contracts/surface-matrix.schema.json').read_text(encoding='utf-8'))
    definition = schema['properties'].get('behavior_contracts')
    if definition is None:
        return [] if 'behavior_contracts' not in surface else ['behavior contracts: unsupported schema']
    errors = [f'behavior contracts: {error.message}' for error in
              jsonschema.Draft202012Validator(definition).iter_errors(contracts)]
    if errors:
        return errors
    seen = set()
    for contract in contracts:
        identity = contract['id']
        if identity in seen:
            errors.append(f'behavior contracts: duplicate id: {identity}')
        seen.add(identity)
        for owner in contract['owners']:
            relative = PurePosixPath(owner)
            path = repo / owner
            if (relative.is_absolute() or '..' in relative.parts or '\\' in owner
                    or ':' in owner or not path.resolve().is_relative_to(repo.resolve())
                    or not path.exists()):
                errors.append(f'behavior contracts: invalid owner: {identity}: {owner}')
    return errors


def report(repo: Path) -> dict:
    surface_path = repo / 'contracts/surface-matrix.json'
    ownership_path = repo / 'contracts/ownership.json'
    surface = json.loads(surface_path.read_text(encoding='utf-8'))
    ownership = json.loads(ownership_path.read_text(encoding='utf-8'))
    ownership_schema_path = repo / 'contracts/ownership.schema.json'
    ownership_schema = json.loads(ownership_schema_path.read_text(encoding='utf-8'))
    ownership_errors = list(jsonschema.Draft202012Validator(ownership_schema).iter_errors(ownership))
    if ownership_errors:
        raise ValueError('behavior coverage ownership: ' + ownership_errors[0].message)
    capabilities = ownership['capabilities']
    ids = [item['id'] for item in capabilities]
    if len(ids) != len(set(ids)):
        raise ValueError('behavior coverage ownership: duplicate capability id')
    registry_path = repo / 'registry.json'
    registry = json.loads(registry_path.read_text(encoding='utf-8'))
    skills = registry.get('skills') if isinstance(registry, dict) else None
    if (not isinstance(skills, list) or any(not isinstance(item, dict)
            or not isinstance(item.get('name'), str) or not isinstance(item.get('status'), str)
            for item in skills)):
        raise ValueError('behavior coverage ownership: invalid registry inventory')
    if (len({item['name'] for item in skills}) != len(skills)
            or {item['name']: item['status'] for item in skills}
            != {item['id']: item['status'] for item in capabilities}):
        raise ValueError('behavior coverage ownership: registry and ownership inventory differ')
    if any(item['owner'] != 'skills/' + item['id'] or not (repo / item['owner'] / 'SKILL.md').is_file()
           for item in capabilities):
        raise ValueError('behavior coverage ownership: invalid capability owner')
    errors = validate_contracts(repo, surface)
    if errors:
        raise ValueError('; '.join(errors))
    contracts = surface.get('behavior_contracts', [])
    rows = []
    for capability in sorted(capabilities, key=lambda item: item['id']):
        if capability['status'] != 'admitted':
            continue
        matches = [item for item in contracts if item['scope'] == 'task-type'
                   and capability['owner'] in item['owners']]
        confirmed = [item['id'] for item in matches if item['authority']['status'] == 'user-confirmed']
        inferred = [item['id'] for item in matches if item['authority']['status'] == 'inferred']
        rows.append({'capability': capability['id'], 'owner': capability['owner'],
                     'purpose_recorded': 'purpose' in capability,
                     'contract_metadata': 'user-confirmed' if confirmed else 'inferred' if inferred else 'missing',
                     'confirmed_contracts': confirmed, 'inferred_contracts': inferred,
                     'existing_selection_evidence': capability['selection_evidence']})
    return {'schema_version': 1, 'mode': 'behavior-contract-coverage',
            'bindings': {path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in (surface_path, ownership_path, registry_path, ownership_schema_path,
                                      repo / 'contracts/surface-matrix.schema.json')},
            'contracts': contracts, 'admitted_capabilities': rows,
            'summary': {'admitted_capabilities': len(rows),
                        'purpose_recorded': sum(row['purpose_recorded'] for row in rows),
                        'task_contract_missing': sum(row['contract_metadata'] == 'missing' for row in rows),
                        'task_contract_inferred': sum(row['contract_metadata'] == 'inferred' for row in rows),
                        'task_contract_user_confirmed': sum(row['contract_metadata'] == 'user-confirmed' for row in rows)},
            'limits': ['Coverage indexes recorded metadata, not actual behavior, benefit, parity or authenticated human approval.',
                       'A system contract does not fill a task-type contract gap. Legacy prose and evidence may still contain useful requirements.',
                       'Missing records require evidence-led reconstruction and focused human clarification; they do not authorize retirement or require inference trials.',
                       'Use existing causal evidence and direct checks first; reuse the existing comparator only for a decision-changing behavioral uncertainty.'],
            'promotion_authority': False, 'inference_performed': False}
