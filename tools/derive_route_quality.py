"""Trusted-controller bridge; raw reports cannot issue their own qualification.

The controller registers an independently reviewed verifier callable and pins its
code/dependencies before dispatch. Neither callable nor pins come from worker
JSON. The only concrete adapter here supports existing inline evaluator reports.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Callable, NamedTuple


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AcceptedOutcome(NamedTuple):
    status: str
    report_sha256: str
    route_sha256: str
    task_contract_sha256: str
    verifier_sha256: str
    scope: str
    task_class: str
    input_sha256: str
    tools_verified: tuple[str, ...] = ()


class QualificationDecision(NamedTuple):
    """A separate qualification policy over an accepted evidence population."""
    status: str
    report_sha256: str
    route_sha256: str
    task_contract_sha256: str
    verifier_sha256: str
    scope: str
    task_class: str
    population_sha256: str
    qualification_policy_sha256: str
    tools_verified: tuple[str, ...] = ()


class TrustedVerifier:
    """In-process authority supplied by the controller, never deserialized."""
    def __init__(self, verify: Callable, identity_sha256: str, source_bindings: dict[Path, str]):
        self.verify = verify
        self.identity_sha256 = identity_sha256
        self.source_bindings = {Path(path).resolve(): sha for path, sha in source_bindings.items()}
        callback_source = inspect.getsourcefile(verify)
        if callback_source is None or Path(callback_source).resolve() not in self.source_bindings:
            raise ValueError("trusted verifier callable source is not pinned")
        self.check_sources()

    def check_sources(self):
        if not self.source_bindings or any(file_hash(path) != sha for path, sha in self.source_bindings.items()):
            raise ValueError("independent verifier source changed")


def _derive(report_path: Path, *, route: dict, task_class: str,
                          task_contract_sha256: str, verifier_sha256: str,
                          scope: str, required_tools: list[str], accepted_report_sha256: str,
                          verifier: TrustedVerifier, input_sha256: str | None = None) -> dict:
    if not isinstance(verifier, TrustedVerifier):
        raise TypeError("a controller-registered independent verifier is required")
    if scope not in {"inline-text", "independent-review", "artifact-effects"}:
        raise ValueError("unknown evidence scope")
    if required_tools and scope != "artifact-effects":
        raise ValueError("inline/review evidence cannot qualify required tool effects")
    if verifier.identity_sha256 != verifier_sha256:
        raise ValueError("verifier identity does not match the frozen task")
    verifier.check_sources()
    report_path = report_path.resolve()
    before = file_hash(report_path)
    if before != accepted_report_sha256:
        raise ValueError("raw evidence differs from the controller's independently accepted artifact")
    binding = {"task_class": task_class, "route_sha256": digest(route), "task_contract_sha256": task_contract_sha256,
               "verifier_sha256": verifier_sha256, "scope": scope}
    if input_sha256 is not None:
        binding["input_sha256"] = input_sha256
    accepted = verifier.verify(report_path, route, binding)
    verifier.check_sources()
    if file_hash(report_path) != before:
        raise ValueError("raw report changed while independently verified")
    expected_type = AcceptedOutcome if input_sha256 is not None else QualificationDecision
    if not isinstance(accepted, expected_type):
        raise TypeError("JSON flags or individual execution outcomes are not independent protocol qualification decisions")
    if accepted.report_sha256 != before or any(getattr(accepted, key) != value for key, value in binding.items()):
        raise ValueError("accepted outcome does not bind the exact report/route/task/verifier/scope")
    allowed = {"pass", "fail", "inconclusive"} if input_sha256 is not None else {"qualified", "regression", "inconclusive"}
    if accepted.status not in allowed:
        raise ValueError("invalid independently accepted status")
    if accepted.status in {"qualified", "pass"} and set(required_tools) - set(accepted.tools_verified):
        raise ValueError("independent verifier did not establish required tool effects")
    if input_sha256 is not None:
        return {"artifact_type": "accepted-route-outcome-observation-v1", **binding,
                "outcome": accepted.status, "quality_status": "unqualified",
                "evidence": {"locator": report_path.as_uri(), "sha256": before}}
    for value in (accepted.population_sha256, accepted.qualification_policy_sha256):
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("protocol qualification requires a pinned population and qualification policy")
    return {"task_class": task_class, **binding, "status": accepted.status,
            "evidence": {"locator": report_path.as_uri(), "sha256": before}}


def derive_quality_record(report_path: Path, **kwargs) -> dict:
    """Only a distinct controller-reviewed qualification decision enters V3 quality."""
    if "input_sha256" in kwargs:
        raise ValueError("quality keys bind the stable protocol, not one input")
    return _derive(report_path, **kwargs)


def derive_outcome_observation(report_path: Path, *, input_sha256: str, **kwargs) -> dict:
    return _derive(report_path, input_sha256=input_sha256, **kwargs)


def inline_evaluator_verifier(*, verify_report: Callable, verification_arguments: dict,
                              task_contract_path: Path, task_contract_sha256: str,
                              input_path: Path, input_sha256: str,
                              execution_manifest_path: Path, execution_manifest_sha256: str,
                              identity_sha256: str, source_bindings: dict[Path, str]) -> TrustedVerifier:
    """Adapt the existing independent verify_eval_report.verify_report owner.

    The stable protocol is separate from concrete input bytes and execution
    metadata. A verified pass is one outcome observation, never general task-cell
    qualification. Effects/tool qualification is unsupported by this adapter.
    """
    contract_path = task_contract_path.resolve()
    if file_hash(contract_path) != task_contract_sha256:
        raise ValueError("task contract hash mismatch")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if file_hash(input_path) != input_sha256 or file_hash(execution_manifest_path) != execution_manifest_sha256:
        raise ValueError("input or execution manifest hash mismatch")
    inputs = json.loads(input_path.read_text(encoding="utf-8"))
    execution = json.loads(execution_manifest_path.read_text(encoding="utf-8"))
    pinned = {Path(path).resolve(): sha for path, sha in source_bindings.items()}
    owner_path = inspect.getsourcefile(verify_report)
    if owner_path is None or Path(owner_path).resolve() not in pinned:
        raise ValueError("existing evaluator verifier source is not pinned")
    if contract.get("scope") != "inline-text" or contract.get("required_tools") != []:
        raise ValueError("this adapter supports inline text only, without tool-effect claims")
    # Every imported evaluator owner must be pinned, not only its thin wrapper.
    required_names = {"verify_eval_report.py", "evaluation_evidence.py", "eval.py", "artifact_hash.py",
                      "evaluation_runtime.py", "evaluation_hermes_worker.py", "fleet.py"}
    if not required_names <= {path.name for path in pinned}:
        raise ValueError("incomplete evaluator dependency pins")

    def accept(report_path, route, binding):
        if file_hash(contract_path) != task_contract_sha256:
            raise ValueError("task contract changed")
        if file_hash(input_path) != input_sha256 or file_hash(execution_manifest_path) != execution_manifest_sha256:
            raise ValueError("input or execution manifest changed")
        if (binding["scope"] != "inline-text" or binding["task_contract_sha256"] != task_contract_sha256
                or binding["task_class"] != contract.get("task_class") or binding.get("input_sha256") != input_sha256):
            raise ValueError("inline evaluator task binding mismatch")
        if (digest(route) != execution.get("route_sha256") or execution.get("input_sha256") != input_sha256
                or execution.get("task_contract_sha256") != task_contract_sha256):
            raise ValueError("route does not match accepted task contract")
        for key in ("suite_path", "candidate_path", "baseline_path"):
            path = verification_arguments.get(key)
            expected = inputs.get(key + "_sha256")
            if (file_hash(Path(path)) if path is not None else None) != expected:
                raise ValueError("frozen task artifact changed: " + key)
        args = dict(verification_arguments)
        expected_route = {"agent": route["host"], "model": route["model"], "provider": route["provider"],
                          "reasoning": route["reasoning_effort"], "tool_policy": "none"}
        if any(args.get(key) != value for key, value in expected_route.items()):
            raise ValueError("verifier arguments do not bind the selected native route")
        comparable_args = {key: str(value) if isinstance(value, Path) else value for key, value in args.items()}
        if digest(comparable_args) != execution.get("verification_arguments_sha256"):
            raise ValueError("verifier policy arguments changed")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        observed_versions = {key: report.get(key) for key in ("agent_version", "judge_version")}
        if observed_versions != execution.get("runtime_versions") or any(not value for value in observed_versions.values()):
            raise ValueError("native runtime observations do not match the frozen contract")
        result = verify_report(report_path, **args)
        status = "inconclusive"
        native_scope = result.get("scope", {})
        exact_scope = native_scope.get("runtime_lane") == "inline-text-no-tools-v1" and native_scope.get("full_suite") is True
        valid = result.get("integrity_valid") is True and result.get("evidence_complete") is True and result.get("operational_ok") is True and exact_scope
        if valid and result.get("positive_decision_sufficient") is True:
            status = "pass"
        elif valid and result.get("decision") == "reject":
            status = "fail"
        return AcceptedOutcome(status, file_hash(report_path), **binding)

    return TrustedVerifier(accept, identity_sha256, {**pinned, Path(__file__).resolve(): file_hash(Path(__file__))})
