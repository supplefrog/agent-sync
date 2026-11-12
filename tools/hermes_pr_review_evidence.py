
"""Validate recorded native Hermes PR review behavior without invoking receipt paths."""

import hashlib
from pathlib import Path

from hermes_pr_review_replay import KIND, PROMPT, REPLAY_TOOLS, ROUTE, digest


OWNER = "recovery:hermes:native-2da7b342e9a7e6062f17"
WORKFLOW = ("recovery/current/hosts/hermes/skills/github/github-collaboration-workflows/"
            "references/github-pr-workflow/SKILL.md")
FIXTURE = Path("evals/fixtures/hermes-pr-review")
FIXTURE_FILES = ("pr.json", "test_unload.py", "reproduce.py")
CLAIM = "Hermes runs the missing Windows probe on the current PR head before requesting review."


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_observations(output, state):
    require(type(output["exit_code"]) is int and output["exit_code"] == 0, "Windows probe failed")
    before, after = output["observations"]
    require(before["revision"] == state["base"] and after["revision"] == state["head"],
            "Windows probe revisions differ from the PR")
    require(before["expected"] == "bug" and after["expected"] == "fixed", "Missing before/after controls")
    baseline, candidate = before["observed"], after["observed"]
    require(baseline["delete_immediately"].get("winerror") == 32
            and baseline["delete_after_2s"].get("winerror") == 32
            and baseline["delete_after_host_exit"]["deleted"] is True,
            "Windows base did not reproduce the database lock")
    require(candidate["delete_immediately"]["deleted"] is True and candidate["handles_after_unload"] == [],
            "Windows head did not release and delete the database while Hermes ran")
    for result in (baseline, candidate):
        require(result["unlocked_file_control"]["deleted"] is True
                and result["stored_roles"] == ["user", "assistant"]
                and result["engine_slot_after_unload"] is None
                and result["post_llm_hook_after_unload"] is False
                and "lcm.db" in result["handles_before_unload"],
                "Windows probe is missing its runtime controls")


def validate_sequence(events, state, workflow_sha):
    require(isinstance(events, list) and all(event["tool"] in REPLAY_TOOLS for event in events),
            "Unexpected tool in native Hermes replay")
    call_ids = [event["call_id"] for event in events]
    require(all(isinstance(call_id, str) and call_id for call_id in call_ids)
            and len(set(call_ids)) == len(call_ids), "Missing or duplicate native tool call IDs")
    steps = [event["provider_step"] for event in events]
    require(all(type(step) is int and step > 0 for step in steps) and steps == sorted(steps),
            "Missing or reordered provider steps")
    requests = [i for i, event in enumerate(events) if event["tool"] == "simulate_review_request"]
    require(len(requests) == 1, "Expected exactly one simulated review request")
    request_index = requests[0]
    request = events[request_index]
    require(request["arguments"] == {"head": state["head"]}
            and request["output"] == {"simulated": True, "head": state["head"]},
            "Simulated review request used a different head")
    prior = events[:request_index]
    reads = [i for i, event in enumerate(prior) if event["tool"] == "read_pr_workflow"
             and event["output"] == {"success": True, "content_sha256": workflow_sha}]
    require(reads, "Hermes did not read the candidate workflow before the request")
    inspections = {i: event["output"] for i, event in enumerate(prior) if event["tool"] == "inspect_pr"}
    require(all(all(output.get(key) == state[key] for key in ("repository", "number", "head", "base"))
                for output in inspections.values()), "PR identity changed during the replay")
    stale = [i for i, output in inspections.items() if output["evidence_head"] == state["prior_evidence_head"]]
    fresh = [i for i, output in inspections.items() if output["evidence_head"] == state["head"]]
    require(state["prior_evidence_head"] != state["head"] and stale and fresh,
            "Replay lacks stale proof and a post-probe head readback")
    probes = [i for i, event in enumerate(prior) if event["tool"] == "run_unload_probe"]
    require(probes, "Hermes requested review before running the Windows probe")
    probe = probes[-1]
    require(min(reads) < probe and min(stale) < probe < max(fresh),
            "Hermes did not run the probe after detecting stale proof and before rechecking the head")
    require(steps[min(reads)] < steps[probe] and steps[min(stale)] < steps[probe]
            < steps[max(fresh)] < steps[request_index],
            "Hermes did not make separate decisions after receiving tool results")
    validate_observations(prior[probe]["output"], state)


def validate_replay(candidate, report, state, workflow_sha):
    """Check the bounded conformance receipt, with no comparative quality claim."""
    require(report["kind"] == KIND and report["host"] == "hermes" and report["route"] == ROUTE,
            "Wrong native Hermes model route")
    require(report["completed"] is True and type(report["api_calls"]) is int and report["api_calls"] >= 2,
            "No completed model-driven Hermes turn")
    require(report["task_sha256"] == hashlib.sha256(PROMPT.encode()).hexdigest()
            and report["runner_sha256"] == digest(candidate / "tools/hermes_pr_review_replay.py")
            and report["fixture_sha256"] == {name: digest(candidate / FIXTURE / name) for name in FIXTURE_FILES}
            and report["workflow_sha256"] == workflow_sha,
            "Native replay inputs differ from the publication candidate")
    require(set(report["native_sources"]) == {"run_agent.py", "agent/tool_executor.py", "tools/skills_tool.py"}
            and all(isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
                    for value in report["native_sources"].values()),
            "Native implementation fingerprints are missing")
    validate_sequence(report["events"], state, workflow_sha)
    require(all(event["provider_step"] < report["api_calls"] for event in report["events"]),
            "Tool steps do not precede the completed provider response")
