import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest


def load():
    path=Path(__file__).resolve().parents[1]/"tools/run_route_eval.py"
    spec=importlib.util.spec_from_file_location("route_faults",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def sample(**changes):
    row={"route_id":"synthetic","task_class":"bounded","passed":True,"duration_seconds":1.0,"transport_success":True,"retries":0,"cleanup_passed":True,"verifier_passed":True,"required_tools_verified":["file"],"nominal_cost_usd":0.1}
    row.update(changes)
    return row


def test_empty_acceptance_does_not_pass(tmp_path):
    result=load().check_acceptance(tmp_path,{"acceptance":{}})
    assert result["passed"] is False


def test_mutable_command_verifier_never_executes(tmp_path):
    case={"fixtures":{"checker.py":"raise SystemExit(1)\n"},"acceptance":{"command":["python","checker.py"],"command_exit":0}}
    (tmp_path/"checker.py").write_text("raise SystemExit(0)\n")
    module=load()
    with mock.patch.object(module.subprocess,"run",return_value=SimpleNamespace(returncode=0,stdout="",stderr="")) as run:
        result=module.check_acceptance(tmp_path,case)
    run.assert_not_called()
    assert result["passed"] is False
    assert "command" in result["unsupported_checks"]


@pytest.mark.parametrize("usage,route",[({},{}),({"input_tokens":100,"output_tokens":0,"cache_read_tokens":0,"cache_write_tokens":0},{}),({"input_tokens":100},{"pricing_usd_per_million":{"input":2}})])
def test_unknown_usage_or_price_is_null(usage,route):
    assert load().nominal_cost_usd(usage,route) is None


def test_summary_does_not_invent_tool_or_concurrency_proof():
    summary=load().summarize_route({"id":"synthetic"},[sample()],concurrency=4)
    metric=summary["task_classes"]["bounded"]
    assert metric["required_tools_verified"]==[]
    assert metric["capabilities_verified"]==[]
    assert metric["concurrency_verified"] is None
    assert summary["evidence_state"]=="descriptive-only"


def test_summary_keeps_unmeasured_cost_components_unknown():
    metric=load().summarize_route({"id":"synthetic"},[sample()],2)["task_classes"]["bounded"]
    assert metric["expected_total_cost_usd"] is None
    assert metric["cost_components"]["verification_usd"] is None
    assert metric["cost_components"]["recovery_usd"] is None
    assert metric["marginal_oauth_cost_usd"] is None


def test_child_environment_drops_personal_state_and_unrelated_secrets():
    env=load().isolated_env({"PATH":"synthetic-path","HOME":"personal-home","HERMES_HOME":"personal-state","TAVILY_API_KEY":"synthetic-secret","OPENAI_API_KEY":"synthetic-key","HERMES_YOLO_MODE":"1","CODEX_THREAD_ID":"synthetic-thread"})
    assert env=={"PATH":"synthetic-path"}


def test_usage_receipt_never_authorizes_global_session_deletion(tmp_path):
    module=load()
    with mock.patch.object(module.subprocess,"run",return_value=SimpleNamespace(returncode=0)) as run:
        assert module._delete_session("forged-session-id",{},tmp_path) is False
    run.assert_not_called()


def test_legacy_execution_rejected_before_launch_or_fixture_mutation(tmp_path):
    module=load();route={"id":"synthetic","model":"synthetic","provider":"openai-codex","reasoning_effort":"low"}
    case={"id":"case","task_class":"bounded","prompt":"synthetic","fixtures":{"changed.txt":"should not materialize"}}
    async def forbidden(*args,**kwargs):
        raise AssertionError("legacy launch reached")
    with mock.patch.object(module.asyncio,"create_subprocess_exec",side_effect=forbidden):
        with pytest.raises(RuntimeError,match="unsupported"):
            asyncio.run(module.run_one(route,case,0,tmp_path,asyncio.Semaphore(1),1,0))
    assert list(tmp_path.iterdir())==[]


@pytest.mark.parametrize("text",['{"a":1} trailing','{"a":1,"a":2}','{"a":NaN}','{"a":1e999}','```json\n{"a":1}\n```'])
def test_strict_json_rejects_ambiguous_or_nonfinite_output(text):
    with pytest.raises(ValueError):load().parse_object(text)


def test_boolean_does_not_satisfy_numeric_answer_key(tmp_path):
    (tmp_path/"answer.json").write_text('{"count":true}')
    assert load().check_acceptance(tmp_path,{"acceptance":{"json_file":"answer.json","expected":{"count":1}}})["passed"] is False


def test_known_included_billing_and_unknown_quota_stay_separate():
    result=load().cost_observation({"cost_status":"included","estimated_cost_usd":0},{})
    assert result["reported_billing_cost_usd"]==0
    assert result["marginal_oauth_cost_usd"]==0
    assert result["nominal_token_cost_usd"] is None
    assert result["quota_cost"] is None


def test_cost_observation_binding_is_task_verifier_and_exact_route_specific():
    module=load();route={"host":"codex","model":"synthetic","reasoning_effort":"low"}
    unbound=module.cost_observation({"cost_status":"included","estimated_cost_usd":0},{})
    assert unbound["task_contract_sha256"] is None and unbound["route_sha256"] is None
    bound=module.cost_observation({"cost_status":"included","estimated_cost_usd":0},{},task_contract_sha256="a"*64,verifier_sha256="b"*64,exact_route=route)
    assert bound["route_sha256"]==module.canonical_hash(route)
    assert bound["task_contract_sha256"]=="a"*64 and bound["verifier_sha256"]=="b"*64
    assert bound["quota_cost"] is None


def test_empty_summary_is_unknown_not_successful():
    result=load().summarize_route({"id":"empty"},[],2)
    assert result["transport"]["sample_size"]==0
    assert result["transport"]["attempt_success_rate"] is None
    assert result["transport"]["cleanup_passed"] is None


def test_no_tools_lane_cannot_supply_tool_observation():
    row=sample(runtime_lane="inline-text-no-tools-v1",tool_observations=[{"name":"terminal","status":"completed"}])
    metric=load().summarize_route({"id":"synthetic"},[row],1)["task_classes"]["bounded"]
    assert metric["observed_tool_names"]==[]
    assert metric["capabilities_verified"]==[]


def test_complete_explicit_costs_sum_without_inventing_zero_components():
    row=sample(attempt_nominal_cost_usd=.1,retry_nominal_cost_usd=.02,verification_cost_usd=.03,recovery_cost_usd=.04,marginal_oauth_cost_usd=0)
    row["cost_observations"]={key:{"amount_usd":row[key],"source":"synthetic-independent-measurement","evidence":{"locator":"fixture-cost.json","sha256":"a"*64}} for key in ["attempt_nominal_cost_usd","retry_nominal_cost_usd","verification_cost_usd","recovery_cost_usd","marginal_oauth_cost_usd"]}
    metric=load().summarize_route({"id":"synthetic"},[row],1)["task_classes"]["bounded"]
    assert metric["expected_total_cost_usd"]==pytest.approx(.19)
    assert metric["marginal_oauth_cost_usd"]==0


def test_historical_zero_cost_assertions_are_not_observations():
    row=sample(verification_cost_usd=0,recovery_cost_usd=0,marginal_oauth_cost_usd=0)
    metric=load().summarize_route({"id":"synthetic"},[row],1)["task_classes"]["bounded"]
    assert metric["cost_components"]["verification_usd"] is None
    assert metric["cost_components"]["recovery_usd"] is None
    assert metric["marginal_oauth_cost_usd"] is None
    assert metric["recorded_cost_claims"][0]["marginal_oauth_cost_usd"]==0


def test_historical_input_is_not_mutated():
    rows=[sample()];before=json.dumps(rows,sort_keys=True)
    load().summarize_route({"id":"synthetic","evidence_state":"verified-local"},rows,2)
    assert json.dumps(rows,sort_keys=True)==before
