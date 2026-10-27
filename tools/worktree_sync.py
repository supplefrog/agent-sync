"""Frozen ready commits, isolated Git integration, existing scoped reconciliation."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import uuid
import shutil

import reconcile
import sync_git

BRANCH = 'agent-sync/published'
INTEGRATION_BRANCH = 'agent-sync/integration'


def _primary(repo):
    common = sync_git.common_dir(Path(repo).resolve())
    if common.name != '.git' or not (common.parent / '.git').is_dir():
        raise sync_git.SyncBlocked('ready integration requires a non-bare primary checkout')
    return common.parent, common


def _atomic(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def _read(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def _names(repo, *args):
    return sorted(set(sync_git.git(repo, *args, '-z').split('\0')) - {''})


def _checkout_git(repo, *args):
    # The existing publisher hashes raw file bytes. Its owned integration
    # checkout must not introduce a global Windows EOL transformation.
    return sync_git.git(repo, '-c', 'core.autocrlf=false', '-c', 'core.eol=lf', *args)


def _options(adopt, include, machine, skill_roots, recovery_roots, message):
    return {'adopt': sorted(set(adopt or ())), 'include': sorted(set(include or ())),
            'machine': machine, 'skill_roots': [str(Path(p).resolve()) for p in skill_roots] if skill_roots is not None else None,
            'recovery_roots': {key: str(Path(p).resolve()) for key, p in (recovery_roots or {}).items()},
            'message': message}


def _qualify(repo, ready, options):
    primary, common = _primary(repo)
    target = sync_git.destination(primary)
    exact = sync_git.git(repo, 'rev-parse', '--verify', str(ready) + '^{commit}')
    public = 'refs/remotes/' + target['remote'] + '/' + target['ref'].removeprefix('refs/heads/')
    base = sync_git.git(repo, 'merge-base', public, exact)
    commits = sync_git.git(repo, 'rev-list', '--reverse', base + '..' + exact).splitlines()
    if not commits:
        raise sync_git.SyncBlocked('ready input contains no unpublished source commits')
    paths = set()
    def admission(commit):
        value = json.loads(sync_git.git(repo, 'show', commit + ':registry.json'))
        return sorted((row['name'], row.get('status')) for row in value['skills'])
    public_admission = admission(base)
    for commit in commits:
        parents = sync_git.git(repo, 'rev-list', '--parents', '-n', '1', commit).split()
        if len(parents) != 2:
            raise sync_git.SyncBlocked('ready integration requires a linear non-merge commit range')
        if admission(commit) != public_admission:
            raise sync_git.SyncBlocked('ready integration cannot change registry admission or lifecycle; normal review is required')
        paths.update(_names(repo, 'diff-tree', '--no-commit-id', '--no-renames', '--name-only', '-r', commit))
    owners = set(options['adopt'])
    included = set(options['include'])
    if not owners and not included:
        raise sync_git.SyncBlocked('ready integration requires explicit owners or exact included files')
    omit_metadata = 'host-deltas.json' in paths and 'host-deltas.json' not in included
    with sync_git.prepare_candidate(repo, {}, base=exact) as (candidate, tree):
        reconcile._selected_owners(candidate, owners, strict=True)
        registry = reconcile.fleet.registry(candidate) if owners else {}
        if any(registry[name].get('status') != 'admitted' for name in owners):
            raise sync_git.SyncBlocked('ready owners must already be admitted')
        if owners:
            published_registry = json.loads(sync_git.git(repo, 'show', base + ':registry.json'))
            admitted = {row['name'] for row in published_registry['skills'] if row.get('status') == 'admitted'}
            if not owners <= admitted:
                raise sync_git.SyncBlocked('ready integration cannot admit a new owner')
        for name in included:
            if sync_git.safe_path(candidate, name) != name:
                raise sync_git.SyncBlocked('ready includes require normalized exact file paths')
        for name in paths:
            if name == 'host-deltas.json' and omit_metadata:
                continue
            if name not in included and not any(name.startswith('skills/' + owner + '/') for owner in owners):
                raise sync_git.SyncBlocked('ready commit contains an unselected path: ' + name)
        if omit_metadata:
            # Check each commit, not just the final tree: policy changes cannot be
            # concealed by a later reversal in the range.
            for commit in commits:
                parent = sync_git.git(repo, 'rev-parse', commit + '^')
                before = json.loads(sync_git.git(repo, 'show', parent + ':host-deltas.json'))
                after = json.loads(sync_git.git(repo, 'show', commit + ':host-deltas.json'))
                selected = reconcile._binding_selection(after, owners, None, included)
                if reconcile._binding_policy(before, selected, project_derived=True) != reconcile._binding_policy(after, selected, project_derived=True):
                    raise sync_git.SyncBlocked('ready metadata policy requires explicit host-deltas.json review')
        selected_paths = sorted(paths - ({'host-deltas.json'} if omit_metadata else set()))
        import instruction_changes
        instruction_changes.check(candidate, repo, base, selected_paths)
        sync_git.assert_publishable(candidate, paths)
        reconcile._prepare_candidate_bindings(candidate, owners, None, selected_paths)
        if (candidate / 'registry.json').is_file():
            reconcile.fleet.render_snapshot(candidate, reconcile._snapshot(candidate))
        checks = reconcile._run_candidate_checks(candidate, reconcile._candidate_commands(candidate, owners, selected_paths), tree)
    return {'ready': exact, 'source_base': base, 'source_commits': commits,
            'paths': selected_paths, 'omit_metadata': omit_metadata, 'target': target,
            'source_repo': str(repo), 'common_repo': str(common), 'options': options,
            'published_repo': str(common / 'agent-signal-published'),
            'integration_repo': str(common / 'agent-signal-integration-worktree'), 'completed_checks': checks}


def ready_plan(repo, ready, *, adopt=(), include=(), machine='local-windows',
               skill_roots=None, recovery_roots=None, message='chore: integrate checked ready change',
               capture_recovery=False, recovery_artifacts=None, **unsupported):
    """Read-only Git/source qualification; no fetch, checkout, config, or deploy."""
    try:
        if capture_recovery or recovery_artifacts or unsupported:
            raise sync_git.SyncBlocked('ready integration supports explicit source/portable scopes only')
        options = _options(adopt, include, machine, skill_roots, recovery_roots, message)
        result = _qualify(Path(repo).resolve(), ready, options)
        return dict(result, result='ready', verification_scope='frozen source candidate checks; no live or remote verification')
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        return {'result': 'review-required', 'reason': str(exc), 'failed_step': 'ready-qualification'}


def _owned_worktree(primary, common, target, name, branch):
    lane = common / name
    marker_path = common / (name + '.json')
    marker = _read(marker_path)
    if lane.exists():
        if lane.is_symlink() or lane.resolve() != lane.absolute() or not marker:
            raise sync_git.SyncBlocked('published integration path is not the owned worktree')
        if marker['target'] != target or marker['common_repo'] != str(common):
            raise sync_git.SyncBlocked('published integration identity or destination changed')
        if sync_git.common_dir(lane) != common or sync_git.git(lane, 'symbolic-ref', '--short', 'HEAD') != branch:
            raise sync_git.SyncBlocked('published integration worktree or branch changed')
        configured_target = sync_git.destination(lane)
        configured_target['branch'] = target['branch']
        if configured_target != target:
            raise sync_git.SyncBlocked('owned worktree publication destination changed')
        return lane, marker_path, marker
    if marker:
        raise sync_git.SyncBlocked('owned published worktree is missing; preserve its recorded state')
    sync_git.git(primary, 'fetch', '--no-tags', target['remote'], target['ref'])
    base = sync_git.git(primary, 'rev-parse', 'FETCH_HEAD')
    # Worktree add refuses an existing branch, avoiding capture of foreign work.
    _checkout_git(primary, 'worktree', 'add', '-b', branch, str(lane), base)
    sync_git.git(primary, 'config', 'branch.' + branch + '.remote', target['remote'])
    sync_git.git(primary, 'config', 'branch.' + branch + '.merge', target['ref'])
    marker = {'schema_version': 1, 'common_repo': str(common), 'target': target, 'head': base}
    _atomic(marker_path, marker)
    return lane, marker_path, marker


def _origin_destinations(lane, options, common):
    if not options['adopt']:
        return []
    destinations = reconcile._destinations(lane, options['machine'], options['skill_roots'])
    for _, path in destinations:
        state = reconcile.fleet.load_state(path)
        origin = state.get('source_snapshot')
        if not isinstance(origin, str) or not Path(origin).is_absolute():
            raise sync_git.SyncBlocked('published source migration requires existing managed origins')
        _, origin_common = reconcile.fleet._source_origin_repository(Path(origin))
        if origin_common != common:
            raise sync_git.SyncBlocked('managed destination origin belongs to another Git repository')
    return [str(path) for _, path in destinations]


def _unpublished_owner_updates(actions, managed_state, snapshot, selected_owners=()):
    """Unselected local-authoring state is not permission to replace it with public bytes."""
    protected = []
    for action in actions:
        name = action['name']
        if name in selected_owners or action['action'] not in {'update', 'remove', 'repair'}:
            continue
        origin = managed_state.get('skills', {}).get(name, {}).get('source_snapshot',
                    managed_state.get('source_snapshot'))
        if origin and Path(origin).resolve() != Path(snapshot).resolve():
            protected.append(name)
    return sorted(protected)


def _rollout_targets(published, journal, save, *, verify_native=None):
    """Extend the existing integration receipt with independently resumable roots."""
    if verify_native is None:
        import install
        verify_native = install.verify_fleet_discovery
    fleet = reconcile.fleet
    snapshot = reconcile._snapshot(published)
    manifest = fleet.load_manifest(snapshot)
    digest = fleet.sha256_file(snapshot / fleet.MANIFEST_FILE)
    rollout = journal.setdefault('rollout', {'commit': journal['last_result']['commit'],
                                           'manifest_sha256': digest, 'targets': {}})
    if rollout['commit'] != journal['last_result']['commit'] or rollout['manifest_sha256'] != digest:
        raise sync_git.SyncBlocked('rollout source differs from the retained integration receipt')
    roots = {}
    retired = {row['name'] for row in json.loads((published / 'registry.json').read_bytes())['skills']
               if row.get('status') == 'retired'}
    for machine, spec in fleet.load_fleet(published)['machines'].items():
        for template in spec['skill_roots']:
            root = fleet.resolve_template(template)
            item = roots.setdefault(str(root), {'machines': [], 'hosts': set(), 'unavailable_transport': []})
            item['machines'].append(machine); item['hosts'].update(spec.get('hosts', []))
            if spec.get('platform') and machine != journal.get('receipt', {}).get('options', {}).get('machine', 'local-windows'):
                item['unavailable_transport'].append(machine)
    if not roots:
        rollout['reason'] = 'no configured installed targets'; save(); return False
    for path, configured in roots.items():
        root = Path(path)
        state = rollout['targets'].setdefault(path, {'machines': configured['machines'], 'hosts': sorted(configured['hosts'])})
        try:
            if not state['hosts']:
                raise sync_git.SyncBlocked('configured target has no native hosts to verify')
            if configured['unavailable_transport']:
                raise sync_git.SyncBlocked('native execution transport unavailable for configured machine: ' + ', '.join(configured['unavailable_transport']))
            with fleet._path_locks([snapshot, root]):
                actions = fleet.plan_snapshot(snapshot, root)
                protected = _unpublished_owner_updates(actions, fleet.load_state(root), snapshot,
                    journal.get('receipt', {}).get('options', {}).get('adopt', ()))
                if protected:
                    raise sync_git.SyncBlocked('unpublished managed owners require their existing authoring outcome: ' + ', '.join(protected))
                conflicts = [a['name'] for a in actions if a['action'] == 'conflict']
                if conflicts:
                    raise sync_git.SyncBlocked('managed drift/unmanaged collision: ' + ', '.join(conflicts))
                if 'required' not in state:
                    required = []
                    for action in actions:
                        if action['action'] not in {'add','adopt','materialize','repair','update'}: continue
                        name = action['name']; current = root/name; desired = snapshot/'skills'/name
                        old = fleet.directory_record(current)['files'] if current.is_dir() and not fleet.is_linklike_path(current) else {}
                        new = manifest['skills'][name]['files']
                        same_content = set(old)==set(new) and all((current/n).read_bytes().replace(b'\r\n',b'\n') ==
                            (desired/n).read_bytes().replace(b'\r\n',b'\n') for n in new)
                        if not same_content: required.append(name)
                    state['required'] = sorted(required)
                    state['retired'] = sorted({a['name'] for a in actions if a['action'] in {'remove','forget'}} |
                                              set(journal.get('rollout_retired', [])) | retired)
                mutations = [a for a in actions if a['action'] != 'unchanged']
                installed_state = fleet.load_state(root)
                metadata_stale = (installed_state.get('manifest_sha256') != digest or
                                  installed_state.get('source_snapshot') != str(snapshot.resolve()))
                if mutations or metadata_stale:
                    if 'backup' not in state:
                        backup = sync_git.common_dir(published) / 'agent-signal-integration-backups' / journal['attempt'] / hashlib.sha256(path.encode()).hexdigest()[:16]
                        backup.mkdir(parents=True, exist_ok=False)
                        source_state = root / fleet.STATE_FILE
                        if source_state.is_file(): shutil.copy2(source_state, backup / fleet.STATE_FILE)
                        for action in actions:
                            if action['action'] in {'update','remove','materialize','repair'} and (root / action['name']).is_dir():
                                shutil.copytree(root / action['name'], backup / action['name'])
                        state.update(backup=str(backup), before_state=fleet.state_identity(root), planned=actions)
                        save()
                    state['phase'] = 'applying'; journal['deployment_started'] = True; save()
                    fleet.apply_snapshot(snapshot, root, expected_state=fleet.state_identity(root))
                findings = fleet.verify_snapshot(snapshot, root)
                if findings: raise sync_git.SyncBlocked('installed hashes differ: ' + str(findings))
                state['phase'] = 'installed'; save()
                state['native'] = {host: verify_native(host, root, state['required'], state['retired']) for host in state['hosts']}
                # A native read or another writer must not invalidate installed verification.
                findings = fleet.verify_snapshot(snapshot, root)
                state['verified'] = not findings and all(v.get('verified') is True for v in state['native'].values())
                state['phase'] = 'verified' if state['verified'] else 'native-verification-incomplete'
                state['installed_hashes'] = {name: row['sha256'] for name,row in manifest['skills'].items()}
                state.pop('reason', None)
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            state.update(verified=False, phase='blocked', reason=str(exc))
        save()
    return all(rollout['targets'][path].get('verified') is True for path in roots)


_ABSENT_CONFIG_VALUE = object()


def _config_value_equal(left, right):
    """JSON structural equality without Python's boolean/number coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_config_value_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_config_value_equal(a, b) for a, b in zip(left, right))
    return left == right


