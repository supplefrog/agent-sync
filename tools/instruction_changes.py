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
NATIVE_LEARNING_OWNER = 'integrations/hermes-native-learning'
NATIVE_LEARNING_REFERENCE = NATIVE_LEARNING_OWNER + '/skills/hermes-native-learning/SKILL.md'
NATIVE_LEARNING_MANIFEST_SHA256 = 'de0e5cf960ac6bc7c1cc849dde7bd72d12a94ea6e71cb62c7a275bbfb4313a9f'
NATIVE_LEARNING_INDEX_SHA256 = '5622e7debb2e435f34fa63593995edce5bdf393dbdd9a951933dc73c67165032'
NATIVE_LEARNING_MAINTENANCE_MANIFEST_SHA256 = '45ff625bff312262629c44be2d7aa7f6ebcf22614d6fcfec0827639c3a49f80e'

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
        # Preserve existing roles; only declared supported role additions qualify.
        additions = {'coordinator', 'computer_use'}
        if not set(old_roles) <= set(new_roles) or set(new_roles) - set(old_roles) - additions:
            return False
        changed = {k for k in new_roles if k not in old_roles or old_roles[k] != new_roles[k]}
        if changed != set(roles) or not changed <= (set(old_roles) | additions):
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


def _approved_reference_transport(candidate, source, name, owner, row, base, paths):
    """One explicitly approved transport, not a reusable prose-adoption waiver.

    The fixed published bytes and URL define this authorization's whole scope.
    This proves content identity and package loading, not natural selection,
    behavioral benefit, or authenticity of the recorded user authorization.
    """
    entry = 'skills/instruction-authoring/SKILL.md'
    document = 'docs/system-requirements.md'
    resource = 'skills/instruction-authoring/references/claim-based-testing-and-retirement.md'
    old_url = b'../../docs/system-requirements.md#claim-based-testing-and-retirement'
    new_url = b'references/claim-based-testing-and-retirement.md#claim-based-testing-and-retirement'
    if (owner != 'skills/instruction-authoring' or name not in {entry, resource}
            or row.get('basis') != 'user-correction'
            or row.get('user_authorized_transport') is not True
            or not {entry, resource} <= set(paths)):
        raise sync_git.SyncBlocked('reference transport is outside the explicit approved repair')
    before = _before(source, base, entry)
    published = _before(source, base, document)
    after = candidate / entry
    packaged = candidate / resource
    canonical = candidate / document
    if any(not f.is_file() or f.is_symlink() for f in (after, packaged, canonical)):
        raise sync_git.SyncBlocked('reference transport requires regular source and package files')
    source_bytes, entry_bytes, resource_bytes = canonical.read_bytes(), after.read_bytes(), packaged.read_bytes()
    if (_hash(before) != 'd9f488eb442c862ac4a8e60ae80dfd3dd990baa8ff5183d4ccf77326c81069e5'
            or _hash(published) != '0f7f45a2e9fcdf24a142840e14efea5b9743f13a318cc12e9ae7a98940c4b309'
            or source_bytes != published
            or _before(source, base, resource) is not None
            or before.count(old_url) != 1
            or entry_bytes != before.replace(old_url, new_url)
            or _hash(entry_bytes) != 'efa9a626ea0683fc5bd5305107511f8a03f1b90a89c232230457288d8a357fed'):
        raise sync_git.SyncBlocked('reference transport changes the approved published source or link-only repair')
    section = re.search(rb'^## Claim-based testing and retirement\r?\n.*?(?=^## |\Z)', published, re.M | re.S)
    if (section is None or resource_bytes != section.group()
            or _hash(resource_bytes) != 'fce6e25097ec08dcb3fce3ccf9b99c02efaa4462b91bd9f92eb251dce303670e'):
        raise sync_git.SyncBlocked('reference transport must copy the exact approved published section')
    # Check the actual package validator as well as the normal owner loading map.
    # The unchanged link label/decision point plus exact target heading preserves
    # this address; this is not evidence of natural triggering by a model.
    if validate.validate_skill(after):
        raise sync_git.SyncBlocked('reference transport package loading validation failed')
    return 'explicitly authorized exact published reference transport with checked package loading'


