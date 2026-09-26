"""Git completion for reconcile.py; no force-push or implicit broad staging."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


class SyncBlocked(RuntimeError):
    pass


def git(repo: Path, *args: str, env=None, input=None) -> str:
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                            text=True, encoding='utf-8', env=env, input=input, timeout=120)
    if result.returncode:
        # Do not persist remote URLs, credential-helper output, or hook secrets.
        raise SyncBlocked('git ' + args[0] + ' failed; inspect the repository or remote')
    return result.stdout if '-z' in args else result.stdout.strip()


def git_dir(repo: Path) -> Path:
    return Path(git(repo, 'rev-parse', '--absolute-git-dir'))


@contextmanager
def lock(repo: Path):
    """OS-released lock: a process crash does not leave a stale lock owner."""
    handle = (git_dir(repo) / 'agent-signal-sync.lock').open('a+b')
    handle.seek(0, 2)
    if handle.tell() == 0:
        handle.write(b'0')
        handle.flush()
    handle.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise SyncBlocked('another sync is running') from exc
    try:
        yield
    finally:
        handle.close()


def changed(repo: Path) -> set[str]:
    # -z handles whitespace, Unicode, and literal pathspec metacharacters.
    tracked = git(repo, 'diff', '--name-only', '-z', 'HEAD', '--')
    new = git(repo, 'ls-files', '--others', '--exclude-standard', '-z')
    return {p for p in (tracked + '\0' + new).split('\0') if p}


def safe_path(repo: Path, value: str) -> str:
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or '..' in relative.parts or '.git' in {part.casefold() for part in relative.parts}:
        raise SyncBlocked('include requires an exact repository-relative file')
    path = repo / relative
    if path.is_dir() or not path.resolve().is_relative_to(repo.resolve()):
        raise SyncBlocked('include cannot select a directory or an external path')
    if any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)()
           for p in (path, *path.parents) if p != repo.parent):
        raise SyncBlocked('linked publication paths require review')
    return relative.as_posix()


def identities(repo: Path, paths) -> dict[str, str]:
    result = {}
    for name in sorted(paths):
        path = repo / safe_path(repo, name)
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'deleted'
    return result


def assert_publishable(repo: Path, paths):
    import public_check
    reviewed = public_check.reviewed_findings(repo)
    for name in paths:
        relative = Path(safe_path(repo, name))
        if any(part in public_check.EXCLUDED_DIRS for part in relative.parts) or relative.name == '.env':
            raise SyncBlocked('private or generated paths cannot be published by sync')
        path = repo / relative
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeError as exc:
            raise SyncBlocked('non-text publication needs separate review') from exc
        for number, line in enumerate(text.splitlines(), 1):
            for rule, pattern in public_check.RULES.items():
                if pattern.search(line) and (relative, number, rule) not in reviewed:
                    raise SyncBlocked(f'public-safety check failed: {name}:{number} ({rule})')


def read_pending(repo: Path):
    path = git_dir(repo) / 'agent-signal-sync.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def save_pending(repo: Path, data):
    path = git_dir(repo) / 'agent-signal-sync.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def destination(repo: Path) -> dict[str, str]:
    branch = git(repo, 'symbolic-ref', '--quiet', '--short', 'HEAD')
    remote = git(repo, 'config', '--get', f'branch.{branch}.remote')
    ref = git(repo, 'config', '--get', f'branch.{branch}.merge')
    if remote == '.' or not ref.startswith('refs/heads/'):
        raise SyncBlocked('sync requires an existing remote branch upstream')
    # Exactly one publication destination; reject ambiguous pushurl overrides.
    fetch_urls = git(repo, 'remote', 'get-url', '--all', remote).splitlines()
    push_urls = git(repo, 'remote', 'get-url', '--push', '--all', remote).splitlines()
    if len(fetch_urls) != 1 or push_urls != fetch_urls:
        raise SyncBlocked('fetch and push destinations must be the same single remote')
    return {'branch': branch, 'remote': remote, 'ref': ref,
            'remote_identity': hashlib.sha256(fetch_urls[0].encode()).hexdigest()}


def preflight(repo: Path, target, *, files=None, scoped=False):
    staged = set(git(repo, 'diff', '--cached', '--no-renames', '--name-only', '-z').split('\0')) - {''}
    if staged and (not scoped or staged & set(files or ())):
        raise SyncBlocked('the Git index already contains staged work; preserve it for review')
    for name in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply'):
        if (git_dir(repo) / name).exists():
            raise SyncBlocked('finish the existing Git merge/rebase operation first')
    git(repo, 'var', 'GIT_AUTHOR_IDENT')
    git(repo, 'var', 'GIT_COMMITTER_IDENT')
    git(repo, 'fetch', '--no-tags', target['remote'], target['ref'])
    git(repo, 'merge-base', '--is-ancestor', 'FETCH_HEAD', 'HEAD')
    if git(repo, 'rev-parse', 'FETCH_HEAD') != git(repo, 'rev-parse', 'HEAD'):
        raise SyncBlocked('existing unpublished commits need review before sync can publish them')


def _raw_git(repo, *args, input=None, env=None):
    result = subprocess.run(['git', '-C', str(repo), *args], input=input,
                            capture_output=True, env=env, timeout=120)
    if result.returncode:
        raise SyncBlocked('git ' + args[0] + ' failed; inspect the repository or remote')
    return result.stdout


def _tree_entries(repo, tree):
    entries = {}
    for entry in _raw_git(repo, 'ls-tree', '-r', '-z', tree).split(b'\0'):
        if not entry:
            continue
        header, name = entry.split(b'\t', 1)
        mode, kind, oid = header.decode('ascii').split()
        name = name.decode('utf-8')
        if mode not in ('100644', '100755') or kind != 'blob':
            raise SyncBlocked('candidate contains linked or unsupported Git entries')
        entries[name] = (mode, oid)
    return entries


def _blobs(repo, entries):
    oids = sorted({oid for _, oid in entries.values()})
    if not oids:
        return {}
    raw = _raw_git(repo, 'cat-file', '--batch', input=('\n'.join(oids) + '\n').encode('ascii'))
    offset = 0
    blobs = {}
    for oid in oids:
        end = raw.find(b'\n', offset)
        fields = raw[offset:end].decode('ascii').split()
        if end < 0 or len(fields) != 3 or fields[:2] != [oid, 'blob']:
            raise SyncBlocked('candidate blob readback failed')
        size = int(fields[2])
        start = end + 1
        if size < 0 or start + size >= len(raw) or raw[start + size:start + size + 1] != b'\n':
            raise SyncBlocked('candidate blob readback is incomplete')
        blobs[oid] = raw[start:start + size]
        offset = start + size + 1
    if offset != len(raw):
        raise SyncBlocked('candidate blob readback has unexpected data')
    return blobs


@contextmanager
def prepare_candidate(repo: Path, files: dict[str, str], base='HEAD', overrides=None):
    """Yield (isolated baseline-plus-selection directory, raw-byte Git tree).

    Overrides support prospective edits without modifying canonical source. Their
    bytes must match files' SHA256 identities (None means 'deleted'). The caller
    owns rechecking upstream identities before applying prospective edits.
    """
    overrides = overrides or {}
    if set(overrides) - set(files):
        raise SyncBlocked('candidate overrides must belong to the reviewed selection')
    base = git(repo, 'rev-parse', '--verify', base + '^{tree}')
    entries = _tree_entries(repo, base)
    with tempfile.TemporaryDirectory(prefix='agent-signal-candidate-') as directory:
        root = Path(directory) / 'source'
        root.mkdir()
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / 'index'))
        git(repo, 'read-tree', base, env=env)
        changes = []
        for name, expected in sorted(files.items()):
            if safe_path(repo, name) != name:
                raise SyncBlocked('candidate paths must be normalized repository-relative files')
            data = overrides[name] if name in overrides else ((repo / name).read_bytes() if (repo / name).is_file() else None)
            actual = hashlib.sha256(data).hexdigest() if data is not None else 'deleted'
            if actual != expected:
                raise SyncBlocked('candidate bytes do not match reviewed file identities')
            if data is None:
                entries.pop(name, None)
                changes.append('0 ' + '0' * len(base) + '\t' + name + '\0')
            else:
                oid = _raw_git(repo, 'hash-object', '-w', '--stdin', input=data).decode('ascii').strip()
                mode = entries.get(name, ('100644', None))[0]
                entries[name] = (mode, oid)
                changes.append(mode + ' ' + oid + '\t' + name + '\0')
        git(repo, 'update-index', '-z', '--index-info', env=env, input=''.join(changes))
        tree = git(repo, 'write-tree', env=env)
        # Materialize blobs directly: checkout/archive can consult attributes,
        # filters, or export rules outside the reviewed tree.
        materialized = {}
        blobs = _blobs(repo, entries)
        for name, (mode, oid) in sorted(entries.items()):
            parts = name.split('/')
            if (any(not part or '\\' in part or ':' in part or part.rstrip(' .') != part
                    or part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                                                     *('COM' + str(i) for i in range(1, 10)),
                                                     *('LPT' + str(i) for i in range(1, 10))}
                    for part in parts)):
                raise SyncBlocked('candidate path cannot be materialized without aliases')
            for count in range(1, len(parts) + 1):
                prefix = '/'.join(parts[:count])
                key = prefix.casefold()
                if key in materialized and materialized[key] != prefix:
                    raise SyncBlocked('candidate path cannot be materialized without aliases')
                materialized[key] = prefix
            if safe_path(root, name) != name:
                raise SyncBlocked('unsafe candidate tree path')
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blobs[oid])
            if mode == '100755':
                path.chmod(0o755)
        yield root, tree


def _index_entries(repo):
    return _raw_git(repo, 'ls-files', '--stage', '-z')


def _reconcile_scoped_index(repo, paths, expected):
    """CAS selected entries while Git's own index lock protects concurrent stage."""
    index = Path(git(repo, 'rev-parse', '--git-path', 'index'))
    if not index.is_absolute():
        index = repo / index
    lock_path = index.with_name(index.name + '.lock')
    try:
        handle = lock_path.open('xb')
    except FileExistsError as exc:
        raise SyncBlocked('Git index is locked by another operation') from exc
    replaced = False
    try:
        if _index_entries(repo) != expected:
            raise SyncBlocked('Git index changed before selected entries were reconciled')
        with tempfile.TemporaryDirectory(prefix='agent-signal-index-') as directory:
            isolated = Path(directory) / 'index'
            shutil.copyfile(index, isolated)
            env = dict(os.environ, GIT_INDEX_FILE=str(isolated))
            git(repo, '--literal-pathspecs', 'reset', '-q', 'HEAD', '--pathspec-from-file=-',
                '--pathspec-file-nul', env=env, input=''.join(p + '\0' for p in sorted(paths)))
            handle.write(isolated.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        handle.close()
        os.replace(lock_path, index)
        replaced = True
    finally:
        handle.close()
        if not replaced:
            lock_path.unlink(missing_ok=True)


def _scoped_selection_gate(repo, pending):
    if identities(repo, pending['files']) != pending['files']:
        raise SyncBlocked('reviewed files changed after checks; review before retrying')
    reference = 'HEAD' if pending.get('index_reconciled') else pending['base']
    staged = set(git(repo, 'diff', '--cached', '--no-renames', '--name-only', '-z', reference).split('\0')) - {''}
    # Recover a crash after selected entries were reset but before journaling it.
    if (staged & set(pending['files']) and not pending.get('index_reconciled')
            and pending.get('tree') and git(repo, 'rev-parse', 'HEAD') != pending['base']
            and git(repo, 'rev-parse', 'HEAD^{tree}') == pending['tree']
            and git(repo, 'rev-list', '--parents', '-n', '1', 'HEAD').split()
            == [git(repo, 'rev-parse', 'HEAD'), pending['base']]):
        staged = set(git(repo, 'diff', '--cached', '--no-renames', '--name-only', '-z', 'HEAD').split('\0')) - {''}
    if staged & set(pending['files']):
        raise SyncBlocked('selected paths overlap staged work; preserve it for review')


def _publish_scoped(repo, pending, *, verify, readback):
    step = 'verify'
    try:
        if destination(repo) != pending['target']:
            raise SyncBlocked('the Git publication destination changed')
        if not pending.get('tree'):
            raise SyncBlocked('scoped publication requires the checked candidate tree')
        import public_check
        if any(Path(name).parts[:len(prefix)] == prefix
               for name in pending['files'] for prefix in public_check.EXCLUDED_PREFIXES):
            raise SyncBlocked('private or generated paths cannot be published by sync')
        _scoped_selection_gate(repo, pending)
        index = _index_entries(repo)
        with prepare_candidate(repo, pending['files'], base=pending['base']) as (candidate, tree):
            if pending.get('tree') and tree != pending['tree']:
                raise SyncBlocked('candidate differs from the checked tree')
            pending['tree'] = tree
            assert_publishable(candidate, pending['files'])
            verify()
            _scoped_selection_gate(repo, pending)
            if _index_entries(repo) != index:
                raise SyncBlocked('Git index changed during verification')
            step = 'commit'
            base = pending['base']
            head = git(repo, 'rev-parse', 'HEAD')
            if 'commit' not in pending:
                if head != base:
                    if (git(repo, 'rev-parse', 'HEAD^') != base
                            or git(repo, 'show', '-s', '--format=%B', 'HEAD') != pending['message']
                            or git(repo, 'rev-parse', 'HEAD^{tree}') != tree):
                        raise SyncBlocked('HEAD changed outside this sync')
                    pending['commit'] = head
                elif tree != git(repo, 'rev-parse', base + '^{tree}'):
                    save_pending(repo, pending)
                    with tempfile.TemporaryDirectory(prefix='agent-signal-index-') as directory:
                        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / 'index'))
                        git(repo, 'read-tree', tree, env=env)
                        git(repo, 'commit', '-m', pending['message'], env=env)
                    pending['commit'] = git(repo, 'rev-parse', 'HEAD')
                else:
                    pending['commit'] = base
                save_pending(repo, pending)
            commit = pending['commit']
            if (git(repo, 'rev-parse', 'HEAD') != commit
                    or git(repo, 'rev-parse', commit + '^{tree}') != tree
                    or (commit != base and git(repo, 'rev-list', '--parents', '-n', '1', commit).split() != [commit, base])):
                raise SyncBlocked('HEAD or a commit hook changed the checked commit')
            _scoped_selection_gate(repo, pending)
            if _index_entries(repo) != index:
                raise SyncBlocked('Git index changed during commit')
            if commit != base and not pending.get('index_reconciled'):
                _reconcile_scoped_index(repo, pending['files'], index)
                pending['index_reconciled'] = True
                save_pending(repo, pending)
            index = _index_entries(repo)
            step = 'verify'
            verify()
            _scoped_selection_gate(repo, pending)
            if _index_entries(repo) != index or git(repo, 'rev-parse', 'HEAD') != commit:
                raise SyncBlocked('repository changed before publication')
            step = 'push'
            target = pending['target']
            if destination(repo) != target:
                raise SyncBlocked('the Git publication destination changed')
            remote = git(repo, 'ls-remote', '--refs', target['remote'], target['ref']).split()
            if remote not in ([base, target['ref']], [commit, target['ref']]):
                raise SyncBlocked('remote branch changed outside this sync')
            if remote != [commit, target['ref']]:
                # Exactly one parent == base and exact checked tree above prove
                # this CAS update is fast-forward; never authorize a rewrite.
                git(repo, 'push', '--force-with-lease=' + target['ref'] + ':' + base,
                    target['remote'], f"{commit}:{target['ref']}")
            step = 'remote-readback'
            if git(repo, 'ls-remote', '--refs', target['remote'], target['ref']).split() != [commit, target['ref']]:
                raise SyncBlocked('remote branch does not match the committed changes')
            step = 'published-readback'
            readback()
            _scoped_selection_gate(repo, pending)
            if (_index_entries(repo) != index or git(repo, 'rev-parse', 'HEAD') != commit
                    or destination(repo) != target):
                raise SyncBlocked('repository changed before final verification')
        (git_dir(repo) / 'agent-signal-sync.json').unlink()
        return {'result': 'synced', 'commit': commit, 'remote': target['remote'],
                'branch': target['branch'], 'agents_verified': bool(pending.get('agents_verified')),
                'remote_verified': True}
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        return {'result': 'incomplete', 'failed_step': step, 'reason': str(exc),
                'commit': pending.get('commit'), 'retry': 'run the same sync after resolving the failure'}