def _changed_config_matches(before, desired, current, path=()):
    """Check only the authored delta; unrelated saved values are not restore targets."""
    missing = _ABSENT_CONFIG_VALUE
    if before is missing and isinstance(desired, dict):
        before = {}
    if isinstance(before, dict) and isinstance(desired, dict):
        if not isinstance(current, dict):
            return False
        return all(_changed_config_matches(before.get(k, missing), desired.get(k, missing),
                                          current.get(k, missing), path + (k,))
                   for k in before.keys() | desired.keys()
                   if not _config_value_equal(before.get(k, missing), desired.get(k, missing)))
    if path in {('plugins', 'enabled'), ('plugins', 'disabled')} and before is missing:
        before = []
    if path in {('plugins', 'enabled'), ('plugins', 'disabled')} and all(
            isinstance(v, list) and all(isinstance(x, str) for x in v) for v in (before, desired, current)):
        return set(desired) - set(before) <= set(current) and not (set(before) - set(desired)) & set(current)
    # JSON booleans must not compare equal to integer settings.
    return _config_value_equal(desired, current)


def _native_destination_completion(lane, journal, *, recovery_module=None):
    """Read-only saved-state check; never restore broad snapshots or restart sessions."""
    if recovery_module is None:
        import recovery as recovery_module
    recovery = recovery_module
    commit = journal['last_result']['commit']
    # The actual published commit's parent preserves selection on source-only resume.
    paths = set(_names(lane, 'diff', '--name-only', commit + '^', commit))
    selected = sorted(p for p in paths if p.startswith('recovery/current/') and p != 'recovery/current/manifest.json')
    result = {'saved_verified': True, 'loaded_verified': None, 'targets': {}}
    if not selected:
        return result
    try:
        policy = recovery._load_policy(lane / 'recovery.json')
        recovery.verify_snapshot(lane / 'recovery.json', lane / 'recovery/current')
        artifacts = {'recovery/current/' + a['snapshot']: (host, a)
                     for host, a in recovery._policy_artifacts(policy)}
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        return dict(result, saved_verified=False, targets={'snapshot': {'verified': False,
                    'reason': str(exc), 'resumption_event': 'Repair and qualify the exact snapshot/policy before retry.'}})
    roots = journal['receipt']['options'].get('recovery_roots') or {}
    for name in selected:
        state = {'verified': False, 'loaded_verified': None,
                 'resumption_event': 'Native owner reconciles the exact selected values, then resume this published attempt; user restarts later.'}
        result['targets'][name] = state
        try:
            host, artifact = artifacts[name]
            _, resolved = recovery._selected_roots(roots, [host])
            target = recovery._safe_join(resolved[host], artifact['source'], must_exist=True)
            identity = recovery._file_identity(target)
            desired_bytes = sync_git.git(lane, 'show', commit + ':' + name)
            old_bytes = sync_git.git(lane, 'show', commit + '^:' + name)
            if artifact['kind'] != 'config':
                raise sync_git.SyncBlocked('Selected native text requires its existing recovery owner readback; skill catalogue is insufficient.')
            home = recovery._target_home(resolved, [host])
            # Bootstrap/restore from the managed published checkout owns the saved source anchor.
            anchor = Path(journal['published_repo'])
            before = recovery._expand(json.loads(old_bytes), resolved, anchor, home=home)
            desired = recovery._expand(json.loads(desired_bytes), resolved, anchor, home=home)
            current = recovery._read_config(target, artifact['format'])
            state['verified'] = _changed_config_matches(before, desired, current)
            if recovery._file_identity(target) != identity:
                state['verified'] = False
                state['reason'] = 'Native target changed during readback.'
            elif not state['verified']:
                state['reason'] = 'Selected native configuration delta is stale; no broad restore was attempted.'
            else:
                state['resumption_event'] = 'Saved values verified; loading is separate and may await the user-managed restart.'
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            state['reason'] = str(exc)
        result['saved_verified'] = result['saved_verified'] and state['verified']
    return result