def _approved_requested_import(candidate, source, name, owner, row, base, paths):
    """Bind an initial instruction-only installation to locally available Git blobs.

    Source authenticity and human authorization remain the caller's responsibility.
    No upstream code is executed and no runtime activation is authorized here.
    """
    import fleet
    acceptance = row.get('requested_import_acceptance', {})
    if not isinstance(owner, str) or not isinstance(name, str):
        raise sync_git.SyncBlocked('requested import requires a canonical owner')
    package = owner.removeprefix('skills/')
    if (not re.fullmatch(r'skills/[a-z0-9]+(?:-[a-z0-9]+)*', owner)
            or row.get('basis') != 'user-correction'
            or not name.startswith(owner + '/') or not isinstance(acceptance, dict)
            or acceptance.get('classification') != 'requested-instruction-package'
            or acceptance.get('runtime_activation') is not False
            or acceptance.get('model_benefit_claim') is not False
            or set(acceptance) != {'classification', 'source_repository', 'source_commit', 'source_path',
                                   'license', 'package_sha256', 'files', 'runtime_activation',
                                   'model_benefit_claim', 'deployment_checks_required'}):
        raise sync_git.SyncBlocked('requested import requires explicit instruction-only acceptance')
    repo, pin, upstream = (acceptance.get(k) for k in ('source_repository', 'source_commit', 'source_path'))
    license = acceptance.get('license')
    if (not isinstance(repo, str) or not re.fullmatch(r'https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo)
            or not isinstance(pin, str) or not re.fullmatch(r'[0-9a-f]{40}', pin)
            or not isinstance(upstream, str) or sync_git.safe_path(candidate, upstream + "/SKILL.md") != upstream + "/SKILL.md"
            or not isinstance(license, str) or not re.fullmatch(r'[A-Za-z0-9.+-]+', license)):
        raise sync_git.SyncBlocked('requested import requires an immutable source pin, path and license')
    if sync_git.git(source, 'cat-file', '-t', pin) != 'commit':
        raise sync_git.SyncBlocked('requested import source pin must be a commit object')
    if acceptance.get('deployment_checks_required') != ['native-hermes-codex-omp-catalogue-body', 'repeat-sync-preserves-source']:
        raise sync_git.SyncBlocked('requested import must retain native loading and repeat-sync checks')
    files = acceptance.get('files')
    actual = fleet.directory_record(candidate / owner)
    disk_files = {p.relative_to(candidate / owner).as_posix()
                  for p in (candidate / owner).rglob('*') if p.is_file()}
    if disk_files != set(actual['files']):
        raise sync_git.SyncBlocked('requested import cannot contain ignored or transient extra files')
    if (not isinstance(files, dict) or set(files) != set(actual['files'])
            or not {'SKILL.md', 'LICENSE'} <= set(files)
            or actual['sha256'] != acceptance.get('package_sha256')
            or not {owner + '/' + f for f in files} <= set(paths)):
        raise sync_git.SyncBlocked('requested import requires the complete selected package')
    baseline = sync_git.git(source, 'ls-tree', '-r', '--name-only', base, '--', owner)
    if baseline:
        raise sync_git.SyncBlocked('requested import cannot change an existing source package')
    # A source path denotes a complete package, not a handpicked projection.
    upstream_names = set(sync_git.git(source, 'ls-tree', '-r', '--name-only', pin, '--', upstream).splitlines())
    bound = set()
    for relative, binding in files.items():
        target = owner + '/' + relative
        if (sync_git.safe_path(candidate, target) != target
                or (Path(relative).suffix.lower() != '.md' and relative != 'LICENSE')
                or not isinstance(binding, dict)
                or set(binding) != {'upstream_path', 'upstream_sha256', 'installed_sha256', 'transformation'}):
            raise sync_git.SyncBlocked('requested import permits only bound Markdown and LICENSE files')
        origin = binding['upstream_path']
        if (not isinstance(origin, str) or sync_git.safe_path(candidate, origin) != origin
                or (relative != 'LICENSE' and origin != upstream + '/' + relative)
                or origin in bound):
            raise sync_git.SyncBlocked('requested import has invalid upstream file mapping')
        bound.add(origin)
        mode = sync_git.git(source, 'ls-tree', pin, '--', origin).split()
        if not mode or mode[0] != '100644':
            raise sync_git.SyncBlocked('requested import upstream must contain regular nonexecutable files')
        original = _before(source, pin, origin)
        installed = (candidate / target).read_bytes()
        expected = original
        transformation = binding['transformation']
        if transformation == 'license-frontmatter' and relative == 'SKILL.md' and original is not None:
            if not original.startswith(b'---\n') or b'\n---\n' not in original[4:]:
                raise sync_git.SyncBlocked('requested import requires LF YAML frontmatter for license insertion')
            front, rest = original[4:].split(b'\n---\n', 1)
            if re.search(rb'^license\s*:', front, re.M):
                raise sync_git.SyncBlocked('requested import cannot replace an upstream license field')
            expected = b'---\n' + front + b'\nlicense: ' + license.encode() + b'\n---\n' + rest
        elif transformation != 'identity':
            raise sync_git.SyncBlocked('requested import has an unsupported transformation')
        if (original is None or _hash(original) != binding['upstream_sha256']
                or _hash(installed) != binding['installed_sha256'] or installed != expected):
            raise sync_git.SyncBlocked('requested import differs from the pinned upstream bytes')
    if not upstream_names or upstream_names - bound:
        raise sync_git.SyncBlocked('requested import omits upstream package files')
    registered = fleet.registry(candidate).get(package, {})
    old_registry = json.loads(_before(source, base, 'registry.json'))
    if (any(r['name'] == package for r in old_registry['skills'])
            or registered.get('status') != 'admitted' or registered.get('license') != license
            or registered.get('source') != repo + '/tree/' + pin + '/' + upstream):
        raise sync_git.SyncBlocked('requested import registry does not match its new source pin')
    metadata, _ = validate.frontmatter((candidate / owner / 'SKILL.md').read_text(encoding='utf-8'))
    if metadata.get('license') != license:
        raise sync_git.SyncBlocked('requested import license disagrees with skill frontmatter')
    ownership = json.loads((candidate / 'contracts/ownership.json').read_bytes())
    if [r.get('owner') for r in ownership.get('capabilities', []) if r.get('id') == package] != [owner]:
        raise sync_git.SyncBlocked('requested import requires one canonical capability owner')
    if validate.validate_skill(candidate / owner / 'SKILL.md'):
        raise sync_git.SyncBlocked('requested import package validation failed')
    return 'explicitly requested pinned instruction package'


def _approved_requested_edit(candidate, source, name, owner, row, base, paths):
    """Bind a user-selected prose edit of an existing admitted portable owner.

    This checks scope and bytes, not human authenticity or model benefit.
    Executable, metadata, ownership and lifecycle changes retain their gates.
    """
    import fleet
    acceptance = row.get('requested_edit_acceptance')
    keys = {'classification', 'baseline_commit', 'license', 'before_package_sha256',
            'after_package_sha256', 'files', 'runtime_activation', 'model_benefit_claim',
            'deployment_checks_required'}
    if (not isinstance(owner, str) or not re.fullmatch(r'skills/[a-z0-9]+(?:-[a-z0-9]+)*', owner)
            or not isinstance(name, str) or not name.startswith(owner + '/')
            or row.get('basis') != 'user-correction' or not isinstance(acceptance, dict)
            or set(acceptance) != keys
            or acceptance.get('classification') != 'requested-existing-instruction-edit'
            or not isinstance(acceptance.get('baseline_commit'), str)
            or not re.fullmatch(r'[0-9a-f]{40}', acceptance['baseline_commit'])
            or not isinstance(acceptance.get('license'), str)
            or not re.fullmatch(r'[A-Za-z0-9.+-]+', acceptance['license'])
            or acceptance.get('runtime_activation') is not False
            or acceptance.get('model_benefit_claim') is not False
            or acceptance.get('deployment_checks_required') !=
                ['native-hermes-codex-omp-catalogue-body', 'repeat-sync-preserves-source']):
        raise sync_git.SyncBlocked('requested edit requires explicit source-bound instruction-only acceptance')
    reviewed = acceptance['baseline_commit']
    # Publication composes onto the current remote. Keep the reviewed identity
    # immutable while permitting unrelated commits between review and rollout.
    try:
        ancestor = (sync_git.git(source, 'cat-file', '-t', reviewed) == 'commit'
                    and sync_git.git(source, 'merge-base', reviewed, base) == reviewed)
    except sync_git.GitFailure as exc:
        raise sync_git.SyncBlocked('requested edit cannot resolve its reviewed ancestor commit') from exc
    if not ancestor:
        raise sync_git.SyncBlocked('requested edit requires a real reviewed ancestor commit')
    if (sync_git.git(source, 'ls-tree', '-r', '-z', reviewed, '--', owner) !=
            sync_git.git(source, 'ls-tree', '-r', '-z', base, '--', owner)):
        raise sync_git.SyncBlocked('requested edit reviewed package changed before publication')
    registry_bytes = _before(source, base, 'registry.json')
    if registry_bytes != (candidate / 'registry.json').read_bytes():
        raise sync_git.SyncBlocked('requested edit cannot change registry or lifecycle')
    package = owner.removeprefix('skills/')
    registered = fleet.registry(candidate).get(package, {})
    reviewed_registry_bytes = _before(source, reviewed, 'registry.json')
    if reviewed_registry_bytes is None:
        raise sync_git.SyncBlocked('requested edit requires a reviewed admission registry')
    reviewed_registry = fleet.registry(candidate, captured=reviewed_registry_bytes)
    if (registered != reviewed_registry.get(package) or registered.get('status') != 'admitted'
            or registered.get('license') != acceptance['license']):
        raise sync_git.SyncBlocked('requested edit requires an existing admitted owner and unchanged license')
    for data in (_before(source, reviewed, 'contracts/ownership.json'),
                 _before(source, base, 'contracts/ownership.json'),
                 (candidate / 'contracts/ownership.json').read_bytes()):
        if data is None or [r.get('owner') for r in json.loads(data).get('capabilities', [])
                            if r.get('id') == package] != [owner]:
            raise sync_git.SyncBlocked('requested edit requires the existing canonical capability owner')
    entries = sync_git.git(source, 'ls-tree', '-r', '-z', base, '--', owner).split('\0')
    before_files = {}
    modes = {}
    for entry in filter(None, entries):
        metadata, target = entry.split('\t', 1)
        relative = target.removeprefix(owner + '/')
        modes[relative] = metadata.split()[0]
        before_files[relative] = _hash(_before(source, base, target))
    actual = fleet.directory_record(candidate / owner)
    disk_files = {p.relative_to(candidate / owner).as_posix()
                  for p in (candidate / owner).rglob('*') if p.is_file()}
    files = acceptance['files']
    if (not isinstance(files, dict) or not before_files or set(files) != set(before_files)
            or set(files) != set(actual['files']) or disk_files != set(files)):
        raise sync_git.SyncBlocked('requested edit requires the complete unchanged package file set')
    digest = hashlib.sha256()
    changed = {}
    # Match directory_record's native Path ordering on both Windows and POSIX.
    for relative in sorted(files, key=Path):
        target = owner + '/' + relative
        if sync_git.safe_path(candidate, target) != target:
            raise sync_git.SyncBlocked('requested edit has an invalid package address')
        expected = {'before_sha256': before_files[relative], 'after_sha256': actual['files'][relative]}
        if files[relative] != expected:
            raise sync_git.SyncBlocked('requested edit has stale package bytes')
        digest.update(relative.encode('utf-8') + b'\0' + bytes.fromhex(before_files[relative]))
        if expected['before_sha256'] != expected['after_sha256']:
            if (Path(relative).suffix.lower() != '.md' or modes[relative] != '100644'
                    or target not in paths):
                raise sync_git.SyncBlocked('requested edit permits only selected existing nonexecutable Markdown edits')
            changed[target] = expected
    if (name not in changed or row.get('artifacts') != changed
            or acceptance['before_package_sha256'] != digest.hexdigest()
            or acceptance['after_package_sha256'] != actual['sha256']):
        raise sync_git.SyncBlocked('requested edit requires exact full-package and changed-source bindings')
    entry = owner + '/SKILL.md'
    import yaml
    def parsed_metadata(data):
        text = data.decode('utf-8').replace('\r\n', '\n')
        if not text.startswith('---\n') or '\n---\n' not in text[4:]:
            raise sync_git.SyncBlocked('requested edit requires skill frontmatter')
        class UniqueLoader(yaml.SafeLoader):
            pass
        def unique_mapping(loader, node):
            result = {}
            for key, value in node.value:
                key = loader.construct_object(key)
                if not isinstance(key, str) or key in result:
                    raise sync_git.SyncBlocked('requested edit has invalid or duplicate metadata keys')
                result[key] = loader.construct_object(value)
            return result
        UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)
        try:
            metadata = yaml.load(text[4:].split('\n---\n', 1)[0], Loader=UniqueLoader)
        except yaml.YAMLError as exc:
            raise sync_git.SyncBlocked('requested edit has invalid skill metadata') from exc
        if not isinstance(metadata, dict):
            raise sync_git.SyncBlocked('requested edit requires structured skill frontmatter')
        return metadata
    old_metadata = parsed_metadata(_before(source, base, entry))
    new_metadata = parsed_metadata((candidate / entry).read_bytes())
    def stable_metadata(metadata):
        metadata = dict(metadata)
        nested = metadata.get('metadata', {})
        if not isinstance(nested, dict):
            raise sync_git.SyncBlocked('requested edit requires structured skill metadata')
        nested = dict(nested)
        for version in (metadata.get('version'), nested.get('version')):
            if version is not None and (isinstance(version, bool) or not isinstance(version, (str, int, float))):
                raise sync_git.SyncBlocked('requested edit requires informational version metadata')
        compatibility = metadata.pop('compatibility', None)
        if 'compatibility' in nested:
            if compatibility is not None and compatibility != nested['compatibility']:
                raise sync_git.SyncBlocked('requested edit has conflicting compatibility declarations')
            compatibility = nested.pop('compatibility')
        metadata.pop('version', None)
        nested.pop('version', None)
        metadata['compatibility'] = compatibility
        metadata['metadata'] = nested
        return metadata
    if (stable_metadata(old_metadata) != stable_metadata(new_metadata) or old_metadata.get('name') != package
            or old_metadata.get('license') != acceptance['license']):
        raise sync_git.SyncBlocked('requested edit cannot change skill metadata or license')
    if validate.validate_skill(candidate / entry):
        raise sync_git.SyncBlocked('requested edit package validation failed')
    return 'explicitly requested existing-owner instruction edit'


