"""Exact reviewed external packages are observations, never fleet authority."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import test_reconcile as fixtures

MARKER = ".paseo-managed-files.json"
CONTRACT = "contracts/external-owners.json"


class ExternalOwnerTests(unittest.TestCase):
    setUp = fixtures.ReconcileTests.setUp
    fixture = fixtures.ReconcileTests.fixture

    def package(self, live, name="paseo"):
        package = live / name
        package.mkdir(exist_ok=True)
        (package / "SKILL.md").write_bytes(
            f"---\nname: {name}\ndescription: Product-owned fixture.\n---\nPRIVATE BODY\n".encode()
        )
        data = {"version": 1, "files": {"SKILL.md": self.fleet.sha256_file(package / "SKILL.md")}}
        (package / MARKER).write_text(json.dumps(data), encoding="utf-8")
        return package

    def contract(self, repo, live, package):
        data = {"schema_version": 1, "packages": [{
            "name": package.name, "owner": "paseo", "machine": "test",
            "skill_root": str(live), "marker_sha256": self.fleet.sha256_file(package / MARKER),
        }]}
        (repo / CONTRACT).write_text(json.dumps(data), encoding="utf-8")
        shutil.copyfile(fixtures.REPO / "contracts/external-owners.schema.json",
                        repo / "contracts/external-owners.schema.json")
        return data

    def prepare(self, root):
        repo, live = self.fixture(root)
        package = self.package(live)
        self.contract(repo, live, package)
        return repo, live, package

    def plan(self, repo, live):
        return self.reconcile.plan(repo, machine="test", recovery_roots={}, skill_roots=[live])

    def finding(self, repo, live, name="paseo"):
        return next(item for item in self.plan(repo, live)["findings"] if item["target"] == name)

    def test_reviewed_package_is_visible_read_only_and_not_admitted(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, package = self.prepare(Path(temp))
            before = fixtures.digest(Path(temp))
            result = self.finding(repo, live)
            self.assertEqual("reviewed-external-owner", result["change_class"])
            self.assertEqual("external:paseo", result["owner"])
            self.assertEqual("no-action", result["disposition"])
            self.assertEqual(self.fleet.sha256_file(package / MARKER), result["marker_sha256"])
            self.assertFalse(result["auto_apply_eligible"])
            self.assertFalse(result["eligible_after_checks"])
            self.assertNotIn("PRIVATE BODY", json.dumps(result))
            self.assertEqual(before, fixtures.digest(Path(temp)))
            self.assertNotIn("paseo", self.fleet.load_manifest(repo / "render/fleet")["skills"])
            self.assertNotIn("paseo", self.fleet.load_state(live)["skills"])

    def test_unknown_near_miss_and_wrong_root_are_not_exempt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, live, package = self.prepare(root)
            self.package(live, "paseo-extra")
            self.assertEqual("stage-for-review", self.finding(repo, live, "paseo-extra")["disposition"])
            other = root / "other"
            other.mkdir()
            shutil.copytree(package, other / "paseo")
            self.assertEqual("stage-for-review", self.finding(repo, other)["disposition"])
            (repo / CONTRACT).unlink()
            self.assertEqual("stage-for-review", self.finding(repo, live)["disposition"])

    def test_missing_changed_or_extra_content_blocks(self):
        for mutation in ("missing-marker", "changed-marker", "changed-skill", "extra-file", "missing-skill"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                repo, live, package = self.prepare(Path(temp))
                if mutation == "missing-marker":
                    (package / MARKER).unlink()
                elif mutation == "changed-marker":
                    (package / MARKER).write_text('{}')
                elif mutation == "changed-skill":
                    (package / "SKILL.md").write_text("different body")
                elif mutation == "extra-file":
                    (package / "unreviewed.txt").write_text("extra")
                else:
                    (package / "SKILL.md").unlink()
                finding = self.finding(repo, live)
                self.assertEqual("review-required", finding["disposition"])
                self.assertFalse(finding["auto_apply_eligible"])

    def test_malformed_records_fail_closed(self):
        for mutation in ("unknown-owner", "unknown-field", "duplicate", "traversal", "bad-hash", "unknown-root", "unknown-machine", "newline-name", "newline-hash"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                repo, live, package = self.prepare(Path(temp))
                data = json.loads((repo / CONTRACT).read_text())
                record = data["packages"][0]
                if mutation == "duplicate":
                    data["packages"].append(copy.deepcopy(record))
                else:
                    key, value = {
                        "unknown-owner": ("owner", "other-product"),
                        "unknown-field": ("ignore_unmanaged", True),
                        "traversal": ("name", "../paseo"),
                        "bad-hash": ("marker_sha256", "bad"),
                        "unknown-root": ("skill_root", "unconfigured-root"),
                        "unknown-machine": ("machine", "unconfigured-machine"),
                        "newline-name": ("name", "paseo\n"),
                        "newline-hash": ("marker_sha256", record["marker_sha256"] + "\n"),
                    }[mutation]
                    record[key] = value
                (repo / CONTRACT).write_text(json.dumps(data))
                with self.assertRaises(RuntimeError):
                    self.plan(repo, live)

    def test_marker_shape_paths_and_frontmatter_fail_even_when_pinned(self):
        for mutation in ("traversal", "backslash", "absolute", "ads", "extra-field", "bool-version", "duplicate-key", "wrong-name"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                repo, live, package = self.prepare(Path(temp))
                data = json.loads((package / MARKER).read_text())
                if mutation in {"traversal", "backslash", "absolute", "ads"}:
                    bad = {"traversal": "../SKILL.md", "backslash": "dir\\SKILL.md",
                           "absolute": "/SKILL.md", "ads": "SKILL.md:stream"}[mutation]
                    data["files"][bad] = "a" * 64
                elif mutation == "extra-field":
                    data["owner"] = "paseo"
                elif mutation == "bool-version":
                    data["version"] = True
                elif mutation == "wrong-name":
                    (package / "SKILL.md").write_text("---\nname: another-skill\n---\n")
                    data["files"]["SKILL.md"] = self.fleet.sha256_file(package / "SKILL.md")
                (package / MARKER).write_text(json.dumps(data))
                if mutation == "duplicate-key":
                    (package / MARKER).write_text('{"version":1,"version":1,"files":{}}')
                self.contract(repo, live, package)
                self.assertEqual("review-required", self.finding(repo, live)["disposition"])

    def test_canonical_registry_and_managed_name_collisions_fail_closed(self):
        for collision in ("canonical", "registry", "managed", "desired"):
            with self.subTest(collision=collision), tempfile.TemporaryDirectory() as temp:
                repo, live, package = self.prepare(Path(temp))
                if collision == "canonical":
                    (repo / "skills/Paseo").mkdir()
                elif collision == "registry":
                    data = json.loads((repo / "registry.json").read_text())
                    data["skills"].append({"name": "paseo", "status": "staged"})
                    (repo / "registry.json").write_text(json.dumps(data))
                elif collision == "managed":
                    data = self.fleet.load_state(live)
                    data["skills"]["paseo"] = {"sha256": self.fleet.directory_record(package)["sha256"]}
                    (live / self.fleet.STATE_FILE).write_text(json.dumps(data))
                else:
                    # A rendered owner can outlive registry/source removal.
                    target = repo / "render/fleet/skills/paseo"
                    shutil.copytree(package, target)
                    data = self.fleet.load_manifest(repo / "render/fleet")
                    data["skills"]["paseo"] = self.fleet.directory_record(target)
                    (repo / "render/fleet/manifest.json").write_text(json.dumps(data))
                with self.assertRaises(RuntimeError):
                    self.plan(repo, live)

    def test_symlinks_are_not_followed_or_concealed(self):
        for location in ("package", "marker", "skill", "root", "unknown-package"):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                repo, live, package = self.prepare(root)
                if location in {"package", "unknown-package"}:
                    target = root / "outside"
                    package.rename(target)
                    link = live / ("paseo" if location == "package" else "paseo-extra")
                elif location == "root":
                    target = root / "outside"
                    live.rename(target)
                    link = live
                else:
                    link = package / (MARKER if location == "marker" else "SKILL.md")
                    target = root / "outside.txt"
                    link.rename(target)
                try:
                    link.symlink_to(target, target_is_directory=target.is_dir())
                except OSError as exc:
                    self.skipTest(f"symlink creation unavailable: {exc}")
                before = fixtures.digest(target) if target.is_dir() else target.read_bytes()
                if location == "root":
                    with self.assertRaises(RuntimeError):
                        self.plan(repo, live)
                else:
                    name = "paseo-extra" if location == "unknown-package" else "paseo"
                    finding = self.finding(repo, live, name)
                    self.assertNotEqual("no-action", finding["disposition"])
                after = fixtures.digest(target) if target.is_dir() else target.read_bytes()
                self.assertEqual(before, after)

    def test_fleet_preserves_external_package_and_ordinary_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, package = self.prepare(Path(temp))
            before = fixtures.digest(package)
            self.fleet.apply_snapshot(repo / "render/fleet", live)
            self.assertEqual(before, fixtures.digest(package))
            (live / "kept/SKILL.md").write_text("ordinary local edit")
            self.assertEqual("managed-skill-conflict", self.finding(repo, live, "kept")["change_class"])
            with self.assertRaises(RuntimeError):
                self.fleet.apply_snapshot(repo / "render/fleet", live)
            self.assertEqual(before, fixtures.digest(package))

    @unittest.skipUnless(os.name == "nt", "Windows reparse point regression")
    def test_real_junctions_are_blocked_without_following_targets(self):
        for location in ("package", "root", "ancestor", "unknown-package"):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                repo, live, package = self.prepare(root)
                target = root / "outside"
                if location in {"root", "ancestor"}:
                    live.rename(target)
                    link = live
                else:
                    package.rename(target)
                    link = live / ("paseo" if location == "package" else "paseo-extra")
                made = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(link), str(target)],
                                      capture_output=True, text=True)
                self.assertEqual(0, made.returncode, made.stdout + made.stderr)
                try:
                    before = fixtures.digest(target)
                    if location == "ancestor":
                        nested = target / "nested"
                        nested.mkdir()
                        with self.assertRaises(RuntimeError):
                            self.plan(repo, link / "nested")
                    elif location == "root":
                        with self.assertRaises(RuntimeError):
                            self.plan(repo, live)
                    else:
                        name = "paseo-extra" if location == "unknown-package" else "paseo"
                        self.assertNotEqual("no-action", self.finding(repo, live, name)["disposition"])
                    self.assertEqual(before, fixtures.digest(target))
                finally:
                    os.rmdir(link)

    def test_file_reparse_metadata_is_rejected_before_reading(self):
        for filename in (MARKER, "SKILL.md"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as temp:
                repo, live, package = self.prepare(Path(temp))
                module = self.reconcile.capability_intake.external_owners
                original = module.fleet.is_linklike_path
                with patch.object(module.fleet, "is_linklike_path",
                                  side_effect=lambda path: path == package / filename or original(path)):
                    self.assertEqual("review-required", self.finding(repo, live)["disposition"])

    def test_absence_does_not_install_and_scope_is_machine_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, package = self.prepare(Path(temp))
            config = self.fleet.load_fleet(repo)
            config["machines"]["other"] = copy.deepcopy(config["machines"]["test"])
            (repo / "fleet.json").write_text(json.dumps(config))
            report = self.reconcile.plan(repo, machine="other", recovery_roots={}, skill_roots=[live])
            finding = next(item for item in report["findings"] if item["target"] == "paseo")
            self.assertEqual("stage-for-review", finding["disposition"])
            shutil.rmtree(package)
            self.assertFalse(any(item["target"] == "paseo" for item in self.plan(repo, live)["findings"]))
            self.assertFalse(package.exists())

    def test_recovery_enabled_scan_retains_the_same_external_observation(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, package = self.prepare(Path(temp))
            home = Path(temp) / "host"
            home.mkdir()
            (home / "SOUL.md").write_text("native instruction\n")
            policy = {"schema_version": 1, "machine": "test", "public_safe": True,
                      "hosts": {"hermes": {"artifacts": [{"id": "instructions", "kind": "text",
                          "source": "SOUL.md", "snapshot": "hosts/hermes/SOUL.md", "format": "text",
                          "include": [], "strategy": "replace-if-absent", "portable_paths": False}]}}}
            (repo / "recovery.json").write_text(json.dumps(policy))
            self.reconcile.recovery.snapshot(repo / "recovery.json", repo / "recovery/current",
                                             {"hermes": home}, repo_root=repo)
            (home / "SOUL.md").write_text("conflicting native instruction\n")
            before = fixtures.digest(Path(temp))
            report = self.reconcile.capability_intake.scan(repo, machine="test", recovery_roots={"hermes": home}, skill_roots=[live])
            finding = next(item for item in report["findings"] if item["target"] == "paseo")
            self.assertEqual("reviewed-external-owner", finding["change_class"])
            native = next(item for item in report["findings"] if item["target"] == "SOUL.md")
            self.assertEqual("conflict", native["source_action"])
            self.assertEqual("review-required", native["disposition"])
            self.assertEqual(before, fixtures.digest(Path(temp)))

    def test_completion_only_passes_reviewed_observation_and_never_selects_it(self):
        import sys
        sys.path.insert(0, str(fixtures.REPO / "tools"))
        import sync_git
        for scenario in ("valid", "invalid", "plan-race"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temp:
                repo, live, package = self.prepare(Path(temp))
                if scenario == "invalid":
                    (package / MARKER).unlink()
                before = fixtures.digest(live)
                real_plan = self.reconcile.plan

                def plan_then_race(*args, **kwargs):
                    result = real_plan(*args, **kwargs)
                    if scenario == "plan-race":
                        (package / MARKER).unlink()
                    return result

                def stop_checks(*args):
                    if scenario == "plan-race":
                        return []
                    raise RuntimeError("test-stop-at-checks")

                # No Git or deployment is performed. Stop at prerequisite checks;
                # all classification and blocker decisions run in production code.
                with patch.object(self.reconcile, "_governance_findings", return_value=[]), \
                     patch.object(sync_git, "lock", return_value=nullcontext()), \
                     patch.object(sync_git, "read_pending", return_value=None), \
                     patch.object(sync_git, "destination", return_value={}), \
                     patch.object(sync_git, "preflight"), \
                     patch.object(sync_git, "changed", return_value=set()), \
                     patch.object(sync_git, "identities", return_value={}), \
                     patch.object(sync_git, "assert_publishable"), \
                     patch.object(self.reconcile, "plan", side_effect=plan_then_race), \
                     patch.object(self.reconcile, "_run_checks", side_effect=stop_checks) as checks, \
                     patch.object(self.reconcile, "sync") as apply:
                    result = self.reconcile.complete_sync(repo, machine="test", recovery_roots={}, skill_roots=[live])
                self.assertEqual(0 if scenario == "invalid" else 1, checks.call_count)
                if scenario == "invalid":
                    self.assertEqual("review-required", result["result"])
                elif scenario == "plan-race":
                    self.assertEqual("unmanaged or external-owner content requires review", result["reason"])
                else:
                    self.assertEqual("test-stop-at-checks", result["reason"])
                apply.assert_not_called()
                if scenario != "plan-race":
                    self.assertEqual(before, fixtures.digest(live))


if __name__ == "__main__":
    unittest.main()
