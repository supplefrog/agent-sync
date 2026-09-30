"""Native selector/capture/profile integration; publication itself has scoped tests."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import reconcile
import recovery
import runtime_defaults
import sync_git
import instruction_profile


class DefaultsReconcileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="defaults-integration-")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.repo = root / "source"
        subprocess.run(["git", "clone", "--quiet", "--shared", str(REPO), str(self.repo)], check=True)
        # Production candidates materialize raw blobs; checkout filters can alter hash-bound snapshots.
        entries = sync_git._tree_entries(REPO, "HEAD")
        blobs = sync_git._blobs(REPO, entries)
        for relative, (_, oid) in entries.items():
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blobs[oid])
        for key, value in (("user.name", "Fixture"), ("user.email", "fixture@example.invalid")):
            sync_git.git(self.repo, "config", key, value)
        self.included = sorted(sync_git.changed(REPO))
        for relative in self.included:
            source, target = REPO / relative, self.repo / relative
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            elif target.is_file():
                target.unlink()
        self.roots = {}
        for host in ("codex", "hermes"):
            host_root = root / host
            host_root.mkdir()
            self.roots[host] = host_root
            config = json.loads((self.repo / f"recovery/current/hosts/{host}/config.json").read_text())
            filename, fmt, _ = runtime_defaults.ADAPTERS[host]
            # Start both fixtures at a supported older selector regardless of current deployment.
            if host == "codex":
                config["model"] = "gpt-6-sol"
            else:
                config["model"]["default"] = "gpt-6-sol"
            (host_root / filename).write_bytes(recovery._serialize_config(config, fmt))

    def invoke(self, completion, candidate_checks=None):
        with mock.patch.object(reconcile, "_run_candidate_checks", return_value=[], side_effect=candidate_checks), \
             mock.patch.object(reconcile, "complete_sync", side_effect=completion):
            return reconcile.complete_defaults_sync(self.repo, hosts=["codex", "hermes"],
                recovery_roots=self.roots, include=self.included, capture_recovery=True)

    def test_real_selectors_capture_and_profile_are_connected(self):
        def completion(repo, **options):
            self.assertEqual(["codex:settings", "hermes:settings"], options["recovery_artifacts"])
            recovery.verify_snapshot(repo / "recovery.json", repo / "recovery/current")
            captured = instruction_profile._selector_observations(repo, ["codex", "hermes"])
            profile = json.loads(instruction_profile.current_profile(repo).read_text())
            for host in captured:
                self.assertEqual("gpt-6.1-sol", captured[host]["model"])
                self.assertEqual("gpt-6.1-sol", profile["hosts"][host]["model"])
                self.assertEqual("known", profile["hosts"][host]["observation"]["time_status"])
            return {"result": "synced"}
        result = self.invoke(completion)
        self.assertEqual("synced", result["result"], result)
        self.assertEqual("applied", result["defaults"]["result"])

    def test_non_ascii_capture_retains_observation_binding_after_recapture(self):
        native = self.roots["hermes"] / runtime_defaults.ADAPTERS["hermes"][0]
        config = recovery._read_config(native, "yaml")
        config.setdefault("display", {})["label"] = "caf\u00e9"
        native.write_bytes(recovery._serialize_config(config, "yaml"))
        unselected = self.repo / "recovery/current/hosts/omp/config.json"
        original_unselected = unselected.read_bytes()

        def completion(repo, **options):
            recovery.snapshot(repo / "recovery.json", repo / "recovery/current",
                self.roots, repo_root=repo, artifacts=options["recovery_artifacts"])
            profile = json.loads(instruction_profile.current_profile(repo).read_text())
            instruction_profile._verify_configured_observation(
                repo, "hermes", profile["hosts"]["hermes"]["observation"])
            captured = json.loads((repo / "recovery/current/hosts/hermes/config.json").read_text(encoding="utf-8"))
            self.assertEqual("caf\u00e9", captured["display"]["label"])
            self.assertEqual(original_unselected, unselected.read_bytes())
            return {"result": "synced"}

        checked = []
        def real_profile_check(candidate, commands, tree):
            instruction_profile.verify_profile(
                candidate, instruction_profile.current_profile(candidate), live=False)
            self.assertEqual("gpt-6-sol", recovery._read_config(native, "yaml")["model"]["default"])
            checked.append(tree)
            return []

        result = self.invoke(completion, candidate_checks=real_profile_check)
        self.assertEqual("synced", result["result"], result)
        self.assertEqual(1, len(checked))

    def test_later_rejection_restores_native_and_derived_files(self):
        originals = {self.roots[host] / runtime_defaults.ADAPTERS[host][0]:
                     (self.roots[host] / runtime_defaults.ADAPTERS[host][0]).read_bytes() for host in self.roots}
        for relative in ("host-deltas.json", "recovery/current/manifest.json", "profiles/current-observed-defaults.json",
                         "recovery/current/hosts/codex/config.json", "recovery/current/hosts/hermes/config.json"):
            originals[self.repo / relative] = (self.repo / relative).read_bytes()
        result = self.invoke(lambda *args, **kwargs: {"result": "rejected", "reason": "fixture postflight failed",
            "failure": {"phase": "postflight", "command": "fixture", "exit_code": 7}})
        self.assertEqual("incomplete", result["result"], result)
        self.assertEqual(7, result["failure"]["exit_code"])
        for path, original in originals.items():
            self.assertEqual(original, path.read_bytes(), path)

    def test_prerequisite_failure_leaves_native_bytes_unchanged(self):
        originals = {host: (root / runtime_defaults.ADAPTERS[host][0]).read_bytes() for host, root in self.roots.items()}
        with mock.patch.object(reconcile, "_run_candidate_checks", side_effect=RuntimeError("fixture check failure")), \
             mock.patch.object(reconcile, "complete_sync") as complete:
            result = reconcile.complete_defaults_sync(self.repo, hosts=["codex", "hermes"],
                recovery_roots=self.roots, include=self.included)
        self.assertEqual("incomplete", result["result"])
        complete.assert_not_called()
        for host, data in originals.items():
            self.assertEqual(data, (self.roots[host] / runtime_defaults.ADAPTERS[host][0]).read_bytes())

    def test_implicit_metadata_edit_during_checks_survives_without_native_apply(self):
        native = {host: (root / runtime_defaults.ADAPTERS[host][0]).read_bytes() for host, root in self.roots.items()}
        implicit = {"host-deltas.json", "recovery/current/manifest.json",
                    "recovery/current/hosts/codex/config.json", "recovery/current/hosts/hermes/config.json"}
        included = [name for name in self.included if name not in implicit]
        # Isolate the final metadata CAS boundary from earlier source admission:
        # the fixture has intentional reviewed snapshot changes outside settings.
        for relative in sorted(implicit):
            with self.subTest(target=relative):
                target = self.repo / relative
                original = target.read_bytes()
                changed = original + b"\n "
                try:
                    with mock.patch.object(reconcile, "_capture_shared_preflight"), \
                         mock.patch.object(reconcile, "_scope_dependencies", return_value={}), \
                         mock.patch.object(reconcile, "_prepare_candidate_bindings"), \
                         mock.patch.object(reconcile, "_run_candidate_checks", side_effect=lambda *args: target.write_bytes(changed)), \
                         mock.patch.object(reconcile, "complete_sync") as complete, \
                         mock.patch.object(runtime_defaults, "apply_defaults") as apply:
                        result = reconcile.complete_defaults_sync(self.repo, hosts=["codex", "hermes"],
                            recovery_roots=self.roots, include=included)
                    self.assertEqual("incomplete", result["result"], result)
                    self.assertIn("derived metadata changed during", result["reason"])
                    self.assertEqual(changed, target.read_bytes())
                    apply.assert_not_called()
                    complete.assert_not_called()
                    for host, data in native.items():
                        self.assertEqual(data, (self.roots[host] / runtime_defaults.ADAPTERS[host][0]).read_bytes())
                finally:
                    target.write_bytes(original)

    def test_metadata_exception_after_replacement_restores_original(self):
        target = self.repo / "recovery/current/manifest.json"
        original = target.read_bytes()
        native = {host: (root / runtime_defaults.ADAPTERS[host][0]).read_bytes() for host, root in self.roots.items()}
        atomic = recovery._atomic_write
        failed = []
        def after_replace(path, data):
            atomic(path, data)
            if path == target and not failed:
                failed.append(True)
                raise OSError("fixture failure after metadata replacement")
        with mock.patch.object(recovery, "_atomic_write", side_effect=after_replace):
            result = self.invoke(lambda *args, **kwargs: {"result": "synced"})
        self.assertEqual("incomplete", result["result"], result)
        self.assertEqual(original, target.read_bytes())
        for host, data in native.items():
            self.assertEqual(data, (self.roots[host] / runtime_defaults.ADAPTERS[host][0]).read_bytes())

    def test_metadata_conflict_reports_recoverable_private_baseline(self):
        target = self.repo / "profiles/current-observed-defaults.json"
        original = target.read_bytes()
        def completion(*args, **kwargs):
            target.write_bytes(b"fixture concurrent edit")
            return {"result": "rejected", "reason": "fixture failure"}
        result = self.invoke(completion)
        self.assertEqual("incomplete", result["result"])
        relative = target.relative_to(self.repo).as_posix()
        self.assertIn(relative, result["metadata_conflicts"])
        backup = Path(result["private_metadata_backups"][relative])
        self.addCleanup(shutil.rmtree, backup)
        self.assertEqual(original, (backup / "original").read_bytes())
        self.assertEqual(b"fixture concurrent edit", target.read_bytes())

    def test_pending_resume_does_not_create_new_observation(self):
        with mock.patch.object(sync_git, "read_pending", return_value={"scoped": True, "recovery_artifacts": ["codex:settings", "hermes:settings"]}), \
             mock.patch.object(runtime_defaults, "prepare_defaults") as prepare, \
             mock.patch.object(reconcile, "complete_sync", return_value={"result": "synced"}) as complete:
            result = reconcile.complete_defaults_sync(self.repo, include=self.included)
        self.assertEqual("synced", result["result"])
        prepare.assert_not_called()
        complete.assert_called_once()

    def test_pending_other_host_is_not_resumed(self):
        with mock.patch.object(sync_git, "read_pending", return_value={"scoped": True, "recovery_artifacts": ["codex:settings"]}), \
             mock.patch.object(runtime_defaults, "prepare_defaults") as prepare, \
             mock.patch.object(reconcile, "complete_sync") as complete:
            result = reconcile.complete_defaults_sync(self.repo, hosts=["hermes"])
        self.assertEqual("incomplete", result["result"])
        self.assertIn("different default target", result["reason"])
        prepare.assert_not_called()
        complete.assert_not_called()

    def test_exact_settings_plan_previews_the_same_defaults_as_sync(self):
        with mock.patch.object(reconcile.recovery, "_parse_roots", return_value=self.roots), \
             mock.patch.object(reconcile, "plan", return_value={}), \
             mock.patch.object(runtime_defaults, "plan_defaults", return_value={"hosts": ["codex"]}) as defaults:
            self.assertEqual(0, reconcile.main(["plan", "--repo", str(self.repo), "--capture-artifact", "codex:settings"]))
        self.assertEqual(["codex"], defaults.call_args.kwargs["hosts"])

    def test_nested_repository_lock_still_excludes_another_process(self):
        with sync_git.lock(self.repo):
            with sync_git.lock(self.repo):
                script = "import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import sync_git;\nwith sync_git.lock(Path(sys.argv[2])):pass"
                result = subprocess.run([sys.executable, "-B", "-c", script, str(REPO / "tools"), str(self.repo)], capture_output=True, text=True)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("another sync is running", result.stderr)
