#!/usr/bin/env python
"""Build a bounded, cache-aware instruction-retirement plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from contextlib import nullcontext

import jsonschema
from artifact_hash import freeze_candidate, harness_hash
import evaluation_evidence
from pathlib import Path
from typing import Any

MODEL_SENSITIVE = {"generic-steering"}
PROTECTED = {"safety-governance"}
EVALUATION_POLICY = {
    "schema_version": 3,
    "matched_trials": True,
    "order_swapped_blind_judges": True,
    "decision_rule": "hoeffding-alpha-spending",
    "required_case_kinds": ["representative", "near-miss", "adversarial", "held-out"],
    "raw_matched_evidence_required": True,
    "receipt_policy": "append-only",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def section(text: str, heading: str) -> str:
    lines = text.splitlines(keepends=True)
    try:
        start = next(index for index, line in enumerate(lines) if line.rstrip("\r\n") == heading)
    except StopIteration as exc:
        raise ValueError(f"heading not found: {heading}") from exc
    level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = re.match(r"^(#+)\s", lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return "".join(lines[start:end]).strip() + "\n"


def without_section(text: str, heading: str) -> str:
    selected = section(text, heading)
    start = text.index(selected.rstrip("\n"))
    end = start + len(selected.rstrip("\n"))
    while end < len(text) and text[end] in "\r\n":
        end += 1
    return (text[:start].rstrip() + "\n\n" + text[end:].lstrip()).strip() + "\n"


def tagged_line(text: str, tag: str) -> str:
    matches = [line for line in text.splitlines(keepends=True) if line.startswith(f"{tag} ") or line.rstrip("\r\n") == tag]
    if len(matches) != 1:
        raise ValueError(f"tagged line must match exactly once: {tag}")
    return matches[0].rstrip("\r\n") + "\n"


def paragraph_prefix(text: str, prefix: str) -> str:
    matches = [
        paragraph
        for paragraph in re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
        if paragraph.lstrip().startswith(prefix)
    ]
    if len(matches) != 1:
        raise ValueError(f"paragraph prefix must match exactly once: {prefix}")
    return matches[0].strip() + "\n"


def selected_text(text: str, selector: dict[str, Any]) -> str:
    kind = selector.get("kind")
    if kind == "whole-file":
        return text
    if kind == "heading":
        return section(text, selector["value"])
    if kind == "tagged-line":
        return tagged_line(text, selector["value"])
    if kind == "paragraph-prefix":
        return paragraph_prefix(text, selector["value"])
    raise ValueError(f"unsupported selector kind: {kind}")


def without_selector(text: str, selector: dict[str, Any]) -> str:
    kind = selector.get("kind")
    if kind == "whole-file":
        return "# No additional candidate instructions\n"
    if kind == "heading":
        return without_section(text, selector["value"])
    if kind == "tagged-line":
        selected = tagged_line(text, selector["value"])
        remaining = text.replace(selected, "", 1)
        return remaining.strip() + "\n" if remaining.strip() else "# No additional candidate instructions\n"
    if kind == "paragraph-prefix":
        selected = paragraph_prefix(text, selector["value"])
        remaining = text.replace(selected, "", 1)
        remaining = re.sub(r"\n{3,}", "\n\n", remaining).strip()
        return remaining + "\n" if remaining else "# No additional candidate instructions\n"
    raise ValueError(f"unsupported selector kind: {kind}")


def unit_text(repo: Path, unit: dict[str, Any]) -> str:
    path = _repo_path(repo, unit["path"])
    text = path.read_text(encoding="utf-8")
    selector = unit.get("selector", {"kind": "whole-file"})
    try:
        return selected_text(text, selector)
    except ValueError as exc:
        raise ValueError(f"{exc} for {unit['id']}") from exc



RECEIPT_VERSION = 3
SUPPORTED_HOSTS = {"codex", "hermes"}
LANE = "inline-text-no-tools-v1"


def _repo_path(repo: Path, relative: str) -> Path:
    path = (repo / relative).resolve()
    if "\\" in relative or Path(relative).is_absolute() or not path.is_relative_to(repo.resolve()):
        raise ValueError(f"source path escapes repository: {relative}")
    return path


def _validate_manifest(repo: Path, manifest: dict[str, Any]) -> None:
    schema = json.loads((repo / "contracts/instruction-units.schema.json").read_bytes())
    jsonschema.Draft202012Validator(schema).validate(manifest)
    ids = [unit["id"] for unit in manifest["units"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate instruction unit id")
    for unit in manifest["units"]:
        _repo_path(repo, unit["path"])
        _repo_path(repo, unit["suite"])


def _span(text: str, selector: dict[str, Any]) -> tuple[int, int]:
    """Find one exact source span without changing neighbors or line endings."""
    kind = selector["kind"]
    if kind == "whole-file":
        return 0, len(text)
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    value = selector["value"]
    if kind in {"heading", "tagged-line"}:
        indexes = [i for i, line in enumerate(lines)
                   if line.rstrip("\r\n") == value or (kind == "tagged-line" and line.startswith(value + " "))]
        if len(indexes) != 1:
            raise ValueError(f"selector must match exactly once: {value}")
        start = indexes[0]
        end = start + 1
        if kind == "heading":
            level = len(value) - len(value.lstrip("#"))
            end = len(lines)
            for i in range(start + 1, len(lines)):
                heading = re.match(r"^(#+)\s", lines[i])
                if heading and len(heading.group(1)) <= level:
                    end = i
                    break
        return offsets[start], offsets[end]
    if kind == "paragraph-prefix":
        boundaries, begin = [], 0
        for match in re.finditer(r"\r?\n[ \t]*\r?\n", text):
            boundaries.append((begin, match.start()))
            begin = match.end()
        boundaries.append((begin, len(text)))
        matches = [(a, b) for a, b in boundaries if text[a:b].lstrip().startswith(value)]
        if len(matches) != 1:
            raise ValueError(f"selector must match exactly once: {value}")
        return matches[0]
    raise ValueError(f"unsupported selector kind: {kind}")


def _materialize(repo: Path, unit: dict[str, Any], target: Path) -> dict[str, Any]:
    source = _repo_path(repo, unit["path"])
    original = freeze_candidate(source)
    source_paths = {(source.parent / name).resolve() for name in original["files"]}
    if source.name == "SKILL.md" and target.resolve().is_relative_to(source.parent):
        raise ValueError("materialization must not be inside its source package")
    for side in ("baseline", "candidate"):
        for relative, expected in original["files"].items():
            data = (source.parent / relative).read_bytes()
            if sha256_bytes(data) != expected:
                raise ValueError("instruction owner changed while freezing")
            path = target / side / relative
            if path.resolve() in source_paths or not path.resolve().is_relative_to(target.resolve()):
                raise ValueError("materialization destination overlaps source or escapes target")
            path.parent.mkdir(parents=True, exist_ok=True)
            # A materialization directory is immutable once populated.
            if path.exists() and path.read_bytes() != data:
                raise ValueError(f"materialization target already has different bytes: {path}")
            if not path.exists():
                path.write_bytes(data)
    baseline = target / "baseline" / source.name
    candidate = target / "candidate" / source.name
    full = baseline.read_bytes().decode("utf-8")
    start, end = _span(full, unit["selector"])
    minus = full[:start] + full[end:]
    candidate.write_bytes(minus.encode("utf-8"))
    frozen = {"baseline": freeze_candidate(baseline), "candidate": freeze_candidate(candidate)}
    if frozen["baseline"] != original or freeze_candidate(source) != original:
        raise ValueError("instruction owner/projection changed while freezing")
    return {**frozen, "unit_sha256": sha256_bytes(full[start:end].encode()),
            "baseline_candidate_path": str(baseline), "candidate_path": str(candidate)}


def build_experiment(repo: Path, unit: dict[str, Any], stack: dict[str, Any],
                     materialize_dir: Path | None = None) -> dict[str, Any]:
    """Bind actual full/minus projections; this does not execute an evaluator."""
    suite_path = _repo_path(repo, unit["suite"])
    suite_raw = suite_path.read_bytes()  # Missing suites fail before selection.
    suite = json.loads(suite_raw)
    evaluation_evidence.evaluator.validate_suite(suite)
    if suite.get("schema_version") != 2:
        raise ValueError("retirement requires a v2 suite in the current producer")
    ids = [case["id"] for case in suite["cases"]]
    requested = stack.get("case_ids", ids)
    if not isinstance(requested, list) or not requested or len(requested) != len(set(requested)) or any(i not in ids for i in requested):
        raise ValueError("unknown, empty or duplicate case selection")
    selected = [i for i in ids if i in requested]
    scope = evaluation_evidence.evaluator.evaluation_scope(suite, selected)
    context = nullcontext(str(materialize_dir)) if materialize_dir is not None else tempfile.TemporaryDirectory(prefix="instruction-retirement-")
    with context as directory:
        arms = _materialize(repo, unit, Path(directory))
    identity = {
        "schema_version": 1,
        "unit": json.loads(json.dumps({key: unit[key] for key in ("id", "path", "selector")})),
        "unit_sha256": arms["unit_sha256"],
        "stack": json.loads(json.dumps(stack)),
        "scope": scope,
        "artifacts": {
            "baseline_candidate_sha256": arms["baseline"]["package_sha256"],
            "baseline_prompt_sha256": arms["baseline"]["prompt_sha256"],
            "candidate_sha256": arms["candidate"]["package_sha256"],
            "candidate_prompt_sha256": arms["candidate"]["prompt_sha256"],
            "suite_sha256": sha256_bytes(suite_raw),
            "harness_sha256": harness_hash(repo / "tools/eval.py"),
        },
        "validator_sha256": sha256_bytes(Path(evaluation_evidence.__file__).read_bytes()),
        "receipt_adapter_sha256": sha256_bytes(Path(__file__).read_bytes()),
    }
    result = {"identity": identity, "cache_key": canonical_hash(identity), "suite": suite}
    if materialize_dir is not None:
        result.update({key: arms[key] for key in ("baseline_candidate_path", "candidate_path")})
    return result


def _bound_validation(report: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
    validation = evaluation_evidence.validate_report(report, experiment["suite"])
    errors = list(validation["errors"])
    if errors:
        return {"errors": errors, "operational_errors": validation["operational_errors"],
                "computed_decision": validation["computed_decision"], "scope": validation["scope"],
                "cache_authority": False, "limitations": validation["limitations"],
                "positive_decision_sufficient": False}
    identity = experiment["identity"]
    expected = identity["stack"]

    def same(actual: Any, required: Any, label: str) -> None:
        if actual != required:
            errors.append(f"retirement binding mismatch: {label}")

    same(report.get("decision_mode"), "retirement", "decision mode")
    same(report.get("schema_version"), 2, "report schema")
    for key, value in identity["artifacts"].items():
        same(report.get("artifacts", {}).get(key), value, key)
    same(validation["scope"], identity["scope"], "case selection and runtime scope")
    host = expected["host"]
    judge_host = expected.get("judge_host", host)
    if host not in SUPPORTED_HOSTS or judge_host not in SUPPORTED_HOSTS:
        errors.append("unsupported retirement host")
    same(report.get("agent"), host, "generation host")
    same(report.get("judge_agent"), judge_host, "judge host")
    for report_key, value in (
        ("agent_version", expected.get("runtime")),
        ("judge_version", expected.get("judge_runtime", expected.get("runtime") if judge_host == host else None)),
    ):
        if not isinstance(value, str) or not value:
            errors.append(f"missing expected runtime: {report_key}")
        same(report.get(report_key), value, report_key)
    observed = report.get("effective_stack", {})
    fields = {key: expected.get(key) for key in ("model", "provider", "reasoning", "tool_policy", "prompt_assembly", "context_policy", "equivalence_group")}
    fields.update(runtime_lane=LANE, judge_model=expected.get("judge_model", expected.get("model")),
                  judge_provider=expected.get("judge_provider", expected.get("provider")),
                  judge_reasoning=expected.get("reasoning"), judge_tool_policy="none", judge_panel="two-order-swapped")
    for key, value in fields.items():
        if not isinstance(value, str) or not value:
            errors.append(f"missing expected stack field: {key}")
        same(observed.get(key), value, key)
    # The current native producer attests labels, not resolved provider snapshots.
    for key in ("model_snapshot", "provider_snapshot", "transport", "tool_schema", "equivalence_hash"):
        if expected.get(key):
            errors.append(f"current producer cannot verify stack claim: {key}")
    trial = expected.get("trial_design", {})
    margin = expected.get("decision_margin", {})
    for key, value in {"min_trials": trial.get("min_trials"), "max_trials": trial.get("max_trials"),
                       "alpha": margin.get("alpha"), "margin": margin.get("margin"),
                       "max_agent_runs": expected.get("max_agent_runs"),
                       "transient_retries_per_run": expected.get("transient_retries", 2),
                       "retry_delay_seconds": expected.get("retry_delay", 2.0)}.items():
        if value is None:
            errors.append(f"missing expected decision rule: {key}")
        same(report.get("decision_rule", {}).get(key), value, key)
    same(margin.get("rule"), EVALUATION_POLICY["decision_rule"], "decision rule method")
    seed = trial.get("seed")
    if type(seed) is not int:
        errors.append("missing expected trial seed")
    else:
        same(report.get("seeds"), list(range(seed, seed + len(report.get("seeds", [])))), "trial seeds")
    decision = (validation.get("computed_decision") or {}).get("decision")
    clean = not errors and validation["evidence_complete"] and not validation["operational_errors"]
    authority = bool(clean and report.get("status") == "complete" and identity["scope"]["full_suite"]
                     and decision in {"retire", "retain"}
                     and (decision != "retire" or validation["positive_decision_sufficient"]))
    return {"errors": sorted(set(errors)), "operational_errors": validation["operational_errors"],
            "computed_decision": validation["computed_decision"], "scope": validation["scope"],
            "cache_authority": authority, "limitations": validation["limitations"],
            "positive_decision_sufficient": validation["positive_decision_sufficient"] and not errors}


def receipt_from_report(report_raw: bytes, experiment: dict[str, Any]) -> dict[str, Any]:
    """Derive a current receipt from raw producer evidence, never a summary label."""
    validation = _bound_validation(json.loads(report_raw), experiment)
    if validation["errors"]:
        raise ValueError("invalid retirement evidence: " + "; ".join(validation["errors"]))
    report_hash = sha256_bytes(report_raw)
    return {"schema_version": RECEIPT_VERSION, "kind": "instruction-retirement-evidence",
            "cache_key": experiment["cache_key"], "experiment": experiment["identity"],
            "raw_report_sha256": report_hash, "raw_evidence_path": f"raw/{report_hash}.json",
            **validation}


def write_receipt(directory: Path, receipt: dict[str, Any], report_raw: bytes) -> Path:
    """Append an evidence bundle; no live surfaces or old records are modified."""
    report_hash = sha256_bytes(report_raw)
    if not re.fullmatch(r"[a-f0-9]{64}", str(receipt.get("cache_key", ""))):
        raise ValueError("invalid receipt cache key")
    if receipt.get("raw_report_sha256") != report_hash or receipt.get("raw_evidence_path") != f"raw/{report_hash}.json":
        raise ValueError("raw evidence bytes do not match receipt")
    raw = directory / "raw" / f"{report_hash}.json"
    target = directory / f"{receipt['cache_key']}-{report_hash}.json"
    for path, data in ((raw, report_raw), (target, (json.dumps(receipt, indent=2) + "\n").encode())):
        if not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError("receipt output escapes evidence bundle")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as stream:
                stream.write(data)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ValueError("append-only evidence collision")
    return target


def load_receipts(path: Path, experiments: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Old formats remain historical; current evidence is revalidated on read."""
    result: dict[str, Any] = {"exact": {}, "equivalent": {}, "historical": [], "invalid": [], "diagnostic": [], "conflicts": []}
    groups: dict[str, list[dict[str, Any]]] = {}
    for candidate in sorted(path.glob("*.json")) if path.is_dir() else []:
        try:
            if candidate.is_symlink():
                raise ValueError("receipt must not be a symbolic link")
            value = json.loads(candidate.read_bytes())
            if not isinstance(value, dict):
                raise ValueError("receipt must be an object")
            if value.get("schema_version") in {1, 2}:
                result["historical"].append({"path": str(candidate), "recorded_decision": value.get("decision"),
                                             "cache_key": value.get("cache_key"), "authority": False})
                continue
            if value.get("schema_version") != RECEIPT_VERSION or value.get("kind") != "instruction-retirement-evidence":
                raise ValueError("unknown current receipt format")
            key = value.get("cache_key")
            experiment = (experiments or {}).get(key)
            if experiment is None:
                result["diagnostic"].append({"path": str(candidate), "reason": "no current exact experiment"})
                continue
            if value.get("experiment") != experiment["identity"] or canonical_hash(value["experiment"]) != key:
                raise ValueError("receipt experiment identity mismatch")
            raw_hash = value.get("raw_report_sha256")
            if not isinstance(raw_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", raw_hash):
                raise ValueError("invalid raw report digest")
            if value.get("raw_evidence_path") != f"raw/{raw_hash}.json":
                raise ValueError("raw report must be in this evidence bundle")
            raw_path = candidate.parent / "raw" / f"{raw_hash}.json"
            if not raw_path.resolve().is_relative_to(candidate.parent.resolve()):
                raise ValueError("raw report escapes evidence bundle")
            raw = raw_path.read_bytes()
            if sha256_bytes(raw) != raw_hash:
                raise ValueError("raw report digest mismatch")
            derived = receipt_from_report(raw, experiment)
            if value != derived:
                raise ValueError("recorded receipt differs from revalidated evidence")
            if derived["cache_authority"]:
                groups.setdefault(key, []).append(derived)
            else:
                result["diagnostic"].append({"path": str(candidate), "decision": derived["computed_decision"],
                                             "operational_errors": derived["operational_errors"], "authority": False})
        except (OSError, ValueError, TypeError, KeyError) as exc:
            result["invalid"].append({"path": str(candidate), "reason": str(exc)})
    for key, receipts in groups.items():
        decisions = {row["computed_decision"]["decision"] for row in receipts}
        if len(decisions) != 1:
            result["conflicts"].append({"cache_key": key, "decisions": sorted(decisions)})
        else:
            result["exact"][key] = receipts[0]
    return result


def normalized(text: str) -> str:
    return " ".join(text.split()).casefold()


def build_plan(repo: Path, manifest: dict[str, Any], stack: dict[str, Any], trigger: str,
               receipts_dir: Path, max_batches: int) -> dict[str, Any]:
    _validate_manifest(repo, manifest)
    if max_batches < 0:
        raise ValueError("max-batches must be non-negative")
    rows, owners, experiments = [], {}, {}
    for unit in manifest["units"]:
        row = {key: unit[key] for key in ("id", "class", "status", "path", "hosts", "suite", "priority")}
        row.update(selected_this_run=False, reasons=[])
        if unit["status"] == "retired":
            action = "skip-retired"
        elif unit["status"] == "reference":
            action = "reference-source-review"
        elif stack["host"] not in unit["hosts"]:
            action = "skip-host"
        elif unit["class"] in PROTECTED:
            action = "protected-manual"
        elif unit["class"] not in MODEL_SENSITIVE:
            action = "owner-specific-review" if trigger in unit["retest_on"] else "skip-trigger"
        else:
            text = unit_text(repo, unit)
            duplicate = owners.setdefault(normalized(text), unit["id"])
            row["bytes"] = len(text.encode())
            if duplicate != unit["id"]:
                action = "static-duplicate-review"
            elif trigger not in unit["retest_on"]:
                action = "skip-trigger"
            elif (stack["host"] not in SUPPORTED_HOSTS or stack.get("judge_host", stack["host"]) not in SUPPORTED_HOSTS
                  or stack.get("tool_policy") != "none"):
                action = "unsupported-runtime"
            else:
                experiment = build_experiment(repo, unit, stack)
                row.update(cache_key=experiment["cache_key"], experiment=experiment["identity"])
                experiments[experiment["cache_key"]] = experiment
                action = "behavior-ablation"
        row["action"] = action
        row["reasons"].append(action)
        rows.append(row)
    receipts = load_receipts(receipts_dir, experiments)
    conflicts = {row["cache_key"] for row in receipts["conflicts"]}
    for row in rows:
        key = row.get("cache_key")
        if key in conflicts:
            row["action"] = "receipt-conflict"
        elif key in receipts["exact"]:
            row["action"] = "cached-" + receipts["exact"][key]["computed_decision"]["decision"]
    suites, selected = [], []
    for row in sorted((r for r in rows if r["action"] == "behavior-ablation"), key=lambda r: (-r["priority"], -r["bytes"], r["id"])):
        if row["suite"] not in suites:
            if len(suites) >= max_batches:
                continue
            suites.append(row["suite"])
        row["selected_this_run"] = True
        selected.append(row["id"])
    return {"schema_version": 2, "trigger": trigger, "stack": stack, "manifest_sha256": canonical_hash(manifest),
            "harness_sha256": harness_hash(repo / "tools/eval.py"), "evaluation_policy": EVALUATION_POLICY,
            "selected_suites": suites, "selected_units": selected, "units": rows,
            "receipt_diagnostics": {key: value for key, value in receipts.items() if key not in {"exact", "equivalent"}},
            "scope": {"runtime_lane": LANE, "projection": "inline-linked-text-only", "live_mutation": False,
                      "cross_host_reuse": "unsupported without a separate verified equivalence consumer"}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--receipts-dir", type=Path)
    parser.add_argument("--trigger", default="model-release")
    parser.add_argument("--host", required=True)
    parser.add_argument("--runtime")
    parser.add_argument("--judge-host")
    parser.add_argument("--judge-runtime")
    for field in ("model", "provider", "reasoning"):
        parser.add_argument("--" + field, required=True)
    for field in ("model-snapshot", "provider-snapshot", "transport", "tool-schema", "equivalence-hash", "judge-model", "judge-provider"):
        parser.add_argument("--" + field)
    parser.add_argument("--tool-policy", default="none")
    parser.add_argument("--prompt-assembly", default="isolated-explicit-artifact-v2")
    parser.add_argument("--context-policy", default="fresh-session-per-output")
    parser.add_argument("--equivalence-group", default="host-scoped-retirement")
    parser.add_argument("--evaluator-identity", default="tools/eval.py")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--min-trials", type=int, default=2)
    parser.add_argument("--max-trials", type=int, default=8)
    parser.add_argument("--max-agent-runs", type=int, default=128)
    parser.add_argument("--transient-retries", type=int, default=2)
    parser.add_argument("--retry-delay", type=float, default=2.0)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--margin", type=float, default=0.1)
    parser.add_argument("--max-batches", type=int, default=2)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--materialize-dir", type=Path)
    parser.add_argument("--record-report", type=Path)
    parser.add_argument("--unit", help="Effective generic unit evaluated by --record-report")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.min_trials < 1 or args.max_trials < args.min_trials or not 0 < args.alpha < 1 or not 0 <= args.margin < 1:
        raise ValueError("invalid trial bounds or decision margin")
    repo = args.repo.resolve()
    manifest = json.loads((args.manifest or repo / "contracts/instruction-units.json").read_bytes())
    _validate_manifest(repo, manifest)
    receipts_dir = args.receipts_dir or repo / "evidence/instruction-retirement"
    fields = ("host", "runtime", "model", "provider", "reasoning", "model_snapshot", "provider_snapshot", "transport",
              "tool_schema", "tool_policy", "prompt_assembly", "context_policy", "equivalence_hash", "equivalence_group",
              "judge_host", "judge_runtime", "judge_model", "judge_provider", "max_agent_runs", "transient_retries", "retry_delay")
    stack = {field: getattr(args, field) for field in fields if getattr(args, field) is not None}
    stack.update(trial_design={"seed": args.seed, "min_trials": args.min_trials, "max_trials": args.max_trials},
                 decision_margin={"alpha": args.alpha, "margin": args.margin, "rule": EVALUATION_POLICY["decision_rule"]})
    if args.case_ids:
        stack["case_ids"] = args.case_ids
    units = {unit["id"]: unit for unit in manifest["units"]}
    if args.record_report:
        unit = units.get(args.unit)
        if unit is None or unit["status"] != "effective" or unit["class"] not in MODEL_SENSITIVE or args.host not in unit["hosts"]:
            raise ValueError("record-report requires an effective generic unit on the selected host")
        experiment = build_experiment(repo, unit, stack)
        raw = args.record_report.read_bytes()
        receipt = receipt_from_report(raw, experiment)
        path = write_receipt(receipts_dir, receipt, raw)
        result = {"receipt": str(path), "cache_authority": receipt["cache_authority"], "decision": receipt["computed_decision"]}
    else:
        result = build_plan(repo, manifest, stack, args.trigger, receipts_dir, args.max_batches)
        if args.materialize_dir:
            rows = {row["id"]: row for row in result["units"]}
            for unit_id in result["selected_units"]:
                frozen = build_experiment(repo, units[unit_id], stack, args.materialize_dir / unit_id)
                if frozen["cache_key"] != rows[unit_id]["cache_key"]:
                    raise ValueError("experiment changed between planning and materialization")
                rows[unit_id].update({key: frozen[key] for key in ("baseline_candidate_path", "candidate_path")})
    payload = json.dumps(result, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
