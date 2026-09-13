"""Selected-host verification must not initialize the receiving profile."""
from pathlib import Path
from unittest.mock import patch

import pytest

from test_host_deltas import load_tool


def entry(readback):
    return {"id": "native", "host": "hermes", "category": "runtime", "required": True,
            "readback": readback, "restore": {"kind": "prerequisite"}}


def test_version_cli_startup_writes_are_isolated_and_removed(tmp_path):
    tool = load_tool("host_deltas")
    target = tmp_path / "receiving-profile"
    manifest = {"machine": "test", "exclusions": [], "entries": [entry(
        {"kind": "command", "argv": ["hermes", "--version"], "contains": "0.21.2"})]}
    checked = []
    def startup(argv, *, env):
        home = Path(env["HERMES_HOME"])
        home.mkdir(parents=True, exist_ok=True)
        (home / "SOUL.md").write_text("Native CLI initialization", encoding="utf-8")
        checked.append(home)
        return 0, "Hermes Agent 0.21.2"
    with patch.object(tool, "load_manifest", return_value=manifest), patch.object(tool, "_run", side_effect=startup):
        report = tool.verify(tmp_path / "unused.json", tmp_path, roots={"hermes": target}, hosts=["hermes"])
    assert report["passed"]
    assert not target.exists()
    assert checked and all(not p.exists() for p in checked)


def test_config_empty_checks_target_state_without_starting_cli(tmp_path):
    tool = load_tool("host_deltas")
    target = tmp_path / "receiving-profile"
    readback = {"kind": "config-empty", "path": "config.yaml", "format": "yaml", "key": "hooks"}
    manifest = {"machine": "test", "exclusions": [], "entries": [entry(readback)]}
    with patch.object(tool, "load_manifest", return_value=manifest), patch.object(tool, "_run", side_effect=AssertionError("CLI must not start")):
        assert tool.verify(tmp_path / "unused.json", tmp_path, roots={"hermes": target}, hosts=["hermes"])["passed"]
        assert not target.exists()
        target.mkdir()
        (target / "config.yaml").write_text("hooks:\n  pre_tool_call: [{command: 'printf safe'}]\n", encoding="utf-8")
        assert not tool.verify(tmp_path / "unused.json", tmp_path, roots={"hermes": target}, hosts=["hermes"])["passed"]
        readback["path"] = "../outside.yaml"
        with pytest.raises(tool.recovery.RecoveryError):
            tool.verify(tmp_path / "unused.json", tmp_path, roots={"hermes": target}, hosts=["hermes"])
