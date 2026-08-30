---
name: openai-delegation-route-research
description: Use when selecting a GPT route for a task or refreshing the reviewed Codex catalogue.
license: MIT
compatibility: Requires the user's OpenAI Codex catalogue and reviewed Artificial Analysis data.
metadata:
  author: supplefrog
  version: "0.4.0"
---

# Automatic GPT routing

Use the reviewed catalogue to select the exact GPT model and reasoning effort for each new task. The caller classifies the task; deterministic code chooses the route.

Read [the selection contract](references/selection-contract.md) and [source policy](references/source-policy.md).

## Select

1. Classify the minimum intelligence tier:
   - `routine`: bounded or mechanical work with cheap retries or direct verification.
   - `standard`: normal professional work; this is the default when no stronger signal exists.
   - `strong`: substantial ambiguity, judgment, or synthesis.
   - `demanding`: hard reasoning where a weaker attempt materially risks rework.
   - `maximum`: quality-ceiling work where the strongest measured route is justified.
2. Set `latency_sensitive: true` only when completion blocks the user or a foreground dependency. Background and nonblocking work defaults to false.
3. Create a task request matching `references/route-task.schema.json` and run:

```text
python scripts/route_selector.py select --catalog <gpt-catalog.json> --task <route-task.json> --out <decision-receipt.json>
```

The selector filters routes below the intelligence floor. Among the remaining routes it chooses lowest Artificial Analysis task cost by default, or lowest Artificial Analysis task time when latency-sensitive. Hallucination rate, excess intelligence, and route ID are deterministic tie-breakers only. Do not manually rerank the result. Use `selected_route_id` plus `selection_reason` only as an explicit operator override; overrides cannot violate the intelligence floor.

Pin once per new task. Reuse the receipt on resume and throughout the run. Reselect only for a new task, an explicit user change, or a separately authorized retry/escalation.

## Surface boundaries

- `routed_delegate_task` is live for automatic Hermes child routing. The caller classifies task requirements only; the plugin selects and pins the exact provider/model/reasoning receipt, disables route fallback, and launches through Hermes's native child builder/finalizer. Reusing the same parent-session/task ID reuses the receipt only when the task and requirements are identical.
- Built-in `delegate_task` still has one global delegation route. It remains the rollback path and homogeneous-batch fallback. Never rewrite shared config between children to imitate per-child routing.
- Exact automatic routes also work on task-thread and receipt-aware workflow tasks. `skills/dynamic-workflows` is the definitive portable DAG state contract: Codex passes the receipt tuple directly to native workers; OMP dispatches an immutable `route-<route-id>` named agent and verifies the resolved model. Hermes has no admitted DAG executor; ordinary Hermes routing remains here, and any future thin DAG adapter must pass current lifecycle/process tests before promotion.
- Workflow retries reuse the original receipt. Never spend through Medium → High → xhigh → Max after the same task fails; return the blocked task to the parent/human or create a separately authorized new task.
- Auxiliary assignments remain purpose-specific. Do not pass bounded utilities through a generic agent-work intelligence floor. For each purpose, inspect the real transformation, input/output bounds, failure cost, incumbent performance, and whether exact verification or cheap retry exists. Compare reasoning-token volume and task cost across efforts, then choose the weakest reliably enforceable effort that clears the purpose-specific fidelity requirement. When that requirement is unknown, keep the current quality incumbent and run a representative non-inferiority evaluation against cheaper challengers; do not ask the user to guess an intelligence level, and do not downgrade from broad benchmark scores alone. Treat the broad Artificial Analysis Intelligence Index as supporting evidence, not a task-specific pass/fail score. Preserve specialized or non-Codex incumbents unless task-specific evidence supports replacement. If a configured effort does not map to an explicit wire value on the intended provider, treat that effort as unavailable until live-verified; never assume an omitted field disables reasoning.
- Thread/DAG construction and prompt wording belong to their existing owners. This skill selects routes only.

## Manual catalogue refresh

Refresh only when the user invokes it after a new GPT family becomes available. Do not poll releases or scrape Artificial Analysis at runtime.

1. Enumerate the exact GPT model/reasoning combinations available to the user's `openai-codex` account.
2. Record the four approved Artificial Analysis axes for each exact comparable variant.
3. Remove unavailable and strictly dominated candidates; record why omissions are evidence-based.
4. Set catalogue-specific intelligence floors from the reviewed frontier. Do not turn one family's index values into universal thresholds.
5. Review auxiliary assignments separately, update dates/versions, and validate the catalogue.

## Verification

1. Validate the catalogue, route request, receipt, and auxiliary assignment files against their schemas.
2. Run `tests/test_route_selector.py` and `tests/test_route_adapter.py`.
3. Exercise cost-default, speed-priority, override, fail-closed, and receipt-reuse paths.
4. Confirm selected model identifiers are still callable through the intended Codex account before live use.

## Boundaries

- Only GPT routes available through `openai-codex` belong in the catalogue.
- Artificial Analysis is reviewed evidence, not a live runtime dependency or a complete task benchmark.
- Missing tiers, unavailable routes, and overrides below the floor fail closed.
- The selector never calls an LLM or edits Hermes configuration.
- Existing runs remain pinned when the catalogue changes.
