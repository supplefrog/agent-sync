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
    if suite.get("schema_version", 1) >= 2:
        present = {case.get("kind") for case in cases}
        missing = sorted(CASE_KINDS - present)
        if missing:
            raise ValueError("suite missing required case kinds: " + ", ".join(missing))


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
) -> dict[str, Any]:
    exe = shutil.which(agent)
    if not exe:
        raise RuntimeError(f"{agent} executable not found")
    workdir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    output_file = workdir / f"last-{time.time_ns()}.txt"
    input_text = None
    run_env = isolated_child_env()
    if agent == "hermes":
        workdir.mkdir(parents=True, exist_ok=True)
        prompt_file = workdir / "eval-prompt.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        command = [exe, "chat", "-Q", "--source", "agent-signal-eval", "--in", str(workdir), "--ignore-rules"]
        if model:
            command += ["-m", model]
        if provider:
            command += ["--provider", provider]
        if reasoning:
            command += ["--reasoning", reasoning]
        if tool_policy == "none":
            command += ["--toolsets", ""]
        elif not full_tools or tool_policy == "safe":
            command.append("--safe-mode")
        command += [
            "-q",
            f"Read the UTF-8 file at {prompt_file.resolve()} completely as the evaluation task, then complete it. Do not summarize or discuss the file itself.",
        ]
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
    return {
        "ok": process.returncode == 0 and session_receipt_error is None,
        "returncode": process.returncode,
        "seconds": elapsed,
        "output": text,
        "stderr": stderr[-4000:],
        "session_ids": session_ids,
        "session_receipt_error": session_receipt_error,
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
    minimum_runs = len(cases) * 4 * args.min_trials
    if args.max_agent_runs < minimum_runs:
        parser.error(f"max-agent-runs must be at least {minimum_runs} for matched generation and order-swapped judges")
    candidate = candidate_prompt_text(args.candidate)
    baseline_candidate = candidate_prompt_text(args.baseline_candidate) if args.baseline_candidate else ""

    judge_agent = args.judge_agent or args.agent
    out = args.out or Path(".evals") / f"{suite.get('name','suite')}-{args.agent}.json"
    out = out.resolve()
    protected = set(args.protected_session)
    protected.update(filter(None, (os.environ.get("HERMES_SESSION_ID"), os.environ.get("HERMES_PARENT_SESSION_ID"))))
    lifecycle = HermesSessionLifecycle(shutil.which("hermes") or "hermes", args.retain_eval_sessions, protected)
    rule = DecisionRule(args.alpha, args.margin, args.min_trials, args.max_trials)
    results: list[dict[str, Any]] = []
    trial_scores: list[float] = []
    workdir = Path(tempfile.mkdtemp(prefix="agent-signal-eval-"))
    run_count = 0
    report: dict[str, Any] = {
        "schema_version": 2,
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
            "prompt_assembly": args.prompt_assembly,
            "context_policy": args.context_policy,
            "equivalence_group": args.equivalence_group,
            "irreducible_differences": args.irreducible_difference,
        },
        "decision_rule": {**rule.as_dict(), "max_agent_runs": args.max_agent_runs, "score_range": [-1, 1]},
        "rollback": args.rollback,
        "seeds": [],
        "artifacts": artifact_hashes(args.candidate, args.baseline_candidate, args.suite),
        "decision": {"decision": "continue"},
        "results": results,
    }

    interrupted = False
    old_handlers: dict[int, Any] = {}

    def interrupt_handler(signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt(f"signal {signum}")

    for signum in (signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.signal(signum, interrupt_handler)
    try:
        for trial_index in range(args.max_trials):
            if run_count + len(cases) * 4 > args.max_agent_runs:
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
                if baseline_candidate:
                    baseline_prompt = f"""Complete the task using the baseline instruction artifact below. Treat it as procedural guidance, but follow the task and safety constraints first.

<BASELINE_INSTRUCTIONS>
{baseline_candidate}
</BASELINE_INSTRUCTIONS>

<TASK>
{case['prompt']}
</TASK>"""
                else:
                    baseline_prompt = f"Complete the following task. Follow only the task requirements.\n\n{case['prompt']}"
                candidate_prompt = f"""Complete the task using the candidate skill below. Treat the skill as procedural guidance, but follow the task and safety constraints first.

<CANDIDATE_SKILL>
{candidate}
</CANDIDATE_SKILL>

<TASK>
{case['prompt']}
</TASK>"""
                baseline = run_agent(args.agent, baseline_prompt, baseline_workdir, args.timeout, args.full_tools, args.model, args.provider, args.reasoning, args.tool_policy, lifecycle)
                contender = run_agent(args.agent, candidate_prompt, candidate_workdir, args.timeout, args.full_tools, args.model, args.provider, args.reasoning, args.tool_policy, lifecycle)
                run_count += 2
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
                    judged_run = run_agent(
                        judge_agent,
                        judge_prompt(suite, case, outputs[judge_order[0]], outputs[judge_order[1]]),
                        judge_workdir / str(judge_index),
                        args.timeout,
                        False,
                        args.judge_model or args.model,
                        args.judge_provider or args.provider,
                        args.reasoning,
                        "safe",
                        lifecycle,
                    )
                    run_count += 1
                    try:
                        judgment = extract_json(judged_run["output"])
                        mapped_winner, mapped_pass = map_judgment(judgment, judge_order)
                        judgments.append({"order": judge_order, "run": judged_run, "judgment": judgment})
                        mapped_winners.append(mapped_winner)
                        mapped_passes.append(mapped_pass)
                    except Exception as exc:
                        judgments.append({"order": judge_order, "run": judged_run, "judgment": {"raw": judged_run["output"]}})
                        judge_errors.append(str(exc))
                winner = mapped_winners[0] if len(mapped_winners) == 2 and len(set(mapped_winners)) == 1 else "tie"
                hard_pass = {
                    name: bool(mapped_passes) and all(mapped[name] for mapped in mapped_passes)
                    for name in ("baseline", "candidate")
                }
                if not baseline_det[0]:
                    hard_pass["baseline"] = False
                if not candidate_det[0]:
                    hard_pass["candidate"] = False
                item = {
                    "id": case.get("id"),
                    "kind": case.get("kind"),
                    "trial": trial_index,
                    "seed": trial_seed,
                    "order": order,
                    "baseline": baseline,
                    "candidate": contender,
                    "deterministic": {"baseline": baseline_det[1], "candidate": candidate_det[1]},
                    "judgments": judgments,
                    "judge_errors": judge_errors,
                    "judge_disagreement": len(mapped_winners) == 2 and len(set(mapped_winners)) > 1,
                    "hard_pass": hard_pass,
                    "winner": winner,
                    "score": 1 if winner == "candidate" else -1 if winner == "baseline" else 0,
                }
                results.append(item)
                trial_results.append(item)
                print(case.get("id"), "->", winner, "candidate_pass=", hard_pass["candidate"])
            trial_scores.append(sum(item["score"] for item in trial_results) / len(trial_results))
            decision = sequential_decision(args.decision_mode, [item["score"] for item in results], rule, len(trial_scores))
            if any(not item["baseline"]["ok"] or not item["candidate"]["ok"] or item["judge_errors"] for item in results):
                decision = {**decision, "decision": "harness-failure"}
            elif any(not item["hard_pass"]["candidate"] for item in results):
                decision = {**decision, "decision": "reject" if args.decision_mode == "admission" else "retain"}
            report["decision"] = decision
            report["run_count"] = run_count
            durable_json_write(out, report)
            if decision["decision"] != "continue":
                break
        if report["decision"]["decision"] == "continue":
            report["decision"] = {**sequential_decision(args.decision_mode, [item["score"] for item in results], rule, len(trial_scores)), "decision": "inconclusive"}
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
        report["summary"] = {
            "candidate_wins": sum(item["winner"] == "candidate" for item in results),
            "candidate_losses": sum(item["winner"] == "baseline" for item in results),
            "ties": sum(item["winner"] == "tie" for item in results),
            "candidate_hard_failures": sum(not item["hard_pass"]["candidate"] for item in results),
            "judge_errors": sum(bool(item["judge_errors"]) for item in results),
            "judge_disagreements": sum(bool(item["judge_disagreement"]) for item in results),
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
