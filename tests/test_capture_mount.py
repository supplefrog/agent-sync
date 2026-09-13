"""Mounted package capture is explicit, read-only, and never a restore escape."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from test_selected_recovery import make_state, recovery


def directory_link(source: Path, target: Path) -> None:
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(source), str(target))
    else:
        target.symlink_to(source, target_is_directory=True)


def mounted_state(tmp_path):
    policy, snapshot, roots = make_state(tmp_path)
    owner = tmp_path / "native-owner"
    owner.mkdir()
    (owner / "SKILL.md").write_text("Reviewed native source\n", encoding="utf-8")
    mount = roots["hermes"] / "skills/example"
    mount.parent.mkdir()
    directory_link(owner, mount)
    data = json.loads(policy.read_text(encoding="utf-8"))
    artifact = data["hosts"]["hermes"]["artifacts"][1]
    artifact.update(source="skills/example/SKILL.md", capture_mount="skills/example")
    policy.write_text(json.dumps(data), encoding="utf-8")
    return policy, snapshot, roots, owner, mount


def test_explicit_mount_captures_without_mutating_owner(tmp_path):
    policy, snapshot, roots, owner, mount = mounted_state(tmp_path)
    before = (owner / "SKILL.md").read_bytes()
    recovery.snapshot(policy, snapshot, roots, repo_root=tmp_path)
    target = tmp_path / "recipient/hermes"
    result = recovery.restore(policy, snapshot, {"hermes": target}, hosts=["hermes"], apply=True, repo_root=tmp_path)
    assert not result["conflicts"]
    assert (target / "skills/example/SKILL.md").read_text(encoding="utf-8") == "Reviewed native source\n"
    assert (owner / "SKILL.md").read_bytes() == before
    mount.rmdir() if os.name == "nt" else mount.unlink()


def test_capture_refuses_unlisted_mount(tmp_path):
    policy, snapshot, roots, owner, mount = mounted_state(tmp_path)
    data = json.loads(policy.read_text(encoding="utf-8"))
    del data["hosts"]["hermes"]["artifacts"][1]["capture_mount"]
    policy.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(recovery.RecoveryError, match="reparse|symlink"):
        recovery.snapshot(policy, snapshot, roots, repo_root=tmp_path)
    mount.rmdir() if os.name == "nt" else mount.unlink()


def test_capture_refuses_nested_link_and_restore_refuses_mount_write(tmp_path):
    policy, snapshot, roots, owner, mount = mounted_state(tmp_path)
    recovery.snapshot(policy, snapshot, roots, repo_root=tmp_path)
    target = tmp_path / "recipient/hermes"
    target_mount = target / "skills/example"
    target_mount.parent.mkdir(parents=True)
    directory_link(owner, target_mount)
    (owner / "SKILL.md").write_text("Recipient local edit\n", encoding="utf-8")
    before = (owner / "SKILL.md").read_bytes()
    plan = recovery.restore(policy, snapshot, {"hermes": target}, hosts=["hermes"], force_text=True, repo_root=tmp_path)
    assert any("read-only" in item["reason"] for item in plan["conflicts"])
    with pytest.raises(recovery.RecoveryError, match="text conflict"):
        recovery.restore(policy, snapshot, {"hermes": target}, hosts=["hermes"], apply=True, force_text=True, repo_root=tmp_path)
    assert (owner / "SKILL.md").read_bytes() == before
    target_mount.rmdir() if os.name == "nt" else target_mount.unlink()
    nested_owner = tmp_path / "nested-owner"
    nested_owner.mkdir()
    (nested_owner / "SKILL.md").write_text("Nested source\n", encoding="utf-8")
    nested = owner / "nested"
    directory_link(nested_owner, nested)
    data = json.loads(policy.read_text(encoding="utf-8"))
    data["hosts"]["hermes"]["artifacts"][1]["source"] = "skills/example/nested/SKILL.md"
    policy.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(recovery.RecoveryError, match="reparse|symlink"):
        recovery.snapshot(policy, snapshot, roots, repo_root=tmp_path)
    nested.rmdir() if os.name == "nt" else nested.unlink()
    mount.rmdir() if os.name == "nt" else mount.unlink()


def test_selected_text_rebases_uninstalled_host_references_without_io(tmp_path):
    home = tmp_path / "recipient"
    value = "Read {{agent-signal:CODEX_HOME}}/config.toml only when Codex is installed."
    expanded = recovery._expand(value, {"hermes": home / ".hermes"}, tmp_path, home=home)
    assert str(home / ".codex") in expanded
    assert not home.exists()
