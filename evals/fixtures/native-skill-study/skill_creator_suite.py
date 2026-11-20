"""Prepare the matched Skill Creator study using existing handoff fixture controls."""
import argparse
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from evaluation_artifact_pilot import sha, tree
from evaluation_measurement import digest


def make_suite(run, upstream, model, reasoning, quota):
    case = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"][0]
    assert case["id"] == "create-handoff"
    fixture = HERE / case["fixture"]
    oracle = HERE / "oracle.py"
    controls = run / "controls"
    accepted = HERE / "blind-quality" / "create-handoff"
    for label in ("A", "B"):
        shutil.copytree(fixture, controls / label)
        shutil.copytree(accepted / label / "deliverables", controls / label / "deliverables")
    catalog = sorted(digest(tree(controls / label)) for label in ("A", "B"))
    control_specs = [
        {"fixture": str(controls / label), "expected_pass": True,
         "rationale": "Previously blind-reviewed usable handoff and reusable skill.",
         "executable_distinctness_review": {
             "source_tree_sha256": digest(tree(controls / label)), "comparison_source_trees_sha256": catalog,
             "oracle_sha256": sha(oracle), "independent": True, "reviewer": "historical blind quality review",
             "decision": "substantively-different",
             "rationale": "Previously reviewed separate authored outputs with different decision procedures and handoff structures."}}
        for label in ("A", "B")
    ]
    control_specs.append({"fixture": str(fixture), "expected_pass": False,
                          "rationale": "Unchanged task inputs omit both required deliverables."})
    case.update(fixture=str(fixture), artifact_controls=control_specs,
                task_qualification={
                    "workload_source": "Existing synthetic customer-trial handoff file task",
                    "claim": "Skill authoring guidance improves the draft package and example",
                    "representative_demands": "Reconcile trial evidence and translate team notes into reusable guidance",
                    "scope_limits": "Single draft and example. No assessment of the full revision loop or deployment.",
                    "reviewer": "Agent Sync Cloud study", "outcome_driven": True, "solution_open": True,
                    "output_kind": "text"},
                workflow_budget={
                    "claim": "Draft artifact correctness and handoff quality",
                    "required_quality": "Both files satisfy the frozen rubric and preserve the source packet",
                    "verification_and_revision": "Time to read the packet, create, inspect, and revise both files",
                    "adequacy_rationale": "Four text sources and two Markdown outputs within each five-minute trial",
                    "reviewer": "Agent Sync Cloud study"})
    return {
        "purpose": "omp-artifact-study", "agent": "omp", "provider": "openai-codex",
        "model": model, "reasoning": reasoning, "quota_remaining": quota,
        "max_workers": 1, "max_iterations": 24, "timeout": 300,
        "oracle": str(oracle), "workspace_root": str(run / "workspaces"),
        "arms": [
            {"id": "without-skill", "instructions": None},
            {"id": "legacy", "instructions": str(ROOT / "skills/skill-writing/SKILL.md")},
            {"id": "anthropic", "instructions": str(upstream)},
            {"id": "agent-sync", "instructions": str(ROOT / "skills/skill-creator/SKILL.md")},
        ],
        "cases": [case],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True, help="Pinned upstream SKILL.md")
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning", default="medium")
    parser.add_argument("--observed-quota", type=float)
    args = parser.parse_args()
    run = args.run.resolve()
    run.mkdir(parents=True)
    (run / "suite.json").write_text(
        json.dumps(make_suite(run, args.upstream.resolve(), args.model, args.reasoning, args.observed_quota), indent=2)
        + "\n", encoding="utf-8")
