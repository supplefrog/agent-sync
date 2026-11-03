"""Selected native text uses recovery's read-only full-file comparison."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import recovery
import worktree_sync


class NativeTextReadbackTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.roots = {host: Path(self.temp.name) / host for host in ("hermes", "codex", "omp")}
        policy = {"schema_version": 1, "machine": "fixture", "public_safe": True, "hosts": {}}
        for host, root in self.roots.items():
            root.mkdir()
            (root / "kept.txt").write_text("kept\n", encoding="utf-8")
            policy["hosts"][host] = {"artifacts": [self.artifact("kept", "kept.txt", host)]}
        self.policy = policy
        self.save_policy()
        recovery.snapshot(self.repo / "recovery.json", self.repo / "recovery/current", self.roots, repo_root=self.repo)
        self.git("init", "-b", "main")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.commit("baseline")
        artifact = self.artifact("model-skill", "extensions/model-skill.js", "omp")
        self.policy["hosts"]["omp"]["artifacts"].append(artifact)
        self.target = self.roots["omp"] / artifact["source"]
        self.target.parent.mkdir()
        self.target.write_text("export default () => {};\n", encoding="utf-8")
        self.save_policy()
        recovery.snapshot(self.repo / "recovery.json", self.repo / "recovery/current", self.roots, repo_root=self.repo, artifacts=["omp:model-skill"])
        self.name = "recovery/current/" + artifact["snapshot"]
        self.commit_id = self.commit("reviewed native addition")

    @staticmethod
    def artifact(identifier, source, host):
        return {"id": identifier, "source": source, "snapshot": f"hosts/{host}/{source}", "kind": "text", "format": "text", "strategy": "replace-if-absent"}

    def save_policy(self):
        (self.repo / "recovery.json").write_text(json.dumps(self.policy), encoding="utf-8")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.DEVNULL, text=True).strip()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD")

    def completion(self, predecessors=None, selected_paths=None):
        journal = {"last_result": {"commit": self.commit_id}, "published_repo": str(self.repo), "predecessors": predecessors or [], "receipt": {"options": {"recovery_roots": {host: str(root) for host, root in self.roots.items()}}, "paths": selected_paths if selected_paths is not None else [self.name]}}
        with patch.object(recovery, "_default_roots", return_value=self.roots):
            return worktree_sync._native_destination_completion(self.repo, journal)

    def test_saved_text_verifies_without_claiming_loading(self):
        result = self.completion()
        self.assertTrue(result["saved_verified"], result)
        self.assertIsNone(result["loaded_verified"])
        self.assertIsNone(result["targets"][self.name]["loaded_verified"])

    def test_missing_or_drifted_text_fails_without_writes(self):
        for content in (None, "changed native code\n"):
            if content is None:
                self.target.unlink()
            else:
                self.target.write_text(content, encoding="utf-8")
            result = self.completion()
            self.assertFalse(result["saved_verified"], result)
            self.assertEqual(self.target.read_text(encoding="utf-8") if self.target.exists() else None, content)

    def test_snapshot_drift_and_changed_target_policy_fail(self):
        path = self.repo / self.name
        original = path.read_bytes()
        path.write_text("wrong source\n", encoding="utf-8")
        self.assertFalse(self.completion()["saved_verified"])
        path.write_bytes(original)
        self.policy["hosts"]["omp"]["artifacts"][-1]["source"] = "other.js"
        self.save_policy()
        self.assertFalse(self.completion()["saved_verified"])

    def test_valid_uncommitted_recapture_cannot_verify_an_inherited_obligation(self):
        original = self.commit_id
        obligations = worktree_sync._publication_native_obligations(self.repo, original)
        (self.repo / "unrelated.txt").write_text("unrelated successor\n", encoding="utf-8")
        self.commit_id = self.commit("unrelated successor")
        self.target.write_text("uncommitted native variant\n", encoding="utf-8")
        recovery.snapshot(self.repo / "recovery.json", self.repo / "recovery/current", self.roots, repo_root=self.repo, artifacts=["omp:model-skill"])
        recovery.verify_snapshot(self.repo / "recovery.json", self.repo / "recovery/current")
        result = self.completion([{"published_commit": original, "native_obligations": obligations}], ["unrelated.txt"])
        self.assertFalse(result["saved_verified"], result)

    def test_valid_working_policy_change_is_not_committed_authority(self):
        self.policy["hosts"]["omp"]["artifacts"][-1]["portable_paths"] = True
        self.save_policy()
        recovery.snapshot(self.repo / "recovery.json", self.repo / "recovery/current", self.roots, repo_root=self.repo)
        self.assertFalse(self.completion()["saved_verified"])

    def test_source_change_after_owner_readback_is_rejected(self):
        restore = recovery.restore
        def change_after(*args, **kwargs):
            result = restore(*args, **kwargs)
            self.target.write_text("new native variant\n", encoding="utf-8")
            recovery.snapshot(self.repo / "recovery.json", self.repo / "recovery/current", self.roots, repo_root=self.repo, artifacts=["omp:model-skill"])
            return result
        with patch.object(recovery, "restore", side_effect=change_after):
            self.assertFalse(self.completion()["saved_verified"])


if __name__ == "__main__":
    unittest.main()
