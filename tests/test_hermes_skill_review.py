"""The bridge inventories proposals; native Hermes remains the write owner."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_tool():
    spec = importlib.util.spec_from_file_location("hermes_skill_review", REPO / "tools/hermes_skill_review.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PendingSkillTests(unittest.TestCase):
    def test_pending_metadata_is_private_and_never_auto_applied(self):
        bridge = load_tool()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            pending = home / "pending/skills/0123abcd.json"
            pending.parent.mkdir(parents=True)
            pending.write_text(json.dumps({"id": "0123abcd", "payload": {
                "name": "private-name", "content": "PRIVATE CONVERSATION"}}))
            before = pending.read_bytes()
            findings = bridge.pending_findings(home)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["pending_id"], "0123abcd")
            self.assertEqual(findings[0]["disposition"], "review-required")
            self.assertFalse(findings[0]["auto_apply_eligible"])
            self.assertNotIn("PRIVATE", json.dumps(findings))
            self.assertNotIn("private-name", json.dumps(findings))
            self.assertNotIn(str(home), json.dumps(findings))
            self.assertEqual(pending.read_bytes(), before)
            pending.write_text("changed")
            self.assertNotEqual(findings, bridge.pending_findings(home))

    def test_empty_home_is_read_only(self):
        bridge = load_tool()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "absent"
            self.assertEqual(bridge.pending_findings(home), [])
            self.assertFalse(home.exists())

    def test_invalid_pending_filename_does_not_leak_or_disappear(self):
        bridge = load_tool()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            pending = home / "pending/skills/PRIVATE-FILENAME.json"
            pending.parent.mkdir(parents=True)
            pending.write_text("not json")
            findings = bridge.pending_findings(home)
            self.assertEqual(len(findings), 1)
            self.assertNotIn("PRIVATE", json.dumps(findings))
            self.assertEqual(findings[0]["disposition"], "review-required")

    def test_record_id_cannot_escape_store(self):
        bridge = load_tool()
        with self.assertRaises(ValueError):
            bridge.validate_id("../../memory/12345678")


@unittest.skipUnless(os.environ.get("HERMES_TEST_RUNTIME"), "set HERMES_TEST_RUNTIME for native integration")
class NativeIntegrationTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".staging"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.runtime = Path(os.environ["HERMES_TEST_RUNTIME"])
        self.env = {**os.environ, "HERMES_HOME": str(self.home), "PYTHONPATH": str(self.runtime),
                    "PYTHONIOENCODING": "utf-8"}
        (self.home / "config.yaml").write_text("skills:\n  write_approval: true\nmemory:\n  write_approval: false\n")
        self.skill = self.home / "skills/proposal-fixture/SKILL.md"
        self.skill.parent.mkdir(parents=True)
        self.skill.write_text("---\nname: proposal-fixture\ndescription: Use for isolated testing.\n---\n\nbaseline\n")

    def native(self, code):
        out = subprocess.run([sys.executable, "-c", code], cwd=self.runtime,
                             env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout.strip().splitlines()[-1])

    def stage(self, batch=False, background=True):
        return self.native("from tools import skill_manager_tool as s, skill_usage as u, skill_provenance as p; "
                           "u.record_created('proposal-fixture', agent_created=True); "
                           f"p.set_current_write_origin({'background_review' if background else 'foreground'!r}); "
                           "op=dict(action='patch',name='proposal-fixture',old_string='baseline',new_string='reviewed'); "
                           + ("print(s.skill_manage(action='',name='',operations=[op]))" if batch else "print(s.skill_manage(**op))"))

    def cli(self, action, pid, token=None, ok=True):
        cmd = [sys.executable, str(REPO / "tools/hermes_skill_review.py"), action, pid,
               "--home", str(self.home), "--runtime", str(self.runtime)]
        if token:
            cmd += ["--review-token", token]
        out = subprocess.run(cmd, env=self.env, capture_output=True, text=True, timeout=60)
        if ok:
            self.assertEqual(out.returncode, 0, out.stderr)
            return json.loads(out.stdout)
        self.assertNotEqual(out.returncode, 0)
        return out.stderr

    def test_real_background_stage_stale_refusal_and_native_apply(self):
        original = self.skill.read_bytes()
        staged = self.stage()
        self.assertTrue(staged.get("staged"), staged)
        pid = staged["pending_id"]
        self.assertEqual(self.skill.read_bytes(), original)
        shown = self.cli("show", pid)
        self.assertTrue(shown["native_apply_allowed"])
        self.assertIn("reviewed", json.dumps(shown["diffs"]))
        self.skill.write_text(self.skill.read_text() + "concurrent edit\n")
        self.assertIn("changed", self.cli("approve", pid, shown["review_token"], ok=False))
        self.assertTrue((self.home / f"pending/skills/{pid}.json").exists())
        shown = self.cli("show", pid)
        applied = self.cli("approve", pid, shown["review_token"])
        self.assertEqual(applied["result"], "applied")
        self.assertIn("reviewed", self.skill.read_text())
        self.assertIn("concurrent edit", self.skill.read_text())
        self.assertFalse((self.home / f"pending/skills/{pid}.json").exists())
        self.assertTrue((self.home / "skills/.curator_ledger.jsonl").exists())

    def test_real_batch_reject_and_memory_unchanged(self):
        original = self.skill.read_bytes()
        staged = self.stage(batch=True, background=False)
        self.assertTrue(staged.get("staged"), staged)
        pid = staged["pending_id"]
        shown = self.cli("show", pid)
        self.assertEqual(len(shown["diffs"]), 1)
        self.cli("reject", pid, shown["review_token"])
        self.assertEqual(original, self.skill.read_bytes())
        self.assertFalse((self.home / f"pending/skills/{pid}.json").exists())
        self.assertTrue(self.native("from tools import write_approval as w; import json; print(json.dumps(w.evaluate_gate(w.MEMORY).allow))"))

    def test_external_owner_cannot_be_approved_in_place(self):
        external = self.home / "external"
        target = external / "proposal-fixture"
        target.mkdir(parents=True)
        self.skill.replace(target / "SKILL.md")
        config = {"skills": {"write_approval": True, "external_dirs": [str(external)]}}
        (self.home / "config.yaml").write_text(json.dumps(config))
        staged = self.stage(background=False)
        self.assertTrue(staged.get("staged"), staged)
        pid = staged["pending_id"]
        shown = self.cli("show", pid)
        self.assertFalse(shown["native_apply_allowed"])
        self.cli("approve", pid, shown["review_token"], ok=False)
        self.assertIn("baseline", (target / "SKILL.md").read_text())
        self.cli("reject", pid, shown["review_token"])

    def test_batch_apply_uses_native_atomic_failure_and_keeps_pending(self):
        result = self.native("from tools import skill_manager_tool as s; "
                             "ops=[dict(action='patch',name='proposal-fixture',old_string='baseline',new_string='reviewed'), "
                             "dict(action='remove_file',name='proposal-fixture',file_path='references/missing.md')]; "
                             "print(s.skill_manage(action='',name='',operations=ops))")
        pid = result["pending_id"]
        shown = self.cli("show", pid)
        self.cli("approve", pid, shown["review_token"], ok=False)
        self.assertIn("baseline", self.skill.read_text())
        self.assertTrue((self.home / f"pending/skills/{pid}.json").exists())

    def test_changed_payload_refused(self):
        pid = self.stage()["pending_id"]
        shown = self.cli("show", pid)
        file = self.home / f"pending/skills/{pid}.json"
        record = json.loads(file.read_text())
        record["payload"]["new_string"] = "not reviewed"
        file.write_text(json.dumps(record))
        self.cli("approve", pid, shown["review_token"], ok=False)
        self.assertIn("baseline", self.skill.read_text())


if __name__ == "__main__":
    unittest.main()
