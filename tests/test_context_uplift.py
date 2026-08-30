import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "context_uplift.py"
SPEC = importlib.util.spec_from_file_location("context_uplift", MODULE_PATH)
context_uplift = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = context_uplift
SPEC.loader.exec_module(context_uplift)


def sample_suite():
    return {
        "schema_version": 1,
        "suite_id": "sample",
        "cases": [
            {
                "id": "early-fact",
                "kind": "exact_fact",
                "critical": True,
                "position": "early",
                "statement": "The launch codename is KESTREL-47.",
                "question": "What is the launch codename?",
                "expected": ["KESTREL-47"],
                "forbidden": [],
            },
            {
                "id": "correction",
                "kind": "correction",
                "critical": True,
                "position": "middle",
                "statement": "Correction: the ship date is 2031-03-04, not 2031-02-11.",
                "question": "What is the corrected ship date?",
                "expected": ["2031-03-04"],
                "forbidden": ["2031-02-11"],
            },
            {
                "id": "identifier",
                "kind": "identifier",
                "critical": True,
                "position": "late",
                "statement": "The immutable receipt ID is rcpt-7f3a9c21.",
                "question": "What is the immutable receipt ID?",
                "expected": ["rcpt-7f3a9c21"],
                "forbidden": [],
            },
        ],
    }


def test_load_suite_rejects_duplicate_ids(tmp_path):
    suite = sample_suite()
    suite["cases"].append(dict(suite["cases"][0]))
    path = tmp_path / "suite.json"
    path.write_text(json.dumps(suite), encoding="utf-8")

    with pytest.raises(context_uplift.SuiteError, match="duplicate case id"):
        context_uplift.load_suite(path)


def test_build_transcript_is_deterministic_and_positions_cases():
    suite = sample_suite()

    first = context_uplift.build_transcript(suite, filler_turns=9)
    second = context_uplift.build_transcript(suite, filler_turns=9)

    assert first == second
    assert first[0]["content"].startswith("Synthetic context-uplift fixture")
    joined = "\n".join(message["content"] for message in first)
    for case in suite["cases"]:
        assert joined.count(case["statement"]) == 1
    locations = {
        case["id"]: next(i for i, message in enumerate(first) if case["statement"] in message["content"])
        for case in suite["cases"]
    }
    assert locations["early-fact"] < locations["correction"] < locations["identifier"]


def test_score_answers_enforces_expected_and_forbidden_tokens():
    suite = sample_suite()
    answers = {
        "early-fact": "The codename was KESTREL-47.",
        "correction": "The corrected date is 2031-03-04.",
        "identifier": "rcpt-7f3a9c21",
    }

    passing = context_uplift.score_answers(suite, answers)
    assert passing["critical_failures"] == []
    assert passing["score"] == 1.0

    answers["correction"] = "It changed from 2031-02-11 to 2031-03-04."
    failing = context_uplift.score_answers(suite, answers)
    assert failing["score"] == pytest.approx(2 / 3)
    assert failing["critical_failures"] == ["correction"]
    assert failing["cases"]["correction"]["forbidden_hits"] == ["2031-02-11"]


def test_choose_winner_ties_and_regressions_favor_baseline():
    baseline = {
        "strategy": "baseline",
        "score": 0.8,
        "critical_failures": [],
        "session_identity_stable": True,
        "restart_recovery": True,
        "extra_visible_sessions": 0,
        "median_latency_ms": 1000,
    }
    tied = dict(baseline, strategy="native")
    regressed = dict(baseline, strategy="lcm", score=0.9, critical_failures=["identifier"])
    improved = dict(
        baseline,
        strategy="native-900k",
        score=0.95,
        median_latency_ms=1100,
    )

    tie_decision = context_uplift.choose_winner([baseline, tied])
    assert tie_decision["winner"] == "baseline"
    assert tie_decision["reason"] == "no candidate materially improved on baseline"

    regression_decision = context_uplift.choose_winner([baseline, regressed])
    assert regression_decision["winner"] == "baseline"
    assert regression_decision["rejected"]["lcm"] == "critical failure"

    improvement_decision = context_uplift.choose_winner([baseline, improved])
    assert improvement_decision["winner"] == "native-900k"
    assert improvement_decision["material_improvement"] is True


