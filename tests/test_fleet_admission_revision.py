"""Protect the selected revision and rollout host set at Fleet Admission."""
import hashlib
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import eval_gate
from artifact_hash import freeze_candidate


def test_gate_rejects_stale_revision_and_missing_rollout_host(tmp_path):
    entry = tmp_path / "SKILL.md"
    entry.write_text("Prior source", encoding="utf-8")
    old = freeze_candidate(entry)
    suite_hash = hashlib.sha256(b"suite").hexdigest()
    artifact = {"suite_sha256": suite_hash, "candidate_sha256": old["package_sha256"],
                "candidate_prompt_sha256": old["prompt_sha256"],
                "candidate_identity_format": old["identity_format"]}
    reports = [
        {"agent": host, "decision_mode": "admission", "decision": {"decision": "admit"},
         "effective_stack": {"equivalence_group": "matched"}, "artifacts": artifact}
        for host in ("codex", "omp")
    ]
    accepted = {"errors": [], "evidence_complete": True, "positive_decision_sufficient": True,
                "computed_decision": "admit", "scope": "fixture", "operational_errors": [],
                "limitations": []}

    def gate(rows, package):
        return eval_gate.aggregate(rows, ["codex", "omp"], "admission", "restore",
                                   {"codex": "1" * 64, "omp": "2" * 64},
                                   suite={}, suite_sha256=suite_hash, candidate=package)

    with patch.object(eval_gate, "validate_report", return_value=accepted):
        assert gate(reports, old)["decision"] == "admit"
        assert gate(reports[:1], old)["missing_hosts"] == ["omp"]
        assert gate(reports[:1], old)["decision"] == "inconclusive"
        entry.with_name("helper.py").write_text("print(42)", encoding="utf-8")
        changed = freeze_candidate(entry)
        assert changed["prompt_sha256"] == old["prompt_sha256"]
        refusal = gate(reports, changed)
        assert refusal["decision"] == "inconclusive"
        assert refusal["invalid_evidence"] == {
            host: ["selected revision mismatch: candidate_sha256"] for host in ("codex", "omp")
        }
