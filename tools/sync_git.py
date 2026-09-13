"""Git completion for reconcile.py; no force-push or implicit broad staging."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
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


def preflight(repo: Path, target):
    if git(repo, 'diff', '--cached', '--name-only', '-z'):
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


def publish(repo: Path, pending, *, verify, readback=lambda: None):
    """Resume exact checked content; success requires remote readback and agent checks."""
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