def requested_import_owners(candidate, source, base, paths):
    """Return only source-bound new owners from selected necessity receipts."""
    owners = set()
    for name in paths:
        if name.startswith('evals/results/') and name.endswith('.json') and (candidate / name).is_file():
            value = json.loads((candidate / name).read_bytes())
            if not isinstance(value, dict):
                raise sync_git.SyncBlocked('invalid instruction change evidence: ' + name)
            rows = value.get('instruction_changes', [])
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise sync_git.SyncBlocked('invalid instruction change evidence: ' + name)
            for row in rows:
                if row.get('change_kind') != 'requested-import':
                    continue
                owner = row.get('owner', '')
                if not isinstance(owner, str):
                    raise sync_git.SyncBlocked('requested import requires a canonical owner')
                _approved_requested_import(candidate, source, owner + '/SKILL.md', owner, row, base, paths)
                if 'behavior_measurements' in row or 'task_contract' in row:
                    raise sync_git.SyncBlocked('requested import cannot carry behavioral-adoption claims')
                owners.add(owner.removeprefix('skills/'))
    return owners


def _approved_requested_reader(candidate, source, name, owner, row, base, paths):
    """Exact user-selected LearnHarness installation; no comparative authority.

    Package/evidence declarations are checked after normal source/owner/loading
    review. They do not authenticate approval, execution or semantic adequacy.
    Any changed reader, other owner or behavioral-benefit claim remains excluded.
    """
    import fleet
    package = 'skills/learnharness'
    pin = '6cba9c8c5afe8a63f47ea4ebae6e91d8a205cebb'
    expected = {'LICENSE': '0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0', 'SKILL.md': '0f29a1a5bd9c6f629d76ec442c78799b9d95a83a0322c3a84e71c2c442df09bb', 'references/data-format.md': 'b34f020e9cca38950548c9e21e8cdf86df35d781154bcf2942fe3e323553d926', 'scripts/_data.py': 'fb4abe3f3e99133a9f5a6e28a0733437d1ec37b5e92ba8413102911145cd2883', 'scripts/graph.py': '95d05acebef77764a215439a95b39b1bc0a81d2595c67349d90053e548e236ed', 'scripts/sessions.py': '864368dfde5a8c7550ebf80ec77671d9f159f80c0859b248cce20fe799b95dc7'}
    required = {package + '/' + relative for relative in expected}
    acceptance = row.get('reader_acceptance')
    checks = {'source-pin-and-license', 'package-validation',
              'synthetic-session-and-graph-results', 'source-bytes-mtimes-tree-unchanged',
              'synthetic-only-no-credentials-network-app', 'explicit-local-fork-data-dir'}
    if (owner != package or name not in {package + '/SKILL.md', package + '/references/data-format.md'}
            or row.get('basis') != 'user-correction' or not required <= set(paths)
            or not isinstance(acceptance, dict)
            or acceptance.get('classification') != 'requested-read-only-capability'
            or acceptance.get('upstream_commit') != pin
            or acceptance.get('package_sha256') != '3cc55b7c53159b111a0b791e46f65305b8a0449c5d94fccd0c69953520970f32'
            or acceptance.get('model_benefit_claim') is not False):
        raise sync_git.SyncBlocked('requested reader is outside the approved capability installation')
    verified = acceptance.get('verified_checks')
    if (not isinstance(verified, list) or any(not isinstance(v, str) for v in verified)
            or len(verified) != len(set(verified)) or set(verified) != checks):
        raise sync_git.SyncBlocked('requested reader lacks source-bound read-only/privacy acceptance')
    if acceptance.get('deployment_checks_required') != ['native-hermes-codex-omp-catalogue-body', 'repeat-sync-preserves-source']:
        raise sync_git.SyncBlocked('requested reader must retain native loading and repeat-sync verification')
    if any(_before(source, base, path) is not None for path in required):
        raise sync_git.SyncBlocked('requested reader category cannot authorize changed deployed instructions')
    actual = fleet.directory_record(candidate / package)
    if actual['files'] != expected or actual['sha256'] != acceptance['package_sha256']:
        raise sync_git.SyncBlocked('requested reader differs from the exact approved upstream package')
    rows = [item for item in fleet.registry(candidate).values() if item.get('name') == 'learnharness']
    if (len(rows) != 1 or rows[0].get('status') != 'admitted' or rows[0].get('license') != 'AGPL-3.0-only'
            or rows[0].get('source') != 'https://github.com/amosblomqvist/learnharness@' + pin):
        raise sync_git.SyncBlocked('requested reader registry/provenance does not match its approved pin')
    if validate.validate_skill(candidate / package / 'SKILL.md'):
        raise sync_git.SyncBlocked('requested reader package validation failed')
    return 'explicitly requested pinned read-only reader; functional acceptance, no comparative model-benefit claim'


