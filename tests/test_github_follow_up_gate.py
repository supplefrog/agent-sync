from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills" / "github-follow-up" / "scripts" / "github-follow-up-gate.py"
REPLACEMENT_SUITE = REPO / "evals" / "github-follow-up-replacement-learning.json"


def load_module():
    spec = importlib.util.spec_from_file_location("github_follow_up_gate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def summary(number: int, state: str = "OPEN") -> dict:
    return {
        "number": number,
        "title": f"PR {number}",
        "url": f"https://github.com/acme/widget/pull/{number}",
        "repository": {"nameWithOwner": "acme/widget"},
        "updatedAt": "2026-08-15T12:00:00Z",
        "state": state,
        "commentsCount": 0,
        "isDraft": False,
    }


def detail(state: str, *, head: str = "head-1", merged_at: str | None = None) -> dict:
    return {
        "state": state,
        "isDraft": False,
        "updatedAt": "2026-08-15T12:00:00Z",
        "closedAt": "2026-08-15T12:00:00Z" if state != "OPEN" else None,
        "mergedAt": merged_at,
        "mergeCommit": {"oid": "merge-1"} if merged_at else None,
        "headRefName": "fix/thing",
        "headRefOid": head,
        "baseRefName": "main",
        "mergeable": "UNKNOWN",
        "reviewDecision": None,
        "closingIssuesReferences": [
            {
                "number": 7,
                "url": "https://github.com/acme/widget/issues/7",
                "repository": {"nameWithOwner": "acme/widget"},
            }
        ],
        "comments": [],
        "reviews": [],
        "statusCheckRollup": [],
    }


class GithubFollowUpGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = load_module()

    def test_closed_unmerged_pr_is_compact_and_keeps_related_issue(self):
        with mock.patch.object(self.gate, "run_gh", return_value=detail("CLOSED")), mock.patch.object(
            self.gate, "fetch_pr_graph", side_effect=AssertionError("terminal PR must not fetch review graph")
        ):
            item = self.gate.inspect_pr(summary(1, "CLOSED"), "me")

        self.assertEqual(item["terminalOutcome"], "closed-unmerged")
        self.assertEqual(item["relatedIssues"][0]["key"], "issue:acme/widget#7")
        self.assertEqual(item["reviewThreadCount"], 0)

    def test_merged_pr_is_terminal_and_records_merge_commit(self):
        merged_at = "2026-08-15T12:00:00Z"
        with mock.patch.object(self.gate, "run_gh", return_value=detail("MERGED", merged_at=merged_at)), mock.patch.object(
            self.gate, "fetch_pr_graph", side_effect=AssertionError("terminal PR must not fetch review graph")
        ):
            item = self.gate.inspect_pr(summary(1, "CLOSED"), "me")

        self.assertEqual(item["terminalOutcome"], "merged")
        self.assertEqual(item["mergeCommitOid"], "merge-1")
        self.assertEqual(item["mergedAt"], merged_at)

    def test_nullable_github_collections_are_treated_as_empty(self):
        nullable = detail("CLOSED")
        nullable.update(
            comments=None,
            reviews=None,
            statusCheckRollup=None,
            closingIssuesReferences=None,
        )
        with mock.patch.object(self.gate, "run_gh", return_value=nullable):
            item = self.gate.inspect_pr(summary(1, "CLOSED"), "me")

        self.assertEqual(item["comments"], [])
        self.assertEqual(item["reviews"], [])
        self.assertEqual(item["checks"], [])
        self.assertEqual(item["relatedIssues"], [])

    def test_reopened_or_force_pushed_pr_uses_current_open_state(self):
        graph = ({"mergeable": "MERGEABLE", "reviewDecision": "REVIEW_REQUIRED"}, [], 0)
        with mock.patch.object(self.gate, "run_gh", return_value=detail("OPEN", head="head-2")), mock.patch.object(
            self.gate, "fetch_pr_graph", return_value=graph
        ) as fetch:
            item = self.gate.inspect_pr(summary(1), "me")

        fetch.assert_called_once()
        self.assertIsNone(item["terminalOutcome"])
        self.assertEqual(item["state"], "OPEN")
        self.assertEqual(item["headRefOid"], "head-2")

    def test_collect_deduplicates_open_and_recent_prs_and_keeps_terminal_outcome(self):
        open_pr = summary(1)
        closed_pr = summary(2, "CLOSED")

        def fake_gh(args):
            if args[:2] == ["api", "user"]:
                return {"login": "me"}
            if args[:2] == ["search", "issues"]:
                return []
            if args[:2] == ["search", "prs"] and "--state" in args:
                return [open_pr]
            if args[:2] == ["search", "prs"]:
                return [open_pr, closed_pr]
            raise AssertionError(args)

        def fake_inspect(item, viewer):
            self.assertEqual(viewer, "me")
            return {
                "kind": "pr",
                "key": f"pr:acme/widget#{item['number']}",
                "repo": "acme/widget",
                "number": item["number"],
                "terminalOutcome": "closed-unmerged" if item["number"] == 2 else None,
            }

        with mock.patch.object(self.gate, "run_gh", side_effect=fake_gh), mock.patch.object(
            self.gate, "inspect_pr", side_effect=fake_inspect
        ) as inspect:
            snapshot = self.gate.collect(45, 200)

        self.assertEqual(snapshot["schema"], 2)
        self.assertEqual(set(snapshot["items"]), {"pr:acme/widget#1", "pr:acme/widget#2"})
        self.assertEqual(inspect.call_count, 2)
        self.assertEqual(snapshot["items"]["pr:acme/widget#2"]["terminalOutcome"], "closed-unmerged")

    def test_terminal_transition_is_changed_instead_of_removed(self):
        old = {"kind": "pr", "key": "pr:acme/widget#1", "state": "OPEN", "headRefOid": "head-1"}
        new = {
            "kind": "pr",
            "key": "pr:acme/widget#1",
            "state": "CLOSED",
            "headRefOid": "head-1",
            "terminalOutcome": "closed-unmerged",
        }
        previous = {"snapshot": {"items": {old["key"]: old}}}
        current = {"items": {new["key"]: new}, "truncated": False}

        self.assertEqual(self.gate.changed_items(previous, current), [new])

    def test_each_truncated_inventory_source_is_named(self):
        current = {
            "items": {},
            "truncated": True,
            "truncatedSources": ["recent-authored-prs"],
        }
        changed = self.gate.changed_items({"snapshot": {"items": {}}}, current)

        self.assertEqual(changed[0]["key"], "inventory:truncated")
        self.assertEqual(changed[0]["truncatedSources"], ["recent-authored-prs"])

    def test_unchanged_tick_emits_wake_false_and_does_not_create_pending(self):
        snapshot = {
            "schema": 2,
            "viewer": "me",
            "lookbackDays": 45,
            "truncated": False,
            "truncatedSources": [],
            "items": {},
        }
        fingerprint = self.gate.fingerprint(snapshot)
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "state.json"
            state.write_text(json.dumps({"fingerprint": fingerprint, "snapshot": snapshot}), encoding="utf-8")
            stdout = io.StringIO()
            argv = [str(SCRIPT), "--state", str(state)]
            with mock.patch.object(self.gate, "collect", return_value=snapshot), mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
                rc = self.gate.main()

            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(stdout.getvalue()), {"wakeAgent": False})
            self.assertFalse(state.with_name("pending.json").exists())

    def test_failed_batch_cannot_acknowledge_a_different_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "state.json"
            pending = state.with_name("pending.json")
            pending.write_text(json.dumps({"fingerprint": "expected", "snapshot": {"items": {}}}), encoding="utf-8")
            argv = [str(SCRIPT), "--state", str(state), "--ack", "wrong"]
            with mock.patch.object(sys, "argv", argv):
                with self.assertRaisesRegex(RuntimeError, "missing or different"):
                    self.gate.main()

            self.assertFalse(state.exists())
            self.assertTrue(pending.exists())

    def test_replacement_learning_suite_covers_decision_boundaries(self):
        suite = json.loads(REPLACEMENT_SUITE.read_text(encoding="utf-8"))
        cases = {case["id"]: case for case in suite["cases"]}

        self.assertEqual(
            set(cases),
            {
                "closed-pr-merged-replacement",
                "same-issue-unrelated-merged-pr",
                "preference-without-technical-evidence",
                "winner-reveals-root-cause-test-lesson",
                "novel-winner-lesson-updates-existing-owner",
            },
        )
        self.assertEqual(
            {case["kind"] for case in cases.values()},
            {"representative", "near-miss", "adversarial", "held-out"},
        )
        self.assertTrue(any("current base" in criterion for criterion in cases["closed-pr-merged-replacement"]["criteria"]))
        self.assertTrue(any("unrelated" in criterion for criterion in cases["same-issue-unrelated-merged-pr"]["criteria"]))
        self.assertTrue(any("no workflow change" in criterion for criterion in cases["preference-without-technical-evidence"]["criteria"]))
        self.assertTrue(any("reusable" in criterion for criterion in cases["winner-reveals-root-cause-test-lesson"]["criteria"]))
        self.assertTrue(any("fresh held-out" in criterion for criterion in cases["novel-winner-lesson-updates-existing-owner"]["criteria"]))


if __name__ == "__main__":
    unittest.main()
