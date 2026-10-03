"""Deterministic, contract-scoped checks of supplied browser measurements."""
import argparse
import json
import math
from pathlib import Path


class Incomplete(ValueError):
    pass


def need(obj, key):
    if not isinstance(obj, dict) or key not in obj:
        raise Incomplete(f"Missing field: {key}")
    return obj[key]


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Incomplete("Expected a finite numeric measurement")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise Incomplete("Expected a finite numeric measurement")
    return value


def tolerance(c, key):
    n = number(need(c, key))
    if n < 0:
        raise Incomplete(f"Negative tolerance: {key}")
    return n


def rect(value):
    result = {k: number(need(value, k)) for k in ("x", "y", "width", "height")}
    if result["width"] <= 0 or result["height"] <= 0:
        raise Incomplete("Rectangle must have positive width and height")
    number(result["x"] + result["width"])
    number(result["y"] + result["height"])
    return result


def boolean(value):
    if not isinstance(value, bool):
        raise Incomplete("Expected a measured boolean")
    return value


def name(value):
    if not isinstance(value, str) or not value:
        raise Incomplete("Expected a nonempty string identifier/state")
    return value


def delta(a, b):
    # Compare all four edges: movement and size both affect the whole control.
    return number(max(abs(a["x"] - b["x"]), abs(a["y"] - b["y"]),
               abs(a["x"] + a["width"] - b["x"] - b["width"]),
               abs(a["y"] + a["height"] - b["y"] - b["height"])))


def control(obs, state, target):
    return need(need(need(need(obs, "states"), state), "controls"), target)


def evaluate(c, obs):
    kind = name(need(c, "kind"))
    if kind == "stable_control":
        if not boolean(need(c, "promised")):
            return True, {"applicable": False, "reason": "No stability promise"}
        states = need(c, "states")
        if not isinstance(states, list) or len(states) < 2:
            raise Incomplete("Stability needs at least two distinct state names")
        states = [name(s) for s in states]
        if len(set(states)) != len(states):
            raise Incomplete("Stability state names must be distinct")
        limit = tolerance(c, "max_edge_delta_px")
        boxes = [rect(need(control(obs, s, name(need(c, "control"))), "rect")) for s in states]
        maximum = max(delta(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:])
        return maximum <= limit, {"states": states, "rects": boxes, "max_edge_delta_px": maximum, "limit_px": limit}
    if kind == "reachable_action":
        target = name(need(c, "control"))
        state = name(need(c, "use_state"))
        m = control(obs, state, target)
        box = rect(need(m, "rect"))
        clip = rect(need(m, "effective_clip_rect"))
        p = need(m, "use_point")
        x, y = number(need(p, "x")), number(need(p, "y"))
        margin = tolerance(c, "min_point_clearance_px")
        # Effective clip is the intersection of viewport and all clipping ancestors.
        left, top = max(box["x"], clip["x"]), max(box["y"], clip["y"])
        right = min(box["x"] + box["width"], clip["x"] + clip["width"])
        bottom = min(box["y"] + box["height"], clip["y"] + clip["height"])
        clearance = number(min(x - left, y - top, right - x, bottom - y))
        hit = boolean(need(m, "hit_target_or_descendant"))
        enabled = boolean(need(m, "enabled"))
        ok = right > left and bottom > top and left <= x < right and top <= y < bottom and clearance >= margin and hit and enabled
        return ok, {"use_state": state, "rect": box, "effective_clip_rect": clip, "use_point": p,
                    "clearance_px": clearance, "required_clearance_px": margin,
                    "hit_target_or_descendant": hit, "enabled": enabled}
    if kind == "activation_events":
        run = need(need(obs, "runs"), name(need(c, "run")))
        latency = tolerance(c, "max_latency_ms")
        if not boolean(need(run, "capture_complete")):
            raise Incomplete("Activation capture is incomplete")
        requests, events = need(run, "requests"), need(run, "events")
        if not isinstance(requests, list) or not requests or not isinstance(events, list):
            raise Incomplete("Need nonempty requests and an events list (empty events is measured loss)")
        start, end = number(need(run, "capture_start_ms")), number(need(run, "capture_end_ms"))
        ids = [name(need(r, "id")) for r in requests]
        if len(set(ids)) != len(ids):
            raise Incomplete("Request IDs must be unique")
        for r in requests:
            t = number(need(r, "time_ms"))
            if t < start or t + latency > end:
                raise Incomplete("Capture does not cover each request response window")
            name(need(r, "from_state"))
            name(need(r, "expected_state"))
            if r["from_state"] == r["expected_state"]:
                raise Incomplete("State-change check cannot verify an intentional no-op request")
        for e in events:
            name(need(e, "request_id"))
            name(need(e, "from_state"))
            name(need(e, "to_state"))
            t = number(need(e, "time_ms"))
            if not start <= t <= end:
                raise Incomplete("Event lies outside capture")
        problems = []
        for r in requests:
            matched = [e for e in events if e["request_id"] == r["id"]]
            if len(matched) != 1:
                problems.append({"request_id": r["id"], "event_count": len(matched)})
            else:
                e = matched[0]
                delay = number(e["time_ms"] - r["time_ms"])
                if e["from_state"] == e["to_state"] or e["from_state"] != r["from_state"] or e["to_state"] != r["expected_state"] or not 0 <= delay <= latency:
                    problems.append({"request": r, "event": e, "delay_ms": delay})
        unexpected = [e for e in events if e["request_id"] not in ids]
        return not problems and not unexpected, {"requests": requests, "events": events, "max_latency_ms": latency,
                                                  "problems": problems, "unexpected_events": unexpected}
    if kind == "settled_geometry":
        m = need(need(obs, "transitions"), name(need(c, "transition")))
        limit = tolerance(c, "max_edge_delta_px")
        wait = tolerance(c, "min_settle_wait_ms")
        if not boolean(need(m, "end_observed")):
            raise Incomplete("Transition end was not observed")
        end_time = number(need(m, "end_time_ms"))
        settled_time = number(need(m, "settled_time_ms"))
        elapsed = number(settled_time - end_time)
        if elapsed < wait:
            raise Incomplete("Settled sample taken before required wait")
        end_box, settled_box = rect(need(m, "end_rect")), rect(need(m, "settled_rect"))
        difference = delta(end_box, settled_box)
        return difference <= limit, {"end_rect": end_box, "settled_rect": settled_box,
                                     "elapsed_ms": elapsed, "max_edge_delta_px": difference, "limit_px": limit}
    raise Incomplete(f"Unsupported check kind: {kind}")


