"""Exact reviewed documentation examples never exempt changed/private content."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import recovery


def test_skill_procedure_names_are_not_confused_with_private_state():
    from pathlib import PurePosixPath
    assert not recovery._blocked_source(PurePosixPath('skills/session-librarian/SKILL.md'), 'text')
    assert not recovery._blocked_source(PurePosixPath('skills/github/scripts/git-credential-token.py'), 'text')
    for path in ('auth.json', 'skills/foo/auth.json', 'skills/foo/.env', 'sessions/transcript.md', 'skills/.archive/sessions.md'):
        assert recovery._blocked_source(PurePosixPath(path), 'text'), path


def test_exact_reviewed_example_can_be_captured_but_changed_line_cannot(tmp_path):
    text = 'Example container home: /root/example\n'
    review = tmp_path / 'evidence/public-safety-allowlist.json'
    review.parent.mkdir()
    review.write_text(json.dumps({'schema_version': 1, 'findings': [{
        'path': 'recovery/current/hosts/hermes/guide.md', 'line': 1,
        'rule': 'posix-user-path',
        'line_sha256': hashlib.sha256(text.strip().encode()).hexdigest(),
        'disposition': 'Reviewed generic container path, no personal identity',
    }]}))
    recovery._assert_artifact_public_safe(text.encode(), 'hosts/hermes/guide.md', tmp_path)
    with pytest.raises(recovery.RecoveryError):
        recovery._assert_artifact_public_safe(b'Private home: /home/private-person\n', 'hosts/hermes/guide.md', tmp_path)
    with pytest.raises(recovery.RecoveryError):
        recovery._assert_artifact_public_safe(text.encode(), 'hosts/hermes/other.md', tmp_path)
    with pytest.raises(recovery.RecoveryError):
        recovery._assert_artifact_public_safe((text + 'Unreviewed /home/private-person\n').encode(), 'hosts/hermes/guide.md', tmp_path)