def _finish_published(primary, common, target, lane, published, published_marker_path, published_marker, journal, *, source_only=False):
    sync_git.assert_integration_owner(lane, journal['attempt'])
    result = dict(journal['last_result'])
    commit = result['commit']
    pending = sync_git.read_pending(lane)
    if pending:
        _validate_pending(lane, journal, pending)
        if not pending.get('completion') or pending['completion'].get('commit') != commit:
            raise sync_git.SyncBlocked('publisher completion does not match the published integration receipt')
        _verify_completion(lane, journal, pending)
    if sync_git.git(lane, 'rev-parse', 'HEAD') != commit:
        raise sync_git.SyncBlocked('completed integration HEAD changed before published source refresh')
    # A verified push may be followed by another independent fast-forward
    # while origin migration is pending. Keep our exact checked source, while
    # proving publication remains in the remote's history; never deploy the
    # external successor as part of this attempt.
    sync_git.git(lane, 'fetch', '--no-tags', target['remote'], target['ref'])
    remote_tip = sync_git.git(lane, 'rev-parse', 'FETCH_HEAD')
    sync_git.git(lane, 'merge-base', '--is-ancestor', commit, remote_tip)
    if sync_git.git(lane, 'ls-remote', '--refs', target['remote'], target['ref']).split() != [remote_tip, target['ref']]:
        raise sync_git.SyncBlocked('remote changed during published source refresh verification')
    if source_only:
        if journal.get('deployment_started'):
            raise sync_git.SyncBlocked('rollout already started; resume the exact installed-target attempt')
        result.update(result='published', rollout_verified=False, installed_verified=False,
                      reason='explicit source-only publication; configured rollout remains incomplete',
                      sync_complete=False, activation_verified=None,
                      resumption_event='Resume the exact published release through normal rollout; retain native saved/loading dependencies.')
        journal['last_result'] = result
        _atomic(common / ('agent-signal-integration-published-' + journal['attempt'] + '.json'), journal)
        if pending:
            (sync_git.git_dir(lane) / 'agent-signal-sync.json').unlink()
        (common / 'agent-signal-integration.json').unlink()
        return result
    if sync_git.changed(published):
        raise sync_git.SyncBlocked('stable published source has unowned dirty files')
    if sync_git.git(published, 'rev-parse', 'HEAD') != published_marker['head']:
        # Recover the owned fast-forward/reset-before-marker crash window.
        if sync_git.git(published, 'rev-parse', 'HEAD') != commit:
            raise sync_git.SyncBlocked('stable published HEAD changed outside its integration attempt')
    sync_git.git(published, 'merge-base', '--is-ancestor', published_marker['head'], commit)
    if 'source_backup' not in journal:
        backup = common / 'agent-signal-integration-backups' / journal['attempt'] / 'source'
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(published_marker_path, backup / 'published-marker.json')
        old_entries = sync_git._tree_entries(published, published_marker['head'])
        old_blobs = sync_git._blobs(published, old_entries)
        changed = set(sync_git.git(published, 'diff', '--name-only', published_marker['head'], commit).splitlines())
        for name, (_, oid) in old_entries.items():
            data = (published / name).read_bytes()
            if data != old_blobs[oid] and data.replace(b'\r\n', b'\n') != old_blobs[oid].replace(b'\r\n', b'\n'):
                raise sync_git.SyncBlocked('unowned raw stable source edit: ' + name)
            if name in changed or data != old_blobs[oid]:
                destination = backup / name; destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
        old_registry = json.loads(sync_git.git(published, 'show', published_marker['head'] + ':registry.json'))
        new_registry = json.loads(sync_git.git(published, 'show', commit + ':registry.json'))
        old_admitted = {r['name'] for r in old_registry['skills'] if r.get('status') == 'admitted'}
        journal['rollout_retired'] = sorted(r['name'] for r in new_registry['skills'] if r.get('status') == 'retired' and r['name'] in old_admitted)
        journal['source_backup'] = str(backup)
        _atomic(common / 'agent-signal-integration.json', journal)
    journal['deployment_started'] = True
    _atomic(common / 'agent-signal-integration.json', journal)
    # This is the coordinator-owned cache refresh, not an authoring write to the
    # stable checkout. Keep raw source bytes independent of checkout EOL rules.
    _checkout_git(published, 'reset', '--hard', commit)
    entries = sync_git._tree_entries(published, commit)
    blobs = sync_git._blobs(published, entries)
    for name, (_, oid) in entries.items():
        if (published / name).read_bytes() != blobs[oid]:
            (published / name).write_bytes(blobs[oid])
    published_marker['head'] = commit
    _atomic(published_marker_path, published_marker)
    snapshot = reconcile._snapshot(published)
    reconcile.fleet.render_snapshot(published, snapshot)
    if not _rollout_targets(published, journal, lambda: _atomic(common / 'agent-signal-integration.json', journal)):
        return dict(result, result='incomplete', failed_step='configured-rollout', publication_verified=True,
                    rollout_verified=False, targets=journal['rollout']['targets'])
    native = _native_destination_completion(lane, journal)
    journal['native_destinations'] = native
    _atomic(common / 'agent-signal-integration.json', journal)
    if not native['saved_verified']:
        return dict(result, result='incomplete', failed_step='native-saved-verification',
                    publication_verified=True, rollout_verified=False, installed_verified=False,
                    sync_complete=False, activation_verified=None, native_destinations=native,
                    targets=journal['rollout']['targets'])
    owners = journal['receipt']['options']['adopt']
    migrations = []
    for path in journal['origin_destinations']:
        destination = Path(path)
        if owners and reconcile.fleet.verify_snapshot(snapshot, destination, names=owners):
            raise sync_git.SyncBlocked('selected installed owners changed before source origin migration')
        migrations.append(reconcile.fleet.migrate_source_origin(snapshot, destination,
                          expected_state=reconcile.fleet.state_identity(destination)))
    result.update(result='synced', sync_complete=True, activation_verified=None, native_destinations=native,
                  published_repo=str(published), integration_repo=str(lane), source_origin_migrations=migrations,
                  agents_verified=True, installed_verified=True, rollout_verified=True, targets=journal['rollout']['targets'],
                  verification_scope='configured installed hashes and fresh native catalogue/body readback; no model behavior or cached-session refresh claim')
    pending = sync_git.read_pending(lane)
    if pending:
        _validate_pending(lane, journal, pending)
        if not pending.get('completion') or pending['completion'].get('commit') != commit:
            raise sync_git.SyncBlocked('publisher completion does not match the published integration receipt')
        (sync_git.git_dir(lane) / 'agent-signal-sync.json').unlink()
    (common / 'agent-signal-integration.json').unlink()
    return result


