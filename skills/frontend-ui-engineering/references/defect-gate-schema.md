# Frontend measurement checker

Python standard library only. Checks supplied browser observations against explicit outcome promises. It does not collect browser data or assess model quality.

From the skill's `scripts` folder (use absolute paths when calling it from a project):

```powershell
python frontend_gate.py contract.example.json observations.clean.json
python -m unittest -v test_frontend_gate.py
```

`observations.bad.json` demonstrates one proven stability failure plus incomplete unrelated checks. `observations.missing.json` demonstrates wholly missing measurements. The 24 tests also exercise the CLI's three exit codes. Test fixtures are read-only; the suite does not require writing to the operating system's temporary directory.

The CLI prints a JSON report. Exit codes: `0` pass, `1` proven failure, `2` incomplete input or evidence. Every check retains concrete measurements or a missing-evidence reason. Overall failure takes precedence over incomplete; a report with an incomplete check never passes. An empty contract is incomplete. Additional fields are ignored, so collectors can retain source references, screenshots and metadata alongside measurements.

## Input schema

Use [contract.example.json](../scripts/contract.example.json) and [observations.clean.json](../scripts/observations.clean.json) as a complete executable example. IDs are project-chosen names, not product-specific selectors. All required fields below must be present. Numeric measurements must be finite JSON numbers; booleans must be actual JSON booleans. Rectangles have positive `width` and `height` and numeric `x`, `y`. Coordinates and tolerances use CSS pixels, in one viewport coordinate system for each comparison. Times use milliseconds on one monotonic clock per run/transition. Choose tolerances before collecting the result, based on the intended outcome and collector precision.

Contract root: `{"checks": [...]}`, a nonempty array with unique string `id` values. Each check is one of:

| Kind | Contract fields | Observation fields |
| --- | --- | --- |
| `stable_control` | `promised` boolean, `control` string, `states` array of at least two distinct names, `max_edge_delta_px` nonnegative | `states[state].controls[control].rect` for every named state |
| `reachable_action` | `control` string, `use_state` string, `min_point_clearance_px` nonnegative | `states[use_state].controls[control]`: `rect`, `effective_clip_rect`, `use_point` with `x`/`y`, `hit_target_or_descendant` boolean, `enabled` boolean |
| `activation_events` | `run` string, `max_latency_ms` nonnegative | `runs[run]`: `capture_complete` boolean, `capture_start_ms`, `capture_end_ms`, nonempty `requests` array, `events` array |
| `settled_geometry` | `transition` string, `max_edge_delta_px` nonnegative, `min_settle_wait_ms` nonnegative | `transitions[transition]`: `end_observed` boolean, `end_time_ms`, `settled_time_ms`, `end_rect`, `settled_rect` |

For a stability check with `promised: false`, remaining stability fields and geometry are not required: it passes as explicitly not applicable. Use separate stability checks per responsive context if the promise applies only within a context. Do not compare desktop to mobile unless that comparison is promised. All pairs of specified states are compared using the largest difference across left/top/right/bottom edges, so a fixed caret origin or unchanged top-left alone cannot establish whole-control stability.

Reachability requires the actual intended point at the actual use state. A menu action can be checked in `menu-open`; it need not exist in `menu-closed`. Supply `effective_clip_rect` as the intersection of the viewport and every rectangular clipping ancestor. The actual point must lie inside both the control and clip, have the contracted minimum clearance from their intersection's edges, hit the target or its descendant, and be enabled. Right and bottom edges are exclusive. A partially visible action passes if its intended point remains reachable with the promised clearance. Collect hit testing at that point, not at some unrelated visible point.

Each activation request has unique string `id`, `time_ms`, `from_state`, `expected_state`. Each observed state event has `request_id`, `time_ms`, `from_state`, `to_state`. Events are state changes, not click handler invocations or rendering frames. An event with the same source/destination cannot establish a response. Intentional no-op requests need a different check and are incomplete here. The collector must observe the complete relevant state-event stream and correlate events to requested activations without filtering out duplicates or inventing missing events. An uncorrelated relevant event can use a string ID absent from `requests`; it fails as unexpected. Exactly one matching event with the expected source/destination and latency from zero through the limit is required per request. Empty `events` means measured lost responses only when capture is complete and every request's full response window is covered; absent `events` means incomplete. Captures ending too early are incomplete. Preserve all repeated events. This check compares each request with its correlated event; it does not establish a single globally continuous state machine across concurrent controls.

For settled geometry, collect the relevant transition/animation end and a later rectangle after at least the contracted wait. Compare all four edges. Deliberate motion during a transition is allowed: the check addresses endpoint-to-settled jumps. It does not require animation in every state; include this check only where an endpoint continuity promise applies. If no end can be identified, report `end_observed: false`; the check is incomplete rather than guessing an endpoint.

## Evidence collection and limits

The collector owns measurement truth, event correlation, state selection and capture completeness. Bind observations to the build/revision, viewport, browser, scenario, source records and time of capture in your surrounding evidence record. The checker cannot prove a boolean assertion was measured, distinguish a fabricated observation, or infer untested states. A passing synthetic fixture proves the deterministic mechanism only; it does not prove a live UI passes.

The rectangular clipping approximation is insufficient for rotated controls, clip paths, masked shapes or irregular hit regions. The point hit test provides evidence at one supplied point, not a guarantee for the entire action surface. It does not measure touch ergonomics, keyboard access, focus, contrast, colors, themes, metaphors, caret conventions, content direction, aesthetic quality or every possible tap sequence. Transition checking uses two samples, so it cannot detect an intermediate jump or prove future stability. Events attributed incorrectly by the collector can hide or invent a defect. No universal tolerance is built in.

The executable tests cover movement, resizing, pairwise tolerance drift, clipped use positions, occlusion, disabled actions, lost/repeated/late/wrong/unrequested responses, premature captures, endpoint jumps and missing/invalid data. Nearby valid cases cover a secondary menu action, explicit absence of a stability promise, exact tolerance boundaries and clean transition geometry. These cases are generated by mutating the clean fixture, keeping one relevant difference observable per case.
