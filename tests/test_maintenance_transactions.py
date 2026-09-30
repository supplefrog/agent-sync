"""Exercise selected maintenance against real artifacts, checks and Git candidates."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_reconcile as fixtures
import test_sync_completion as completion


def entry(identity, name, digest):
    return {"id": name, "host": "hermes", "category": "settings", "owner": "agent-signal",
            "source_identity": identity, "version_or_hash": "sha256:" + digest,
            "enablement": "managed", "prerequisites": [], "desired_state": "tracked artifact",
            "required": True, "restore": {"kind": "repository", "reference": "tracked"},
            "readback": {"kind": "none"}, "redaction": "public-artifact"}


class MaintenanceTransactions(unittest.TestCase):
    setUp = fixtures.ReconcileTests.setUp
    fixture = fixtures.ReconcileTests.fixture
    setup_git = completion.CompleteSyncTests.setup_git
    git = completion.CompleteSyncTests.git

    def binding_fixture(self, root):
        repo, live = self.fixture(root)
        (repo / "selected.md").write_text("selected")
        (repo / "other.md").write_text("other")
        manifest = json.loads((repo / "host-deltas.json").read_text())
        manifest["entries"] = [entry("repository:selected.md", "selected", "0" * 64),
                               entry("repository:other.md", "other", "1" * 64)]
        path = repo / "host-deltas.json"
        path.write_text(json.dumps(manifest))
        return repo, live, path

    def test_scoped_plan_uses_sync_classification_and_separates_observations(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            path = repo / "skills/kept/SKILL.md"
            path.write_text(path.read_text() + "\ncanonical change\n")
            report = self.reconcile.plan(repo, machine="test", recovery_roots={}, skill_roots=[live], adopt=["kept"])
            selected = [row for row in report["findings"] if row.get("owner") == "kept"]
            self.assertEqual("deploy-canonical", selected[0]["source_action"])
            state = self.reconcile._skill_state(repo, repo / "render/fleet", [("test", live)], "kept")
            self.assertEqual(state["mode"], selected[0]["source_action"])
            self.assertEqual(["kept"], report["selection"]["owners"])
            self.assertTrue(report["observations"])
            self.assertFalse(report["mutation_performed"])

    def test_unknown_plan_selectors_fail_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            before = fixtures.digest(repo)
            for selection in ({"adopt": ["missing"]}, {"adopt": ["../kept"]},
                              {"include": ["missing.md"]}, {"recovery_artifacts": ["hermes:missing"]}):
                with self.subTest(selection=selection), self.assertRaises(RuntimeError):
                    self.reconcile.plan(repo, machine="test", recovery_roots={}, skill_roots=[live], **selection)
            self.assertEqual(before, fixtures.digest(repo))

    def test_selected_binding_commits_and_unrelated_stale_hash_is_deferred(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, _, path = self.binding_fixture(Path(temp))
            other = json.loads(path.read_text())["entries"][1]
            result = self.reconcile.host_deltas.refresh_bindings(path, repo, source_identities=["repository:selected.md"])
            self.assertTrue(result["binding_refresh"]["committed"])
            self.assertEqual(["other"], [row["id"] for row in result["binding_refresh"]["deferred"]])
            written = json.loads(path.read_text())
            self.assertEqual(other, written["entries"][1])
            self.assertEqual("sha256:" + hashlib.sha256(b"selected").hexdigest(), written["entries"][0]["version_or_hash"])
            with self.assertRaisesRegex(RuntimeError, "binding mismatch for other"):
                self.reconcile.host_deltas.load_manifest(path, repo)

    def test_invalid_selected_dependency_or_selector_never_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, _, path = self.binding_fixture(Path(temp))
            before = path.read_bytes()
            for selected in ([], ["repository:missing.md"]):
                with self.subTest(selected=selected), self.assertRaises(RuntimeError):
                    self.reconcile.host_deltas.refresh_bindings(path, repo, source_identities=selected)
                self.assertEqual(before, path.read_bytes())
            (repo / "selected.md").unlink()
            with self.assertRaisesRegex(RuntimeError, "target is missing"):
                self.reconcile.host_deltas.refresh_bindings(path, repo, source_identities=["repository:selected.md"])
            self.assertEqual(before, path.read_bytes())

    def test_unrelated_missing_dependency_is_deferred_and_whole_verifier_rejects(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, _, path = self.binding_fixture(Path(temp))
            (repo / "other.md").unlink()
            result = self.reconcile.host_deltas.refresh_bindings(path, repo, source_identities=["repository:selected.md"])
            self.assertTrue(result["binding_refresh"]["committed"])
            self.assertEqual("unselected artifact dependency is missing", result["binding_refresh"]["deferred"][0]["reason"])
            with self.assertRaisesRegex(RuntimeError, "target is missing"):
                self.reconcile.host_deltas.load_manifest(path, repo)

    def test_metadata_concurrent_edit_is_preserved_by_binding_commit_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, _, path = self.binding_fixture(Path(temp))
            prepare = self.reconcile.host_deltas.prepare_bindings
            concurrent = path.read_text() + "\n "
            def race(*args, **kwargs):
                prepared = prepare(*args, **kwargs)
                path.write_text(concurrent)
                return prepared
            with patch.object(self.reconcile.host_deltas, "prepare_bindings", side_effect=race):
                with self.assertRaisesRegex(RuntimeError, "metadata changed"):
                    self.reconcile.host_deltas.refresh_bindings(path, repo, source_identities=["repository:selected.md"])
            self.assertEqual(concurrent, path.read_text())

    def test_metadata_edit_during_transaction_preparation_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, path = self.binding_fixture(Path(temp))
            copy_source = self.reconcile._copy_binding_source
            concurrent = path.read_text() + "\n "
            def race(*args, **kwargs):
                copy_source(*args, **kwargs)
                path.write_text(concurrent)
            with patch.object(self.reconcile, "_copy_binding_source", side_effect=race):
                result = self.reconcile.sync(repo, machine="test", recovery_roots={}, skill_roots=[live],
                    binding_identities=["repository:selected.md"], check_commands=[], scoped=True)
            self.assertEqual("rejected", result["result"], result)
            self.assertIn("metadata changed", result["failure"]["diagnostic"])
            self.assertEqual(concurrent, path.read_text())

    def test_actual_failed_check_retains_actionable_safe_diagnostic_and_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            original = (repo / "skills/kept/SKILL.md").read_bytes()
            target = live / "kept/SKILL.md"
            target.write_text(target.read_text() + "\nrequested adoption\n")
            report = self.reconcile.sync(repo, machine="test", recovery_roots={}, skill_roots=[live],
                adopt=["kept"], scoped=True, check_commands=[[sys.executable, "-c",
                    "print('acceptance requires frontmatter; token=private-value'); raise SystemExit(7)"]])
            self.assertEqual("rejected", report["result"], report)
            self.assertEqual("validate", report["failure"]["phase"])
            self.assertEqual(7, report["failure"]["exit_code"])
            self.assertIn("acceptance requires frontmatter", report["failure"]["diagnostic"])
            self.assertNotIn("private-value", json.dumps(report))
            self.assertTrue((repo / report["failure"]["local_log"]).is_file())
            self.assertEqual(original, (repo / "skills/kept/SKILL.md").read_bytes())

    def test_candidate_checks_rerun_when_dependency_changes_at_same_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidate"
            candidate.mkdir()
            (candidate / "owner.md").write_text("unchanged")
            dependency = root / "dependency.py"
            dependency.write_text("VALUE = 1")
            command = [[sys.executable, "-B", "-c",
                f"import runpy; assert runpy.run_path({str(dependency)!r})['VALUE'] == 1"]]
            self.reconcile._run_candidate_checks(candidate, command, "same-tree")
            self.reconcile._run_candidate_checks(candidate, command, "same-tree")
            dependency.write_text("VALUE = 2")
            with self.assertRaises(self.reconcile.CheckFailure):
                self.reconcile._run_candidate_checks(candidate, command, "same-tree")

    def test_cli_plan_and_sync_forward_identical_scope_and_capture_flags(self):
        cases = [[], ["--adopt", "kept"], ["--adopt", "kept", "--full"],
                 ["--no-capture-recovery"], ["--capture-artifact", "hermes:one"]]
        for flags in cases:
            with self.subTest(flags=flags), patch.object(self.reconcile.recovery, "_parse_roots", return_value={}), \
                 patch.object(self.reconcile, "plan", return_value={}) as preview, \
                 patch.object(self.reconcile, "complete_sync", return_value={"result": "synced"}) as complete, \
                 patch("sys.stdout"):
                self.assertEqual(0, self.reconcile.main(["plan", *flags]))
                self.assertEqual(0, self.reconcile.main(["sync", *flags]))
                for key in ("adopt", "include", "capture_recovery", "recovery_artifacts", "scoped"):
                    self.assertEqual(preview.call_args.kwargs[key], complete.call_args.kwargs[key], key)

    def test_defaults_plan_normalizes_the_same_mapped_settings_artifacts(self):
        import runtime_defaults
        cases = [([], ["codex", "hermes"], ["codex:settings", "hermes:settings"]),
                 (["--capture-artifact", "codex:settings"], ["codex"], ["codex:settings"]),
                 (["--maintenance-host", "omp"], ["omp"], None)]
        for flags, chosen, expected in cases:
            with self.subTest(flags=flags), \
                 patch.object(runtime_defaults, "load_preferences", return_value={"runtime_defaults": {"codex": "worker", "hermes": "hermes"}}), \
                 patch.object(runtime_defaults, "selected_hosts", return_value=chosen), \
                 patch.object(runtime_defaults, "plan_defaults", return_value={"hosts": chosen}) as defaults, \
                 patch.object(self.reconcile, "plan", return_value={}) as preview:
                self.assertEqual(0, self.reconcile.main(["plan", "--reconcile-defaults", *flags]))
            self.assertEqual(expected, preview.call_args.kwargs["recovery_artifacts"])
            self.assertEqual(bool(expected), preview.call_args.kwargs["capture_recovery"])
            self.assertTrue(preview.call_args.kwargs["scoped"])
            self.assertEqual(chosen, defaults.return_value["hosts"])

    def test_cli_plan_and_sync_reject_contradictory_intent_before_dispatch(self):
        cases = [["--capture-recovery", "--no-capture-recovery"],
                 ["--full", "--capture-artifact", "hermes:one"],
                 ["--no-capture-recovery", "--capture-artifact", "hermes:one"],
                 ["--no-capture-recovery", "--reconcile-defaults"],
                 ["--full", "--reconcile-defaults"]]
        cases.append(["--adopt", "kept", "--capture-recovery"])
        for action in ("plan", "sync"):
            for flags in cases:
                with self.subTest(action=action, flags=flags), \
                     patch.object(self.reconcile, "plan") as preview, \
                     patch.object(self.reconcile, "complete_sync") as complete, \
                     patch.object(self.reconcile, "complete_defaults_sync") as defaults, \
                     patch("sys.stderr"), patch("sys.stdout"):
                    with self.assertRaises(SystemExit) as raised:
                        self.reconcile.main([action, *flags])
                    self.assertEqual(2, raised.exception.code)
                    preview.assert_not_called()
                    complete.assert_not_called()
                    defaults.assert_not_called()

    def test_real_plan_and_completion_reject_scoped_capture_without_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            before = (repo / "host-deltas.json").read_bytes()
            with self.assertRaisesRegex(ValueError, "explicit artifact contract"):
                self.reconcile.plan(repo, adopt=["kept"], capture_recovery=True,
                    machine="test", skill_roots=[live])
            result = self.reconcile.complete_sync(repo, adopt=["kept"], capture_recovery=True,
                machine="test", skill_roots=[live])
            self.assertEqual("review-required", result["result"])
            self.assertIn("explicit artifact contract", result["reason"])
            self.assertEqual(before, (repo / "host-deltas.json").read_bytes())

    def test_broad_no_capture_completion_omits_native_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            native = Path(temp) / "native"
            native.mkdir()
            (native / "config.json").write_text("invalid excluded native data")
            fleet_config = json.loads((repo / "fleet.json").read_text())
            fleet_config["machines"]["local-windows"] = fleet_config["machines"].pop("test")
            (repo / "fleet.json").write_text(json.dumps(fleet_config))
            evidence = repo / "evals/results"
            evidence.mkdir(parents=True)
            for name in ("fleet-discovery-local-windows", "unified-reconciliation-local-windows"):
                (evidence / (name + ".json")).write_text('{}')
            tools = repo / "tools"
            tools.mkdir()
            for name in ("validate.py", "public_check.py"):
                (tools / name).write_text("pass\n")
            (tools / "audit.py").write_text("import sys\nassert '--structural' in sys.argv, 'excluded whole evidence check'\n")
            # This fixture has no host profile. Exercise actual subprocess wiring:
            # its checker exposes any forbidden live invocation with a marker.
            marker = native / "live-check-ran"
            (tools / "instruction_profile.py").write_text(
                "import sys\nfrom pathlib import Path\n"
                "if '--artifact-only' not in sys.argv:\n"
                f"    Path({str(marker)!r}).write_text('excluded native check')\n"
                "    sys.exit(7)\n")
            self.git(repo, "add", "tools", "fleet.json", "evals")
            self.git(repo, "commit", "-m", "fixture checker boundary")
            self.git(repo, "push", "origin", "main")
            (repo / "notes.md").write_text("reviewed note")
            hook = remote / "hooks/pre-receive"
            hook.write_text("#!/bin/sh\nexit 1\n")
            hook.chmod(0o755)
            with patch.object(self.reconcile.capability_intake, "scan", side_effect=AssertionError("excluded native scan")) as scan, \
                 patch("audit.refresh_current_evidence", side_effect=AssertionError("excluded whole native evidence refresh")) as refresh:
                options = dict(machine="local-windows", skill_roots=[live], recovery_roots={"hermes": native},
                               include=["notes.md"], capture_recovery=False, scoped=False)
                first = self.reconcile.complete_sync(repo, **options)
                self.assertEqual("incomplete", first["result"], first)
                self.assertEqual("push", first["failed_step"])
                self.assertEqual(2, len(first["deferred_evidence"]))
                hook.unlink()
                report = self.reconcile.complete_sync(repo, **options)
            self.assertEqual("synced", report["result"], report)
            scan.assert_not_called()
            refresh.assert_not_called()
            self.assertEqual(2, len(report["deferred_evidence"]))
            self.assertFalse(marker.exists())
            self.assertEqual("reviewed note", self.git(remote, "show", "main:notes.md"))

    def test_plan_full_expands_owner_selection_and_no_capture_omits_native_scan(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            fixtures.write_skill(repo, "other", "other baseline")
            registry = json.loads((repo / "registry.json").read_text())
            registry["skills"].append({"name": "other", "status": "admitted"})
            (repo / "registry.json").write_text(json.dumps(registry))
            with patch.object(self.reconcile.capability_intake, "scan") as native_scan:
                report = self.reconcile.plan(repo, adopt=["kept"], scoped=False,
                    capture_recovery=False, machine="test", skill_roots=[live])
            native_scan.assert_not_called()
            self.assertEqual({"scoped": False, "capture_recovery": False}, report["intent"])
            self.assertNotIn("selection", report)
            owners = {row.get("owner") for row in report["findings"]}
            self.assertIn("other", owners)

    def test_candidate_check_that_changes_its_input_is_not_cacheable(self):
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp)
            (candidate / "owner.md").write_text("before")
            command = [[sys.executable, "-c", "from pathlib import Path; Path('owner.md').write_text('after')"]]
            with self.assertRaisesRegex(RuntimeError, "immutable source inputs"):
                self.reconcile._run_candidate_checks(candidate, command, "tree")

    def test_file_only_checks_are_proportional_and_audit_covers_profile_once(self):
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp)
            (candidate / "tools").mkdir()
            for name in ("validate.py", "instruction_profile.py", "audit.py"):
                (candidate / "tools" / name).write_text("pass")
            self.assertEqual([], self.reconcile._candidate_commands(candidate, [], ["notes.md"]))
            commands = self.reconcile._candidate_commands(candidate, [], ["tools/reconcile.py"])
            self.assertEqual(1, len(commands))
            self.assertIn("audit.py", commands[0][1])
            owner = self.reconcile._candidate_commands(candidate, ["kept"], ["skills/kept/SKILL.md"])
            self.assertEqual(1, len(owner))
            self.assertIn("validate.py", owner[0][1])

    def test_scoped_owner_binding_uses_frozen_baseline_and_selected_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, _ = self.setup_git(Path(temp))
            fixtures.write_skill(repo, "other", "other baseline")
            registry = json.loads((repo / "registry.json").read_text())
            registry["skills"].append({"name": "other", "status": "admitted"})
            (repo / "registry.json").write_text(json.dumps(registry))
            self.fleet.render_snapshot(repo, repo / "render/fleet")
            self.fleet.apply_snapshot(repo / "render/fleet", live)
            manifest = json.loads((repo / "host-deltas.json").read_text())
            manifest["entries"] = [entry("fleet:canonical admitted skills", "fleet", self.reconcile.host_deltas._canonical_fleet_digest(repo))]
            (repo / "host-deltas.json").write_text(json.dumps(manifest))
            self.git(repo, "add", ".")
            self.git(repo, "commit", "-m", "fleet binding baseline")
            unrelated = repo / "skills/other/SKILL.md"
            unrelated.write_text(unrelated.read_text() + "\nunrelated dirty source\n")
            untouched = unrelated.read_bytes()
            selected = live / "kept/SKILL.md"
            selected.write_text(selected.read_text() + "\nselected live adoption\n")
            import sync_git
            overrides = {"skills/kept/SKILL.md": selected.read_bytes()}
            identities = {key: hashlib.sha256(value).hexdigest() for key, value in overrides.items()}
            with sync_git.prepare_candidate(repo, identities, overrides=overrides) as (candidate, _):
                expected = self.reconcile.host_deltas._canonical_fleet_digest(candidate)
            result = self.reconcile.sync(repo, machine="test", recovery_roots={}, skill_roots=[live],
                adopt=["kept"], scoped=True, check_commands=[])
            self.assertEqual("applied", result["result"], result)
            written = json.loads((repo / "host-deltas.json").read_text())["entries"][0]
            self.assertEqual("sha256:" + expected, written["version_or_hash"])
            self.assertEqual(untouched, unrelated.read_bytes())
            self.assertEqual(selected.read_bytes(), (repo / "skills/kept/SKILL.md").read_bytes())
            with self.assertRaisesRegex(RuntimeError, "binding mismatch"):
                self.reconcile.host_deltas.load_manifest(repo / "host-deltas.json", repo)

    def test_include_bound_file_publishes_derived_hash_without_unrelated_dirty_file(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            (repo / "notes.md").write_text("notes baseline")
            (repo / "other.md").write_text("other baseline")
            manifest = json.loads((repo / "host-deltas.json").read_text())
            manifest["entries"] = [entry("repository:" + name, name.replace(".md", ""),
                hashlib.sha256((repo / name).read_bytes()).hexdigest()) for name in ("notes.md", "other.md")]
            (repo / "host-deltas.json").write_text(json.dumps(manifest))
            self.git(repo, "add", ".")
            self.git(repo, "commit", "-m", "repository binding baseline")
            self.git(repo, "push", "origin", "main")
            (repo / "notes.md").write_text("reviewed selected note")
            (repo / "other.md").write_text("unrelated dirty note")
            report = self.reconcile.complete_sync(repo, machine="test", recovery_roots={}, skill_roots=[live], include=["notes.md"])
            self.assertEqual("synced", report["result"], report)
            self.assertFalse(report["installed_verified"])
            self.assertEqual([], report["verified_owners"])
            remote_manifest = json.loads(self.git(remote, "show", "main:host-deltas.json"))
            self.assertEqual("sha256:" + hashlib.sha256(b"reviewed selected note").hexdigest(), remote_manifest["entries"][0]["version_or_hash"])
            self.assertEqual(manifest["entries"][1], remote_manifest["entries"][1])
            self.assertEqual("other baseline", self.git(remote, "show", "main:other.md"))
            self.assertEqual("unrelated dirty note", (repo / "other.md").read_text())
            with self.assertRaisesRegex(RuntimeError, "binding mismatch for other"):
                self.reconcile.host_deltas.load_manifest(repo / "host-deltas.json", repo)

    def test_capture_and_repository_binding_share_selected_derived_dependency_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, live, _ = self.setup_git(root)
            native = root / "native"
            native.mkdir()
            (native / "config.json").write_text('{"value":"baseline"}')
            policy = json.loads((repo / "recovery.json").read_text())
            policy["hosts"]["hermes"]["artifacts"] = [{"id": "settings", "kind": "config", "format": "json",
                "source": "config.json", "snapshot": "hosts/hermes/config.json", "strategy": "merge", "include": ["value"]}]
            policy["hosts"] = {"hermes": policy["hosts"]["hermes"]}
            (repo / "recovery.json").write_text(json.dumps(policy))
            self.reconcile.recovery.snapshot(repo / "recovery.json", repo / "recovery/current", {"hermes": native}, repo_root=repo)
            (repo / "notes.md").write_text("baseline note")
            manifest = json.loads((repo / "host-deltas.json").read_text())
            manifest["entries"] = [entry("repository:notes.md", "notes", hashlib.sha256(b"baseline note").hexdigest()),
                entry("recovery-artifact:hermes:settings", "settings", self.fleet.sha256_file(repo / "recovery/current/hosts/hermes/config.json"))]
            (repo / "host-deltas.json").write_text(json.dumps(manifest))
            self.git(repo, "add", ".")
            self.git(repo, "commit", "-m", "combined binding baseline")
            self.git(repo, "push", "origin", "main")
            (repo / "notes.md").write_text("selected note")
            (native / "config.json").write_text('{"value":"selected"}')
            report = self.reconcile.complete_sync(repo, machine="test", recovery_roots={"hermes": native}, skill_roots=[live],
                include=["notes.md"], recovery_artifacts=["hermes:settings"])
            self.assertEqual("synced", report["result"], report)
            self.assertTrue(report["capture_verified"])
            self.assertFalse(report["installed_verified"])
            self.reconcile.host_deltas.load_manifest(repo / "host-deltas.json", repo)

    def test_resumed_publication_failure_keeps_diagnostic_log_in_original_repo(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            (repo / "tools").mkdir()
            (repo / "tools/validate.py").write_text("import os\nprint('precise resumed acceptance failure')\n"
                "raise SystemExit(7 if os.environ.get('AGENT_SYNC_TEST_FAIL_CHECK') else 0)\n")
            self.git(repo, "add", ".")
            self.git(repo, "commit", "-m", "check baseline")
            self.git(repo, "push", "origin", "main")
            selected = repo / "skills/kept/SKILL.md"
            selected.write_text(selected.read_text() + "\nselected canonical edit\n")
            hook = remote / "hooks/pre-receive"
            hook.write_text("#!/bin/sh\nexit 1\n")
            hook.chmod(0o755)
            first = self.reconcile.complete_sync(repo, machine="test", recovery_roots={}, skill_roots=[live], adopt=["kept"])
            self.assertEqual("incomplete", first["result"], first)
            self.assertEqual("push", first["failed_step"])
            hook.unlink()
            with patch.dict(os.environ, {"AGENT_SYNC_TEST_FAIL_CHECK": "yes"}):
                retry = self.reconcile.complete_sync(repo, machine="test", recovery_roots={}, skill_roots=[live], adopt=["kept"])
            self.assertEqual("incomplete", retry["result"], retry)
            self.assertEqual("verify", retry["failed_step"])
            self.assertEqual(7, retry["failure"]["exit_code"])
            self.assertIn("precise resumed acceptance failure", retry["failure"]["diagnostic"])
            self.assertTrue((repo / retry["failure"]["local_log"]).is_file())


if __name__ == "__main__":
    unittest.main()