def unchanged_published(repo, *, machine, skill_roots=None):
    """Recognize only a clean source already installed from its owned cache.

    This is a read-only qualification for reusing publication, not an exception
    for fleet drift. The normal rollout still verifies remote and native state.
    """
    repo = Path(repo).resolve()
    try:
        primary, common = _primary(repo)
        marker = _read(common / 'agent-signal-published.json')
        published = common / 'agent-signal-published'
        if not marker or not published.is_dir() or sync_git.changed(repo):
            return None
        commit = sync_git.git(repo, 'rev-parse', 'HEAD')
        if commit != marker.get('head') or sync_git.git(published, 'rev-parse', 'HEAD') != commit:
            return None
        target = sync_git.destination(primary)
        _owned_worktree(primary, common, target, 'agent-signal-published', BRANCH)
        if sync_git.changed(published) or sync_git.read_pending(repo):
            return None
        snapshot = reconcile._snapshot(published)
        for _, root in reconcile._destinations(repo, machine, skill_roots):
            if reconcile.fleet.verify_snapshot(snapshot, root):
                return None
        return commit
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError):
        return None


def publication_request(options):
    """Bind an ordinary sync retry to its existing source selection."""
    value = _options(options.get('adopt'), options.get('include'), options.get('machine', 'local-windows'),
                     options.get('skill_roots'), options.get('recovery_roots'), options.get('message'))
    value.update(capture_recovery=options.get('capture_recovery'), scoped=options.get('scoped'),
                 recovery_artifacts=sorted(options.get('recovery_artifacts') or ()))
    # None means configured native roots; {} deliberately captures none.
    value['default_recovery_roots'] = options.get('recovery_roots') is None
    return value


def published_retry(repo, request):
    """Read the existing journal; never consume a different source request."""
    try:
        repo = Path(repo).resolve()
        journal = _read(sync_git.common_dir(repo) / 'agent-signal-integration.json')
        if (not journal or journal.get('phase') != 'published' or
                journal.get('publication_request') != request or sync_git.changed(repo)):
            return None
        commit = journal['last_result']['commit']
        return commit if sync_git.git(repo, 'rev-parse', 'HEAD') == commit else None
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError):
        return None


def rollout_published(repo, commit, *, source_only=False, machine='local-windows', request=None):
    """Resume a verified published release through the existing integration journal.

    Publication-only recovery creates no new source decision or publication. It
    still uses managed worktree ownership, exact remote readback and root guards.
    """
    repo = Path(repo).resolve()
    journal = None
    try:
        primary, common = _primary(repo)
        with sync_git.lock(repo, timeout=120):
            target = sync_git.destination(primary)
            exact = sync_git.git(repo, 'rev-parse', str(commit) + '^{commit}')
            journal_path = common / 'agent-signal-integration.json'
            journal = _read(journal_path)
            if journal:
                if journal.get('phase') != 'published' or journal.get('last_result', {}).get('commit') != exact:
                    raise sync_git.SyncBlocked('resume the existing exact integration attempt before another rollout')
                if request is not None and journal.get('publication_request') != request:
                    raise sync_git.SyncBlocked('published rollout belongs to another source selection')
            else:
                sync_git.git(repo, 'fetch', '--no-tags', target['remote'], target['ref'])
                if sync_git.git(repo, 'ls-remote', '--refs', target['remote'], target['ref']).split() != [exact, target['ref']]:
                    raise sync_git.SyncBlocked('published rollout requires the exact configured remote release')
                lane, lane_marker_path, lane_marker = _owned_worktree(primary, common, target, 'agent-signal-integration-worktree', INTEGRATION_BRANCH)
                published, published_marker_path, published_marker = _owned_worktree(primary, common, target, 'agent-signal-published', BRANCH)
                if sync_git.read_pending(lane) or sync_git.changed(lane):
                    raise sync_git.SyncBlocked('integration lane contains unowned pending or dirty state')
                if sync_git.git(lane, 'rev-parse', 'HEAD') != lane_marker['head']:
                    raise sync_git.SyncBlocked('integration lane HEAD differs from its owner marker')
                sync_git.git(lane, 'merge-base', '--is-ancestor', lane_marker['head'], exact)
                _checkout_git(lane, 'reset', '--hard', exact)
                lane_marker['head'] = exact; _atomic(lane_marker_path, lane_marker)
                # Preserve explicit roots on resume; otherwise use the existing native-root resolver.
                import recovery
                roots = (recovery._default_roots() if request is None or request.get('default_recovery_roots')
                         else request.get('recovery_roots') or {})
                options = _options((), (), machine, None, roots, 'resume published rollout')
                journal = {'schema_version':1, 'attempt':uuid.uuid4().hex, 'phase':'published',
                           'base':exact, 'deployment_started':False, 'published_repo':str(published),
                           'integration_repo':str(lane), 'origin_destinations':[],
                           'receipt':{'ready':exact, 'options':options, 'target':target, 'source_base':exact, 'source_commits':[]},
                           'last_result':{'result':'published','commit':exact,'remote':target['remote'],
                                          'branch':target['branch'],'remote_verified':True,'agents_verified':False}}
                if request is not None:
                    journal['publication_request'] = request
                _atomic(journal_path, journal)
            lane = Path(journal['integration_repo']); published = Path(journal['published_repo'])
            marker_path = common / 'agent-signal-published.json'
            return _finish_published(primary, common, target, lane, published, marker_path, _read(marker_path), journal, source_only=source_only)
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        return {'result':'incomplete','failed_step':'configured-rollout','reason':str(exc),
                'commit':str(commit),'publication_verified':bool(journal), 'rollout_verified':False,
                'attempt':journal.get('attempt') if journal else None}