PUBLIC_AUDIENCE_PAIR = {
    'surfaces/core.md': ('surfaces/core.md',
        '06cc6b8c34a148116d42aff8aac8e515a16c2f6ae72373732baaec2e6d9d62c3',
        '994ce832c51ef670cf0a65b760719e2d2ca8214e82e44cf0f2fe976e35b75051'),
    'skills/humanizer/SKILL.md': ('skills/humanizer',
        '7b087ef814d61896cd6e8ba13996158bfd7648098f5357a65b782668b9388729',
        '03ae59a428b8723ccc73798d57088b98ce403b6c442b5eddba2b08b2c5be457f'),
}
PUBLIC_AUDIENCE_ACCEPTANCE = {
    'decision': 'public-audience-r2-20261026',
    'source_freeze_sha256': 'd3bf90395bd133d5bd359d024e892e203c45100d35948d7ade7a742189d0656a',
    'recovery_freeze_sha256': 'b8e9dfc51e8235edbfd373400cebdd83b1d495f6af87f6fbfa306359ea73bb34',
    'no_behavioral_improvement_claim': True,
}


def _approved_public_audience(candidate, source, name, owner, row, base, paths, reconciliations):
    """One exact user-approved correction; records do not authenticate approval."""
    required = set(PUBLIC_AUDIENCE_PAIR) | CONTRACTS
    if (name not in PUBLIC_AUDIENCE_PAIR or owner != PUBLIC_AUDIENCE_PAIR[name][0]
            or row.get('basis') != 'user-correction'
            or row.get('public_audience_acceptance') != PUBLIC_AUDIENCE_ACCEPTANCE
            or row['public_audience_acceptance'].get('no_behavioral_improvement_claim') is not True
            or not required <= set(paths)):
        raise sync_git.SyncBlocked('public audience correction requires the exact approved pair and decision')
    for target, (_, old_hash, new_hash) in PUBLIC_AUDIENCE_PAIR.items():
        path = candidate / target
        if (not path.is_file() or _hash(_before(source, base, target)) != old_hash
                or _hash(path.read_bytes()) != new_hash):
            raise sync_git.SyncBlocked('public audience correction differs from approved source bytes: ' + target)
    bound = [r for r in reconciliations if r.get('requirement_change') is True
             and required <= set(r.get('artifacts', {}))]
    if len(bound) != 1 or any(_before(source, base, n) == (candidate / n).read_bytes() for n in CONTRACTS):
        raise sync_git.SyncBlocked('public audience correction requires bound changed intent and status')
    # Dependency review checks these same bindings and declared authority before this dispatcher.
    return 'exact user-approved public audience R2 correction; source/recovery review, no behavioral proof'


def native_learning_source_reference(repo, name):
    """Recognize one pinned package reference, never a global skill/adoption grant."""
    if name != NATIVE_LEARNING_REFERENCE:
        return False
    try:
        def read(relative):
            if sync_git.safe_path(repo, relative) != relative:
                raise sync_git.SyncBlocked('native reference path is not exact')
            return (repo / relative).read_bytes()
        index_raw = read(INDEX)
        if _hash(index_raw) != NATIVE_LEARNING_INDEX_SHA256:
            return False
        index = json.loads(index_raw)
        rows = [row for row in index['surfaces'] if row.get('artifact') == name]
        expected = {'id': 'learning.native-source.9', 'owner': NATIVE_LEARNING_OWNER,
                    'artifact': name, 'kind': 'portable-reference', 'scope': 'project',
                    'status': 'reference', 'model_sensitive': True, 'backup': 'not-effective',
                    'assembly_order': 0, 'hosts': ['hermes', 'codex']}
        if len(rows) != 1 or any(rows[0].get(key) != value for key, value in expected.items()):
            return False
        manifest_raw = read(NATIVE_LEARNING_OWNER + '/PUBLIC-FILES.json')
        # Preserve original V3 recognition and add only this exact maintained package.
        counts = {NATIVE_LEARNING_MANIFEST_SHA256: (89, 90),
                  NATIVE_LEARNING_MAINTENANCE_MANIFEST_SHA256: (104, 105)}.get(_hash(manifest_raw))
        if counts is None:
            return False
        manifest = json.loads(manifest_raw)
        members = manifest['files']
        if (manifest.get('fileCount') != counts[0] or manifest.get('publicationFileCount') != counts[1]
                or len(members) != counts[0] or len({row['path'] for row in members}) != len(members)):
            return False
        reference = None
        for row in members:
            relative = NATIVE_LEARNING_OWNER + '/' + row['path']
            data = read(relative)
            if _hash(data) != row['sha256'] or len(data) != row['bytes']:
                return False
            if relative == name:
                reference = data
        if reference is None:
            return False
        registry = json.loads(read('registry.json'))
        for row in registry['skills']:
            canonical = 'skills/' + row['name'] + '/SKILL.md'
            if row['name'] == 'hermes-native-learning':
                return False
            if (repo / canonical).is_file():
                # A registered global copy is not the conditional source category,
                # even if its different name or CRLF encoding hides the duplication.
                if read(canonical).replace(b'\r\n', b'\n') == reference.replace(b'\r\n', b'\n'):
                    return False
        if (repo / 'skills/hermes-native-learning/SKILL.md').is_file():
            return False
        return True
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError):
        return False


