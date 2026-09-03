#!/usr/bin/env python
"""Blind baseline-versus-skill evaluation on fresh Hermes or Codex sessions."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    from artifact_hash import candidate_hash, candidate_prompt_text
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from artifact_hash import candidate_hash, candidate_prompt_text


def command_version(name: str) -> str:
    exe = shutil.which(name)
    if not exe:
        return "not-found"
    result = subprocess.run([exe, "--version"], text=True, capture_output=True, check=False)
    return (result.stdout or result.stderr).strip()


def clean_output(text: str) -> str:
    """Remove leading Hermes terminal-only reasoning decoration from quiet output."""
    lines = text.strip().splitlines()
    while lines and (not lines[0].strip() or "\x1b" in lines[0]):
        lines.pop(0)
    return "\n".join(lines).strip()


# CLI sessions currently use six hex characters; older/gateway-issued IDs may
# use eight. Accept only those runtime formats, not arbitrary list output.
SESSION_ID_RE = re.compile(r"\b\d{8}_\d{6}_[0-9a-f]{6}(?:[0-9a-f]{2})?\b", re.IGNORECASE)
CASE_KINDS = {"representative", "near-miss", "adversarial", "held-out"}
CHILD_ENV_EXACT = {
    "HERMES_SESSION_ID",
    "HERMES_PARENT_SESSION_ID",
    "HERMES_SESSION_KEY",
    "HERMES_SESSION_SOURCE",
    "HERMES_GATEWAY_SESSION",
    "HERMES_DELEGATED_CHILD_CONTEXT",
}
CHILD_ENV_PREFIXES = ("HERMES_KANBAN_", "HERMES_DELEGATION_", "DELEGATION_")
TRANSIENT_PROVIDER_ERROR_RE = re.compile(
    r"(?:\b(?:429|502|503|504)\b|rate[_ -]?limit(?:ed|_exceeded)?|overload(?:ed)?|"
    r"temporar(?:ily|y) unavailable|service unavailable|server_error|upstream connect error|"
    r"non-streaming api call timed out after \d+(?:\.\d+)?s with no response)",
    re.IGNORECASE,
)


def parse_session_ids(text: str) -> set[str]:
    return set(SESSION_ID_RE.findall(text))


def isolated_child_env(source: dict[str, str] | None = None) -> dict[str, str]:
    """Remove inherited worker/delegation identity from evaluator children."""
    env = dict(source if source is not None else os.environ)
    for key in list(env):
        if key in CHILD_ENV_EXACT or key.startswith(CHILD_ENV_PREFIXES):
            env.pop(key, None)
    return env


class HermesSessionLifecycle:
    """Track only sessions created by this evaluator and retire them via the CLI."""

    def __init__(self, hermes_exe: str, retain: bool, protected: set[str] | None = None) -> None:
        self.hermes_exe = hermes_exe
        self.retain = retain
        self.protected = set(protected or ())
        self.created: set[str] = set()
        self.receipt_errors: list[str] = []

    def list(self, workspace: Path | None = None) -> set[str]:
        command = [self.hermes_exe, "sessions", "list", "--source", "agent-signal-eval", "--limit", "10000"]
        if workspace is not None:
            command += ["--workspace", str(workspace)]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            self.receipt_errors.append("session readback failed: " + (result.stderr or result.stdout).strip())
            return set()
        return parse_session_ids(result.stdout)

    def register_receipt(self, stderr: str) -> tuple[list[str], str | None]:
        """Register the runtime-issued ID emitted by this exact child process."""
        session_ids = sorted(parse_session_ids(stderr))
        if len(session_ids) != 1:
            error = f"expected one direct child session receipt, found {len(session_ids)}"
            self.receipt_errors.append(error)
            return [], error
        self.created.add(session_ids[0])
        return session_ids, None

    def cleanup(self) -> dict[str, Any]:
        protected = sorted(self.created & self.protected)
        targets = sorted(self.created - self.protected)
        if self.retain:
            return {
                "policy": "retain-evidence",
                "created": sorted(self.created),
                "protected": protected,
                "deleted": [],
                "remaining": targets,
                "errors": self.receipt_errors,
            }
        deleted: list[str] = []
        delete_errors: list[str] = []
        for session_id in targets:
            result = subprocess.run(
                [self.hermes_exe, "sessions", "delete", session_id, "--yes"],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode == 0:
                deleted.append(session_id)
            else:
                delete_errors.append(f"{session_id}: {(result.stderr or result.stdout).strip()}")
        remaining = sorted(set(targets) & self.list())
        errors = [*self.receipt_errors, *delete_errors]
        return {
            "policy": "delete-after-durable-report",
            "created": sorted(self.created),
            "protected": protected,
            "deleted": deleted,
            "remaining": remaining,
            "errors": errors,
        }


class DecisionRule:
    def __init__(self, alpha: float = 0.05, margin: float = 0.1, min_trials: int = 2, max_trials: int = 8) -> None:
        self.alpha = alpha
        self.margin = margin
        self.min_trials = min_trials
        self.max_trials = max_trials

    def as_dict(self) -> dict[str, Any]:
        return {
            "alpha": self.alpha,
            "margin": self.margin,
            "min_trials": self.min_trials,
            "max_trials": self.max_trials,
        }


def decision_scores(results: list[dict[str, Any]]) -> list[float]:
    """Return comparative scores only when at least one answer hard-passes."""
    return [
        float(item["score"])
        for item in results
        if bool(item.get("hard_pass", {}).get("baseline"))
        or bool(item.get("hard_pass", {}).get("candidate"))
    ]


def sequential_decision(mode: str, scores: list[float], rule: DecisionRule, looks: int | None = None) -> dict[str, Any]:
    """Anytime-valid Hoeffding confidence sequence with alpha spending.

    Each matched case/trial observation contributes a score in [-1, 1]. The
    alpha budget is spent by trial look, while the finite-suite mean uses every
    paired observation; case and repeated-generation variance remain explicit.
    """
    n = len(scores)
    look = looks if looks is not None else n
    mean = sum(scores) / n if n else 0.0
    alpha_n = rule.alpha / max(1, look * (look + 1))
    radius = min(2.0, math.sqrt(2.0 * math.log(2.0 / alpha_n) / max(1, n)))
    lower = max(-1.0, mean - radius)
    upper = min(1.0, mean + radius)
    decision = "continue"
    if look >= rule.min_trials:
        if mode == "admission" and lower > rule.margin:
            decision = "admit"
        elif mode == "admission" and upper <= rule.margin:
            decision = "reject"
        elif mode == "retirement" and lower >= -rule.margin:
            decision = "retire"
        elif mode == "retirement" and upper < -rule.margin:
            decision = "retain"
    if decision == "continue" and look >= rule.max_trials:
        decision = "inconclusive"
    return {
        "decision": decision,
        "mean": mean,
        "trials": look,
        "observations": n,
        "confidence_sequence": {
            "method": "hoeffding-alpha-spending",
            "alpha": rule.alpha,
            "look_alpha": alpha_n,
            "radius": radius,
            "lower": lower,
            "upper": upper,
        },
    }


def validate_suite(suite: dict[str, Any]) -> None:
    cases = suite.get("cases", [])
    if len(cases) < 3:
        raise ValueError("suite must contain at least three cases")
    ids = [case.get("id") for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("suite case ids must be unique")
    schema_version = int(suite.get("schema_version", 1))
    if schema_version >= 2:
        present = {case.get("kind") for case in cases}
        missing = sorted(CASE_KINDS - present)
        if missing:
            raise ValueError("suite missing required case kinds: " + ", ".join(missing))
    if schema_version < 3:
        return

    receipt_schema = suite.get("receipt_schema")
    if not isinstance(receipt_schema, dict) or receipt_schema.get("type") != "object":
        raise ValueError("schema v3 requires an object receipt_schema")
    stability = suite.get("stability")
    if not isinstance(stability, dict):
        raise ValueError("schema v3 requires a stability contract")
    trials = stability.get("trials")
    if not isinstance(trials, int) or isinstance(trials, bool) or trials < 1:
        raise ValueError("schema v3 stability.trials must be a positive integer")
    required_win_kinds = stability.get("required_win_kinds", [])
    if not isinstance(required_win_kinds, list) or any(kind not in CASE_KINDS for kind in required_win_kinds):
        raise ValueError("schema v3 stability.required_win_kinds contains an invalid case kind")

    for case in cases:
        expected = case.get("expected_receipt")
        if not isinstance(expected, dict) or not expected:
            raise ValueError(f"schema v3 case {case.get('id')} requires expected_receipt")
        for path, value in expected.items():
            node = _schema_for_path(receipt_schema, str(path))
            if node is None:
                raise ValueError(f"schema v3 case {case.get('id')} expected_receipt path not in receipt_schema: {path}")
            if "enum" in node and value not in node["enum"]:
                raise ValueError(f"schema v3 case {case.get('id')} expected_receipt value is outside enum: {path}")
        semantic = case.get("semantic_criteria", [])
        if not isinstance(semantic, list) or not semantic:
            raise ValueError(f"schema v3 case {case.get('id')} requires semantic_criteria")
        criterion_ids = [item.get("id") for item in semantic if isinstance(item, dict)]
        if len(criterion_ids) != len(semantic) or any(not item for item in criterion_ids):
            raise ValueError(f"schema v3 case {case.get('id')} has invalid semantic criterion")
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError(f"schema v3 case {case.get('id')} has duplicate semantic criterion ids")
        if any(not str(item.get("text", "")).strip() for item in semantic):
            raise ValueError(f"schema v3 case {case.get('id')} has empty semantic criterion text")


def durable_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def finalize_report(path: Path, report: dict[str, Any], lifecycle: HermesSessionLifecycle) -> None:
    # Unique evidence exists in the report before any supported session delete.
    durable_json_write(path, report)
    report["session_lifecycle"] = lifecycle.cleanup()
    durable_json_write(path, report)


def codex_route_attestation(stderr: str, model: str | None, provider: str | None, reasoning: str | None) -> dict[str, Any]:
    def observed(label: str) -> str | None:
        match = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.*?)\s*$", stderr)
        return match.group(1).strip() if match else None

    actual = {
        "model": observed("model"),
        "provider": observed("provider"),
        "reasoning": observed("reasoning effort"),
    }
    errors: list[str] = []
    if not actual["model"]:
        errors.append("model observation missing")
    elif model and actual["model"] != model:
        errors.append(f"model mismatch: requested {model}, observed {actual['model']}")
    if not actual["provider"]:
        errors.append("provider observation missing")
    elif provider and actual["provider"] not in {provider, "openai" if provider == "openai-codex" else provider}:
        errors.append(f"provider mismatch: requested {provider}, observed {actual['provider']}")
    if not actual["reasoning"]:
        errors.append("reasoning observation missing")
    elif reasoning and actual["reasoning"] != reasoning:
        errors.append(f"reasoning mismatch: requested {reasoning}, observed {actual['reasoning']}")
    return {
        "requested": {"model": model, "provider": provider, "reasoning": reasoning},
        "observed": actual,
        "ok": not errors,
        "errors": errors,
    }


def _structured_tool_call_count(row: dict[str, Any]) -> int | None:
    explicit = row.get("tool_calls_count")
    if isinstance(explicit, int) and explicit >= 0:
        return explicit
    messages = row.get("messages")
    if not isinstance(messages, list):
        return None
    assistant_calls = 0
    tool_results = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        calls = message.get("tool_calls")
        if isinstance(calls, list):
            assistant_calls += len(calls)
        if message.get("role") in {"tool", "tool_result"}:
            tool_results += 1
    return max(assistant_calls, tool_results)


def hermes_route_attestation(
    executable: str,
    session_ids: list[str],
    model: str | None,
    provider: str | None,
    reasoning: str | None,
    tool_policy: str | None,
    *,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Attest a Hermes route from one redacted native session export."""

    requested = {"model": model, "provider": provider, "reasoning": reasoning, "tool_policy": tool_policy}
    if len(session_ids) != 1:
        return {
            "requested": requested,
            "observed": {},
            "ok": False,
            "errors": [f"Hermes route attestation requires exactly one session, observed {len(session_ids)}"],
        }
    session_id = session_ids[0]
    command = [
        executable,
        "sessions",
        "export",
        "-",
        "--format",
        "jsonl",
        "--session-id",
        session_id,
        "--redact",
        "--yes",
    ]
    try:
        exported = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "requested": requested,
            "observed": {},
            "ok": False,
            "errors": [f"Hermes route export failed: {type(exc).__name__}"],
        }
    if exported.returncode != 0:
        return {
            "requested": requested,
            "observed": {},
            "ok": False,
            "errors": [f"Hermes route export exited {exported.returncode}"],
        }
    lines = [line for line in exported.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        return {
            "requested": requested,
            "observed": {},
            "ok": False,
            "errors": [f"Hermes route export returned {len(lines)} records instead of one"],
        }
    try:
        row = json.loads(lines[0])
        raw_config = row.get("model_config") or {}
        model_config = json.loads(raw_config) if isinstance(raw_config, str) else raw_config
        reasoning_config = model_config.get("reasoning_config", {}) if isinstance(model_config, dict) else {}
        actual = {
            "model": row.get("model"),
            "provider": row.get("billing_provider"),
            "reasoning": reasoning_config.get("effort") if isinstance(reasoning_config, dict) else None,
            "tool_calls_count": _structured_tool_call_count(row),
        }
    except (AttributeError, json.JSONDecodeError, TypeError):
        return {
            "requested": requested,
            "observed": {},
            "ok": False,
            "errors": ["Hermes route export was not a valid session record"],
        }
    errors: list[str] = []
    if row.get("id") != session_id:
        errors.append("session id mismatch in Hermes route export")
    for key in ("model", "provider", "reasoning"):
        expected = requested[key]
        observed = actual.get(key)
        if not observed:
            errors.append(f"{key} observation missing")
        elif expected and observed != expected:
            errors.append(f"{key} mismatch: requested {expected}, observed {observed}")
    if tool_policy == "none" and actual.get("tool_calls_count") != 0:
        errors.append(
            f"tool calls mismatch: requested none, observed {actual.get('tool_calls_count')} calls"
        )
    return {"requested": requested, "observed": actual, "ok": not errors, "errors": errors}


def v3_route_supported(agent: str, judge_agent: str) -> bool:
    """V3 supports attested Codex/Hermes generators and Codex judges."""

    return agent in {"codex", "hermes"} and judge_agent == "codex"


def run_agent(
    agent: str,
    prompt: str,
    workdir: Path,
    timeout: int,
    full_tools: bool,
    model: str | None = None,
    provider: str | None = None,
    reasoning: str | None = None,
    tool_policy: str = "safe",
    lifecycle: HermesSessionLifecycle | None = None,
    output_schema: dict[str, Any] | None = None,
    require_attestation: bool = False,
) -> dict[str, Any]:
    exe = shutil.which(agent)
    if not exe:
        raise RuntimeError(f"{agent} executable not found")
    workdir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    output_file = workdir / f"last-{time.time_ns()}.txt"
    input_text = None
    run_env = isolated_child_env()
    schema_file: Path | None = None
    if output_schema is not None:
        schema_file = workdir / "output-schema.json"
        schema_file.write_text(json.dumps(output_schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if agent == "hermes":
        if output_schema is not None:
            prompt += "\n\nReturn only one JSON object matching this schema:\n" + json.dumps(output_schema, ensure_ascii=False)
        command = [exe, "chat", "-Q", "--source", "agent-signal-eval", "--in", str(workdir), "--ignore-rules"]
        if model:
            command += ["-m", model]
        if provider:
            command += ["--provider", provider]
        if reasoning:
            command += ["--reasoning", reasoning]
        if tool_policy == "none":
            # Empty/falsey toolsets trigger Hermes' configured coding-tool fallback.
            # A truthy unknown sentinel produces an explicit empty selection.
            command += ["--toolsets", "none"]
        elif not full_tools or tool_policy == "safe":
            command.append("--safe-mode")
        command += ["-q", prompt]
    elif agent == "codex":
        source_codex_home = Path(run_env.get("CODEX_HOME") or Path.home() / ".codex")
        isolated_codex_home = workdir / ".codex"
        isolated_codex_home.mkdir(parents=True, exist_ok=True)
        source_auth = source_codex_home / "auth.json"
        if source_auth.is_file():
            shutil.copy2(source_auth, isolated_codex_home / "auth.json")
        # Codex discovers user skills below HOME. Isolate HOME so a candidate
        # already present in ~/.agents/skills or CODEX_HOME cannot contaminate
        # the baseline. Copy only auth into the disposable home.
        run_env["HOME"] = str(workdir)
        run_env["USERPROFILE"] = str(workdir)
        run_env["CODEX_HOME"] = str(isolated_codex_home)
        command = [exe, "exec"]
        if model:
            command += ["-m", model]
        if reasoning:
            command += ["-c", f'model_reasoning_effort="{reasoning}"']
        if schema_file is not None:
            command += ["--output-schema", str(schema_file)]
        command += [
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "--sandbox",
            "read-only",
            "-C",
            str(workdir),
            "-o",
            str(output_file),
            "-",
        ]
        input_text = prompt
    else:
        raise RuntimeError("agent must be hermes or codex")
    session_ids: list[str] = []
    session_receipt_error: str | None = None
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=run_env,
    )
    try:
        stdout, stderr = process.communicate(input=input_text, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        stdout, stderr = process.communicate()
        elapsed = round(time.monotonic() - started, 3)
        if agent == "hermes" and lifecycle:
            session_ids, session_receipt_error = lifecycle.register_receipt(stderr or "")
        return {
            "ok": False,
            "returncode": None,
            "seconds": elapsed,
            "output": clean_output(stdout or exc.stdout or ""),
            "stderr": f"timed out after {timeout}s",
            "session_ids": session_ids,
            "session_receipt_error": session_receipt_error,
            "route_attestation": {"required": require_attestation, "ok": False, "errors": ["run timed out"]},
        }
    except BaseException:
        process.kill()
        _stdout, stderr = process.communicate()
        if agent == "hermes" and lifecycle:
            lifecycle.register_receipt(stderr or "")
        raise
    elapsed = round(time.monotonic() - started, 3)
    if agent == "hermes" and lifecycle:
        session_ids, session_receipt_error = lifecycle.register_receipt(stderr or "")
    text = output_file.read_text(encoding="utf-8") if output_file.exists() else stdout
    text = clean_output(text)
    if require_attestation and agent == "codex":
        route_attestation = {"required": True, **codex_route_attestation(stderr or "", model, provider, reasoning)}
    elif require_attestation and agent == "hermes":
        route_attestation = {
            "required": True,
            **hermes_route_attestation(exe, session_ids, model, provider, reasoning, tool_policy, env=run_env),
        }
    elif require_attestation:
        route_attestation = {
            "required": True,
            "requested": {"model": model, "provider": provider, "reasoning": reasoning},
            "observed": {},
            "ok": False,
            "errors": [f"observed route attestation unsupported for {agent}"],
        }
    else:
        route_attestation = {
            "required": False,
            "requested": {"model": model, "provider": provider, "reasoning": reasoning},
            "observed": {},
            "ok": True,
            "errors": [],
        }
    return {
        "ok": process.returncode == 0 and session_receipt_error is None and route_attestation["ok"],
        "returncode": process.returncode,
        "seconds": elapsed,
        "output": text,
        "stderr": stderr[-4000:],
        "session_ids": session_ids,
        "session_receipt_error": session_receipt_error,
        "route_attestation": route_attestation,
    }


class AgentRunBudget:
    """Physical subprocess-attempt budget shared by normal runs and retries."""

    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("agent run budget must be positive")
        self.limit = limit
        self.used = 0

    @property
    def remaining(self) -> int:
        return self.limit - self.used

    def claim(self) -> bool:
        if self.remaining <= 0:
            return False
        self.used += 1
        return True


def transient_provider_failure(result: dict[str, Any]) -> bool:
    """Return true only for explicit retryable provider/transport failures."""

    if result.get("ok") or result.get("returncode") in {None, 0}:
        return False
    text = f"{result.get('stderr', '')}\n{result.get('output', '')}"
    return bool(TRANSIENT_PROVIDER_ERROR_RE.search(text))


def run_agent_with_retry(
    budget: AgentRunBudget,
    *args: Any,
    transient_retries: int = 2,
    retry_delay: float = 2.0,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run once, retrying only explicit transient provider failures."""

    if transient_retries < 0:
        raise ValueError("transient retries must be non-negative")
    if retry_delay < 0:
        raise ValueError("retry delay must be non-negative")
    attempts: list[dict[str, Any]] = []
    retries_used = 0
    result: dict[str, Any] | None = None
    budget_exhausted = False
    while True:
        if not budget.claim():
            budget_exhausted = True
            if result is None:
                result = {
                    "ok": False,
                    "returncode": None,
                    "seconds": 0.0,
                    "output": "",
                    "stderr": "physical agent run budget exhausted",
                    "session_ids": [],
                    "session_receipt_error": None,
                    "route_attestation": {"required": False, "ok": False, "errors": ["run budget exhausted"]},
                }
            break
        result = run_agent(*args, **kwargs)
        transient = transient_provider_failure(result)
        attempts.append(
            {
                "attempt": len(attempts) + 1,
                "ok": bool(result.get("ok")),
                "returncode": result.get("returncode"),
                "seconds": result.get("seconds"),
                "transient_provider_failure": transient,
                "stderr": str(result.get("stderr", ""))[-1000:],
            }
        )
        if not transient or retries_used >= transient_retries:
            break
        if budget.remaining <= 0:
            budget_exhausted = True
            break
        delay = retry_delay * (2 ** retries_used)
        if delay:
            time.sleep(delay)
        retries_used += 1
    assert result is not None
    return {
        **result,
        "attempt_count": len(attempts),
        "transient_retry_count": retries_used,
        "run_budget_exhausted": budget_exhausted,
        "attempts": attempts,
    }


def extract_json(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
    raise ValueError("judge did not return a JSON object")


def _schema_for_path(schema: dict[str, Any], path: str) -> dict[str, Any] | None:
    node: dict[str, Any] = schema
    for part in path.split("."):
        properties = node.get("properties")
        if not isinstance(properties, dict) or part not in properties or not isinstance(properties[part], dict):
            return None
        node = properties[part]
    return node


def _value_at_path(value: dict[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _json_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _schema_reasons(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    reasons: list[str] = []
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _json_type_matches(value, expected_type):
        return [f"{path}: expected {expected_type}"]
    if "enum" in schema and value not in schema["enum"]:
        reasons.append(f"{path}: value {value!r} is outside enum")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                reasons.append(f"{path}.{key}: missing required field")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    reasons.append(f"{path}.{key}: unexpected field")
        for key, item in value.items():
            child_schema = properties.get(key) if isinstance(properties, dict) else None
            if isinstance(child_schema, dict):
                reasons.extend(_schema_reasons(item, child_schema, f"{path}.{key}"))
    elif isinstance(value, list):
        if isinstance(schema.get("minItems"), int) and len(value) < schema["minItems"]:
            reasons.append(f"{path}: fewer than {schema['minItems']} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                reasons.extend(_schema_reasons(item, item_schema, f"{path}[{index}]"))
    return reasons


def structured_receipt_check(case: dict[str, Any], output: str, receipt_schema: dict[str, Any]) -> dict[str, Any]:
    try:
        receipt = extract_json(output)
    except ValueError as exc:
        return {"pass": False, "receipt": None, "reasons": [f"invalid receipt: {exc}"]}
    reasons = _schema_reasons(receipt, receipt_schema)
    for path, expected in case.get("expected_receipt", {}).items():
        found, observed = _value_at_path(receipt, str(path))
        if not found:
            reasons.append(f"{path}: expected value is missing")
        elif observed != expected:
            reasons.append(f"{path}: expected {expected!r}, observed {observed!r}")
    return {"pass": not reasons, "receipt": receipt, "reasons": reasons}


def deterministic(case: dict[str, Any], output: str) -> tuple[bool, list[str]]:
    lowered = output.lower()
    reasons: list[str] = []
    for needle in case.get("must_contain", []):
        if needle.lower() not in lowered:
            reasons.append(f"missing: {needle}")
    for needle in case.get("must_not_contain", []):
        if needle.lower() in lowered:
            reasons.append(f"forbidden: {needle}")
    return not reasons, reasons


def judge_prompt(suite: dict[str, Any], case: dict[str, Any], a: str, b: str) -> str:
    case_criteria = "\n".join(f"- {item}" for item in case.get("criteria", []))
    return f"""Judge two anonymous answers to the same task. Judge task success, not style preference. A concise answer can beat a longer one. Mark hard_pass false for any critical factual, safety, scope, or instruction failure. Apply only the requirements below; do not require unrelated parts of the broader capability claim.

Required criteria for this case:
{case_criteria or '- Correctly completes the task'}

Task:
{case['prompt']}

ANSWER A
{a}

ANSWER B
{b}

Return only JSON with this exact shape:
{{"a":{{"hard_pass":true,"reason":"..."}},"b":{{"hard_pass":true,"reason":"..."}},"winner":"A|B|tie","reason":"..."}}
"""


def decision_pass(mode: str, candidate_wins: int, candidate_losses: int, candidate_failures: int, judge_errors: int) -> bool:
    """Compatibility helper for old report consumers; v2 uses sequential_decision."""
    clean = candidate_losses == 0 and candidate_failures == 0 and judge_errors == 0
    return clean if mode == "retirement" else clean and candidate_wins >= 1


def map_judgment(judgment: dict[str, Any], order: list[str]) -> tuple[str, dict[str, bool]]:
    anonymous_winner = str(judgment.get("winner", "tie")).upper()
    if anonymous_winner == "A":
        winner = order[0]
    elif anonymous_winner == "B":
        winner = order[1]
    else:
        winner = "tie"
    return winner, {
        order[0]: bool(judgment.get("a", {}).get("hard_pass")),
        order[1]: bool(judgment.get("b", {}).get("hard_pass")),
    }


def v3_judge_prompt(case: dict[str, Any], a: str, b: str) -> str:
    criteria = "\n".join(f"- {item['id']}: {item['text']}" for item in case.get("semantic_criteria", []))
    return f"""Judge two anonymous structured decision receipts for the same task. Critical receipt correctness is checked separately and must not be re-litigated here. Judge only the semantic criteria below, cite evidence from each receipt, and prefer concise causal reasoning over verbosity. Do not require unrelated workflow details.

Semantic criteria:
{criteria}

Task:
{case['prompt']}

RECEIPT A
{a}

RECEIPT B
{b}

Return only JSON matching the supplied output schema. Include every semantic criterion exactly once for A and B.
"""


def v3_judge_schema(criterion_ids: list[str]) -> dict[str, Any]:
    criterion = {
        "type": "object",
        "required": ["id", "pass", "evidence"],
        "properties": {
            "id": {"type": "string", "enum": criterion_ids},
            "pass": {"type": "boolean"},
            "evidence": {"type": "string"},
        },
        "additionalProperties": False,
    }
    answer = {
        "type": "object",
        "required": ["criteria"],
        "properties": {
            "criteria": {"type": "array", "minItems": len(criterion_ids), "items": criterion},
        },
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "required": ["a", "b", "winner", "reason"],
        "properties": {
            "a": answer,
            "b": answer,
            "winner": {"type": "string", "enum": ["A", "B", "tie"]},
            "reason": {"type": "string"},
        },
        "additionalProperties": False,
    }


def map_v3_judgment(
    judgment: dict[str, Any], order: list[str], criterion_ids: list[str]
) -> tuple[str, dict[str, dict[str, bool]]]:
    anonymous_winner = str(judgment.get("winner", "tie")).upper()
    if anonymous_winner == "A":
        winner = order[0]
    elif anonymous_winner == "B":
        winner = order[1]
    elif anonymous_winner == "TIE":
        winner = "tie"
    else:
        raise ValueError(f"invalid v3 winner: {anonymous_winner}")

    mapped: dict[str, dict[str, bool]] = {}
    for anonymous, name in (("a", order[0]), ("b", order[1])):
        answer = judgment.get(anonymous)
        entries = answer.get("criteria") if isinstance(answer, dict) else None
        if not isinstance(entries, list):
            raise ValueError(f"{anonymous} missing semantic criteria")
        values: dict[str, bool] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"{anonymous} has invalid semantic criterion")
            criterion_id = str(entry.get("id", ""))
            if criterion_id not in criterion_ids:
                raise ValueError(f"{anonymous} has unknown semantic criterion: {criterion_id}")
            if criterion_id in values:
                raise ValueError(f"{anonymous} has duplicate semantic criterion: {criterion_id}")
            if not isinstance(entry.get("pass"), bool):
                raise ValueError(f"{anonymous} semantic criterion lacks boolean pass: {criterion_id}")
            if not str(entry.get("evidence", "")).strip():
                raise ValueError(f"{anonymous} semantic criterion lacks evidence: {criterion_id}")
            values[criterion_id] = entry["pass"]
        for criterion_id in criterion_ids:
            if criterion_id not in values:
                raise ValueError(f"{anonymous} missing semantic criterion: {criterion_id}")
        mapped[name] = values
    return winner, mapped


def v3_disagreement(winners: list[str], passes: list[dict[str, dict[str, bool]]]) -> dict[str, Any]:
    winner_disagreement = len(winners) != 2 or len(set(winners)) > 1
    details: list[str] = []
    if len(passes) != 2:
        details.append("criterion judgment count")
    else:
        names = sorted(set(passes[0]) | set(passes[1]))
        for name in names:
            criterion_ids = sorted(set(passes[0].get(name, {})) | set(passes[1].get(name, {})))
            for criterion_id in criterion_ids:
                values = [item.get(name, {}).get(criterion_id) for item in passes]
                if len(set(values)) > 1:
                    details.append(f"{name}.{criterion_id}")
    return {"winner": winner_disagreement, "criteria": bool(details), "details": details}


def resolve_v3_judgments(
    winners: list[str],
    passes: list[dict[str, dict[str, bool]]],
    criterion_ids: list[str],
) -> dict[str, Any]:
    """Resolve a two-judge consensus or a bounded three-judge panel.

    The third vote is only collected after the order-swapped pair disagrees.
    Raw disagreement remains auditable; only a strict majority resolves it.
    """
    winner_votes = {name: winners.count(name) for name in ("baseline", "candidate", "tie")}
    winner = max(winner_votes, key=winner_votes.get) if winners else "tie"
    winner_unresolved = not winners or winner_votes[winner] <= len(winners) / 2
    if winner_unresolved:
        winner = "tie"

    resolved_passes: dict[str, dict[str, bool]] = {"baseline": {}, "candidate": {}}
    criterion_votes: dict[str, dict[str, list[bool | None]]] = {"baseline": {}, "candidate": {}}
    unresolved_details: list[str] = []
    for name in ("baseline", "candidate"):
        for criterion_id in criterion_ids:
            values = [item.get(name, {}).get(criterion_id) for item in passes]
            criterion_votes[name][criterion_id] = values
            true_votes = sum(value is True for value in values)
            false_votes = sum(value is False for value in values)
            if true_votes > len(values) / 2:
                resolved_passes[name][criterion_id] = True
            elif false_votes > len(values) / 2:
                resolved_passes[name][criterion_id] = False
            else:
                resolved_passes[name][criterion_id] = False
                unresolved_details.append(f"{name}.{criterion_id}")

    return {
        "winner": winner,
        "passes": resolved_passes,
        "votes": {"winners": winners, "winner_counts": winner_votes, "criteria": criterion_votes},
        "unresolved": {
            "winner": winner_unresolved,
            "criteria": bool(unresolved_details),
            "details": unresolved_details,
        },
    }


def v3_effective_result(
    resolution: dict[str, Any],
    receipt_passes: dict[str, bool],
    criterion_ids: list[str],
) -> tuple[str, dict[str, bool]]:
    """Apply deterministic and semantic eligibility before preference ranking."""

    hard_pass = {
        name: bool(receipt_passes.get(name))
        and all(resolution.get("passes", {}).get(name, {}).get(criterion_id) is True for criterion_id in criterion_ids)
        for name in ("baseline", "candidate")
    }
    if hard_pass["candidate"] and not hard_pass["baseline"]:
        return "candidate", hard_pass
    if hard_pass["baseline"] and not hard_pass["candidate"]:
        return "baseline", hard_pass
    if not hard_pass["baseline"] and not hard_pass["candidate"]:
        return "tie", hard_pass
    return str(resolution.get("winner", "tie")), hard_pass


def v3_stability_decision(results: list[dict[str, Any]], contract: dict[str, Any], trials_run: int) -> dict[str, Any]:
    required_trials = int(contract.get("trials", 1))
    receipt_failures = sum(not item.get("candidate_receipt_pass", False) for item in results)
    candidate_failures = sum(
        not item.get("candidate_hard_pass", item.get("candidate_receipt_pass", False))
        for item in results
    )
    losses = sum(item.get("winner") == "baseline" for item in results)
    disagreements = sum(bool(item.get("judge_disagreement")) for item in results)
    required_win_kinds = list(contract.get("required_win_kinds", []))
    missing_win_kinds = [
        kind for kind in required_win_kinds
        if not any(item.get("kind") == kind and item.get("winner") == "candidate" for item in results)
    ]
    metrics = {
        "trials": trials_run,
        "required_trials": required_trials,
        "candidate_receipt_failures": receipt_failures,
        "candidate_hard_failures": candidate_failures,
        "candidate_losses": losses,
        "judge_disagreements": disagreements,
        "missing_required_win_kinds": missing_win_kinds,
    }
    if receipt_failures or candidate_failures or losses:
        return {"decision": "reject", "basis": "bounded-stability", **metrics}
    if trials_run < required_trials:
        return {"decision": "continue", "basis": "bounded-stability", **metrics}
    if disagreements or missing_win_kinds:
        return {"decision": "inconclusive", "basis": "bounded-stability", **metrics}
    return {"decision": "admit", "basis": "bounded-stability", **metrics}


def artifact_hashes(candidate: Path, baseline: Path | None, suite: Path) -> dict[str, Any]:
    return {
        "candidate_sha256": candidate_hash(candidate),
        "baseline_candidate_sha256": candidate_hash(baseline) if baseline else None,
        "suite_sha256": hashlib.sha256(suite.read_bytes()).hexdigest(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", type=Path)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline-candidate", type=Path, help="Optional current/full instruction artifact for retirement A/B tests")
    parser.add_argument("--agent", choices=("hermes", "codex"), default="hermes")
    parser.add_argument("--judge-agent", choices=("hermes", "codex"))
    parser.add_argument("--model", required=True, help="Exact model override for baseline and candidate")
    parser.add_argument("--provider", required=True, help="Exact provider override for baseline, candidate, and same-host judge")
    parser.add_argument("--reasoning", default="low", help="Exact reasoning effort")
    parser.add_argument("--judge-model", help="Exact model override for the blind judge")
    parser.add_argument("--judge-provider", help="Exact provider override for the blind judge")
    parser.add_argument("--decision-mode", choices=("admission", "retirement"), default="admission")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--min-trials", type=int, default=2)
    parser.add_argument("--max-trials", type=int, default=8)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--margin", type=float, default=0.1)
    parser.add_argument("--max-agent-runs", type=int, default=128)
    parser.add_argument("--transient-retries", type=int, default=2)
    parser.add_argument("--retry-delay", type=float, default=2.0)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--full-tools", action="store_true")
    parser.add_argument("--tool-policy", choices=("none", "safe", "full"), default="safe")
    parser.add_argument("--prompt-assembly", default="isolated-explicit-artifact-v2")
    parser.add_argument("--context-policy", default="fresh-session-per-output")
    parser.add_argument("--equivalence-group", required=True, help="Cross-host effective-stack equivalence group")
    parser.add_argument("--irreducible-difference", action="append", default=[])
    parser.add_argument("--rollback", required=True, help="Concrete rollback action if promotion/retirement regresses")
    parser.add_argument("--retain-eval-sessions", action="store_true")
    parser.add_argument("--protected-session", action="append", default=[])
    parser.add_argument("--case", action="append", dest="case_ids", help="Run only the named case; repeatable")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    try:
        validate_suite(suite)
    except ValueError as exc:
        parser.error(str(exc))
    schema_version = int(suite.get("schema_version", 1))
    is_v3 = schema_version >= 3
    all_cases = suite.get("cases", [])
    if args.case_ids:
        requested = set(args.case_ids)
        available = {case["id"] for case in all_cases}
        unknown = requested - available
        if unknown:
            parser.error(f"unknown case id(s): {', '.join(sorted(unknown))}")
        cases = [case for case in all_cases if case["id"] in requested]
    else:
        cases = all_cases
    if not 0 < args.alpha < 1:
        parser.error("alpha must be between 0 and 1")
    if not 0 <= args.margin < 1:
        parser.error("margin must be in [0, 1)")
    if args.min_trials < 1 or args.max_trials < args.min_trials:
        parser.error("trial bounds must satisfy 1 <= min-trials <= max-trials")
    if args.transient_retries < 0:
        parser.error("transient-retries must be non-negative")
    if args.retry_delay < 0:
        parser.error("retry-delay must be non-negative")
    judge_agent = args.judge_agent or args.agent
    effective_prompt_assembly = args.prompt_assembly
    if is_v3:
        stability_trials = int(suite["stability"]["trials"])
        if args.decision_mode != "admission":
            parser.error("schema v3 currently supports admission decisions only")
        if not v3_route_supported(args.agent, judge_agent):
            parser.error("schema v3 requires attested Codex or Hermes generation with Codex judging")
        if not args.baseline_candidate:
            parser.error("schema v3 requires --baseline-candidate for matched evaluation")
        if args.prompt_assembly not in {
            "isolated-explicit-artifact-v2",
            "isolated-anonymous-artifact-v3",
        }:
            parser.error("schema v3 requires isolated-anonymous-artifact-v3 prompt assembly")
        effective_prompt_assembly = "isolated-anonymous-artifact-v3"
        if args.min_trials != stability_trials or args.max_trials != stability_trials:
            parser.error(
                "schema v3 trial bounds must exactly match stability.trials "
                f"({stability_trials})"
            )
    runs_per_case = 5 if is_v3 else 4
    minimum_runs = len(cases) * runs_per_case * args.min_trials
    if args.max_agent_runs < minimum_runs:
        panel = "matched generation, order-swapped judges, and bounded tiebreaks" if is_v3 else "matched generation and order-swapped judges"
        parser.error(f"max-agent-runs must be at least {minimum_runs} for {panel}")
    candidate = candidate_prompt_text(args.candidate)
    baseline_candidate = candidate_prompt_text(args.baseline_candidate) if args.baseline_candidate else ""

    out = args.out or Path(".evals") / f"{suite.get('name','suite')}-{args.agent}.json"
    out = out.resolve()
    protected = set(args.protected_session)
    protected.update(filter(None, (os.environ.get("HERMES_SESSION_ID"), os.environ.get("HERMES_PARENT_SESSION_ID"))))
    lifecycle = HermesSessionLifecycle(shutil.which("hermes") or "hermes", args.retain_eval_sessions, protected)
    rule = DecisionRule(args.alpha, args.margin, args.min_trials, args.max_trials)
    results: list[dict[str, Any]] = []
    trial_scores: list[float] = []
    workdir = Path(tempfile.mkdtemp(prefix="agent-signal-eval-"))
    run_budget = AgentRunBudget(args.max_agent_runs)
    report: dict[str, Any] = {
        "schema_version": 3 if is_v3 else 2,
        "suite": suite.get("name"),
        "claim": suite.get("claim"),
        "candidate": str(args.candidate.resolve()),
        "baseline_candidate": str(args.baseline_candidate.resolve()) if args.baseline_candidate else None,
        "agent": args.agent,
        "agent_version": command_version(args.agent),
        "judge_agent": judge_agent,
        "judge_version": command_version(judge_agent),
        "decision_mode": args.decision_mode,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "running",
        "effective_stack": {
            "model": args.model,
            "provider": args.provider,
            "reasoning": args.reasoning,
            "judge_model": args.judge_model or args.model,
            "judge_provider": args.judge_provider or args.provider,
            "tool_policy": args.tool_policy,
            "prompt_assembly": effective_prompt_assembly,
            "context_policy": args.context_policy,
            "equivalence_group": args.equivalence_group,
            "irreducible_differences": args.irreducible_difference,
            "route_attestation_required": True,
            "judge_panel": "two-order-swapped-plus-bounded-tiebreak" if is_v3 else "two-order-swapped",
        },
        "decision_rule": {
            **rule.as_dict(),
            "max_agent_runs": args.max_agent_runs,
            "transient_retries_per_run": args.transient_retries,
            "retry_delay_seconds": args.retry_delay,
            "score_range": [-1, 1],
        },
        "rollback": args.rollback,
        "seeds": [],
        "artifacts": artifact_hashes(args.candidate, args.baseline_candidate, args.suite),
        "decision": {"decision": "continue"},
        "results": results,
    }
    if is_v3:
        report["stability"] = suite["stability"]

    interrupted = False
    old_handlers: dict[int, Any] = {}

    def interrupt_handler(signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt(f"signal {signum}")

    for signum in (signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.signal(signum, interrupt_handler)
    try:
        for trial_index in range(args.max_trials):
            if run_budget.remaining < len(cases) * runs_per_case:
                break
            trial_seed = args.seed + trial_index
            report["seeds"].append(trial_seed)
            rng = random.Random(trial_seed)
            trial_results: list[dict[str, Any]] = []
            for case_index, case in enumerate(cases):
                safe_id = "".join(char if char.isalnum() or char in "-_" else "-" for char in str(case.get("id", case_index)))
                case_root = workdir / f"trial-{trial_index:03d}" / f"{case_index:03d}-{safe_id}"
                baseline_workdir = case_root / "baseline"
                candidate_workdir = case_root / "candidate"
                judge_workdir = case_root / "judge"
                if is_v3:
                    baseline_prompt = f"""Complete the task using the instruction artifact below. Treat it as procedural guidance, but follow the task and safety constraints first.

<INSTRUCTION_ARTIFACT>
{baseline_candidate}
</INSTRUCTION_ARTIFACT>

<TASK>
{case['prompt']}
</TASK>"""
                    candidate_prompt = f"""Complete the task using the instruction artifact below. Treat it as procedural guidance, but follow the task and safety constraints first.

<INSTRUCTION_ARTIFACT>
{candidate}
</INSTRUCTION_ARTIFACT>

<TASK>
{case['prompt']}
</TASK>"""
                elif baseline_candidate:
                    baseline_prompt = f"""Complete the task using the baseline instruction artifact below. Treat it as procedural guidance, but follow the task and safety constraints first.

<BASELINE_INSTRUCTIONS>
{baseline_candidate}
</BASELINE_INSTRUCTIONS>

<TASK>
{case['prompt']}
</TASK>"""
                else:
                    baseline_prompt = f"Complete the following task. Follow only the task requirements.\n\n{case['prompt']}"
                if not is_v3:
                    candidate_prompt = f"""Complete the task using the candidate skill below. Treat the skill as procedural guidance, but follow the task and safety constraints first.

<CANDIDATE_SKILL>
{candidate}
</CANDIDATE_SKILL>

<TASK>
{case['prompt']}
</TASK>"""
                receipt_schema = suite["receipt_schema"] if is_v3 else None
                baseline = run_agent_with_retry(
                    run_budget,
                    args.agent,
                    baseline_prompt,
                    baseline_workdir,
                    args.timeout,
                    args.full_tools,
                    args.model,
                    args.provider,
                    args.reasoning,
                    args.tool_policy,
                    lifecycle,
                    output_schema=receipt_schema,
                    require_attestation=True,
                    transient_retries=args.transient_retries,
                    retry_delay=args.retry_delay,
                )
                contender = run_agent_with_retry(
                    run_budget,
                    args.agent,
                    candidate_prompt,
                    candidate_workdir,
                    args.timeout,
                    args.full_tools,
                    args.model,
                    args.provider,
                    args.reasoning,
                    args.tool_policy,
                    lifecycle,
                    output_schema=receipt_schema,
                    require_attestation=True,
                    transient_retries=args.transient_retries,
                    retry_delay=args.retry_delay,
                )
                if is_v3:
                    baseline_det = structured_receipt_check(case, baseline["output"], suite["receipt_schema"])
                    candidate_det = structured_receipt_check(case, contender["output"], suite["receipt_schema"])
                else:
                    baseline_det = deterministic(case, baseline["output"])
                    candidate_det = deterministic(case, contender["output"])

                order = ["baseline", "candidate"]
                rng.shuffle(order)
                outputs = {"baseline": baseline["output"], "candidate": contender["output"]}
                judgments: list[dict[str, Any]] = []
                mapped_winners: list[str] = []
                mapped_passes: list[dict[str, bool]] = []
                judge_errors: list[str] = []
                for judge_index, judge_order in enumerate((order, list(reversed(order)))):
                    criterion_ids = [item["id"] for item in case.get("semantic_criteria", [])]
                    prompt = (
                        v3_judge_prompt(case, outputs[judge_order[0]], outputs[judge_order[1]])
                        if is_v3
                        else judge_prompt(suite, case, outputs[judge_order[0]], outputs[judge_order[1]])
                    )
                    judge_output_schema = v3_judge_schema(criterion_ids) if is_v3 else None
                    judged_run = run_agent_with_retry(
                        run_budget,
                        judge_agent,
                        prompt,
                        judge_workdir / str(judge_index),
                        args.timeout,
                        False,
                        args.judge_model or args.model,
                        args.judge_provider or args.provider,
                        args.reasoning,
                        "safe",
                        lifecycle,
                        output_schema=judge_output_schema,
                        require_attestation=True,
                        transient_retries=args.transient_retries,
                        retry_delay=args.retry_delay,
                    )
                    try:
                        if is_v3 and not judged_run["ok"]:
                            errors = judged_run.get("route_attestation", {}).get("errors", [])
                            raise ValueError("judge run failed" + (": " + "; ".join(errors) if errors else ""))
                        judgment = extract_json(judged_run["output"])
                        if is_v3:
                            mapped_winner, mapped_pass = map_v3_judgment(judgment, judge_order, criterion_ids)
                        else:
                            mapped_winner, mapped_pass = map_judgment(judgment, judge_order)
                        judgments.append({"order": judge_order, "run": judged_run, "judgment": judgment})
                        mapped_winners.append(mapped_winner)
                        mapped_passes.append(mapped_pass)
                    except Exception as exc:
                        judgments.append({"order": judge_order, "run": judged_run, "judgment": {"raw": judged_run["output"]}})
                        judge_errors.append(str(exc))
                if is_v3:
                    raw_disagreement = v3_disagreement(mapped_winners, mapped_passes)
                    used_tiebreak = False
                    if (raw_disagreement["winner"] or raw_disagreement["criteria"]) and not judge_errors:
                        tiebreak_order = list(order if rng.choice((True, False)) else reversed(order))
                        prompt = v3_judge_prompt(
                            case,
                            outputs[tiebreak_order[0]],
                            outputs[tiebreak_order[1]],
                        )
                        judged_run = run_agent_with_retry(
                            run_budget,
                            judge_agent,
                            prompt,
                            judge_workdir / "tiebreak",
                            args.timeout,
                            False,
                            args.judge_model or args.model,
                            args.judge_provider or args.provider,
                            args.reasoning,
                            "safe",
                            lifecycle,
                            output_schema=v3_judge_schema(criterion_ids),
                            require_attestation=True,
                            transient_retries=args.transient_retries,
                            retry_delay=args.retry_delay,
                        )
                        used_tiebreak = True
                        try:
                            if not judged_run["ok"]:
                                errors = judged_run.get("route_attestation", {}).get("errors", [])
                                raise ValueError("tiebreak judge run failed" + (": " + "; ".join(errors) if errors else ""))
                            judgment = extract_json(judged_run["output"])
                            mapped_winner, mapped_pass = map_v3_judgment(
                                judgment, tiebreak_order, criterion_ids,
                            )
                            judgments.append({"order": tiebreak_order, "run": judged_run, "judgment": judgment, "role": "tiebreak"})
                            mapped_winners.append(mapped_winner)
                            mapped_passes.append(mapped_pass)
                        except Exception as exc:
                            judgments.append({
                                "order": tiebreak_order,
                                "run": judged_run,
                                "judgment": {"raw": judged_run["output"]},
                                "role": "tiebreak",
                            })
                            judge_errors.append(str(exc))
                    resolution = resolve_v3_judgments(mapped_winners, mapped_passes, criterion_ids)
                    winner, hard_pass = v3_effective_result(
                        resolution,
                        {
                            "baseline": bool(baseline_det["pass"]),
                            "candidate": bool(candidate_det["pass"]),
                        },
                        criterion_ids,
                    )
                    disagreement = {
                        **resolution["unresolved"],
                        "raw": raw_disagreement,
                        "resolved_by": "third-judge" if used_tiebreak and not (resolution["unresolved"]["winner"] or resolution["unresolved"]["criteria"]) else None,
                        "votes": resolution["votes"],
                    }
                    deterministic_report = {"baseline": baseline_det, "candidate": candidate_det}
                else:
                    winner = mapped_winners[0] if len(mapped_winners) == 2 and len(set(mapped_winners)) == 1 else "tie"
                    raw_disagreement = {
                        "winner": len(mapped_winners) == 2 and len(set(mapped_winners)) > 1,
                        "criteria": False,
                        "details": [],
                    }
                    disagreement = {
                        **raw_disagreement,
                    }
                    hard_pass = {
                        name: bool(mapped_passes) and all(mapped[name] for mapped in mapped_passes)
                        for name in ("baseline", "candidate")
                    }
                    if not baseline_det[0]:
                        hard_pass["baseline"] = False
                    if not candidate_det[0]:
                        hard_pass["candidate"] = False
                    deterministic_report = {"baseline": baseline_det[1], "candidate": candidate_det[1]}
                item = {
                    "id": case.get("id"),
                    "kind": case.get("kind"),
                    "trial": trial_index,
                    "seed": trial_seed,
                    "order": order,
                    "baseline": baseline,
                    "candidate": contender,
                    "deterministic": deterministic_report,
                    "judgments": judgments,
                    "judge_errors": judge_errors,
                    "raw_judge_disagreement": bool(raw_disagreement["winner"] or raw_disagreement["criteria"]),
                    "judge_disagreement": bool(disagreement["winner"] or disagreement["criteria"]),
                    "judge_disagreement_detail": disagreement,
                    "hard_pass": hard_pass,
                    "winner": winner,
                    "score": 1 if winner == "candidate" else -1 if winner == "baseline" else 0,
                }
                if is_v3:
                    item["candidate_receipt_pass"] = bool(candidate_det["pass"])
                    item["candidate_hard_pass"] = bool(hard_pass["candidate"])
                results.append(item)
                trial_results.append(item)
                print(case.get("id"), "->", winner, "candidate_pass=", hard_pass["candidate"])
            trial_evidence = decision_scores(trial_results)
            trial_scores.append(sum(trial_evidence) / len(trial_evidence) if trial_evidence else 0.0)
            harness_failure = any(
                not item["baseline"]["ok"]
                or not item["candidate"]["ok"]
                or item["judge_errors"]
                for item in results
            )
            if is_v3:
                decision = v3_stability_decision(results, suite["stability"], len(trial_scores))
                if harness_failure:
                    decision = {**decision, "decision": "harness-failure"}
            else:
                decision = sequential_decision(args.decision_mode, decision_scores(results), rule, len(trial_scores))
                if harness_failure:
                    decision = {**decision, "decision": "harness-failure"}
                elif any(not item["hard_pass"]["candidate"] for item in results):
                    decision = {**decision, "decision": "reject" if args.decision_mode == "admission" else "retain"}
            report["decision"] = decision
            report["run_count"] = run_budget.used
            durable_json_write(out, report)
            if decision["decision"] != "continue":
                break
        if report["decision"]["decision"] == "continue":
            if is_v3:
                report["decision"] = {
                    **v3_stability_decision(results, suite["stability"], len(trial_scores)),
                    "decision": "inconclusive",
                }
            else:
                report["decision"] = {**sequential_decision(args.decision_mode, decision_scores(results), rule, len(trial_scores)), "decision": "inconclusive"}
        report["status"] = "complete"
    except KeyboardInterrupt as exc:
        interrupted = True
        report["status"] = "interrupted"
        report["interruption"] = str(exc)
        report["decision"] = {"decision": "harness-failure", "reason": "interrupted"}
    except Exception as exc:
        report["status"] = "failed"
        report["failure"] = f"{type(exc).__name__}: {exc}"
        report["decision"] = {"decision": "harness-failure", "reason": "exception"}
    finally:
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)
        report["run_count"] = run_budget.used
        report["summary"] = {
            "candidate_wins": sum(item["winner"] == "candidate" for item in results),
            "candidate_losses": sum(item["winner"] == "baseline" for item in results),
            "ties": sum(item["winner"] == "tie" for item in results),
            "candidate_hard_failures": sum(not item["hard_pass"]["candidate"] for item in results),
            "judge_errors": sum(bool(item["judge_errors"]) for item in results),
            "judge_disagreements": sum(bool(item["judge_disagreement"]) for item in results),
            "raw_judge_disagreements": sum(bool(item.get("raw_judge_disagreement")) for item in results),
            "criterion_disagreements": sum(bool(item.get("judge_disagreement_detail", {}).get("criteria")) for item in results),
            "raw_criterion_disagreements": sum(
                bool(item.get("judge_disagreement_detail", {}).get("raw", {}).get("criteria"))
                for item in results
            ),
            "candidate_receipt_failures": sum(not item.get("candidate_receipt_pass", item["hard_pass"]["candidate"]) for item in results),
            "route_attestation_failures": sum(
                not run.get("route_attestation", {}).get("ok", True)
                for item in results
                for run in (item["baseline"], item["candidate"], *(judgment["run"] for judgment in item["judgments"]))
            ),
            "trial_scores": trial_scores,
        }
        finalize_report(out, report, lifecycle)
        shutil.rmtree(workdir, ignore_errors=True)
    print(json.dumps({"status": report["status"], **report["decision"]}, indent=2))
    print("report:", out)
    passed = report["decision"]["decision"] in {"admit", "retire"}
    return 130 if interrupted else 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
