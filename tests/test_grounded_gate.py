from __future__ import annotations

import copy
import functools
import hashlib
import importlib.util
import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "evals" / "fixtures" / "grounded-verification"
TRUSTED_FREEZE_RECEIPT = "sha256:3868a5160cea5766b95b0dc7d0ce767405851bfd85915b45c0d72799d8a6c4c5"
TRUSTED_TEST_AUTHOR_RECEIPT = "sha256:29eb735dac530fd486a25234879c6b8b090f3cc602299b0b0838ca39b92caa53"
VERIFICATION_RECEIPT_PATH = FIXTURES / "verification-receipt.json"
TRUSTED_VERIFICATION_RECEIPT = "sha256:" + hashlib.sha256(VERIFICATION_RECEIPT_PATH.read_bytes()).hexdigest()


def load_module():
    path = REPO / "tools" / "grounded_gate.py"
    spec = importlib.util.spec_from_file_location("grounded_gate", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class GroundedVerificationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = load_module()
        cls.gate.validate_contract = functools.partial(
            cls.gate.validate_contract,
            trusted_freeze_receipt=TRUSTED_FREEZE_RECEIPT,
            trusted_test_author_receipt=TRUSTED_TEST_AUTHOR_RECEIPT,
            trusted_verification_receipt=TRUSTED_VERIFICATION_RECEIPT,
        )
        cls.valid = json.loads((FIXTURES / "valid.json").read_text(encoding="utf-8"))
        cls.schema = json.loads((REPO / "contracts" / "grounded-verification.schema.json").read_text(encoding="utf-8"))

    def test_valid_fixture_satisfies_schema_and_semantic_contract(self):
        jsonschema.Draft202012Validator(self.schema).validate(self.valid)
        self.assertEqual(self.gate.validate_contract(self.valid), [])

    def test_validation_fails_closed_without_verifier_supplied_freeze_root(self):
        errors = load_module().validate_contract(self.valid)
        self.assertIn("verifier-supplied trusted freeze receipt digest is required", errors)
        self.assertIn("verifier-supplied trusted test-author receipt digest is required", errors)
        self.assertIn("verifier-supplied trusted verification receipt digest is required", errors)

    def test_coordinated_fabricated_evidence_and_contract_rewrite_is_rejected_by_external_root(self):
        contract = copy.deepcopy(self.valid)
        fabricated = {
            "schema_version": 1,
            "artifact_type": "grounded-verification-decision-evidence",
            "contract_id": contract["contract_id"],
            "scope_id": "S-VERIFICATION",
            "decision_type": "verification",
            "evidence_lanes": [lane["lane_id"] for lane in contract["decision_evidence"][0]["lanes"]],
            "result": "pass",
            "basis": {lane["lane_id"]: "unsupported implementer-authored pass" for lane in contract["decision_evidence"][0]["lanes"]},
        }
        with tempfile.TemporaryDirectory() as temp:
            artifact_path = Path(temp) / "fabricated-evidence.json"
            artifact_path.write_text(json.dumps(fabricated), encoding="utf-8")
            digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            for lane in contract["decision_evidence"][0]["lanes"]:
                lane.update({"evidence_path": str(artifact_path), "sha256": digest, "result": "pass"})
            contract["gates"][0]["result"] = "pass"
            contract["verdict"]["decision"] = "pass"
            errors = load_module().validate_contract(
                contract,
                trusted_freeze_receipt=TRUSTED_FREEZE_RECEIPT,
                trusted_test_author_receipt=TRUSTED_TEST_AUTHOR_RECEIPT,
                trusted_verification_receipt=TRUSTED_VERIFICATION_RECEIPT,
            )
        self.assertIn("verification receipt does not match the complete evidence and verdict manifest", errors)

    def test_all_negative_fixtures_are_rejected(self):
        fixtures = sorted(FIXTURES.glob("negative-*.json"))
        self.assertGreaterEqual(len(fixtures), 5)
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                contract = json.loads(fixture.read_text(encoding="utf-8"))
                self.assertTrue(self.gate.validate_contract(contract))

    def test_role_permutation_and_collision_property(self):
        roles = list(self.valid["roles"].items())
        for permutation in itertools.permutations(roles):
            contract = copy.deepcopy(self.valid)
            contract["roles"] = dict(permutation)
            self.assertEqual(self.gate.validate_contract(contract), [])
        for left, right in itertools.combinations(self.valid["roles"], 2):
            contract = copy.deepcopy(self.valid)
            contract["roles"][right]["principal_id"] = contract["roles"][left]["principal_id"]
            self.assertIn("role principal_id values must be distinct", self.gate.validate_contract(contract))

    def test_frozen_criteria_hash_is_tamper_evident(self):
        contract = copy.deepcopy(self.valid)
        contract["criteria_freeze"]["criteria"][0]["statement"] += " weakened"
        self.assertIn(
            "criteria_sha256 does not match canonical frozen criteria",
            self.gate.validate_contract(contract),
        )

    def test_recomputed_current_hash_without_decision_event_is_rejected(self):
        contract = copy.deepcopy(self.valid)
        freeze = contract["criteria_freeze"]
        freeze["criteria"][0]["statement"] += " silently rewritten"
        freeze["criteria_sha256"] = self.gate.canonical_sha256({
            "criteria": freeze["criteria"],
            "pilot_manifest": freeze["pilot_manifest"],
            "decision_scopes": freeze["decision_scopes"],
        })
        freeze["decision_events"] = []
        self.assertIn(
            "current criteria are not connected to the immutable freeze receipt by decision events",
            self.gate.validate_contract(contract),
        )

    def test_coordinated_source_contract_and_receipt_rewrite_is_rejected_by_external_root(self):
        contract = copy.deepcopy(self.valid)
        freeze = contract["criteria_freeze"]
        contract["source_intent"]["reference"] = "kanban:t_67bb4407"
        for criterion in freeze["criteria"]:
            criterion["source_reference"] = "kanban:t_67bb4407"
        freeze["criteria_sha256"] = self.gate.canonical_sha256({
            "criteria": freeze["criteria"],
            "pilot_manifest": freeze["pilot_manifest"],
            "decision_scopes": freeze["decision_scopes"],
        })
        freeze["decision_events"] = []
        receipt = {
            "schema_version": 1,
            "receipt_type": "grounded-verification-criteria-freeze",
            "contract_id": contract["contract_id"],
            "source_intent_reference": "kanban:t_67bb4407",
            "frozen_at": freeze["frozen_at"],
            "original_criteria_sha256": freeze["criteria_sha256"],
            "scope": "coordinated rewrite",
        }
        with tempfile.TemporaryDirectory() as temp:
            receipt_path = Path(temp) / "rewritten-freeze-receipt.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            freeze["freeze_receipt_path"] = str(receipt_path)
            freeze["freeze_receipt"] = "sha256:" + hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            self.assertIn(
                "criteria freeze receipt does not match verifier-supplied trust root",
                self.gate.validate_contract(contract, trusted_freeze_receipt=TRUSTED_FREEZE_RECEIPT),
            )

    def test_source_card_and_held_out_board_regression_are_frozen(self):
        self.assertEqual(self.valid["source_intent"]["reference"], "kanban:t_1e0d8e90")
        criterion_ids = {item["id"] for item in self.valid["criteria_freeze"]["criteria"]}
        self.assertTrue({f"AC-{index:03d}" for index in range(1, 9)} <= criterion_ids)
        expected = set(self.valid["criteria_freeze"]["pilot_manifest"]["expected_blocker_ids"])
        self.assertIn("review-blocked-status-not-proactively-surfaced", expected)
        self.assertIn("phantom-assignee-not-reconciled-or-escalated", expected)
        result = self.gate.evaluate_pilot_evidence(
            json.loads((FIXTURES / "pilot-evidence.json").read_text(encoding="utf-8"))
        )
        blocker_ids = {item["id"] for item in result["blockers"]}
        self.assertIn("review-blocked-status-not-proactively-surfaced", blocker_ids)
        self.assertIn("phantom-assignee-not-reconciled-or-escalated", blocker_ids)

    def test_post_freeze_user_decisions_are_chained_and_fully_scoped(self):
        freeze = self.valid["criteria_freeze"]
        self.assertEqual([event["id"] for event in freeze["decision_events"]], ["DEC-001", "DEC-002", "DEC-003", "DEC-004"])
        self.assertEqual(freeze["decision_events"][-1]["after_sha256"], freeze["criteria_sha256"])
        criterion_ids = {item["id"] for item in freeze["criteria"]}
        self.assertTrue({f"AC-{index:03d}" for index in range(14, 20)} <= criterion_ids)
        scopes = {scope["id"]: scope for scope in freeze["decision_scopes"]}
        self.assertEqual(set(scopes["S-INTENT-LINEAGE"]["criterion_ids"]), {"AC-014", "AC-015", "AC-016"})
        self.assertEqual(set(scopes["S-ULTIMATE-AGENT"]["criterion_ids"]), {"AC-017", "AC-018", "AC-019"})
        self.assertIn("no-downstream-pass-claim", scopes["S-ULTIMATE-AGENT"]["required_evidence_lanes"])

    def test_freeze_receipt_binds_complete_amendment_chain(self):
        receipt = json.loads((FIXTURES / "criteria-freeze-receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["decision_chain_event_ids"], ["DEC-001", "DEC-002", "DEC-003", "DEC-004"])
        self.assertEqual(receipt["final_criteria_sha256"], self.valid["criteria_freeze"]["criteria_sha256"])
        contract = copy.deepcopy(self.valid)
        contract["criteria_freeze"]["decision_events"].pop()
        self.assertTrue(any("complete amendment chain" in error or "connected" in error for error in self.gate.validate_contract(contract)))

    def test_amended_held_out_regressions_are_deterministically_detected(self):
        evidence = json.loads((FIXTURES / "pilot-evidence.json").read_text(encoding="utf-8"))
        result = self.gate.evaluate_pilot_evidence(evidence)
        blocker_ids = {item["id"] for item in result["blockers"]}
        self.assertTrue({
            "evolving-multi-turn-lineage-lost",
            "summary-overwrites-authoritative-lineage",
            "research-first-cross-host-resume-omitted",
            "material-status-required-user-reminder",
            "summarizer-intake-required-second-reminder",
            "legacy-done-status-treated-as-evidence",
            "ultimate-agent-convergence-claim-unrevalidated",
            "prime-boundaries-not-evidence-bound",
            "fleet-omission-required-third-reminder",
        } <= blocker_ids)

    def test_test_author_receipt_covers_every_amended_criterion(self):
        artifact = json.loads((FIXTURES / "independent-test-author.json").read_text(encoding="utf-8"))
        expected = [item["id"] for item in self.valid["criteria_freeze"]["criteria"]]
        self.assertEqual(artifact["frozen_input"]["criterion_ids"], expected)
        covered = {criterion_id for check in artifact["acceptance_checks"] for criterion_id in check["criterion_ids"]}
        self.assertEqual(covered, set(expected))
        self.assertEqual(artifact["source"]["tool_policy"], "todo-only")
        self.assertFalse(artifact["source"]["implementation_access"])

    def test_independent_test_author_receipt_is_bound_and_stale_substitution_is_rejected(self):
        binding = self.valid["test_author_receipt"]
        self.assertEqual(binding["artifact_path"], "evals/fixtures/grounded-verification/independent-test-author.json")
        contract = copy.deepcopy(self.valid)
        contract["test_author_receipt"]["receipt"] = "sha256:" + "0" * 64
        self.assertTrue(any("test-author receipt hash mismatch" in error for error in self.gate.validate_contract(contract)))

        artifact = json.loads((FIXTURES / "independent-test-author.json").read_text(encoding="utf-8"))
        artifact["frozen_input"]["frozen_at"] = "2026-08-16T02:26:49Z"
        with tempfile.TemporaryDirectory() as temp:
            stale_artifact = Path(temp) / "independent-test-author.json"
            stale_artifact.write_text(json.dumps(artifact), encoding="utf-8")
            receipt = json.loads((FIXTURES / "independent-test-author-receipt.json").read_text(encoding="utf-8"))
            receipt["artifact_path"] = str(stale_artifact)
            receipt["artifact_sha256"] = hashlib.sha256(stale_artifact.read_bytes()).hexdigest()
            stale_receipt = Path(temp) / "independent-test-author-receipt.json"
            stale_receipt.write_text(json.dumps(receipt), encoding="utf-8")
            contract = copy.deepcopy(self.valid)
            contract["test_author_receipt"].update({
                "artifact_path": str(stale_artifact),
                "artifact_sha256": receipt["artifact_sha256"],
                "receipt_path": str(stale_receipt),
                "receipt": "sha256:" + hashlib.sha256(stale_receipt.read_bytes()).hexdigest(),
            })
            self.assertTrue(any("test-author artifact freeze timestamp mismatch" in error for error in self.gate.validate_contract(contract)))

        artifact = json.loads((FIXTURES / "independent-test-author.json").read_text(encoding="utf-8"))
        artifact["acceptance_checks"][0]["expected_outcome"] = "coherently rewritten proxy"
        with tempfile.TemporaryDirectory() as temp:
            replacement_artifact = Path(temp) / "independent-test-author.json"
            replacement_artifact.write_text(json.dumps(artifact), encoding="utf-8")
            receipt = json.loads((FIXTURES / "independent-test-author-receipt.json").read_text(encoding="utf-8"))
            receipt["artifact_path"] = str(replacement_artifact)
            receipt["artifact_sha256"] = hashlib.sha256(replacement_artifact.read_bytes()).hexdigest()
            replacement_receipt = Path(temp) / "independent-test-author-receipt.json"
            replacement_receipt.write_text(json.dumps(receipt), encoding="utf-8")
            contract = copy.deepcopy(self.valid)
            contract["test_author_receipt"].update({
                "artifact_path": str(replacement_artifact),
                "artifact_sha256": receipt["artifact_sha256"],
                "receipt_path": str(replacement_receipt),
                "receipt": "sha256:" + hashlib.sha256(replacement_receipt.read_bytes()).hexdigest(),
            })
            errors = load_module().validate_contract(
                contract,
                trusted_freeze_receipt=TRUSTED_FREEZE_RECEIPT,
                trusted_test_author_receipt=TRUSTED_TEST_AUTHOR_RECEIPT,
            )
            self.assertIn("test-author receipt does not match verifier-supplied trust root", errors)

    def test_shared_proxy_cannot_claim_full_independence(self):
        contract = copy.deepcopy(self.valid)
        contract["verifier"]["isolation_strength"] = "principal-and-workspace-isolated"
        contract["verifier"]["shared_visible_proxy"] = True
        self.assertIn(
            "shared visible proxy can only be labeled context-only isolation",
            self.gate.validate_contract(contract),
        )

    def test_access_scope_overlap_and_fabricated_receipt_are_rejected(self):
        contract = copy.deepcopy(self.valid)
        boundary = next(item for item in contract["isolation"] if item["subject_role"] == "implementer")
        boundary["readable_scopes"].append("held_out_tests")
        self.assertTrue(any("both readable and denied" in error for error in self.gate.validate_contract(contract)))
        contract = copy.deepcopy(self.valid)
        contract["isolation"][0]["receipt"] = "sha256:" + "0" * 64
        self.assertTrue(any("isolation receipt hash mismatch" in error for error in self.gate.validate_contract(contract)))

    def test_trivial_or_missing_gate_evidence_is_rejected(self):
        contract = copy.deepcopy(self.valid)
        contract["gates"][0]["command_or_probe"] = "true"
        contract["gates"][0]["evidence_path"] = "does/not/exist"
        errors = self.gate.validate_contract(contract)
        self.assertIn("gate G-CONTRACT uses a trivial command or probe", errors)
        self.assertIn("gate G-CONTRACT evidence path does not exist", errors)

    def test_trust_downgrade_and_failed_basis_gate_are_rejected(self):
        contract = copy.deepcopy(self.valid)
        gate = next(item for item in contract["gates"] if item["id"] == "G-TEETH")
        gate["trusted"] = False
        contract["verifier"]["reexecuted_gate_ids"].remove("G-TEETH")
        errors = self.gate.validate_contract(contract)
        self.assertTrue(any("material path" in error for error in errors))
        self.assertIn("verdict basis gate G-TEETH must be trusted and passing", errors)

    def test_verdict_cannot_omit_gate_required_by_claimed_decision_scope(self):
        contract = copy.deepcopy(self.valid)
        contract["verdict"]["basis_gate_ids"].remove("G-PILOT")
        self.assertIn(
            "claimed decision scope S-ADOPTION lacks required verdict gates: G-PILOT",
            self.gate.validate_contract(contract),
        )

    def test_terminal_candidate_trial_cannot_inflate_to_comparison_scope(self):
        contract = copy.deepcopy(self.valid)
        comparison = next(item for item in contract["decision_evidence"] if item["scope_id"] == "S-ADOPTION")
        comparison["lanes"] = [
            lane for lane in comparison["lanes"] if lane["lane_id"] == "candidate-trial"
        ]
        self.assertIn(
            "decision scope S-ADOPTION lacks required evidence lanes: baseline, cost, host-neutrality, maintenance, portability, rollback",
            self.gate.validate_contract(contract),
        )

    def test_ultimate_agent_scope_cannot_drop_downstream_nonclaim_lane(self):
        contract = copy.deepcopy(self.valid)
        evidence = next(item for item in contract["decision_evidence"] if item["scope_id"] == "S-ULTIMATE-AGENT")
        evidence["lanes"] = [lane for lane in evidence["lanes"] if lane["lane_id"] != "no-downstream-pass-claim"]
        self.assertIn(
            "decision scope S-ULTIMATE-AGENT lacks required evidence lanes: no-downstream-pass-claim",
            self.gate.validate_contract(contract),
        )

    def test_frozen_pilot_manifest_and_attribution_are_enforced(self):
        contract = copy.deepcopy(self.valid)
        contract["pilot"]["known_blockers"].pop(0)
        self.assertIn("pilot blocker set does not match the frozen manifest", self.gate.validate_contract(contract))
        contract = copy.deepcopy(self.valid)
        lifecycle = next(item for item in contract["pilot"]["known_blockers"] if item["id"].startswith("native-cc"))
        lifecycle["classification"] = "routing-patch-regression"
        self.assertIn(
            "pilot blocker detection or attribution does not match deterministic evidence",
            self.gate.validate_contract(contract),
        )

    def test_pilot_evidence_derives_all_blockers_and_non_regression(self):
        evidence = json.loads((FIXTURES / "pilot-evidence.json").read_text(encoding="utf-8"))
        result = self.gate.evaluate_pilot_evidence(evidence)
        self.assertEqual(len(result["blockers"]), 16)
        self.assertIn("routing-specific-receipt-invalidation-fix", result["non_regressions"])
        self.assertFalse(result["live_route_changed"])

    def test_verifier_must_reexecute_every_trusted_deterministic_gate(self):
        contract = copy.deepcopy(self.valid)
        contract["verifier"]["reexecuted_gate_ids"].remove("G-TEETH")
        self.assertIn(
            "verifier did not re-execute deterministic gates: G-TEETH",
            self.gate.validate_contract(contract),
        )

    def test_pilot_accounts_for_every_preserved_blocker(self):
        blockers = [item for item in self.valid["pilot"]["known_blockers"] if item["expected"] == "blocker"]
        self.assertEqual(len(blockers), 16)
        self.assertTrue(all(item["detected"] for item in blockers))
        self.assertEqual(self.valid["pilot"]["false_positives"], 0)
        self.assertEqual(self.valid["pilot"]["false_negatives"], 0)

    def test_cli_accepts_valid_and_rejects_negative(self):
        valid = subprocess.run(
            [
                sys.executable,
                str(REPO / "tools" / "grounded_gate.py"),
                str(FIXTURES / "valid.json"),
                "--trusted-freeze-receipt",
                TRUSTED_FREEZE_RECEIPT,
                "--trusted-test-author-receipt",
                TRUSTED_TEST_AUTHOR_RECEIPT,
                "--trusted-verification-receipt",
                TRUSTED_VERIFICATION_RECEIPT,
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        invalid = subprocess.run(
            [
                sys.executable,
                str(REPO / "tools" / "grounded_gate.py"),
                str(FIXTURES / "negative-role-collision.json"),
                "--trusted-freeze-receipt",
                TRUSTED_FREEZE_RECEIPT,
                "--trusted-test-author-receipt",
                TRUSTED_TEST_AUTHOR_RECEIPT,
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        untrusted = subprocess.run(
            [sys.executable, str(REPO / "tools" / "grounded_gate.py"), str(FIXTURES / "valid.json")],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertEqual(invalid.returncode, 1, invalid.stdout + invalid.stderr)
        self.assertEqual(untrusted.returncode, 1, untrusted.stdout + untrusted.stderr)
        self.assertIn("verifier-supplied trusted freeze receipt digest is required", untrusted.stderr)

    def test_cli_enforces_json_schema_and_receipt_semantics(self):
        contract = copy.deepcopy(self.valid)
        contract.pop("rollback")
        self.assertTrue(self.gate.validate_schema(contract))
        contract = copy.deepcopy(self.valid)
        contract["unexpected"] = True
        self.assertTrue(self.gate.validate_schema(contract))
        contract = copy.deepcopy(self.valid)
        contract["isolation"][0]["receipt_path"] = "README.md"
        import hashlib
        contract["isolation"][0]["receipt"] = "sha256:" + hashlib.sha256((REPO / "README.md").read_bytes()).hexdigest()
        self.assertTrue(any("isolation receipt" in error for error in self.gate.validate_contract(contract)))
        receipt_path = FIXTURES / "isolation-receipts.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["contract_id"] = "different-contract"
        with __import__("tempfile").TemporaryDirectory() as temp:
            mutated = Path(temp) / "receipt.json"
            mutated.write_text(json.dumps(receipt), encoding="utf-8")
            contract = copy.deepcopy(self.valid)
            for boundary in contract["isolation"]:
                boundary["receipt_path"] = str(mutated)
                boundary["receipt"] = "sha256:" + hashlib.sha256(mutated.read_bytes()).hexdigest()
            self.assertTrue(any("wrong type or role" in error for error in self.gate.validate_contract(contract)))


if __name__ == "__main__":
    unittest.main()