def _sanitized_commit(repo, commit):
    """Remove only already-qualified generated metadata from a Git source diff."""
    parent = sync_git.git(repo, 'rev-parse', commit + '^')
    with tempfile.TemporaryDirectory(prefix='agent-signal-ready-index-') as temporary:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'))
        sync_git.git(repo, 'read-tree', commit, env=env)
        row = sync_git.git(repo, 'ls-tree', parent, '--', 'host-deltas.json')
        if row:
            metadata, name = row.split('\t', 1)
            mode, _, oid = metadata.split()
            sync_git.git(repo, 'update-index', '--add', '--cacheinfo', mode, oid, name, env=env)
        else:
            sync_git.git(repo, 'update-index', '--force-remove', 'host-deltas.json', env=env)
        tree = sync_git.git(repo, 'write-tree', env=env)
        return sync_git.git(repo, 'commit-tree', tree, '-p', parent, input='qualified ready source ' + commit + '\n')


def _archive(common, journal, reason, conflicts=()):
    journal.update(phase='source-conflict', reason=reason, conflicts=list(conflicts))
    _atomic(common / ('agent-signal-integration-failed-' + journal['attempt'] + '.json'), journal)
    (common / 'agent-signal-integration.json').unlink()


def _abort_composition(lane, base, journal):
    files = journal.get('composition_files', {})
    if files and sync_git.identities(lane, files) != files:
        raise sync_git.SyncBlocked('owned composition changed concurrently; preserve integration bytes for inspection')
    sync_git.git(lane, 'cherry-pick', '--quit')
    _checkout_git(lane, 'reset', '--hard', base)
    for name, identity in files.items():
        if identity != 'deleted' and not sync_git.git(lane, 'ls-tree', base, '--', name):
            path = lane / sync_git.safe_path(lane, name)
            if path.is_file():
                # These exact newly added bytes were journaled before unstaging;
                # hard reset alone would leave them untracked after that point.
                if sync_git.identities(lane, [name])[name] != identity:
                    raise sync_git.SyncBlocked('owned new file changed during composition rollback')
                path.unlink()


def _validate_pending(lane, journal, pending):
    sync_git.assert_integration_owner(lane, journal['attempt'])
    options = journal['receipt']['options']
    target = dict(pending.get('target', {}))
    target['branch'] = journal['receipt']['target']['branch']
    if (pending.get('integration_attempt') != journal['attempt']
            or pending.get('base') != journal['base']
            or target != journal['receipt']['target']
            or pending.get('machine') != options['machine']
            or set(pending.get('owners', ())) != set(options['adopt'])
            or pending.get('capture_recovery')
            or not set(options['include']) <= set(pending.get('files', {}))):
        raise sync_git.SyncBlocked('inner publisher pending state belongs to another integration attempt or scope')


def _verify_composition(lane, journal):
    sync_git.assert_integration_owner(lane, journal['attempt'])
    files = journal['composition_files']
    if (sync_git.git(lane, 'rev-parse', 'HEAD') != journal['base']
            or sync_git.git(lane, 'write-tree') != sync_git.git(lane, 'rev-parse', journal['base'] + '^{tree}')
            or sync_git.changed(lane) != set(files)
            or sync_git.identities(lane, files) != files):
        raise sync_git.SyncBlocked('integration composition changed; preserve unreviewed bytes and retry the exact checked tree')
    with sync_git.prepare_candidate(lane, files, base=journal['base']) as (_, tree):
        if tree != journal['composed_tree']:
            raise sync_git.SyncBlocked('integration composition differs from the frozen checked tree')


def _verify_completion(lane, journal, pending):
    completion = pending['completion']
    commit = completion.get('commit')
    if (completion.get('result') not in {'published', 'synced'} or commit != pending.get('commit')
            or sync_git.git(lane, 'rev-parse', 'HEAD') != commit
            or sync_git.git(lane, 'rev-parse', 'HEAD^{tree}') != pending.get('tree')):
        raise sync_git.SyncBlocked('completed publisher receipt or integration HEAD changed')
    sync_git._scoped_selection_gate(lane, pending)
    options = journal['receipt']['options']
    destinations = reconcile._destinations(lane, options['machine'], options['skill_roots']) if options['adopt'] else []
    actual = reconcile._agent_scope_identities(destinations, options['adopt'])
    expected = pending.get('agent_identities', {})
    for label, root in destinations:
        if actual.get(label) == expected.get(label):
            continue
        # Full-fleet apply removes scoped per-owner provenance while preserving
        # the checked content hash. Accept only that exact normalization during
        # a recorded rollout, including the apply-before-receipt crash window.
        target_state = journal.get('rollout', {}).get('targets', {}).get(str(root), {})
        if not (journal.get('deployment_started') and target_state.get('phase') in
                {'applying', 'installed', 'verified', 'native-verification-incomplete'}):
            raise sync_git.SyncBlocked('selected installed owners changed after publisher completion')
        for name in options['adopt']:
            old = expected.get(label, {}).get(name, {})
            new = actual.get(label, {}).get(name, {})
            if new.get('content') != old.get('content') or new.get('managed') != {'sha256': old.get('content')}:
                raise sync_git.SyncBlocked('selected installed owners changed after publisher completion')
    with sync_git.prepare_candidate(lane, {}, base=commit) as (candidate, _):
        snapshot = reconcile._snapshot(candidate)
        reconcile.fleet.render_snapshot(candidate, snapshot)
        for _, destination in destinations:
            if options['adopt'] and reconcile.fleet.verify_snapshot(snapshot, destination, names=options['adopt']):
                raise sync_git.SyncBlocked('selected installed owner readback differs from the completed commit')
    return dict(completion, completion_recovered=True, verified_owners=options['adopt'],
                installed_verified=bool(pending.get('installed_verified')),
                verification_scope=pending.get('limits'))