def _approved_native_learning_source(candidate, source, name, owner, row, base, paths, reconciliations):
    """One pinned requested-capability source package, never an activation grant."""
    prefix = NATIVE_LEARNING_OWNER
    model_sources = ['integrations/hermes-native-learning/docs/KNOWLEDGE.md', 'integrations/hermes-native-learning/docs/MATERIALS-JOBS.md', 'integrations/hermes-native-learning/docs/PROTOCOL.md', 'integrations/hermes-native-learning/reference/planning.md', 'integrations/hermes-native-learning/reference/practice-base.md', 'integrations/hermes-native-learning/reference/practice-doctrine.md', 'integrations/hermes-native-learning/reference/probe-doctrine.md', 'integrations/hermes-native-learning/reference/teacher-cycle.md', 'integrations/hermes-native-learning/reference/teacher-step.md', 'integrations/hermes-native-learning/skills/hermes-native-learning/SKILL.md', 'integrations/hermes-native-learning/t3/AGENT-PROTOCOL.md']
    if owner != prefix or name not in model_sources or row.get("basis") != "user-correction":
        return None
    expected_acceptance = {'manifest_sha256': NATIVE_LEARNING_MANIFEST_SHA256, 'source_review_sha256': 'ec6c83f3e10d58136a8690ff47fee09807415632cac2e490dfa8a36cce2f607a', 'basis': 'requested-capability-source', 'hermes_evidence': 'bounded native walkthrough', 't3_evidence': 'reviewed source/components; no live qualification', 'activation': 'separate', 'behavioral_benefit_claim': False}
    if row.get("native_learning_acceptance") != expected_acceptance:
        raise sync_git.SyncBlocked("native learning source acceptance is not the selected V3 scope")
    manifest_name = prefix + "/PUBLIC-FILES.json"
    manifest_raw = (candidate / manifest_name).read_bytes()
    if _hash(manifest_raw) != expected_acceptance["manifest_sha256"]:
        raise sync_git.SyncBlocked("native learning package manifest mismatch")
    manifest = json.loads(manifest_raw)
    required = {prefix + "/" + item["path"] for item in manifest["files"]} | {manifest_name, INDEX} | CONTRACTS
    if (manifest.get("fileCount") != 89 or manifest.get("publicationFileCount") != 90
            or not required <= set(paths)):
        raise sync_git.SyncBlocked("native learning requires its complete selected package and intent/status")
    for item in manifest["files"]:
        data = (candidate / (prefix + "/" + item["path"])).read_bytes()
        if _hash(data) != item["sha256"] or len(data) != item["bytes"]:
            raise sync_git.SyncBlocked("native learning source bytes differ from the reviewed package")
    if (_hash(_before(source, base, INDEX)) != '8d51deb084b1e361f26d13f7a979fc6887ab44d96a16ed2b6cde561d12867fc5'
            or _hash((candidate / INDEX).read_bytes()) != NATIVE_LEARNING_INDEX_SHA256
            or any(_before(source, base, target) is not None for target in model_sources)):
        raise sync_git.SyncBlocked("native learning source ownership/baseline differs from the selected scope")
    matching = [record for record in reconciliations if record.get("requirement_change") is True
                and (set(model_sources) | {INDEX} | CONTRACTS) <= set(record.get("artifacts", {}))]
    if len(matching) != 1 or any(_before(source, base, target) == (candidate / target).read_bytes() for target in CONTRACTS):
        raise sync_git.SyncBlocked("native learning requires one bound changed-intent record")
    if _hash((candidate / 'docs/system-requirements.md').read_bytes()) != 'd9ff350d7f93ccf161f2bc04cc8f891f8ce19074749e6c6cbf3689139b2de320':
        raise sync_git.SyncBlocked("native learning changes intent outside the selected source decision")
    if _hash((candidate / 'docs/requirement-status.md').read_bytes()) != '0308f47552aa4ddc9ebb97786886d40c524eed5d7b43ab007ac7767e71da21b0':
        raise sync_git.SyncBlocked("native learning changes intent outside the selected source decision")
    for target in set(model_sources) | {INDEX} | CONTRACTS:
        expected = {"before_sha256": _hash(_before(source, base, target)),
                    "after_sha256": _hash((candidate / target).read_bytes())}
        if matching[0]["artifacts"][target] != expected:
            raise sync_git.SyncBlocked("native learning intent/source binding mismatch: " + target)
    return "exact requested native-learning capability source; no runtime activation or behavioral improvement claimed"


def _approved_item_review_maintenance(candidate, source, name, owner, row, base, paths, reconciliations):
    """Closed, explicitly selected operational correction; no behavioral proof."""
    guide = "skills/instruction-authoring/references/item-review-loop.md"
    if (name != guide or owner != "skills/instruction-authoring"
            or row.get("basis") != "user-correction"):
        return None
    pins = {'skills/instruction-authoring/SKILL.md': ('efa9a626ea0683fc5bd5305107511f8a03f1b90a89c232230457288d8a357fed', 'dd2b576f4dd1558d5f7427ebdf589c10f701a8f3d6495e5770da89d55feca41d'), 'skills/instruction-authoring/references/item-review-loop.md': ('absent', '70b4ecf1c7d893fb519aa2907306acb3fea4ef9397a8252adf310a0648ba7e02'), 'docs/system-requirements.md': ('8f9a173ef7f97ed477345d94611ad10f0238c93fad75978102ff80d8dec7de0c', 'd9ff350d7f93ccf161f2bc04cc8f891f8ce19074749e6c6cbf3689139b2de320'), 'docs/requirement-status.md': ('4b547698e601de0c867a2f60dc2fbe9e8c02f493077ecf1ce6c9bf2c31723f5b', '0308f47552aa4ddc9ebb97786886d40c524eed5d7b43ab007ac7767e71da21b0')}
    if not set(pins) <= set(paths):
        raise sync_git.SyncBlocked("item-review maintenance requires both exact products and changed intent/status")
    for path, (old_hash, new_hash) in pins.items():
        target = candidate / path
        current = target.read_bytes() if target.is_file() else None
        if _hash(_before(source, base, path)) != old_hash or _hash(current) != new_hash:
            raise sync_git.SyncBlocked("item-review maintenance is outside the approved byte pairs")
    matching = [record for record in reconciliations if record.get("requirement_change") is True
                and set(pins) <= set(record.get("artifacts", {}))]
    if len(matching) != 1:
        raise sync_git.SyncBlocked("item-review maintenance needs one bound changed-intent record")
    for path, (old_hash, new_hash) in pins.items():
        if matching[0]["artifacts"][path] != {"before_sha256": old_hash, "after_sha256": new_hash}:
            raise sync_git.SyncBlocked("item-review maintenance reconciliation binding mismatch")
    return "exact reviewed item-review operational maintenance"


def _approved_curator_scope_maintenance(candidate, source, name, owner, row, base, paths, reconciliations):
    """Closed source-scope maintenance; no model benefit or lifecycle adoption."""
    products = {'skills/capability-curator/SKILL.md', 'skills/cross-agent-surface-engineering/SKILL.md', 'skills/capability-curator/references/instruction-retirement.md'}
    if (name not in products or owner != 'skills/' + name.split('/')[1]
            or row.get('basis') != 'user-correction'
            or row.get('acceptance_classification') != 'curator-scope-maintenance'):
        return None
    pins = {'skills/capability-curator/SKILL.md': ('d6caa0472e4c29e3295d12a28e4b165c5b55af43b7df5ee4009d7aaa71176ae0', '59ba241f89c096bbbf89be7b102033c87a8eef0b6ecd29d578902789f5833bc5'), 'skills/capability-curator/references/instruction-retirement.md': ('ad16e0493f8ac6a8581d24ff404d8ad818f07b6b06c8792ac6356dad8d3eecaa', 'a3bbe9ee22fbfbb7a1496fc01b9b895dda486f995b7300e7c8350215130bcda4'), 'skills/cross-agent-surface-engineering/SKILL.md': ('c50e56494d5a1b42896ce175acdc6255d32f0643c7138d35170d7d23a2104121', '9031131e8be66964c739fbdcc6701485b64d8c00f8d1bc6d36b2c16f605265da'), 'docs/system-requirements.md': ('e93d09bc37280a07f91369d8c1d5c8377b75483328f3dad7e567c784b762b036', 'c0f6c9b8f0491328358fbf9c4bc0127180b1ff5f4c6d8e89b73f5b5423f79424'), 'docs/requirement-status.md': ('89d7d2275e13eba8d05fb1ae58042c1edcf329f7f134b6d37ac372724e4cbd5c', '6ca8918106373db901efa02926227d974ecaff358a3526326aa1a3fe1f4c3967')}
    if not set(pins) <= set(paths):
        raise sync_git.SyncBlocked('curator maintenance requires the exact products and changed intent/status')
    for target, (before, after) in pins.items():
        path = candidate / target
        if (_hash(_before(source, base, target)) != before
                or _hash(path.read_bytes() if path.is_file() else None) != after):
            raise sync_git.SyncBlocked('curator maintenance differs from reviewed source byte pairs')
    fixed = {'registry.json': '2a56f0366330b79db8cadcb439141f4ff4a4c1b0d700d533a46e22737027711e', 'contracts/ownership.json': 'ce5755cecd713686c77bf6927e646c6a61f9cb9c10e566c5ef1384894adde9f7', 'contracts/instruction-surfaces.json': '5622e7debb2e435f34fa63593995edce5bdf393dbdd9a951933dc73c67165032'}
    for target, identity in fixed.items():
        path = candidate / target
        if (_hash(_before(source, base, target)) != identity
                or not path.is_file() or _hash(path.read_bytes()) != identity):
            raise sync_git.SyncBlocked('curator maintenance cannot change owner, staging or instruction lifecycle')
    matching = [record for record in reconciliations if record.get('requirement_change') is True
                and set(pins) <= set(record.get('artifacts', {}))]
    if len(matching) != 1 or any(matching[0]['artifacts'][target] !=
            {'before_sha256': before, 'after_sha256': after} for target, (before, after) in pins.items()):
        raise sync_git.SyncBlocked('curator maintenance requires one exact changed-intent reconciliation')
    return 'exact reviewed curator scope maintenance; staging, ownership and retirement safeguards retained'


