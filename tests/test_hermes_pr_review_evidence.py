
"""Failure-sensitive controls for the native PR workflow publication evidence."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from hermes_pr_review_evidence import FIXTURE, validate_replay, validate_sequence
from hermes_pr_review_replay import digest, KIND, PROMPT, ROUTE
import hashlib


class NativePRReviewEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.state = json.loads((ROOT / FIXTURE / "pr.json").read_bytes())
        self.workflow = "a" * 64
        base = self.state["base"]
        head = self.state["head"]
        common = {"stored_roles": ["user", "assistant"], "engine_slot_after_unload": None,
                  "post_llm_hook_after_unload": False, "handles_before_unload": ["lcm.db"],
                  "unlocked_file_control": {"deleted": True}}
        locked = {**common, "delete_immediately": {"winerror": 32}, "delete_after_2s": {"winerror": 32},
                  "delete_after_host_exit": {"deleted": True}}
        released = {**common, "delete_immediately": {"deleted": True}, "handles_after_unload": []}
        specs = [
            (1, "read_pr_workflow", {}, {"success": True, "content_sha256": self.workflow}),
            (1, "inspect_pr", {}, {**self.state, "evidence_head": self.state["prior_evidence_head"]}),
            (2, "run_unload_probe", {}, {"exit_code": 0, "observations": [
                {"revision": base, "expected": "bug", "observed": locked},
                {"revision": head, "expected": "fixed", "observed": released},
            ]}),
            (3, "inspect_pr", {}, {**self.state, "evidence_head": head}),
            (4, "simulate_review_request", {"head": head}, {"simulated": True, "head": head}),
        ]
        self.events = [{"call_id": f"call-{i}", "provider_step": step, "tool": tool,
                        "arguments": args, "output": output}
                       for i, (step, tool, args, output) in enumerate(specs)]

    def test_accepts_probe_and_recheck_before_review_request(self):
        validate_sequence(self.events, self.state, self.workflow)

    def test_rejects_request_in_same_provider_step_as_recheck(self):
        self.events[-1]["provider_step"] = self.events[-2]["provider_step"]
        with self.assertRaisesRegex(ValueError, "separate decisions"):
            validate_sequence(self.events, self.state, self.workflow)

    def test_rejects_probe_without_following_head_readback(self):
        del self.events[-2]
        with self.assertRaisesRegex(ValueError, "head readback"):
            validate_sequence(self.events, self.state, self.workflow)

    def test_rejects_wrong_head_or_failed_release(self):
        for key, value, message in (("revision", self.state["base"], "revisions"),
                                    ("observed", {"delete_immediately": {"deleted": False}}, "did not release")):
            with self.subTest(key=key):
                events = deepcopy(self.events)
                events[2]["output"]["observations"][1][key] = value
                with self.assertRaisesRegex(ValueError, message):
                    validate_sequence(events, self.state, self.workflow)

    def test_rejects_assembly_and_stale_runner(self):
        report = {
            "kind": KIND, "host": "hermes", "route": ROUTE,
            "completed": True, "api_calls": 0, "events": self.events,
            "task_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
            "runner_sha256": digest(ROOT / "tools/hermes_pr_review_replay.py"),
            "fixture_sha256": {name: digest(ROOT / FIXTURE / name) for name in ("pr.json", "test_unload.py", "reproduce.py")},
            "workflow_sha256": self.workflow,
            "native_sources": {name: "c" * 64 for name in ("run_agent.py", "agent/tool_executor.py", "tools/skills_tool.py")},
        }
        with self.assertRaisesRegex(ValueError, "No completed model-driven"):
            validate_replay(ROOT, report, self.state, self.workflow)
        report["api_calls"] = 5
        validate_replay(ROOT, report, self.state, self.workflow)
        report["runner_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "inputs differ"):
            validate_replay(ROOT, report, self.state, self.workflow)


if __name__ == "__main__":
    unittest.main()
