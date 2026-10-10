"""Frozen ready commits, isolated Git integration, existing scoped reconciliation."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid

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


def _finish_published(primary, common, target, lane, published, published_marker_path, published_marker, journal):
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
    if sync_git.changed(published):
        raise sync_git.SyncBlocked('stable published source has unowned dirty files')
    if sync_git.git(published, 'rev-parse', 'HEAD') != published_marker['head']:
        # Recover the owned fast-forward/reset-before-marker crash window.
        if sync_git.git(published, 'rev-parse', 'HEAD') != commit:
            raise sync_git.SyncBlocked('stable published HEAD changed outside its integration attempt')
    sync_git.git(published, 'merge-base', '--is-ancestor', published_marker['head'], commit)
    _checkout_git(published, 'reset', '--hard', commit)
    published_marker['head'] = commit
    _atomic(published_marker_path, published_marker)
    snapshot = reconcile._snapshot(published)
    reconcile.fleet.render_snapshot(published, snapshot)
    owners = journal['receipt']['options']['adopt']
    migrations = []
    for path in journal['origin_destinations']:
        destination = Path(path)
        if owners and reconcile.fleet.verify_snapshot(snapshot, destination, names=owners):
            raise sync_git.SyncBlocked('selected installed owners changed before source origin migration')
        migrations.append(reconcile.fleet.migrate_source_origin(snapshot, destination,
                          expected_state=reconcile.fleet.state_identity(destination)))
    result.update(published_repo=str(published), integration_repo=str(lane), source_origin_migrations=migrations)
    pending = sync_git.read_pending(lane)
    if pending:
        _validate_pending(lane, journal, pending)
        if not pending.get('completion') or pending['completion'].get('commit') != commit:
            raise sync_git.SyncBlocked('publisher completion does not match the published integration receipt')
        (sync_git.git_dir(lane) / 'agent-signal-sync.json').unlink()
    (common / 'agent-signal-integration.json').unlink()
    return result


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
    if (completion.get('result') != 'synced' or commit != pending.get('commit')
            or sync_git.git(lane, 'rev-parse', 'HEAD') != commit
            or sync_git.git(lane, 'rev-parse', 'HEAD^{tree}') != pending.get('tree')):
        raise sync_git.SyncBlocked('completed publisher receipt or integration HEAD changed')
    sync_git._scoped_selection_gate(lane, pending)
    options = journal['receipt']['options']
    destinations = reconcile._destinations(lane, options['machine'], options['skill_roots']) if options['adopt'] else []
    if reconcile._agent_scope_identities(destinations, options['adopt']) != pending.get('agent_identities', {}):
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
               capture_recovery=False, recovery_artifacts=None, **unsupported):
    repo = Path(repo).resolve()
    phase = 'ready-qualification'
    journal = None
    try:
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
                return _finish_published(primary, common, target, lane, published, published_marker_path, published_marker, journal)
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
                           'base': base, 'phase': 'composing', 'published_repo': str(published), 'integration_repo': str(lane)}
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
            result.update(ready=exact, base=journal['base'], published_repo=str(published), integration_repo=str(lane),
                          source_base=receipt['source_base'], source_commits=receipt['source_commits'])
            if result.get('result') == 'synced':
                marker['head'] = sync_git.git(lane, 'rev-parse', 'HEAD')
                _atomic(marker_path, marker)
                journal.update(phase='published', last_result=result)
                _atomic(journal_path, journal)
                phase = 'published-source-refresh'
                return _finish_published(primary, common, target, lane, published, published_marker_path, published_marker, journal)
            else:
                journal['last_result'] = result
                _atomic(journal_path, journal)
            return result
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        return {'result': 'incomplete', 'failed_step': phase, 'reason': str(exc),
                'ready': str(ready), 'published_repo': journal.get('published_repo') if journal else None,
                'commit': (journal or {}).get('last_result', {}).get('commit'),
                'publication_verified': bool(journal and journal.get('phase') == 'published')}
