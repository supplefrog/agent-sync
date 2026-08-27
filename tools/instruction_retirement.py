#!/usr/bin/env python
"""Build a bounded, cache-aware instruction-retirement plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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


def unit_text(repo: Path, unit: dict[str, Any]) -> str:
    path = repo / unit["path"]
    text = path.read_text(encoding="utf-8")
    selector = unit.get("selector", {"kind": "whole-file"})
    kind = selector.get("kind")
    if kind == "whole-file":
        return text
    if kind == "heading":
        return section(text, selector["value"])
    raise ValueError(f"unsupported selector kind for {unit['id']}: {kind}")


def receipt_key(stack: dict[str, Any], unit_hash: str, suite_hash: str, harness_hash: str) -> str:
    return canonical_hash(
        {
            "stack": stack,
            "unit_sha256": unit_hash,
            "suite_sha256": suite_hash,
            "harness_sha256": harness_hash,
            "evaluation_policy": EVALUATION_POLICY,
        }
    )


def equivalence_receipt_key(
    stack: dict[str, Any], unit_hash: str, suite_hash: str, harness_hash: str
) -> str | None:
    equivalence_hash = stack.get("equivalence_hash")
    if not isinstance(equivalence_hash, str) or not equivalence_hash:
        return None
    return canonical_hash(
        {
            "equivalence_hash": equivalence_hash,
            "evaluator_identity": stack.get("evaluator_identity"),
            "trial_design": stack.get("trial_design"),
            "decision_margin": stack.get("decision_margin"),
            "unit_sha256": unit_hash,
            "suite_sha256": suite_hash,
            "harness_sha256": harness_hash,
            "evaluation_policy": EVALUATION_POLICY,
        }
    )


def load_receipts(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    receipts: dict[str, dict[str, dict[str, Any]]] = {"exact": {}, "equivalent": {}}
    if not path.is_dir():
        return receipts
    for candidate in sorted(path.glob("*.json")):
        try:
            value = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict) or value.get("schema_version") not in {1, 2}:
            continue
        if value.get("schema_version") == 2:
            raw_path = value.get("raw_evidence_path")
            if not isinstance(raw_path, str):
                continue
            raw_evidence = Path(raw_path)
            if not raw_evidence.is_absolute():
                raw_evidence = candidate.parent / raw_evidence
            if not raw_evidence.is_file():
                continue
        cache_key = value.get("cache_key")
        if isinstance(cache_key, str):
            receipts["exact"].setdefault(cache_key, value)
        equivalence_key = value.get("equivalence_cache_key")
        if (
            value.get("schema_version") == 2
            and isinstance(value.get("equivalence_hash"), str)
            and isinstance(equivalence_key, str)
        ):
            receipts["equivalent"].setdefault(equivalence_key, value)
    return receipts


def normalized(text: str) -> str:
    return " ".join(text.split()).casefold()


def build_plan(
    repo: Path,
    manifest: dict[str, Any],
    stack: dict[str, Any],
    trigger: str,
    receipts_dir: Path,
    max_batches: int,
) -> dict[str, Any]:
    harness = repo / "tools" / "eval.py"
    harness_hash = sha256_bytes(harness.read_bytes())
    receipts = load_receipts(receipts_dir)
    rows: list[dict[str, Any]] = []
    normalized_owners: dict[str, str] = {}

    for unit in manifest["units"]:
        text = unit_text(repo, unit)
        unit_hash = sha256_bytes(text.encode("utf-8"))
        suite = repo / unit["suite"]
        suite_hash = sha256_bytes(suite.read_bytes()) if suite.is_file() else "missing"
        key = receipt_key(stack, unit_hash, suite_hash, harness_hash)
        equivalence_key = equivalence_receipt_key(stack, unit_hash, suite_hash, harness_hash)
        cached = receipts["exact"].get(key)
        cached_by_equivalence = False
        if cached is None and equivalence_key is not None:
            cached = receipts["equivalent"].get(equivalence_key)
            cached_by_equivalence = cached is not None
        duplicate_of = normalized_owners.get(normalized(text))
        if duplicate_of is None:
            normalized_owners[normalized(text)] = unit["id"]

        classification = unit["class"]
        reasons: list[str] = []
        if duplicate_of and classification not in PROTECTED:
            action = "static-duplicate-review"
            reasons.append(f"exact normalized duplicate of {duplicate_of}")
        elif cached:
            action = f"cached-{cached.get('decision', 'inconclusive')}"
            reasons.append(
                "explicit cross-host equivalence receipt exists"
                if cached_by_equivalence
                else "exact host/stack/unit/suite/harness receipt exists"
            )
        elif classification in PROTECTED:
            action = "protected-manual"
            reasons.append("guarantee requires equivalent enforced owner and explicit approval")
        elif trigger not in unit.get("retest_on", []):
            action = "skip-trigger"
            reasons.append(f"{classification} does not reopen on {trigger}")
        elif classification in MODEL_SENSITIVE:
            action = "behavior-ablation"
            reasons.append("model-sensitive steering has no current exact receipt")
        else:
            action = "owner-specific-review"
            reasons.append(f"{classification} changed on an owning trigger")

        rows.append(
            {
                "id": unit["id"],
                "class": classification,
                "status": unit.get("status", "active"),
                "path": unit["path"],
                "hosts": unit.get("hosts", []),
                "suite": unit["suite"],
                "bytes": len(text.encode("utf-8")),
                "unit_sha256": unit_hash,
                "suite_sha256": suite_hash,
                "cache_key": key,
                "equivalence_cache_key": equivalence_key,
                "action": action,
                "priority": int(unit.get("priority", 0)),
                "reasons": reasons,
            }
        )

    behavior = sorted(
        (row for row in rows if row["action"] == "behavior-ablation"),
        key=lambda row: (-row["priority"], -row["bytes"], row["id"]),
    )
    suites: list[str] = []
    selected: list[str] = []
    for row in behavior:
        if row["suite"] not in suites:
            if len(suites) >= max_batches:
                continue
            suites.append(row["suite"])
        selected.append(row["id"])
    for row in rows:
        row["selected_this_run"] = row["id"] in selected

    return {
        "schema_version": 1,
        "trigger": trigger,
        "stack": stack,
        "manifest_sha256": canonical_hash(manifest),
        "harness_sha256": harness_hash,
        "evaluation_policy": EVALUATION_POLICY,
        "selected_suites": suites,
        "selected_units": selected,
        "estimated_generation_runs_before_judging": 2 * len(suites) + len(selected),
        "units": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--receipts-dir", type=Path)
    parser.add_argument("--trigger", default="model-release")
    parser.add_argument("--host", required=True)
    parser.add_argument("--runtime")
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-snapshot")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--provider-snapshot")
    parser.add_argument("--transport")
    parser.add_argument("--reasoning", required=True)
    parser.add_argument("--tool-policy", default="default")
    parser.add_argument("--tool-schema")
    parser.add_argument("--prompt-assembly", default="current-host")
    parser.add_argument("--context-policy")
    parser.add_argument("--evaluator-identity", default="tools/eval.py")
    parser.add_argument("--equivalence-hash")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--min-trials", type=int, default=2)
    parser.add_argument("--max-trials", type=int, default=8)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--margin", type=float, default=0.1)
    parser.add_argument("--max-batches", type=int, default=2)
    parser.add_argument("--materialize-dir", type=Path, help="Write full and leave-one-unit-out artifacts for selected units")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    manifest_path = args.manifest or repo / "contracts" / "instruction-units.json"
    receipts_dir = args.receipts_dir or repo / "evidence" / "instruction-retirement"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("units"), list):
        raise ValueError("unsupported instruction-unit manifest")
    if args.max_batches < 0:
        raise ValueError("max-batches must be non-negative")
    if args.min_trials < 1 or args.max_trials < args.min_trials:
        raise ValueError("trial bounds must satisfy 1 <= min-trials <= max-trials")
    if not 0 < args.alpha < 1 or not 0 <= args.margin < 1:
        raise ValueError("alpha and margin are outside their valid ranges")
    stack = {
        "host": args.host,
        "runtime": args.runtime,
        "model": args.model,
        "model_snapshot": args.model_snapshot,
        "provider": args.provider,
        "provider_snapshot": args.provider_snapshot,
        "transport": args.transport,
        "reasoning": args.reasoning,
        "tool_policy": args.tool_policy,
        "tool_schema": args.tool_schema,
        "prompt_assembly": args.prompt_assembly,
        "context_policy": args.context_policy,
        "evaluator_identity": args.evaluator_identity,
        "trial_design": {
            "seed": args.seed,
            "min_trials": args.min_trials,
            "max_trials": args.max_trials,
        },
        "decision_margin": {
            "alpha": args.alpha,
            "margin": args.margin,
            "rule": EVALUATION_POLICY["decision_rule"],
        },
    }
    if args.equivalence_hash:
        stack["equivalence_hash"] = args.equivalence_hash
    plan = build_plan(repo, manifest, stack, args.trigger, receipts_dir, args.max_batches)
    if args.materialize_dir:
        materialize_root = args.materialize_dir.resolve()
        units = {unit["id"]: unit for unit in manifest["units"]}
        rows = {row["id"]: row for row in plan["units"]}
        for unit_id in plan["selected_units"]:
            unit = units[unit_id]
            source = (repo / unit["path"]).resolve()
            target = materialize_root / unit_id
            target.mkdir(parents=True, exist_ok=True)
            selector = unit.get("selector", {"kind": "whole-file"})
            if selector["kind"] == "whole-file":
                minus = "# No additional candidate instructions\n"
            else:
                minus = without_section(source.read_text(encoding="utf-8"), selector["value"])
            minus_path = target / "minus.md"
            minus_path.write_text(minus, encoding="utf-8")
            rows[unit_id]["baseline_candidate_path"] = str(source)
            rows[unit_id]["candidate_path"] = str(minus_path)
    payload = json.dumps(plan, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