def check(contract, observations):
    results = []
    try:
        checks = need(contract, "checks")
        if not isinstance(checks, list) or not checks:
            raise Incomplete("Contract must contain nonempty checks")
        ids = [name(need(c, "id")) for c in checks]
        if len(set(ids)) != len(ids):
            raise Incomplete("Check IDs must be unique")
    except (Incomplete, TypeError) as exc:
        return {"status": "incomplete", "checks": [], "reason": str(exc)}
    for c in checks:
        try:
            passed, evidence = evaluate(c, observations)
            result = {"id": c["id"], "status": "pass" if passed else "fail", "evidence": evidence}
        except (Incomplete, TypeError, KeyError) as exc:
            result = {"id": c["id"], "status": "incomplete", "reason": str(exc)}
        results.append(result)
    # A proven defect remains a fail, with missing checks explicitly retained.
    status = "fail" if any(r["status"] == "fail" for r in results) else "incomplete" if any(r["status"] == "incomplete" for r in results) else "pass"
    return {"status": status, "checks": results}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("contract", type=Path)
    p.add_argument("observations", type=Path)
    args = p.parse_args()
    def invalid_constant(value):
        raise Incomplete(f"Non-JSON numeric constant: {value}")
    try:
        report = check(json.loads(args.contract.read_text(encoding="utf-8-sig"), parse_constant=invalid_constant),
                       json.loads(args.observations.read_text(encoding="utf-8-sig"), parse_constant=invalid_constant))
    except (OSError, ValueError) as exc:
        report = {"status": "incomplete", "checks": [], "reason": str(exc)}
    print(json.dumps(report, indent=2, allow_nan=False))
    return {"pass": 0, "fail": 1, "incomplete": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