def publish(repo: Path, pending, *, verify, readback=lambda: None):
    """Resume exact checked content; success requires remote readback and agent checks."""
    if pending.get('scoped'):
        return _publish_scoped(repo, pending, verify=verify, readback=readback)
    step = 'verify'
    try:
        if destination(repo) != pending['target']:
            raise SyncBlocked('the Git publication destination changed')
        if git(repo, 'diff', '--cached', '--name-only', '-z'):
            own_commit_window = (not pending.get('index_reconciled') and pending.get('tree')
                                 and git(repo, 'rev-parse', 'HEAD^{tree}') == pending['tree']
                                 and git(repo, 'write-tree') == git(repo, 'rev-parse', pending['base'] + '^{tree}'))
            if not own_commit_window:
                raise SyncBlocked('new staged work must be preserved; resolve it before retrying sync')
        if identities(repo, pending['files']) != pending['files']:
            raise SyncBlocked('reviewed files changed after checks; review before retrying')
        if changed(repo) - set(pending['files']):
            raise SyncBlocked('new unrelated changes appeared during sync')
        verify()
        assert_publishable(repo, pending['files'])
        if identities(repo, pending['files']) != pending['files'] or changed(repo) - set(pending['files']):
            raise SyncBlocked('files changed during verification')
        step = 'commit'
        head = git(repo, 'rev-parse', 'HEAD')
        base = pending['base']
        if 'commit' not in pending:
            if head != base:
                # Recover the crash window after commit but before journal update.
                if git(repo, 'rev-parse', 'HEAD^') != base or git(repo, 'show', '-s', '--format=%B', 'HEAD') != pending['message']:
                    raise SyncBlocked('HEAD changed outside this sync')
                pending['commit'] = head
            elif changed(repo):
                # Isolated index preserves the operator's real index on failure.
                if git(repo, 'diff', '--cached', '--name-only', '-z'):
                    raise SyncBlocked('new staged work appeared during sync')
                with tempfile.TemporaryDirectory(prefix='agent-signal-index-') as directory:
                    env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / 'index'))
                    git(repo, 'read-tree', 'HEAD', env=env)
                    paths = sorted(pending['files'])
                    # NUL-delimited stdin preserves exact paths without an
                    # argv proportional to snapshot size (Windows limit).
                    git(repo, '--literal-pathspecs', 'add', '-A', '--pathspec-from-file=-',
                        '--pathspec-file-nul', env=env, input=''.join(p + '\0' for p in paths))
                    pending['tree'] = git(repo, 'write-tree', env=env)
                    save_pending(repo, pending)
                    git(repo, 'commit', '-m', pending['message'], env=env)
                pending['commit'] = git(repo, 'rev-parse', 'HEAD')
            else:
                pending['commit'] = head
            save_pending(repo, pending)
        commit = pending['commit']
        if git(repo, 'rev-parse', 'HEAD') != commit:
            raise SyncBlocked('HEAD changed outside this sync')
        if commit != base:
            if git(repo, 'rev-parse', 'HEAD^{tree}') != pending.get('tree'):
                raise SyncBlocked('a commit hook changed the checked tree; review required')
            committed_paths = set(git(repo, 'diff', '--name-only', '-z', base, commit).split('\0')) - {''}
            if not committed_paths <= set(pending['files']):
                raise SyncBlocked('commit contains unreviewed paths')
            # HEAD moved using an isolated index; update only our entries in the real index.
            git(repo, '--literal-pathspecs', 'reset', '-q', 'HEAD', '--pathspec-from-file=-',
                '--pathspec-file-nul', input=''.join(p + '\0' for p in sorted(pending['files'])))
            pending['index_reconciled'] = True
            save_pending(repo, pending)
        if changed(repo) or git(repo, 'diff', '--cached', '--name-only', '-z'):
            raise SyncBlocked('worktree/index no longer match the checked commit')
        step = 'verify'
        verify()
        if identities(repo, pending['files']) != pending['files'] or changed(repo):
            raise SyncBlocked('files changed before publication')
        step = 'push'
        target = pending['target']
        git(repo, 'push', target['remote'], f"{commit}:{target['ref']}")
        step = 'remote-readback'
        remote = git(repo, 'ls-remote', '--refs', target['remote'], target['ref']).split()
        if remote != [commit, target['ref']]:
            raise SyncBlocked('remote branch does not match the committed changes')
        step = 'published-readback'
        readback()
        if changed(repo) or git(repo, 'rev-parse', 'HEAD') != commit:
            raise SyncBlocked('repository changed before final verification')
        (git_dir(repo) / 'agent-signal-sync.json').unlink()
        return {'result': 'synced', 'commit': commit, 'remote': target['remote'],
                'branch': target['branch'], 'agents_verified': True, 'remote_verified': True}
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return {'result': 'incomplete', 'failed_step': step, 'reason': str(exc),
                'commit': pending.get('commit'), 'retry': 'run the same sync after resolving the failure'}