def test_equal_recall_prefers_lower_resource_rank_before_latency():
    baseline = {
        "strategy": "baseline", "score": 0.6, "critical_failures": [],
        "session_identity_stable": False, "restart_recovery": True,
        "extra_visible_sessions": 1, "median_latency_ms": 1000,
    }
    native = dict(baseline, strategy="native-in-place", score=1.0,
                  session_identity_stable=True, extra_visible_sessions=0,
                  median_latency_ms=9000, resource_rank=1)
    large = dict(native, strategy="native-900k", median_latency_ms=5000,
                 resource_rank=2)

    decision = context_uplift.choose_winner([baseline, native, large])

    assert decision["winner"] == "native-in-place"


def test_public_receipt_contains_hashes_but_no_raw_transcript_or_private_path():
    suite = sample_suite()
    result = {
        "strategy": "native",
        "score": 1.0,
        "critical_failures": [],
        "session_identity_stable": True,
        "restart_recovery": True,
        "extra_visible_sessions": 0,
        "median_latency_ms": 42,
        "answers": {"identifier": "rcpt-7f3a9c21"},
        "raw_transcript": [{"role": "user", "content": "private"}],
        "artifact_path": "PRIVATE-PATH-SENTINEL",
    }

    receipt = context_uplift.build_public_receipt(suite, result, harness_bytes=b"harness")
    encoded = json.dumps(receipt, sort_keys=True)

    assert receipt["suite_sha256"]
    assert receipt["harness_sha256"]
    assert receipt["strategy"] == "native"
    assert "raw_transcript" not in encoded
    assert "answers" not in encoded
    assert "PRIVATE-PATH-SENTINEL" not in encoded
    assert receipt["critical_failures"] == []


def test_repository_suite_is_representative_and_valid():
    suite = context_uplift.load_suite(ROOT / "evals" / "context-uplift-suite.json")
    kinds = {case["kind"] for case in suite["cases"]}

    assert len(suite["cases"]) >= 8
    assert {"exact_fact", "correction", "identifier", "preference", "procedure", "negative"} <= kinds
    assert {case["position"] for case in suite["cases"]} == {"early", "middle", "late"}
    assert sum(bool(case["critical"]) for case in suite["cases"]) >= 5


def test_native_question_prompt_has_ids_and_questions_but_not_gold_answers():
    suite = sample_suite()
    prompt = context_uplift.build_question_prompt(suite)

    assert '"identifier"' in prompt
    assert "What is the immutable receipt ID?" in prompt
    assert "rcpt-7f3a9c21" not in prompt


def test_extract_answer_mapping_accepts_fenced_json_and_rejects_missing_ids():
    suite = sample_suite()
    text = (
        "result:\n```json\n"
        '{"early-fact": "KESTREL-47", "identifier": "rcpt-7f3a9c21", '
        '"correction": "2028-04-19"}\n```'
    )

    answers = context_uplift.extract_answer_mapping(text, suite)
    assert answers == {
        "early-fact": "KESTREL-47",
        "correction": "2028-04-19",
        "identifier": "rcpt-7f3a9c21",
    }

    with pytest.raises(context_uplift.ResultError, match="missing answer ids"):
        context_uplift.extract_answer_mapping('{"identifier": "rcpt-7f3a9c21"}', suite)


def test_validate_result_requires_all_contract_fields():
    with pytest.raises(context_uplift.ResultError, match="missing result fields"):
        context_uplift.validate_result({"strategy": "native", "score": 1.0})

    valid = {
        "strategy": "native",
        "score": 1.0,
        "critical_failures": [],
        "session_identity_stable": True,
        "restart_recovery": True,
        "extra_visible_sessions": 0,
        "median_latency_ms": 42,
        "resource_rank": 0,
    }
    assert context_uplift.validate_result(valid) == valid
