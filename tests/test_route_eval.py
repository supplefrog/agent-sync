from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def load_route_eval():
    path = REPO / "tools" / "run_route_eval.py"
    spec = importlib.util.spec_from_file_location("route_eval_v2", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_materialize_and_check_json_plus_command_acceptance():
    route_eval = load_route_eval()
    case = {
        "fixtures": {
            "result.json": json.dumps({"status": "ok"}),
            "test_ok.py": "raise SystemExit(0)\n",
        },
        "acceptance": {
            "json_file": "result.json",
            "expected": {"status": "ok"},
            "command": ["python", "test_ok.py"],
            "command_exit": 0,
        },
    }
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        route_eval.materialize_case(root, case)
        result = route_eval.check_acceptance(root, case)
    assert result["passed"] is False
    assert result["json_match"] is True
    assert result["command_exit_code"] is None
    assert result["unsupported_checks"] == ["command"]


def test_materialize_rejects_fixture_path_escape():
    route_eval = load_route_eval()
    with tempfile.TemporaryDirectory() as temp:
        with pytest.raises(ValueError, match="escapes trial root"):
            route_eval.materialize_case(Path(temp), {"fixtures": {"../outside": "bad"}})


def test_usage_is_public_safe_and_session_id_is_hash_only():
    route_eval = load_route_eval()
    cleaned = route_eval.sanitize_usage(
        {
            "session_id": "private-session-id",
            "model": "gpt-5.6-luna",
            "provider": "openai-codex",
            "input_tokens": 10,
        }
    )
    assert "session_id" not in cleaned
    assert len(cleaned["session_id_sha256"]) == 64
    assert cleaned["model"] == "gpt-5.6-luna"
    safe_text = route_eval._public_safe_text(
        "Bearer secret-value C:/" + "Users/Person/private Â«redacted:sk-â€¦Â»", Path("C:/trial")
    )
    assert "secret-value" not in safe_text
    assert "C:/" + "Users/Person" not in safe_text
    assert "sk-exampletoken" not in safe_text


def test_nominal_cost_uses_input_output_cache_read_and_cache_write_rates():
    route_eval = load_route_eval()
    route = {
        "pricing_usd_per_million": {
            "input": 2.0,
            "output": 10.0,
            "cache_read": 0.2,
            "cache_write": 2.5,
        }
    }
    usage = {
        "input_tokens": 1_000_000,
        "output_tokens": 100_000,
        "cache_read_tokens": 500_000,
        "cache_write_tokens": 200_000,
    }
    assert route_eval.nominal_cost_usd(usage, route) == pytest.approx(3.6)


def test_route_summary_is_per_task_class_and_records_transport_retries_cleanup_and_cost():
    route_eval = load_route_eval()
    route = {"id": "candidate"}
    trials = [
        {
            "route_id": "candidate",
            "task_class": "mechanical-bounded",
            "passed": True,
            "duration_seconds": 10.0,
            "transport_success": True,
            "retries": 0,
            "cleanup_passed": True,
            "nominal_cost_usd": 0.10,
            "required_tools_verified": ["file"],
            "verifier_passed": True,
        },
        {
            "route_id": "candidate",
            "task_class": "mechanical-bounded",
            "passed": False,
            "duration_seconds": 20.0,
            "transport_success": True,
            "retries": 1,
            "cleanup_passed": True,
            "nominal_cost_usd": 0.20,
            "required_tools_verified": [],
            "verifier_passed": True,
        },
    ]
    result = route_eval.summarize_route(route, trials, concurrency=2)
    task = result["task_classes"]["mechanical-bounded"]
    assert task["sample_size"] == 2
    assert task["pass_rate"] == 0.5
    assert task["p50_seconds"] == 15.0
    assert task["p95_seconds"] == 20.0
    assert task["attempt_success_rate"] == 1.0
    assert task["expected_retries"] == 0.5
    assert task["max_retries_observed"] == 1
    assert task["cleanup_passed"] is True
    assert task["expected_total_cost_usd"] is None
    assert task["generation_nominal_cost_usd"] == pytest.approx(0.15)
    assert task["required_tools_verified"] == []
    assert result["transport"]["sample_size"] == 2
    assert result["transport"]["p95_seconds"] == 20.0


def test_frozen_suite_and_shortlist_bind_live_catalog_models_efforts_and_constraints():
    suite = json.loads(
        (REPO / "evals" / "suites" / "adaptive-routing-hermes-0205-v1.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (
            REPO
            / "evals"
            / "fixtures"
            / "adaptive-routing"
            / "openai-codex-routes-hermes-0205-v1.json"
        ).read_text(encoding="utf-8")
    )
    catalog = {item["id"]: item for item in manifest["catalog"]}
    task_classes = {case["task_class"] for case in suite["cases"]}
    assert suite["repeats_per_task_class"] == 8
    assert task_classes == {
        "mechanical-bounded",
        "research-synthesis",
        "implementation-debugging",
        "verification-refutation",
    }
    assert set(suite["hard_constraints"]) == task_classes
    for constraint in suite["hard_constraints"].values():
        assert constraint["min_sample_size"] == 8
        assert constraint["max_critical_failures"] == 0
        assert constraint["max_retries"] == 1
    for route in manifest["routes"]:
        assert route["provider"] == "openai-codex"
        assert route["model"] in catalog
        assert route["reasoning_effort"] in catalog[route["model"]]["thinking"]
