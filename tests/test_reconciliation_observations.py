"""Audit the same non-mutating observations that complete sync leaves alone."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audit
import reconcile


def observations():
    return [
        {"surface": "skill-proposals", "host": "hermes", "pending_id": "a1b2c3d4",
         "target": "a1b2c3d4", "sha256": "a" * 64, "disposition": "review-required",
         "auto_apply_eligible": False},
        {"surface": "fleet", "target": "paseo", "destination": "local-windows:skill-root-1",
         "source_action": "observe-external", "change_class": "reviewed-external-owner",
         "disposition": "no-action", "auto_apply_eligible": False, "eligible_after_checks": False,
         "owner": "external:paseo", "external_owner": "paseo",
         "content_sha256": "b" * 64, "marker_sha256": "c" * 64},
    ]


class ReconciliationObservationTests(unittest.TestCase):
    def check(self, report, **kwargs):
        def run(argv, **unused):
            is_plan = Path(argv[1]).name == "reconcile.py"
            payload = report if is_plan else {"changes": [], "conflicts": []}
            return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")
        with patch.object(audit.subprocess, "run", side_effect=run):
            return audit.run_live_system_checks(ROOT, **kwargs)

    def test_pending_and_exact_external_observations_do_not_block_unrelated_sync(self):
        rows = observations()
        before = copy.deepcopy(rows)
        self.assertEqual([], self.check({"findings": rows, "summary": {"total": 2}}))
        self.assertEqual(before, rows)  # Neither proposal approval nor package mutation.

    def test_observations_remain_visible_as_public_safe_counts(self):
        counts = {}
        self.assertEqual([], self.check({"findings": observations(), "summary": {"total": 2}},
                                        observations=counts))
        self.assertEqual({"total": 2, "blocking": 0, "staged-skill-proposal": 1,
                          "reviewed-external-owner": 1}, counts)
        self.assertNotIn("a1b2c3d4", json.dumps(counts))

    def test_unknown_and_mutated_findings_still_block(self):
        good = observations()
        cases = [
            {"surface": "recovery", "disposition": "no-action"},
            {"surface": "fleet", "source_action": "unmanaged", "disposition": "no-action"},
            {**good[0], "auto_apply_eligible": True},
            {**good[0], "disposition": "approved"},
            {**good[0], "sha256": ""},
            {**good[0], "pending_id": "different"},
            {**good[1], "eligible_after_checks": True},
            {**good[1], "source_action": "unmanaged"},
            {**good[1], "change_class": "unknown"},
            {**good[1], "marker_sha256": ""},
            {**good[1], "owner": "skills/paseo"},
        ]
        for row in cases:
            with self.subTest(row=row):
                self.assertIn("reconciliation plan: unresolved findings",
                              self.check({"findings": good + [row], "summary": {"total": len(good) + 1}}))
                self.assertIsNone(reconcile.nonblocking_observation_kind(row))

    def test_incomplete_or_malformed_reports_fail_closed(self):
        cases = [{}, {"findings": {}}, {"findings": [None]},
                 {"findings": observations(), "summary": {"total": 3}},
                 {"findings": observations()},
                 *({"findings": observations(), "summary": summary}
                   for summary in (None, [], "bad", {}, {"total": True}, {"total": 2.0})),
                 {"findings": [], "summary": {"total": 0}, "changes": ["unresolved"]},
                 {"findings": [], "summary": {"total": 0}, "conflicts": ["unresolved"]}]
        for report in cases:
            with self.subTest(report=report):
                self.assertTrue(self.check(report))


if __name__ == "__main__":
    unittest.main()
