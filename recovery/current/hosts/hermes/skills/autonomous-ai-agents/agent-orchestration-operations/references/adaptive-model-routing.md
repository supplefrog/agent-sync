# Manual OpenAI delegation routing

Use this reference when choosing an exact GPT route for a new delegation task across subagents, task threads, CC-style DAG nodes, or Kanban workers. Hermes auxiliary tasks are a separate assignment problem.

## Decision unit

A delegation route is an exact provider/model/reasoning/runtime tuple from the current GPT catalogue. In OpenAI-only mode, require a callable `openai-codex` route; an OpenAI-looking model name alone is not enough.

## Refresh

Refresh manually when the user asks after a new GPT family appears:

1. Enumerate exact GPT model/reasoning tuples available through `openai-codex`.
2. Record current Artificial Analysis Intelligence Index, Time per Intelligence Index Task, Cost per Intelligence Index Task, and AA-Omniscience Hallucination Rate for each tuple.
3. Judge useful delegation roles from the current evidence and the user's actual priorities. Write plain-language recommendations; do not create universal thresholds, tiers, weighted scores, pairwise formulas, or Pareto rules from one model family.
4. Review auxiliary tasks separately. Preserve their incumbents unless task-specific evidence supports a change.
5. Stage and validate the catalogue; never auto-promote or rewrite live config.

## Selection

For each new delegation task, the main conversational agent chooses one exact route using the user outcome, task shape, failure cost, UX sensitivity, current catalogue recommendations, and all four evidence axes. It may infer silently and should ask only when unresolved ambiguity materially changes the product outcome.

Deterministic selector code validates that the chosen route exists and emits a hash-bound receipt. It does not rank models or choose alternatives. Missing or unknown selections fail closed.

## Receipt and pinning

Persist the catalogue hash, task-constraint hash, selected exact tuple, evidence locator, selection reason, verifier plan, attempt number, and pin status. Existing runs reuse their receipt. Reselect only for a new task, an explicit user change, or a separately authorized retry/escalation.

## Surface boundaries

- Delegation surfaces: `hermes-delegate`, `hermes-task-thread`, `cc-dynamic-workflow`, and `kanban-worker`.
- Auxiliary assignments are owned by the auxiliary assignment catalogue and are not accepted by the delegation selector or adapter.
- Host adapters consume exact selected receipts; they do not perform policy ranking.
- Existing runs remain pinned even when the catalogue is refreshed.

## Verification

Validate the GPT catalogue, one route task, the resulting receipt, and the separate auxiliary assignment file against their schemas. Run selector and adapter tests, then one CLI selection through the adapter. Confirm the exact route is callable before live use. Keep integration staged until host-native receipt propagation is verified.