def _approved_retirement_maintenance(candidate, source, name, owner, row, base, paths, retirement):
    """One exact user-directed retirement; no generic measurement waiver.

    Hashes and recorded authority establish consistency, never authenticate the
    human. The separately scope-bound operation review and normal action-time
    approval remain mandatory at the retirement entrypoint.
    """
    selected_owner = 'outcome-first-workflow-design'
    reviewed_base = '51f43f68dd45e51f6222a68d3e90570c27f4e77c'
    pins = {'contracts/ownership.json': {'after_sha256': '6b8b7fc2b2785868827d223688270723667b6240a5c871ecb022f0bc14fbbfec',
                              'before_sha256': '3caf885799bdb2287f5843b6a4eae289690ddfaa96081821bab977ad145e732e'},
 'contracts/surface-matrix.json': {'after_sha256': 'b347a7047bd61cd31097ea515b06bda53113abf4434fda68ba713129e0def454',
                                   'before_sha256': '80cfc8534de934b8fa8767fe6618f8eaeefc635591cd9e44666f87c5f53d9823'},
 'registry.json': {'after_sha256': '41d1e695d5e43e20150f32577d366fd8b28bd7663529743d7aa1f57da3c173da',
                   'before_sha256': 'd4f6235d60fe8c92fbfe394dbb298bc1baf3ccb9e9722b05004d69c4eccf03b1'},
 'skills/answer-key-gauntlet/SKILL.md': {'after_sha256': '8349dd394d243b7d0b6861288af763bd13959e2aa02d939056a7b95c911f2d7f',
                                         'before_sha256': '3c8f7dd7491680622f8f03f606238715c8402fdf5101a0d2fb0baed65c4e029b'},
 'skills/cross-agent-surface-engineering/SKILL.md': {'after_sha256': '923adca7174c8205ecb6801472d7193cc4055e5c821dc759d68c8ca6515c995c',
                                                     'before_sha256': '9031131e8be66964c739fbdcc6701485b64d8c00f8d1bc6d36b2c16f605265da'},
 'skills/instruction-authoring/SKILL.md': {'after_sha256': '95521cea4e0db3f411951e06090fa0f75d83c8684fa26fb9a1042c9ffb7ac872',
                                           'before_sha256': 'dd2b576f4dd1558d5f7427ebdf589c10f701a8f3d6495e5770da89d55feca41d'},
 'skills/openai-delegation-route-research/SKILL.md': {'after_sha256': '15a59edb6acc2067c4a3b68779e2eb8ffde0fc28b1c5adf40578b241f207424d',
                                                      'before_sha256': '34e1e85b361c4e50a567910deec9de4419773252acbd798a57ade894f9b115e4'},
 'skills/project-prior-art/SKILL.md': {'after_sha256': '0c34de00be0402b4ef985ec79d3f9135f6f6a9a78f8c1faaec79754d1882e96b',
                                       'before_sha256': '53899faafd3164b0f6c0a61ee7ed94e18e4c8d6e9b54dacbed08040951337168'},
 'surfaces/core.md': {'after_sha256': 'fefa76dee2bf0838fbe4126ad5249e4dd15d54be96ab68f9c2efcccefc2c4a90',
                      'before_sha256': '2b306ff51a7a8845b7b7bb26db43f51ef0fa77d54b772ab54bcd8d4accd3d6eb'}}
    if (not isinstance(retirement, dict) or retirement.get('owner') != selected_owner
            or base != reviewed_base or row.get('basis') != 'user-correction'
            or row.get('acceptance_classification') != 'outcome-design-retirement-maintenance'
            or name not in pins or not set(pins) <= set(paths)
            or retirement.get('git_recovery', {}).get('commit') != base
            or retirement.get('source_commit') != sync_git.git(candidate, 'rev-parse', 'HEAD')):
        raise sync_git.SyncBlocked('retirement maintenance requires its exact reviewed operation context')
    for target, expected in pins.items():
        current = candidate / target
        if (not current.is_file() or
                {'before_sha256': _hash(_before(source, base, target)),
                 'after_sha256': _hash(current.read_bytes())} != expected):
            raise sync_git.SyncBlocked('retirement maintenance source differs from reviewed scope: ' + target)
    records = retirement.get('evidence', {})
    def read_record(record):
        if not isinstance(record, dict) or set(record) != {'path', 'sha256'}:
            raise sync_git.SyncBlocked('retirement maintenance lacks a bound authority/reference body')
        path = Path(record['path'])
        if path.is_symlink() or path.stat().st_size > 1_000_000:
            raise sync_git.SyncBlocked('retirement maintenance evidence must be bounded regular data')
        raw = path.read_bytes()
        if _hash(raw) != record['sha256']:
            raise sync_git.SyncBlocked('retirement maintenance evidence bytes changed')
        return json.loads(raw)
    references = read_record(records.get('references'))
    authority = read_record(references.get('retirement_authority'))
    instruction_pins = {n: v for n, v in pins.items() if n.startswith(('skills/', 'surfaces/'))}
    if (authority.get('kind') != 'user-directed-skill-retirement'
            or authority.get('owner') != selected_owner or authority.get('decision') != 'retire'
            or authority.get('baseline_commit') != base
            or authority.get('source_commit') != retirement['source_commit']
            or authority.get('artifacts') != instruction_pins
            or not isinstance(authority.get('user_directive'), str)
            or not authority['user_directive'].strip()
            or references.get('complete') is not True
            or references.get('owner') != selected_owner
            or references.get('source_commit') != retirement['source_commit']):
        raise sync_git.SyncBlocked('retirement maintenance authority does not cover this source')
    native = references.get('native_instruction_removals', {})
    if (native.get('owner') != selected_owner or native.get('base_commit') != base
            or set(native.get('artifacts', {})) !=
                {'codex:global-instructions', 'hermes:standing-instructions', 'omp:global-instructions'}):
        raise sync_git.SyncBlocked('retirement maintenance requires the native route-removal plan')
    review = read_record(records.get('operation_review'))
    from reconcile import _retirement_review_scope
    if review != {'schema_version': 1, 'kind': 'reviewed-retirement-operation',
                  'verdict': 'PASS', 'scope_sha256': _retirement_review_scope(retirement),
                  'decision': records.get('decision'), 'coverage': records.get('coverage')}:
        raise sync_git.SyncBlocked('retirement maintenance needs the matching operation review')
    return 'exact reviewed user-directed retirement maintenance; recovery and native checks remain required'


# One completed local operation, not a general lifecycle or approval exception.
_COMPLETED_RETIREMENT_SHA256 = 'eb69555ea02ce07fdc3cc7f38bfc19d05340ede0d1da9a60f9a7d9d558ec4485'
_RETIREMENT_ORIGINAL_SOURCE = '52f674444bc075836ffe371dd1781d9a6016a019'
_RETIREMENT_ORIGINAL_BASE = '51f43f68dd45e51f6222a68d3e90570c27f4e77c'
_RETIREMENT_PROPAGATION_BASE = '29400d50cdb48ec967de94df07cbf4dcd232fac7'
_RETIREMENT_PUBLICATION_ADDITIONS = {
    'tools/worktree_sync.py', 'docs/worktree-publication.md',
    'tests/test_completed_retirement_publication.py',
}