def ready_sync(repo, ready, *, adopt=(), include=(), machine='local-windows',
               skill_roots=None, recovery_roots=None, message='chore: integrate checked ready change',
               capture_recovery=False, recovery_artifacts=None, source_only=False, **unsupported):
    repo = Path(repo).resolve()
    phase = 'ready-qualification'
    journal = None
    try:
        if source_only and adopt:
            raise sync_git.SyncBlocked('source-only requires include-only publication without native owner selectors')
        if capture_recovery or recovery_artifacts or unsupported:
            raise sync_git.SyncBlocked('ready integration supports explicit source/portable scopes only')
        primary, common = _primary(repo)
        options = _options(adopt, include, machine, skill_roots, recovery_roots, message)
        exact = sync_git.git(repo, 'rev-parse', '--verify', str(ready) + '^{commit}')
        journal_path = common / 'agent-signal-integration.json'
        observed = _read(journal_path)
        receipt = observed['receipt'] if observed else _qualify(repo, exact, options)
        with sync_git.lock(repo, timeout=120):
            target = sync_git.destination(primary)
            journal = _read(journal_path)
            if journal and journal.get('phase') in {'releasing', 'released'}:
                raise sync_git.SyncBlocked('integration release is pending; resume its exact attempt first')
            if journal:
                receipt = journal['receipt']
                if receipt['ready'] != exact or receipt['options'] != options or receipt['target'] != target:
                    raise sync_git.SyncBlocked('pending integration requires the same exact ready input, scope, and destination')
            elif observed:
                # Another process completed the observed attempt while we waited.
                raise sync_git.SyncBlocked('integration state changed; retry qualification against the published baseline')
            if receipt['target'] != target:
                raise sync_git.SyncBlocked('publication destination changed during readiness checks')
            phase = 'integration-preflight'
            lane, marker_path, marker = _owned_worktree(primary, common, target, 'agent-signal-integration-worktree', INTEGRATION_BRANCH)
            published, published_marker_path, published_marker = _owned_worktree(primary, common, target, 'agent-signal-published', BRANCH)
            if journal and journal['phase'] == 'published':
                phase = 'published-source-refresh'
                return _finish_published(primary, common, target, lane, published, published_marker_path, published_marker, journal, source_only=source_only)
            if not journal:
                if sync_git.read_pending(lane) or sync_git.changed(lane):
                    raise sync_git.SyncBlocked('published integration worktree has unowned pending or dirty state')
                if sync_git.git(lane, 'rev-parse', 'HEAD') != marker['head']:
                    raise sync_git.SyncBlocked('published integration HEAD moved outside its recorded attempt')
                for operation in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply', 'sequencer'):
                    if (sync_git.git_dir(lane) / operation).exists():
                        raise sync_git.SyncBlocked('published worktree has an existing Git operation')
                sync_git.git(lane, 'fetch', '--no-tags', target['remote'], target['ref'])
                base = sync_git.git(lane, 'rev-parse', 'FETCH_HEAD')
                sync_git.git(lane, 'merge-base', '--is-ancestor', marker['head'], base)
                _checkout_git(lane, 'reset', '--hard', base)
                marker['head'] = base
                _atomic(marker_path, marker)
                journal = {'schema_version': 1, 'attempt': uuid.uuid4().hex, 'receipt': receipt,
                           'base': base, 'phase': 'composing', 'deployment_started': False,
                           'published_repo': str(published), 'integration_repo': str(lane)}
                _atomic(journal_path, journal)
                if (lane / 'registry.json').is_file():
                    # The reconciler requires a rendered public baseline even
                    # for a newly created lane; source changes follow below.
                    reconcile.fleet.render_snapshot(lane, reconcile._snapshot(lane))
                phase = 'composing'
                try:
                    for commit in receipt['source_commits']:
                        applying = _sanitized_commit(lane, commit) if receipt['omit_metadata'] else commit
                        _checkout_git(lane, 'cherry-pick', '--no-commit', applying)
                    composed = sync_git.git(lane, 'write-tree')
                    journal['composition_files'] = sync_git.identities(lane, sync_git.changed(lane))
                    _atomic(journal_path, journal)
                    sync_git.git(lane, 'reset', '--mixed', base)
                    files = sync_git.identities(lane, sync_git.changed(lane))
                    with sync_git.prepare_candidate(lane, files, base=base) as (_, recreated):
                        if recreated != composed:
                            raise sync_git.SyncBlocked('scoped publication cannot reproduce the composed Git tree')
                    journal.update(phase='composed', composed_tree=composed)
                    journal['origin_destinations'] = _origin_destinations(lane, options, common)
                    _atomic(journal_path, journal)
                except sync_git.SyncBlocked as exc:
                    conflicts = _names(lane, 'diff', '--name-only', '--diff-filter=U')
                    # Source-only failure: retain exact commit/conflict evidence,
                    # then abort only our owned composition, before any deploy.
                    _abort_composition(lane, base, journal)
                    _archive(common, journal, str(exc), conflicts)
                    return {'result': 'conflict' if conflicts else 'incomplete', 'reason': str(exc),
                            'conflicts': conflicts, 'ready': exact, 'base': base,
                            'published_repo': str(published), 'integration_repo': str(lane)}
            elif journal['phase'] not in {'composed', 'reconciling'}:
                raise sync_git.SyncBlocked('interrupted integration requires inspection of its owned composition')
            phase = 'reconciling'
            pending = sync_git.read_pending(lane)
            if pending:
                _validate_pending(lane, journal, pending)
            else:
                _verify_composition(lane, journal)
                destinations = reconcile._destinations(lane, machine, skill_roots) if adopt else []
                for owner in adopt:
                    owner_state = reconcile._skill_state(lane, reconcile._snapshot(lane), destinations, owner)
                    changed_in_ready = any(path.startswith('skills/' + owner + '/') for path in receipt['paths'])
                    if owner_state.get('origin') or (not changed_in_ready and owner_state.get('changed_live')):
                        raise sync_git.SyncBlocked('ready committed source cannot adopt an unreviewed live origin')
            journal['phase'] = phase
            _atomic(journal_path, journal)
            if pending and pending.get('completion'):
                result = _verify_completion(lane, journal, pending)
            else:
                result = reconcile.complete_sync(lane, machine=machine, adopt=list(adopt),
                    include=list(include), recovery_roots=recovery_roots or {}, skill_roots=skill_roots,
                    capture_recovery=False, scoped=True, message=message, integration_attempt=journal['attempt'])
            # The inner reconciler writes monotonic deployment evidence before
            # touching live roots. Never overwrite it with this caller's cache.
            current = _read(journal_path)
            if not current or current.get('attempt') != journal['attempt']:
                raise sync_git.SyncBlocked('integration journal changed during reconciliation')
            journal = current
            result.update(ready=exact, base=journal['base'], published_repo=str(published), integration_repo=str(lane),
                          source_base=receipt['source_base'], source_commits=receipt['source_commits'])
            if result.get('result') in {'published', 'synced'}:
                marker['head'] = sync_git.git(lane, 'rev-parse', 'HEAD')
                _atomic(marker_path, marker)
                journal.update(phase='published', last_result=result)
                _atomic(journal_path, journal)
                phase = 'published-source-refresh'
                return _finish_published(primary, common, target, lane, published, published_marker_path, published_marker, journal, source_only=source_only)
            else:
                journal['last_result'] = result
                _atomic(journal_path, journal)
            return result
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        return {'result': 'incomplete', 'failed_step': phase, 'reason': str(exc),
                'ready': str(ready), 'published_repo': journal.get('published_repo') if journal else None,
                'commit': (journal or {}).get('last_result', {}).get('commit'),
                'publication_verified': bool(journal and journal.get('phase') == 'published')}


def _release_paths(common, attempt):
    if not re.fullmatch('[0-9a-f]{32}', attempt):
        raise sync_git.SyncBlocked('release requires an exact coordinator attempt identity')
    archive = common / ('agent-signal-released-' + attempt)
    return archive, archive / 'integration-worktree', 'agent-sync/released-' + attempt


def _release_qualification(path, original, original_bytes):
    """Bind an explicitly reviewed legacy witness; do not judge its truth."""
    path = Path(path).absolute()
    if path.is_symlink() or path.resolve() != path:
        raise sync_git.SyncBlocked('qualification evidence cannot be redirected')
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict) or not isinstance(value.get('review'), dict):
        raise sync_git.SyncBlocked('legacy qualification requires a reviewed object')
    review = value.get('review', {})
    binding = {key: original[key] for key in ('attempt', 'base', 'composed_tree')}
    binding['ready'] = original['receipt']['ready']
    if (value.get('schema_version') != 1 or value.get('kind') != 'reviewed-legacy-predeployment'
            or value.get('journal_sha256') != hashlib.sha256(original_bytes).hexdigest()
            or value.get('binding') != binding
            or review.get('decision') != 'qualified-predeployment'
            or not all(isinstance(review.get(k), str) and review[k].strip()
                       for k in ('reason', 'reviewer_ref', 'coverage_end', 'no_retry_since_checkpoint'))
            or not all(isinstance(value.get(k), str) and value[k].strip()
                       for k in ('original_sync_command_id', 'checkpoint_command_id'))):
        raise sync_git.SyncBlocked('legacy qualification is not bound to this reviewed attempt')
    evidence = value['evidence']
    if (not isinstance(evidence, dict)
            or set(evidence) != {'execution', 'supplement', 'state', 'remote', 'remote_checkpoint', 'checkpoint'}):
        raise sync_git.SyncBlocked('legacy qualification requires all six reviewed evidence roles')
    bundle = {'receipt.json': raw}
    for record in evidence.values():
        if not isinstance(record, dict):
            raise sync_git.SyncBlocked('qualification evidence requires file identities')
        name = record['file']
        if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.json', name)
                or name in bundle or not re.fullmatch('[0-9a-f]{64}', record['sha256'])):
            raise sync_git.SyncBlocked('qualification evidence name or identity is invalid')
        source = path.parent / name
        if source.is_symlink() or source.resolve() != source.absolute():
            raise sync_git.SyncBlocked('qualification evidence cannot be redirected')
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != record['sha256']:
            raise sync_git.SyncBlocked('reviewed qualification evidence changed')
        bundle[name] = data
    return value, bundle


