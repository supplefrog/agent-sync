import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


APP = Path(__file__).with_name("breadcrumb.py")


class BreadcrumbCliTests(unittest.TestCase):
    def run_cli(self, *args, cwd):
        return subprocess.run(
            [sys.executable, str(APP), *map(str, args)],
            cwd=cwd,
            text=True,
            capture_output=True,
        )

    def write_json(self, path, value):
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def valid_record(self, record_id="change-1", evidence="evidence.txt"):
        return {
            "schema_version": 1,
            "id": record_id,
            "title": "Deploy the safe change",
            "intent": {
                "text": "Prevent the stale deployment prose from returning.",
                "provenance": {"refs": [evidence]},
            },
            "change": {
                "text": "Updated the deployment record and rollback note.",
                "refs": [evidence],
            },
            "checks": {
                "text": "Ran the focused regression test.",
                "refs": [evidence],
                "limits": ["Does not inspect service health."],
            },
            "deployment": {
                "status": "deployed",
                "refs": [evidence],
                "session_limits": ["One manually invoked session."],
            },
            "rollback": "Restore the previous record revision.",
            "supersedes": {
                "scope": "Only the deployment wording for this change.",
                "refs": [evidence],
            },
            "revision": 1,
            "history": [],
        }

    def test_init_is_explicit_and_never_clobbers(self):
        with tempfile.TemporaryDirectory() as temp:
            record = Path(temp) / "pilot.json"
            first = self.run_cli("init", record, cwd=temp)
            self.assertEqual(first.returncode, 0, first.stderr)
            scaffold = json.loads(record.read_text(encoding="utf-8"))
            self.assertEqual(scaffold["id"], "pilot")
            self.assertEqual(
                scaffold["intent"]["provenance"]["missing_reason"],
                "Intent provenance is not recorded yet.",
            )

            before = record.read_bytes()
            second = self.run_cli("init", record, cwd=temp)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(record.read_bytes(), before)

            checked = self.run_cli("check", record, cwd=temp)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("missing", checked.stderr.lower())

    def test_check_accepts_explicit_unknown_provenance_and_checks_local_refs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / "evidence.txt"
            evidence.write_text("evidence contents must not be rendered", encoding="utf-8")
            record = root / "record.json"
            value = self.valid_record(evidence.name)
            value["intent"]["provenance"] = {
                "refs": [],
                "missing_reason": "The original intent source was not retained.",
            }
            self.write_json(record, value)

            checked = self.run_cli("check", record, cwd=temp)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertIn("structural", checked.stdout.lower())
            self.assertIn("not inspected", checked.stdout.lower())

            evidence.unlink()
            broken = self.run_cli("check", record, cwd=temp)
            self.assertNotEqual(broken.returncode, 0)
            self.assertIn("broken local reference", broken.stderr.lower())

    def test_network_refs_are_unsupported_not_claimed_as_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            record = Path(temp) / "record.json"
            value = self.valid_record()
            value["change"]["refs"] = ["https://example.invalid/evidence"]
            self.write_json(record, value)

            checked = self.run_cli("check", record, cwd=temp)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("unsupported network", checked.stderr.lower())
            self.assertNotIn("passed", checked.stdout.lower())

    def test_update_is_validate_first_and_preserves_previous_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "evidence.txt").write_text("local", encoding="utf-8")
            record = root / "record.json"
            original = self.valid_record()
            self.write_json(record, original)

            replacement = root / "replacement.json"
            updated = self.valid_record()
            updated["title"] = "New deployment wording"
            updated["revision"] = 999
            self.write_json(replacement, updated)
            changed = self.run_cli("update", record, "--from", replacement, cwd=temp)
            self.assertEqual(changed.returncode, 0, changed.stderr)

            current = json.loads(record.read_text(encoding="utf-8"))
            self.assertEqual(current["revision"], 2)
            self.assertEqual(current["title"], "New deployment wording")
            self.assertEqual(len(current["history"]), 1)
            self.assertEqual(current["history"][0]["revision"], 1)
            self.assertEqual(current["history"][0]["title"], original["title"])

            before = record.read_bytes()
            invalid = dict(updated)
            invalid["deployment"] = dict(updated["deployment"], status="made-up")
            self.write_json(replacement, invalid)
            rejected = self.run_cli("update", record, "--from", replacement, cwd=temp)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("status", rejected.stderr.lower())
            self.assertEqual(record.read_bytes(), before)

            wrong_id = dict(updated)
            wrong_id["id"] = "other"
            self.write_json(replacement, wrong_id)
            rejected_id = self.run_cli("update", record, "--from", replacement, cwd=temp)
            self.assertNotEqual(rejected_id.returncode, 0)
            self.assertIn("immutable", rejected_id.stderr.lower())
            self.assertEqual(record.read_bytes(), before)

    def test_update_resolves_relative_refs_from_target_record_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            records = root / "records"
            inputs = root / "inputs"
            evidence = root / "evidence"
            records.mkdir()
            inputs.mkdir()
            evidence.mkdir()
            (evidence / "trace.txt").write_text("trace", encoding="utf-8")

            record = records / "record.json"
            replacement = inputs / "replacement.json"
            value = self.valid_record("change-1", "../evidence/trace.txt")
            self.write_json(record, value)
            updated = dict(value)
            updated["title"] = "Updated from another input directory"
            self.write_json(replacement, updated)

            result = self.run_cli("update", record, "--from", replacement, cwd=temp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(record.read_text(encoding="utf-8"))["revision"], 2)

    def test_render_separates_current_state_from_historical_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "evidence.txt").write_text("do not copy this evidence", encoding="utf-8")
            record = root / "record.json"
            self.write_json(record, self.valid_record())
            replacement = root / "replacement.json"
            updated = self.valid_record()
            updated["title"] = "Current title"
            updated["deployment"]["status"] = "rolled_back"
            updated["supersedes"] = {
                "scope": "Only the rollback wording in the current change.",
                "refs": ["evidence.txt"],
            }
            self.write_json(replacement, updated)
            self.assertEqual(
                self.run_cli("update", record, "--from", replacement, cwd=temp).returncode,
                0,
            )

            rendered = self.run_cli("render", record, cwd=temp)
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            output = rendered.stdout
            self.assertIn("## Current state", output)
            self.assertIn("Current title", output)
            self.assertIn("rolled_back", output)
            self.assertIn("Only the rollback wording in the current change.", output)
            self.assertIn("One manually invoked session.", output)
            self.assertIn("Restore the previous record revision.", output)
            self.assertIn("## Historical revisions (not current)", output)
            self.assertIn("historical and not current", output.lower())
            self.assertNotIn("do not copy this evidence", output)
            self.assertIn("structural", output.lower())

    def test_init_scaffold_can_be_completed_and_is_preserved_as_draft(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / "evidence.txt"
            evidence.write_text("completion evidence", encoding="utf-8")
            record = root / "pilot.json"
            initialized = self.run_cli("init", record, cwd=temp)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)

            replacement = root / "replacement.json"
            self.write_json(replacement, self.valid_record("pilot", evidence.name))
            updated = self.run_cli("update", record, "--from", replacement, cwd=temp)
            self.assertEqual(updated.returncode, 0, updated.stderr)

            current = json.loads(record.read_text(encoding="utf-8"))
            self.assertEqual(current["revision"], 2)
            self.assertEqual(len(current["history"]), 1)
            draft = current["history"][0]
            self.assertTrue(draft["draft"])
            self.assertEqual(draft["id"], "pilot")
            self.assertEqual(draft["title"], "")
            self.assertEqual(draft["revision"], 1)

            checked = self.run_cli("check", record, cwd=temp)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            rendered = self.run_cli("render", record, cwd=temp)
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertIn("draft", rendered.stdout.lower())
            self.assertIn("historical and not current", rendered.stdout.lower())

    def test_malformed_reference_shapes_are_clean_update_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "evidence.txt").write_text("local", encoding="utf-8")
            record = root / "record.json"
            self.write_json(record, self.valid_record())
            replacement = root / "replacement.json"

            malformed_values = [
                ("change", {"text": "bad", "refs": None}, "change.refs"),
                (
                    "intent",
                    {"text": "bad", "provenance": {"refs": 2}},
                    "intent.provenance.refs",
                ),
            ]
            for field, value, message in malformed_values:
                candidate = self.valid_record()
                candidate[field] = value
                self.write_json(replacement, candidate)
                result = self.run_cli("update", record, "--from", replacement, cwd=temp)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertNotIn("traceback", result.stderr.lower())

            malformed_current = self.valid_record()
            malformed_current["intent"]["provenance"]["refs"] = 2
            self.write_json(record, malformed_current)
            self.write_json(replacement, self.valid_record())
            result = self.run_cli("update", record, "--from", replacement, cwd=temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("intent.provenance.refs", result.stderr)
            self.assertNotIn("traceback", result.stderr.lower())

    def test_status_list_and_schema_metadata_are_cleanly_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "evidence.txt").write_text("local", encoding="utf-8")
            record = root / "record.json"
            cases = [
                ({"deployment": {"status": []}}, "deployment.status"),
                ({"schema_version": True}, "schema_version"),
                ({"schema_version": None}, "schema_version"),
                ({"revision": None}, "revision"),
            ]
            for changes, message in cases:
                candidate = self.valid_record()
                for field, value in changes.items():
                    if field == "deployment":
                        candidate[field] = dict(candidate[field], **value)
                    else:
                        candidate[field] = value
                self.write_json(record, candidate)
                result = self.run_cli("check", record, cwd=temp)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertNotIn("traceback", result.stderr.lower())

            candidate = self.valid_record()
            del candidate["schema_version"]
            self.write_json(record, candidate)
            missing_version = self.run_cli("check", record, cwd=temp)
            self.assertNotEqual(missing_version.returncode, 0)
            self.assertIn("schema_version", missing_version.stderr)

            candidate = self.valid_record()
            del candidate["revision"]
            self.write_json(record, candidate)
            missing_revision = self.run_cli("check", record, cwd=temp)
            self.assertNotEqual(missing_revision.returncode, 0)
            self.assertIn("revision", missing_revision.stderr)

    def test_historical_missing_refs_warn_and_update_repairs_current_refs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "evidence.txt").write_text("current evidence", encoding="utf-8")
            record = root / "record.json"
            original = self.valid_record(evidence="archived-missing.txt")
            older = self.valid_record(evidence="older-missing.txt")
            del older["history"]
            original["history"] = [older]
            self.write_json(record, original)

            replacement = root / "replacement.json"
            self.write_json(replacement, self.valid_record(evidence="evidence.txt"))
            updated = self.run_cli("update", record, "--from", replacement, cwd=temp)
            self.assertEqual(updated.returncode, 0, updated.stderr)

            current = json.loads(record.read_text(encoding="utf-8"))
            self.assertEqual(len(current["history"]), 2)
            self.assertEqual(current["history"][0]["change"]["refs"], ["older-missing.txt"])
            self.assertEqual(current["history"][1]["change"]["refs"], ["archived-missing.txt"])

            checked = self.run_cli("check", record, cwd=temp)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertIn("warning", checked.stdout.lower())
            self.assertIn("historical", checked.stdout.lower())
            self.assertIn("older-missing.txt", checked.stdout)
            self.assertIn("archived-missing.txt", checked.stdout)

            rendered = self.run_cli("render", record, cwd=temp)
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertIn("historical", rendered.stdout.lower())
            self.assertIn("older-missing.txt", rendered.stdout)
            self.assertIn("archived-missing.txt", rendered.stdout)

    def test_unc_refs_are_rejected_without_network_path_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            record = Path(temp) / "record.json"
            for reference in (r"\\server\share\evidence.txt", "//server/share/evidence.txt"):
                candidate = self.valid_record()
                candidate["change"]["refs"] = [reference]
                self.write_json(record, candidate)
                result = self.run_cli("check", record, cwd=temp)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unsupported network", result.stderr.lower())
                self.assertNotIn("cannot inspect", result.stderr.lower())

    def test_render_refs_are_absolute_escaped_file_links(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence_dir = root / "evidence folder"
            evidence_dir.mkdir()
            evidence = evidence_dir / "trace #1.txt"
            evidence.write_text("do not render contents", encoding="utf-8")
            record = root / "record.json"
            reference = "evidence folder/trace #1.txt"
            self.write_json(record, self.valid_record(evidence=reference))

            rendered = self.run_cli("render", record, cwd=temp)
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            uri = evidence.resolve().as_uri()
            self.assertIn(f"[`{reference}`]({uri})", rendered.stdout)
            self.assertIn("%20", rendered.stdout)
            self.assertIn("%23", rendered.stdout)
            self.assertNotIn("do not render contents", rendered.stdout)

    def test_malformed_json_is_a_clean_error(self):
        with tempfile.TemporaryDirectory() as temp:
            record = Path(temp) / "bad.json"
            record.write_text("{not json", encoding="utf-8")
            result = self.run_cli("check", record, cwd=temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid json", result.stderr.lower())
            self.assertNotIn("traceback", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
