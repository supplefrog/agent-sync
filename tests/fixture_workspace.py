"""Opt-in test workspace using ordinary inherited directory creation.

Set AGENT_SYNC_TEST_WORKSPACE to an existing, permitted absolute directory.
No fallback, permission repair, retry on denial, or cleanup error suppression.
Only this test process's tempfile constructors are adapted; production cleanup
and its assertions still execute normally.
"""
from pathlib import Path
from contextlib import contextmanager
import json
import os
import shutil
import tempfile
import uuid

_root = None
_original_directory = tempfile.TemporaryDirectory


def _preflight(path):
    probe = path / ('.file-access-probe-' + uuid.uuid4().hex)
    with probe.open('x', encoding='utf-8') as stream:
        stream.write('created')
    if probe.read_text(encoding='utf-8') != 'created':
        raise RuntimeError('workspace create/read preflight failed: ' + str(path))
    with probe.open('a', encoding='utf-8') as stream:
        stream.write('-updated')
    if probe.read_text(encoding='utf-8') != 'created-updated':
        raise RuntimeError('workspace write/read preflight failed: ' + str(path))
    probe.unlink()


def _directory(suffix=None, prefix=None, dir=None):
    parent = Path(dir).absolute() if dir is not None else _root
    if parent is None or not parent.resolve().is_relative_to(_root):
        raise ValueError('test directory must remain inside the provided workspace')
    _preflight(parent)
    path = parent / ((prefix or 'tmp') + uuid.uuid4().hex + (suffix or ''))
    if not path.resolve().is_relative_to(_root):
        raise ValueError('test directory name escapes the provided workspace')
    # Ordinary creation inherits this pre-provisioned workspace's permissions;
    # never change an existing path's permissions or retry a denied operation.
    path.mkdir()
    _preflight(path)
    return str(path)


class WorkspaceDirectory:
    def __init__(self, suffix=None, prefix=None, dir=None, **kwargs):
        if kwargs:
            raise ValueError('unsupported test directory options: ' + ', '.join(kwargs))
        self.name = _directory(suffix, prefix, dir)

    def __enter__(self):
        return self.name

    def cleanup(self):
        path = Path(self.name)
        if not path.resolve().is_relative_to(_root) or path.resolve() == _root:
            raise ValueError('refusing cleanup outside the owned test directory')
        if path.exists():
            shutil.rmtree(path)  # No onerror/chmod/reset fallback; failures propagate.

    def __exit__(self, *_args):
        self.cleanup()


@contextmanager
def provided_workspace():
    """Git fixture lifetime belongs to the external test-workspace owner.

    Explicit retention is selected before construction, never as a fallback
    for failed deletion. Body/preflight errors propagate. Production cleanup
    under test is unchanged; these source/remote fixture repositories remain
    available for inspection and separate authorized workspace disposal.
    """
    if _root is None:
        with _original_directory() as name:
            yield name
        return
    name = _directory(prefix='git-fixture-')
    with (_root / 'provided-git-fixtures.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'path': name, 'lifetime': 'externally-managed; retained, not cleanup-verified'}) + '\n')
    yield name


def configure():
    global _root
    value = os.environ.get('AGENT_SYNC_TEST_WORKSPACE')
    if not value:
        return False
    root = Path(value)
    if not root.is_absolute() or not root.is_dir() or root.resolve() != root.absolute():
        raise ValueError('AGENT_SYNC_TEST_WORKSPACE must be an existing regular absolute directory')
    if _root is not None and _root != root:
        raise ValueError('test workspace cannot change after configuration')
    _preflight(root)
    _root = root
    tempfile.mkdtemp = _directory
    tempfile.TemporaryDirectory = WorkspaceDirectory
    return True