def _release_live_qualification(value, original):
    # Current equality only corroborates the independently reviewed history.
    roots = original['origin_destinations']
    live = value['live']
    owners = original['receipt']['options']['adopt']
    if (not isinstance(live, list) or any(not isinstance(row, dict) or not isinstance(row.get('owners'), dict) for row in live)
            or len(live) != len(roots) or sorted(row['root'] for row in live) != sorted(roots)
            or any(sorted(row['owners']) != sorted(owners) for row in live)):
        raise sync_git.SyncBlocked('qualification live scope differs from the frozen attempt')
    for row in live:
        root = Path(row['root'])
        if reconcile.fleet.sha256_file(root / reconcile.fleet.STATE_FILE) != row['managed_state_sha256']:
            raise sync_git.SyncBlocked('qualified managed state changed')
        for owner, identity in row['owners'].items():
            if reconcile.fleet.directory_record(root / owner)['sha256'] != identity:
                raise sync_git.SyncBlocked('qualified live owner changed')


def _retain_release_bytes(path, data):
    if path.is_symlink() or path.resolve() != path.absolute():
        raise sync_git.SyncBlocked('release evidence cannot be redirected')
    existing = path.read_bytes() if path.exists() else b''
    if not data.startswith(existing):
        raise sync_git.SyncBlocked('release archived evidence differs')
    with path.open('ab') as handle:
        handle.write(data[len(existing):])
        handle.flush()
        os.fsync(handle.fileno())


def _release_source_kind(original):
    """Classify truthful pre-publisher evidence, never manufacture a rejection."""
    result = original.get('last_result')
    receipt = original.get('receipt')
    options = receipt.get('options') if isinstance(receipt, dict) else None
    if (original.get('schema_version') == 1 and original.get('phase') == 'reconciling'
            and original.get('deployment_started') is False and result is None
            and isinstance(options, dict) and options.get('adopt') == []
            and isinstance(options.get('include'), list) and options['include']
            and original.get('origin_destinations') == []
            and isinstance(original.get('composition_files'), dict) and original['composition_files']
            and set(options['include']) == set(original['composition_files'])
            and isinstance(original.get('composed_tree'), str)
            and re.fullmatch('[0-9a-f]{40}', original['composed_tree'])):
        return 'interrupted-include-only'
    return 'owner-classification'


def _release_preflight(primary, common, original, archive, archived_lane, archived_branch, qualification=None):
    """Verify an exact rejected or interrupted source before any publisher action."""
    interrupted = _release_source_kind(original) == 'interrupted-include-only'
    result = original.get('last_result') or {}
    allowed_result = {'result', 'reason', 'owners', 'measurements', 'ready', 'base',
                      'published_repo', 'integration_repo', 'source_base', 'source_commits'}
    if not interrupted and (original.get('schema_version') != 1 or original.get('phase') != 'reconciling'
            or not (original.get('deployment_started') is False
                    or ('deployment_started' not in original and qualification is not None))
            or result.get('result') != 'review-required'
            or result.get('reason') != 'selected owner missing, unadmitted, or conflicting'
            or set(result) - allowed_result
            or result.get('measurements', {}).get('checks', [])):
        raise sync_git.SyncBlocked('only a recorded pre-publisher owner-classification rejection can be released')
    if qualification is not None:
        _release_live_qualification(qualification, original)
    target = original['receipt']['target']
    receipt = original['receipt']
    if not interrupted and (result.get('ready') != receipt['ready'] or result.get('base') != original['base']
            or result.get('owners') != sorted(receipt['options']['adopt'])
            or any(result.get(key) != original[key] for key in ('integration_repo', 'published_repo'))
            or any(result.get(key) != receipt[key] for key in ('source_base', 'source_commits'))):
        raise sync_git.SyncBlocked('release rejection is not bound to the pending source and selection')
    if sync_git.destination(primary) != target:
        raise sync_git.SyncBlocked('release publication destination changed')
    old_lane = common / 'agent-signal-integration-worktree'
    published = common / 'agent-signal-published'
    if original['integration_repo'] != str(old_lane) or original['published_repo'] != str(published):
        raise sync_git.SyncBlocked('release worktree paths are not coordinator owned')
    if old_lane.exists() == archived_lane.exists():
        raise sync_git.SyncBlocked('release requires exactly one retained integration worktree')
    lane = old_lane if old_lane.exists() else archived_lane
    old_marker = common / 'agent-signal-integration-worktree.json'
    archived_marker = archive / 'integration-marker.json'
    if old_marker.exists() == archived_marker.exists():
        raise sync_git.SyncBlocked('release integration marker is missing or ambiguous')
    marker_path = old_marker if old_marker.exists() else archived_marker
    for path in (archive, lane, published, marker_path, common / 'agent-signal-published.json'):
        if path.is_symlink() or path.resolve() != path.absolute():
            raise sync_git.SyncBlocked('release paths cannot be linked or redirected')
    marker = _read(marker_path)
    published_marker = _read(common / 'agent-signal-published.json')
    for owned, record in ((lane, marker), (published, published_marker)):
        if (not record or record['common_repo'] != str(common) or record['target'] != target
                or (owned == lane and record['head'] != original['base'])
                or (not interrupted and record['head'] != original['base'])
                or sync_git.common_dir(owned) != common
                or sync_git.git(owned, 'rev-parse', 'HEAD') != record['head']):
            raise sync_git.SyncBlocked('release worktree identity, marker or publication HEAD changed')
        if interrupted and owned == published:
            # Source-only history can leave the stable cache behind the published base.
            # It is not modified by release; only an exact owned ancestor is acceptable.
            sync_git.git(published, 'merge-base', '--is-ancestor', record['head'], original['base'])
        admin = sync_git.git_dir(owned)
        pointer = owned / '.git'
        if (not admin.is_relative_to(common / 'worktrees') or admin.resolve() != admin.absolute()
                or not pointer.is_file() or pointer.is_symlink()
                or Path((admin / 'gitdir').read_text(encoding='utf-8').rstrip('\r\n')).resolve() != pointer.absolute()):
            raise sync_git.SyncBlocked('release worktree registration backlink differs; preserve and inspect the interrupted Git move')
        configured = sync_git.destination(owned)
        configured['branch'] = target['branch']
        if configured != target:
            raise sync_git.SyncBlocked('release worktree upstream changed')
        if (sync_git.git_dir(owned) / 'agent-signal-sync.json').exists():
            raise sync_git.SyncBlocked('publisher evidence exists; release cannot undo deployment or publication')
    branch = sync_git.git(lane, 'symbolic-ref', '--short', 'HEAD')
    if branch not in ({INTEGRATION_BRANCH, archived_branch} if lane == old_lane else {archived_branch}):
        raise sync_git.SyncBlocked('release integration branch changed')
    if sync_git.git(published, 'symbolic-ref', '--short', 'HEAD') != BRANCH:
        raise sync_git.SyncBlocked('release published branch changed')
    if branch == INTEGRATION_BRANCH and sync_git.git(primary, 'for-each-ref', '--format=%(refname)', 'refs/heads/' + archived_branch):
        raise sync_git.SyncBlocked('release archive branch already exists')
    for operation in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply', 'sequencer'):
        if (sync_git.git_dir(lane) / operation).exists():
            raise sync_git.SyncBlocked('release cannot preserve an uncertain Git operation as a finished composition')
    files = original['composition_files']
    tree = original['composed_tree']
    if (not files or sync_git.changed(lane) != set(files)
            or sync_git.identities(lane, files) != files
            or sync_git.git(lane, 'write-tree') != sync_git.git(lane, 'rev-parse', original['base'] + '^{tree}')
            or set(_names(lane, 'diff', '--name-only', '--no-renames', original['base'], tree)) != set(files)):
        raise sync_git.SyncBlocked('release composition or index changed; preserve the pending attempt')
    for name, identity in files.items():
        expected = (hashlib.sha256(sync_git._raw_git(lane, 'show', tree + ':' + name)).hexdigest()
                    if sync_git.git(lane, 'ls-tree', tree, '--', name) else 'deleted')
        if identity != expected:
            raise sync_git.SyncBlocked('release composition differs from its frozen Git tree')
    return lane, marker_path, branch


