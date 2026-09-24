"""Retired optional hooks must not displace independent safety owners."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RecoveryRetirementTests(unittest.TestCase):
    def test_codex_gsd_retirement_preserves_the_independent_guard(self):
        policy = json.loads((ROOT / "recovery.json").read_text(encoding="utf-8"))
        artifacts = policy["hosts"]["codex"]["artifacts"]
        by_id = {item["id"]: item for item in artifacts}
        retired = {"session-start-hook", "update-hook", "update-hook-worker", "managed-hook-registry"}
        self.assertFalse(retired.intersection(by_id))
        self.assertNotIn("hooks.SessionStart", by_id["settings"]["include"])
        self.assertIn("hooks.PreToolUse", by_id["settings"]["include"])
        self.assertEqual("hooks/windows_destructive_commands.py", by_id["destructive-command-guard"]["source"])
        self.assertEqual("replace-if-absent", by_id["destructive-command-guard"]["strategy"])

    def test_retired_surface_remains_explicit_but_not_captured(self):
        inventory = json.loads((ROOT / "contracts/instruction-surfaces.json").read_text(encoding="utf-8"))
        surface = next(item for item in inventory["surfaces"] if item["id"] == "codex.session-start-hook")
        self.assertEqual("retired", surface["status"])
        self.assertEqual("retired", surface["backup"])
        self.assertNotIn("artifact", surface)

    def test_current_profiles_do_not_select_the_retired_hook(self):
        current = []
        for path in (ROOT / "profiles").glob("*.json"):
            profile = json.loads(path.read_text(encoding="utf-8"))
            if profile.get("status") != "current-observed":
                continue
            current.append(path.name)
            for host in profile["hosts"].values():
                self.assertNotIn("codex.session-start-hook", host["effective_surfaces"])
        self.assertTrue(current)


if __name__ == "__main__":
    unittest.main()
