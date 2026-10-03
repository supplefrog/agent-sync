import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from frontend_gate import check

ROOT = Path(__file__).parent


class GateTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((ROOT / "contract.example.json").read_text())
        self.obs = json.loads((ROOT / "observations.clean.json").read_text())

    def result(self, index):
        return check({"checks": [self.contract["checks"][index]]}, self.obs)

    def test_clean_including_secondary_menu_action(self):
        self.assertEqual(check(self.contract, self.obs)["status"], "pass")

    def test_moving_whole_control_fails_even_with_fixed_caret_origin(self):
        m = self.obs["states"]["open"]["controls"]["toggle"]
        m["rect"]["x"] += 12
        m["caret_origin"] = {"x": 30, "y": 50}
        self.assertEqual(self.result(0)["status"], "fail")

    def test_resize_fails_with_fixed_top_left(self):
        self.obs["states"]["open"]["controls"]["toggle"]["rect"]["width"] += 8
        self.assertEqual(self.result(0)["status"], "fail")

    def test_pairwise_comparison_detects_opposite_tolerance_offsets(self):
        self.contract["checks"][0]["states"].append("third")
        self.obs["states"]["third"] = copy.deepcopy(self.obs["states"]["open"])
        self.obs["states"]["open"]["controls"]["toggle"]["rect"]["x"] += 1
        self.obs["states"]["third"]["controls"]["toggle"]["rect"]["x"] -= 1
        self.assertEqual(self.result(0)["status"], "fail")

    def test_responsive_or_deliberate_movement_without_promise_passes(self):
        self.contract["checks"][0]["promised"] = False
        self.obs["states"] = {}  # Geometry is not required for an excluded promise.
        self.assertEqual(self.result(0)["status"], "pass")

    def test_partial_visibility_does_not_prove_actual_point_reachable(self):
        m = self.obs["states"]["menu-open"]["controls"]["export"]
        m["effective_clip_rect"]["height"] = 160  # top 10px visible, actual use point clipped
        self.assertEqual(self.result(1)["status"], "fail")

    def test_occlusion_and_disabled_action_fail(self):
        m = self.obs["states"]["menu-open"]["controls"]["export"]
        for field in ("enabled", "hit_target_or_descendant"):
            with self.subTest(field=field):
                m[field] = False
                self.assertEqual(self.result(1)["status"], "fail")
                m[field] = True

    def test_lost_and_repeated_taps_fail(self):
        run = self.obs["runs"]["toggle-sequence"]
        events = copy.deepcopy(run["events"])
        for replacement in ([], events[:1], events + [events[0]]):
            with self.subTest(events=replacement):
                run["events"] = replacement
                self.assertEqual(self.result(2)["status"], "fail")

    def test_wrong_late_or_unrequested_event_fails(self):
        run = self.obs["runs"]["toggle-sequence"]
        clean = copy.deepcopy(run["events"])
        for field, value in (("to_state", "closed"), ("time_ms", 351), ("request_id", "unknown")):
            with self.subTest(field=field):
                run["events"] = copy.deepcopy(clean)
                run["events"][0][field] = value
                self.assertEqual(self.result(2)["status"], "fail")

    def test_short_or_incomplete_capture_is_incomplete_not_loss(self):
        run = self.obs["runs"]["toggle-sequence"]
        run["capture_end_ms"] = 600
        self.assertEqual(self.result(2)["status"], "incomplete")
        run["capture_end_ms"] = 2000
        run["capture_complete"] = False
        self.assertEqual(self.result(2)["status"], "incomplete")

    def test_transition_end_jump_fails(self):
        self.obs["transitions"]["panel-open"]["settled_rect"]["height"] += 6
        self.assertEqual(self.result(3)["status"], "fail")

    def test_early_settled_sample_is_incomplete(self):
        self.obs["transitions"]["panel-open"]["settled_time_ms"] = 450
        self.assertEqual(self.result(3)["status"], "incomplete")

    def test_missing_measurement_for_each_kind_is_incomplete(self):
        removals = [
            (self.obs["states"]["open"]["controls"]["toggle"], "rect"),
            (self.obs["states"]["menu-open"]["controls"]["export"], "hit_target_or_descendant"),
            (self.obs["runs"]["toggle-sequence"], "events"),
            (self.obs["transitions"]["panel-open"], "end_rect")]
        for i, (obj, key) in enumerate(removals):
            with self.subTest(kind=i):
                value = obj.pop(key)
                self.assertEqual(self.result(i)["status"], "incomplete")
                obj[key] = value

    def test_invalid_numbers_and_tolerances_are_incomplete(self):
        for value in (True, float("nan"), float("inf"), 10**400, "20"):
            self.obs["states"]["open"]["controls"]["toggle"]["rect"]["x"] = value
            self.assertEqual(self.result(0)["status"], "incomplete")
        self.contract["checks"][1]["min_point_clearance_px"] = -1
        self.assertEqual(self.result(1)["status"], "incomplete")

    def test_tolerance_boundary_passes_and_no_tolerance_default_exists(self):
        self.obs["states"]["open"]["controls"]["toggle"]["rect"]["x"] += 1
        self.assertEqual(self.result(0)["status"], "pass")
        del self.contract["checks"][0]["max_edge_delta_px"]
        self.assertEqual(self.result(0)["status"], "incomplete")

    def test_empty_unknown_duplicate_contracts_do_not_pass(self):
        for c in ({"checks": []}, {"checks": [{"id": "x", "kind": "unknown"}]},
                  {"checks": [self.contract["checks"][0]] * 2}):
            self.assertEqual(check(c, self.obs)["status"], "incomplete")

    def test_fail_retains_incomplete_check(self):
        self.obs["states"]["open"]["controls"]["toggle"]["rect"]["x"] += 10
        del self.obs["runs"]
        report = check(self.contract, self.obs)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["checks"][2]["status"], "incomplete")

    def test_null_state_names_and_nonstring_ids_are_incomplete(self):
        run = self.obs["runs"]["toggle-sequence"]
        run["requests"][0]["expected_state"] = None
        run["events"][0]["to_state"] = None
        self.assertEqual(self.result(2)["status"], "incomplete")
        self.contract["checks"][0]["id"] = 1
        self.assertEqual(self.result(0)["status"], "incomplete")

    def test_partial_control_with_reachable_point_passes(self):
        m = self.obs["states"]["menu-open"]["controls"]["export"]
        m["effective_clip_rect"]["height"] = 180
        self.assertEqual(self.result(1)["status"], "pass")

    def test_deliberate_animation_endpoint_within_tolerance_passes(self):
        m = self.obs["transitions"]["panel-open"]
        m["start_rect"] = {"x": 20, "y": 80, "width": 250, "height": 1}
        m["settled_rect"]["height"] += 1
        self.assertEqual(self.result(3)["status"], "pass")

    def test_cli_reports_all_statuses_with_exit_codes(self):
        for status, code, fixture in (("pass", 0, "clean"), ("fail", 1, "bad"), ("incomplete", 2, "missing")):
            with self.subTest(status=status):
                p = subprocess.run([sys.executable, str(ROOT / "frontend_gate.py"),
                                    str(ROOT / "contract.example.json"), str(ROOT / f"observations.{fixture}.json")],
                                   capture_output=True, text=True)
                self.assertEqual(p.returncode, code, p.stderr)
                self.assertEqual(json.loads(p.stdout)["status"], status)

    def test_unchanged_event_does_not_establish_response(self):
        run = self.obs["runs"]["toggle-sequence"]
        run["events"][0]["to_state"] = run["events"][0]["from_state"]
        self.assertEqual(self.result(2)["status"], "fail")

    def test_intentional_noop_needs_a_different_check(self):
        run = self.obs["runs"]["toggle-sequence"]
        run["requests"][0]["expected_state"] = run["requests"][0]["from_state"]
        run["events"][0]["to_state"] = run["events"][0]["from_state"]
        self.assertEqual(self.result(2)["status"], "incomplete")

    def test_derived_overflow_is_structured_incomplete(self):
        m = self.obs["states"]["open"]["controls"]["toggle"]["rect"]
        m["x"], m["width"] = 1e308, 1e308
        self.assertEqual(self.result(0)["status"], "incomplete")
        m["x"], m["width"] = -1e308, 10
        self.obs["states"]["closed"]["controls"]["toggle"]["rect"]["x"] = 1e308
        self.assertEqual(self.result(0)["status"], "incomplete")


if __name__ == "__main__":
    unittest.main()