def release_predeployment(repo, attempt, qualification=None):
    """Retain an exact rejected or interrupted source attempt, freeing its coordinator slot.

    No deployment, fetch, reset, checkout, file deletion or baseline update.
    The releasing phase blocks every publisher and permits exact crash recovery.
    """
    try:
        primary, common = _primary(Path(repo).resolve())
        archive, archived_lane, archived_branch = _release_paths(common, attempt)
        journal_path = common / 'agent-signal-integration.json'
        with sync_git.lock(primary):
            journal = _read(journal_path)
            if not journal or journal.get('attempt') != attempt:
                raise sync_git.SyncBlocked('release requires the exact currently pending attempt')
            if journal.get('phase') in {'releasing', 'released'}:
                retained = archive / 'attempt.json'
                if (archive.is_symlink() or archive.resolve() != archive.absolute()
                        or retained.is_symlink() or retained.resolve() != retained.absolute()):
                    raise sync_git.SyncBlocked('release journal evidence cannot be redirected')
                original_bytes = retained.read_bytes()
                release = journal.get('release') or {}
                if (set(release) - {'original_sha256', 'qualification_sha256'}
                        or release.get('original_sha256') != hashlib.sha256(original_bytes).hexdigest()
                        or ('qualification_sha256' in release and not re.fullmatch('[0-9a-f]{64}', release['qualification_sha256']))):
                    raise sync_git.SyncBlocked('release evidence identity changed')
                original = json.loads(original_bytes)
                if original.get('attempt') != attempt:
                    raise sync_git.SyncBlocked('release evidence belongs to another attempt')
            else:
                original_bytes = journal_path.read_bytes()
                original = journal
            proof, bundle = None, None
            retained_proof = (journal.get('release') or {}).get('qualification_sha256')
            if (journal.get('phase') in {'releasing', 'released'} and not retained_proof
                    and ('deployment_started' not in original or (archive / 'qualification').exists())):
                raise sync_git.SyncBlocked('retained qualification is missing its release binding')
            proof_path = archive / 'qualification' / 'receipt.json' if retained_proof else qualification
            if proof_path is not None:
                if 'deployment_started' in original:
                    raise sync_git.SyncBlocked('external qualification applies only to an absent legacy deployment marker')
                proof, bundle = _release_qualification(proof_path, original, original_bytes)
                digest = hashlib.sha256(bundle['receipt.json']).hexdigest()
                if retained_proof and digest != retained_proof:
                    raise sync_git.SyncBlocked('release qualification identity changed')
                if retained_proof and set(p.name for p in (archive / 'qualification').iterdir()) != set(bundle):
                    raise sync_git.SyncBlocked('retained qualification evidence set changed')
                if retained_proof and qualification is not None and Path(qualification).read_bytes() != bundle['receipt.json']:
                    raise sync_git.SyncBlocked('retry qualification differs from retained evidence')
            lane, marker_path, branch = _release_preflight(primary, common, original, archive, archived_lane, archived_branch, proof)
            if journal.get('phase') not in {'releasing', 'released'}:
                if archive.exists():
                    if set(p.name for p in archive.iterdir()) - ({'attempt.json', 'qualification'} if bundle else {'attempt.json'}):
                        raise sync_git.SyncBlocked('release archive already contains other evidence')
                else:
                    archive.mkdir()
                _retain_release_bytes(archive / 'attempt.json', original_bytes)
                release = {'original_sha256': hashlib.sha256(original_bytes).hexdigest()}
                if bundle:
                    directory = archive / 'qualification'
                    if directory.is_symlink() or directory.resolve() != directory.absolute():
                        raise sync_git.SyncBlocked('qualification archive cannot be redirected')
                    directory.mkdir(exist_ok=True)
                    if set(p.name for p in directory.iterdir()) - set(bundle):
                        raise sync_git.SyncBlocked('qualification archive contains other evidence')
                    for name, data in bundle.items():
                        _retain_release_bytes(directory / name, data)
                    release['qualification_sha256'] = hashlib.sha256(bundle['receipt.json']).hexdigest()
                journal = dict(original, phase='releasing', release=release)
                _atomic(journal_path, journal)
            # Recheck exact evidence on retries and between each retained-state move.
            if branch == INTEGRATION_BRANCH:
                sync_git.git(lane, 'branch', '-m', archived_branch)
            lane, marker_path, _ = _release_preflight(primary, common, original, archive, archived_lane, archived_branch, proof)
            if lane != archived_lane:
                sync_git.git(primary, 'worktree', 'move', str(lane), str(archived_lane))
            lane, marker_path, _ = _release_preflight(primary, common, original, archive, archived_lane, archived_branch, proof)
            if marker_path != archive / 'integration-marker.json':
                marker_path.rename(archive / 'integration-marker.json')
            _release_preflight(primary, common, original, archive, archived_lane, archived_branch, proof)
            if (archive / 'release.json').exists():
                raise sync_git.SyncBlocked('release completion evidence already exists')
            journal['phase'] = 'released'
            _atomic(journal_path, journal)
            journal_path.rename(archive / 'release.json')
            return {'result': 'released', 'attempt': attempt, 'archive': str(archive),
                    'retained_worktree': str(archived_lane), 'retained_branch': archived_branch,
                    'verification_scope': 'truthful pre-publisher disposition and frozen local composition; no deployment or remote action'}
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        return {'result': 'review-required', 'attempt': attempt, 'reason': str(exc)}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Retain and release a rejected pre-deployment ready attempt.')
    parser.add_argument('action', choices=['release','rollout'])
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--attempt')
    parser.add_argument('--commit', help='exact verified published release to finish installing')
    parser.add_argument('--qualification', type=Path, help='explicitly reviewed, source-bound legacy evidence receipt')
    args = parser.parse_args(argv)
    if args.action == 'release':
        if not args.attempt: parser.error('release requires --attempt')
        result = release_predeployment(args.repo, args.attempt, args.qualification)
    else:
        if not args.commit: parser.error('rollout requires --commit')
        result = rollout_published(args.repo, args.commit)
    print(json.dumps(result, indent=2))
    return 0 if result['result'] in {'released','synced'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
