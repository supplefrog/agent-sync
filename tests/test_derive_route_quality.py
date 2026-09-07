import importlib.util
import json
from pathlib import Path
import sys

import pytest


HERE=Path(__file__).resolve()
TOOLS=HERE.parents[1]/"tools"
spec=importlib.util.spec_from_file_location("derive_quality",TOOLS/"derive_route_quality.py")
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)


def arguments(path,verifier):
    return dict(report_path=path,route={"host":"hermes","model":"synthetic"},task_class="bounded",task_contract_sha256="a"*64,verifier_sha256="b"*64,scope="inline-text",required_tools=[],accepted_report_sha256=bridge.file_hash(path),verifier=verifier)


def test_self_reported_json_flags_are_not_accepted_outcomes(tmp_path):
    raw=tmp_path/"raw.json";raw.write_text('{"evidence_state":"verified-local","passed":true}')
    def self_report(path,route,binding):return json.loads(path.read_text())
    verifier=bridge.TrustedVerifier(self_report,"b"*64,{HERE:bridge.file_hash(HERE)})
    with pytest.raises(TypeError,match="JSON flags"):
        bridge.derive_quality_record(**arguments(raw,verifier))


def test_independent_check_can_reject_a_claimed_success(tmp_path):
    raw=tmp_path/"raw.json";raw.write_text('{"passed":true,"actual":9}')
    def independent(path,route,binding):
        status="pass" if json.loads(path.read_text())["actual"]==10 else "fail"
        return bridge.AcceptedOutcome(status,bridge.file_hash(path),**binding)
    verifier=bridge.TrustedVerifier(independent,"b"*64,{HERE:bridge.file_hash(HERE)})
    result=bridge.derive_outcome_observation(**arguments(raw,verifier),input_sha256="c"*64)
    assert result["outcome"]=="fail"
    assert result["quality_status"]=="unqualified"
    with pytest.raises(ValueError,match="accepted artifact"):
        bridge.derive_quality_record(**{**arguments(raw,verifier),"accepted_report_sha256":"c"*64})
    with pytest.raises(ValueError,match="required tool effects"):
        bridge.derive_quality_record(**{**arguments(raw,verifier),"required_tools":["terminal"]})


@pytest.mark.parametrize("outcome,expected",[("win","pass"),("tie","inconclusive"),("early-failure","fail")])
def test_actual_existing_evaluator_verifier_adapter(tmp_path,outcome,expected):
    stage=HERE.parents[1]
    if not (stage/"tools/verify_eval_report.py").is_file():
        stage=HERE.parents[4]/"agent-signal"  # separate audit checkout only
    sys.path.insert(0,str(stage/"tools"));sys.path.insert(0,str(stage/"tests"))
    from test_evaluation_evidence import make_evaluation
    from verify_eval_report import verify_report
    fixture=make_evaluation(tmp_path,outcome=outcome)
    report=fixture["report"]
    route={"host":report["agent"],"transport":"inline-text-no-tools-v1","provider":"openai-codex","model":"gpt-6-astra","reasoning_effort":"xhigh","runtime":{"agent_version":report["agent_version"]},"contract_sha256":"d"*64}
    kwargs={"suite_path":fixture["suite_path"],"candidate_path":fixture["candidate_path"],"baseline_path":fixture["baseline_path"],"agent":route["host"],"decision":report["decision"]["decision"],"model":route["model"],"provider":route["provider"],"reasoning":route["reasoning_effort"],"tool_policy":"none","equivalence_group":"fixture-group","min_trials":2,"max_trials":2,"max_agent_runs":fixture["max_agent_runs"]}
    contract={"scope":"inline-text","required_tools":[],"task_class":"bounded","protocol":"synthetic evaluator outcome protocol"}
    inputs={}
    for key in ["suite_path","candidate_path","baseline_path"]:
        inputs[key+"_sha256"]=bridge.file_hash(kwargs[key]) if kwargs[key] is not None else None
    path=tmp_path/"task-contract.json";path.write_text(json.dumps(contract),encoding="utf-8")
    input_path=tmp_path/"input.json";input_path.write_text(json.dumps(inputs),encoding="utf-8")
    execution={"route_sha256":bridge.digest(route),"task_contract_sha256":bridge.file_hash(path),"input_sha256":bridge.file_hash(input_path),"runtime_versions":{key:report[key] for key in ["agent_version","judge_version"]},"verification_arguments_sha256":bridge.digest({k:str(v) if isinstance(v,Path) else v for k,v in kwargs.items()})}
    execution_path=tmp_path/"execution.json";execution_path.write_text(json.dumps(execution),encoding="utf-8")
    names=["verify_eval_report.py","evaluation_evidence.py","eval.py","artifact_hash.py","evaluation_runtime.py","evaluation_hermes_worker.py","fleet.py"]
    bindings={stage/"tools"/name:bridge.file_hash(stage/"tools"/name) for name in names}
    verifier=bridge.inline_evaluator_verifier(verify_report=verify_report,verification_arguments=kwargs,task_contract_path=path,task_contract_sha256=bridge.file_hash(path),input_path=input_path,input_sha256=bridge.file_hash(input_path),execution_manifest_path=execution_path,execution_manifest_sha256=bridge.file_hash(execution_path),identity_sha256="b"*64,source_bindings=bindings)
    result=bridge.derive_outcome_observation(**{**arguments(fixture["report_path"],verifier),"route":route,"task_contract_sha256":bridge.file_hash(path)},input_sha256=bridge.file_hash(input_path))
    assert result["outcome"]==expected
    assert result["quality_status"]=="unqualified"


def test_individual_accepted_pass_does_not_become_protocol_qualification(tmp_path):
    raw=tmp_path/"one.json";raw.write_text('{"actual":10}')
    def individual(path,route,binding):
        return bridge.AcceptedOutcome("pass",bridge.file_hash(path),**binding,input_sha256="c"*64)
    verifier=bridge.TrustedVerifier(individual,"b"*64,{HERE:bridge.file_hash(HERE)})
    with pytest.raises(TypeError,match="individual execution outcomes"):
        bridge.derive_quality_record(**arguments(raw,verifier))


def test_separate_exhaustive_finite_domain_policy_can_issue_qualification(tmp_path):
    raw=tmp_path/"population.json";raw.write_text('{"inputs":[0,1,2],"outputs":[0,2,4]}')
    def qualification(path,route,binding):
        data=json.loads(path.read_text())
        # Complete finite synthetic domain, not statistical generalization from a pass.
        complete=data["inputs"]==[0,1,2] and data["outputs"]==[2*x for x in data["inputs"]]
        return bridge.QualificationDecision("qualified" if complete else "inconclusive",bridge.file_hash(path),**binding,population_sha256=bridge.digest(data),qualification_policy_sha256=bridge.file_hash(HERE))
    verifier=bridge.TrustedVerifier(qualification,"b"*64,{HERE:bridge.file_hash(HERE)})
    result=bridge.derive_quality_record(**arguments(raw,verifier))
    assert result["status"]=="qualified"
    assert "input_sha256" not in result
