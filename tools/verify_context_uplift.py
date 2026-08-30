#!/usr/bin/env python
"""Verify the frozen context-uplift answer key and public receipts."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_IDS = {f"AK-{number:03d}" for number in range(1, 17)}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_answer_key() -> None:
    text = (ROOT / ".wayfinder" / "answer-key.md").read_text(encoding="utf-8")
    present = {token for token in EXPECTED_IDS if token in text}
    assert present == EXPECTED_IDS, f"missing answer-key IDs: {sorted(EXPECTED_IDS - present)}"
    assert "| UNRUN |" not in text
    assert "| FAIL |" not in text
    assert "| BLOCKED |" not in text


def verify_harness() -> None:
    sys.path.insert(0, str(ROOT / "tools"))
    from context_uplift import load_suite

    suite_path = ROOT / "evals" / "context-uplift-suite.json"
    suite = load_suite(suite_path)
    assert len(suite["cases"]) == 8
    receipt = load_json(ROOT / "evals" / "results" / "context-uplift-2026-08-30.json")
    suite_hash = hashlib.sha256(suite_path.read_bytes()).hexdigest()
    assert receipt["suite_sha256"] == suite_hash
    assert receipt["fixture"] == {
        "synthetic": True,
        "messages": 1362,
        "estimated_tokens": 236832,
        "raw_transcript_committed": False,
    }
    assert receipt["verification"]["agent_signal_targeted_tests"] == "12 passed"


def verify_compare() -> None:
    receipt = load_json(ROOT / "evals" / "results" / "context-uplift-2026-08-30.json")
    arms = {arm["strategy"]: arm for arm in receipt["arms"]}
    assert receipt["decision"]["winner"] == "native-in-place"
    assert arms["baseline-current-rotating-compressor"]["score"] == 0.625
    assert arms["native-in-place"]["score"] == 1.0
    assert arms["native-in-place"]["native_checkpoint_items"] >= 1
    assert arms["native-in-place"]["extra_visible_sessions"] == 0
    assert arms["native-900k"]["score"] == 1.0
    assert arms["native-900k"]["replay_mode"].startswith("full-")
    assert arms["hermes-lcm-intact"]["critical_failures"]
    promotion = receipt["promotion"]
    assert promotion["compression.in_place"] is True
    assert promotion["compression.codex_responses_native"] is True
    assert promotion["effective_base_threshold"] == 127808
    assert promotion["session_count_before"] == promotion["session_count_after"]


def verify_scout() -> None:
    registry = load_json(ROOT / "registry.json")
    scout = load_json(ROOT / "evals" / "results" / "capability-scout-2026-08-30.json")
    registry_names = {item["name"] for item in registry["skills"]}
    scout_names = {item["name"] for item in scout["capabilities"]}
    assert scout["inventory_count"] == len(registry_names) == 18
    assert scout_names == registry_names
    assert [item["priority"] for item in scout["next_pilots"]] == [1, 2, 3]
    assert any(lane["decision"] == "adopted" for lane in scout["lane_decisions"])


def verify_all() -> None:
    verify_answer_key()
    verify_harness()
    verify_compare()
    verify_scout()
    ownership = (ROOT / "contracts" / "ownership.json").read_text(encoding="utf-8")
    assert "foreground-context-router" not in ownership
    recovery = load_json(ROOT / "recovery" / "current" / "hosts" / "hermes" / "config.json")
    compression = recovery["compression"]
    assert compression["in_place"] is True
    assert compression["codex_responses_native"] is True
    assert compression["codex_responses_compact_threshold"] == 200000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=["answer-key", "harness", "compare", "scout", "all"])
    args = parser.parse_args()
    checks = {
        "answer-key": verify_answer_key,
        "harness": verify_harness,
        "compare": verify_compare,
        "scout": verify_scout,
        "all": verify_all,
    }
    checks[args.check]()
    print(json.dumps({"check": args.check, "status": "pass"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