def _completed_retirement_record(reference):
    if (not isinstance(reference, dict) or set(reference) != {'path', 'sha256'}
            or not isinstance(reference['path'], str)
            or not isinstance(reference['sha256'], str)):
        raise sync_git.SyncBlocked('completed retirement requires a bound evidence reference')
    path = Path(reference['path'])
    try:
        if (not path.is_absolute() or path.is_symlink() or path.resolve() != path.absolute()
                or not path.is_file() or path.stat().st_size > 1_000_000):
            raise ValueError('not bounded canonical regular data')
        with path.open('rb') as stream:
            raw = stream.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError('evidence exceeds the bounded record size')
        if _hash(raw) != reference['sha256']:
            raise ValueError('evidence digest differs')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError('evidence is not an object')
        return value
    except (OSError, ValueError) as exc:
        raise sync_git.SyncBlocked('completed retirement evidence missing, changed or invalid') from exc


def completed_retirement_publication(candidate, source, base, paths, proof, *, ready=None):
    """Verify retained completion and exact source propagation; never apply it.

    Consistency is not human authentication or permission to publish. The
    ordinary action review, dependency/source checks and manifest guard remain.
    Private proof stays in the existing private publication options/journals.
    """
    owner = 'outcome-first-workflow-design'
    if (not isinstance(proof, dict) or set(proof) !=
            {'schema_version', 'kind', 'completion', 'base_commit', 'ready_commit', 'files'}
            or type(proof['schema_version']) is not int or proof['schema_version'] != 1
            or proof['kind'] != 'completed-retirement-publication'
            or not isinstance(proof.get('completion'), dict)
            or not isinstance(proof.get('ready_commit'), str)
            or not re.fullmatch('[0-9a-f]{40}', proof['ready_commit'])
            or base != _RETIREMENT_PROPAGATION_BASE or proof['base_commit'] != base
            or (ready is not None and proof['ready_commit'] != ready)
            or proof['completion'].get('sha256') != _COMPLETED_RETIREMENT_SHA256):
        raise sync_git.SyncBlocked('completed retirement publication has a foreign completion, base or ready source')
    completed = _completed_retirement_record(proof['completion'])
    if (completed.get('status') != 'local retirement verified' or completed.get('owner') != owner
            or completed.get('source_commit') != _RETIREMENT_ORIGINAL_SOURCE
            or completed.get('remaining_local_retirement_gate') is not None
            or completed.get('uncertain_operations') is not False
            or any(completed.get(key) is not True for key in
                   ('shared_package_directory_absent', 'managed_state_entry_absent', 'installed_snapshot_verified'))):
        raise sync_git.SyncBlocked('completed retirement is incomplete or belongs to another owner')
    request = _completed_retirement_record(completed['execution_request'])
    request_sha = completed['execution_request']['sha256']
    if (request.get('kind') != 'reviewed-skill-retirement-v1' or request.get('owner') != owner
            or request.get('machine') != 'local-windows'
            or request.get('source_commit') != _RETIREMENT_ORIGINAL_SOURCE
            or request.get('git_recovery', {}).get('commit') != _RETIREMENT_ORIGINAL_BASE):
        raise sync_git.SyncBlocked('completed retirement request does not match its original source/recovery')
    from reconcile import _retirement_review_scope
    scope = _retirement_review_scope(request)
    review = _completed_retirement_record(completed['review'])
    if (request['evidence']['operation_review'] != completed['review']
            or scope != completed['scope_sha256']
            or review != {'schema_version': 1, 'kind': 'reviewed-retirement-operation',
                          'verdict': 'PASS', 'scope_sha256': scope,
                          'decision': request['evidence']['decision'], 'coverage': request['evidence']['coverage']}):
        raise sync_git.SyncBlocked('completed retirement lacks its exact matching operation review')
    for key in ('decision', 'coverage', 'references'):
        _completed_retirement_record(request['evidence'][key])
    references = _completed_retirement_record(request['evidence']['references'])
    authority = _completed_retirement_record(references['retirement_authority'])
    if (references.get('complete') is not True or references.get('owner') != owner
            or references.get('source_commit') != _RETIREMENT_ORIGINAL_SOURCE
            or authority.get('kind') != 'user-directed-skill-retirement'
            or authority.get('owner') != owner or authority.get('decision') != 'retire'
            or authority.get('source_commit') != _RETIREMENT_ORIGINAL_SOURCE):
        raise sync_git.SyncBlocked('completed retirement reference/authority scope differs')
    applied = _completed_retirement_record(completed['apply_return'])
    retained_ref = completed['retained_operation_receipt']
    expected_store = sync_git.common_dir(source) / 'agent-signal-retirements' / (request_sha + '.json')
    if Path(retained_ref['path']).resolve() != expected_store.resolve():
        raise sync_git.SyncBlocked('completed retirement is not retained by this repository')
    retained = _completed_retirement_record(retained_ref)
    for result in (applied, retained):
        if (result.get('result') != 'retired-local' or result.get('owner') != owner
                or result.get('source_commit') != _RETIREMENT_ORIGINAL_SOURCE
                or result.get('request_sha256') != request_sha
                or result.get('actions') != request['expected_actions']):
            raise sync_git.SyncBlocked('completed retirement apply/retained result differs from the reviewed request')
    native = _completed_retirement_record(completed['native_finish'])
    if (native.get('status') != 'verified' or native.get('scope_sha256') != scope
            or native.get('source_commit') != _RETIREMENT_ORIGINAL_SOURCE
            or any(native.get(k) is not True for k in
                   ('native_catalogues_verified', 'retired_directory_absent', 'retired_state_entry_absent', 'installed_snapshot_clean'))
            or set(completed['native_readbacks']) != {'codex', 'hermes', 'omp'}):
        raise sync_git.SyncBlocked('completed retirement lacks closed native discovery/readback')
    for host, row in completed['native_readbacks'].items():
        body = _completed_retirement_record({'path': row['path'], 'sha256': row['sha256']})
        if (body.get('host') != host or body.get('verified') is not True
                or body.get('loading_verified') is not True or body.get('retired_offered') != []
                or set(body.get('required_present', [])) != set(request['expected_actions']) - {owner}):
            raise sync_git.SyncBlocked('completed retirement native body/reference differs')
    allowed = set(request['source_files']) | _RETIREMENT_PUBLICATION_ADDITIONS
    original_paths = set(sync_git.git(source, 'diff', '--name-only', _RETIREMENT_ORIGINAL_BASE, _RETIREMENT_ORIGINAL_SOURCE).splitlines())
    if (set(request['source_files']) != original_paths or any(
            value != _hash(_before(source, _RETIREMENT_ORIGINAL_SOURCE, name))
            for name, value in request['source_files'].items())):
        raise sync_git.SyncBlocked('completed retirement original request/source mapping differs')
    if (not isinstance(proof['files'], dict) or set(proof['files']) != allowed or set(paths) != allowed):
        raise sync_git.SyncBlocked('completed retirement publication has an unrelated or missing selected path')
    exact = proof['ready_commit']
    sync_git.git(source, 'merge-base', '--is-ancestor', base, exact)
    changed = set(sync_git.git(source, 'diff', '--name-only', base, exact).splitlines())
    if changed != allowed:
        raise sync_git.SyncBlocked('completed retirement ready tree changes a different public scope')
    for name, pair in proof['files'].items():
        if sync_git.safe_path(source, name) != name:
            raise sync_git.SyncBlocked('completed retirement source address is unsafe')
        old, new = _before(source, base, name), _before(source, exact, name)
        if pair != {'before_sha256': _hash(old), 'after_sha256': _hash(new)}:
            raise sync_git.SyncBlocked('completed retirement source mapping differs: ' + name)
        if candidate is not None:
            path = candidate / name
            if (not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(candidate.resolve())
                    or path.read_bytes() != new):
                raise sync_git.SyncBlocked('completed retirement candidate differs from ready bytes: ' + name)
    # Reuse the actually reviewed original instruction transfer, not arbitrary
    # new guidance hidden behind a completion label or a caller-supplied digest.
    instructions = {row['path'] for row in applied['admission'] if row.get('owner')}
    if instructions != {'surfaces/core.md', *('skills/' + n + '/SKILL.md' for n in set(request['expected_actions']) - {owner})}:
        raise sync_git.SyncBlocked('completed retirement original instruction scope differs')
    for name in instructions | {'contracts/surface-matrix.json'}:
        if (_before(source, exact, name) != _before(source, _RETIREMENT_ORIGINAL_SOURCE, name)
                or _before(source, base, name) != _before(source, _RETIREMENT_ORIGINAL_BASE, name)):
            raise sync_git.SyncBlocked('completed retirement propagation alters the reviewed instructions: ' + name)
    for name, key, identity in [('registry.json', 'skills', 'name'), ('contracts/ownership.json', 'capabilities', 'id')]:
        original = json.loads(_before(source, _RETIREMENT_ORIGINAL_SOURCE, name))
        expected = json.loads(_before(source, base, name))
        matching = [r for r in original[key] if r[identity] == owner]
        if len(matching) != 1:
            raise sync_git.SyncBlocked('completed retirement original lifecycle owner differs')
        expected[key] = [matching[0] if r[identity] == owner else r for r in expected[key]]
        if json.loads(_before(source, exact, name)) != expected:
            raise sync_git.SyncBlocked('completed retirement changes another lifecycle selection: ' + name)
    return {'owner': owner, 'completed_scope_sha256': scope,
            'completion_sha256': _COMPLETED_RETIREMENT_SHA256, 'publication_authorized': False}


def _approved_user_preference(candidate, source, name, owner, row, base):
    """Check declared preference scope; human authority and meaning need owner review."""
    preference = row.get('user_preference')
    if (row.get('basis') != 'user-correction' or owner != name
            or name not in {'surfaces/core.md', *ADAPTERS}
            or not isinstance(preference, dict)
            or set(preference) != {'request', 'scope', 'authority', 'protected_guarantees_unchanged'}
            or preference.get('authority') != 'explicit-user-request'
            or preference.get('protected_guarantees_unchanged') is not True
            or any(not isinstance(preference.get(key), str) or not preference[key].strip()
                   for key in ('request', 'scope'))):
        raise sync_git.SyncBlocked('user preference requires explicit scope and retained guarantees at its existing owner')
    old = _before(source, base, name)
    path = candidate / name
    if old is None or not path.is_file() or path.is_symlink():
        raise sync_git.SyncBlocked('user preference requires an existing regular instruction source')
    new = path.read_bytes()
    if name == 'surfaces/core.md':
        def outside(data):
            start, end = b'<!-- agent-sync-standing -->', b'<!-- /agent-sync-standing -->'
            if data.count(start) != 1 or data.count(end) != 1 or data.index(start) >= data.index(end):
                raise sync_git.SyncBlocked('user preference requires one standing section')
            prefix, body = data.split(start)
            _, suffix = body.split(end)
            return prefix, suffix
        if outside(old) != outside(new):
            raise sync_git.SyncBlocked('user preference cannot change core outside standing instructions')
    else:
        try:
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('duplicate preference adapter key')
                    result[key] = value
                return result
            before, after = json.loads(old, object_pairs_hook=unique), json.loads(new, object_pairs_hook=unique)
            for value in (before, after):
                projection = value['instructions'].pop('projection')
                if not isinstance(projection, dict):
                    raise ValueError('invalid projection')
            if json.dumps(before, sort_keys=True, allow_nan=False) != json.dumps(after, sort_keys=True, allow_nan=False):
                raise ValueError('non-instruction adapter change')
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise sync_git.SyncBlocked('user preference may change only the adapter instruction projection') from exc
    return 'explicit user preference with checked source scope'


def correction_eligibility(candidate, source, name, owner, row, base, paths, reconciliations, retirement=None, retirement_publication=None):
    """Narrow reviewed correction routes after necessity/dependency validation.

    Record validation does not authenticate authority or prove semantic scope.
    Other instruction adoption still uses the measured-evidence gate.
    """
    old = _before(source, base, name)
    path = candidate / name
    new = path.read_bytes() if path.is_file() else None
    kind = row.get('change_kind', 'add-or-change')
    reason = None
    if row.get('acceptance_classification') == 'outcome-design-retirement-maintenance':
        if kind not in {'remove', 'add-or-change'}:
            raise sync_git.SyncBlocked('retirement maintenance must retain its actual edit/removal kind')
        if retirement_publication is not None:
            completed_retirement_publication(candidate, source, base, paths, retirement_publication)
            reason = 'source propagation of the exact completed retirement; no new native operation'
        else:
            reason = _approved_retirement_maintenance(candidate, source, name, owner, row, base, paths, retirement)
    elif (kind == 'add-or-change' and row.get('basis') == 'mechanical-maintenance'
            and old is not None and new is not None
            and old.replace(b'\r\n', b'\n') == new.replace(b'\r\n', b'\n')):
        reason = 'content-identical line-ending repair'
    elif (kind == 'add-or-change' and name == owner == 'surfaces/core.md'
            and row.get('basis') == 'user-correction' and _preference_data_only(old, new, row)):
        reason = 'explicit user model-selector data; standing instructions unchanged'
    elif kind == 'user-preference':
        reason = _approved_user_preference(candidate, source, name, owner, row, base)
    elif kind == 'requested-native-learning':
        reason = _approved_native_learning_source(candidate, source, name, owner, row, base, paths, reconciliations)
    elif kind == 'requested-import':
        reason = _approved_requested_import(candidate, source, name, owner, row, base, paths)
    elif kind == 'requested-edit':
        reason = _approved_requested_edit(candidate, source, name, owner, row, base, paths)
    elif kind == 'requested-reader':
        reason = _approved_requested_reader(candidate, source, name, owner, row, base, paths)
    elif kind == 'reference-transport':
        reason = _approved_reference_transport(candidate, source, name, owner, row, base, paths)
    elif kind == 'public-audience-correction':
        reason = _approved_public_audience(candidate, source, name, owner, row, base, paths, reconciliations)
    elif (kind == 'contract-correction'
            and row.get('acceptance_classification') == 'curator-scope-maintenance'):
        reason = _approved_curator_scope_maintenance(candidate, source, name, owner, row, base, paths, reconciliations)
    elif (kind == 'contract-correction'
            and name == 'skills/instruction-authoring/references/item-review-loop.md'):
        reason = _approved_item_review_maintenance(candidate, source, name, owner, row, base, paths, reconciliations)
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


def check(candidate: Path, source: Path, base: str, paths, retirement=None, *, retirement_publication=None):
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
        if kind not in {'add-or-change', 'remove', 'contract-correction', 'reference-transport', 'requested-import', 'requested-edit', 'requested-reader', 'requested-native-learning', 'public-audience-correction', 'user-preference'}:
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
        eligibility = correction_eligibility(candidate, source, name, owner, row, base, paths, reconciliation_records, retirement, retirement_publication)
        if eligibility is None:
            eligibility = measurement_eligibility(candidate, source, name, owner, row, base)
        if not eligibility['eligible']:
            raise sync_git.SyncBlocked(eligibility['reason'] + ': ' + name)
    return used + dependencies
