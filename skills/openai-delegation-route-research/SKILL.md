---
name: openai-delegation-route-research
description: Use for explicitly requested route-catalog research or existing pinned route receipts. Not ordinary worker selection, delegation, or an automatic prerequisite to useful work.
license: MIT
compatibility: Requires current native route availability and the repository's existing jsonschema dependency.
metadata:
  author: supplefrog
  version: "0.5.1"
---

# Task-aware GPT routing

The custom selector is opt-in, not the default coordinator policy. Do not invoke this workflow merely because a task needs a worker. Its contracts below apply only to explicit routing research, explicitly selected routed tasks, and existing pinned runs. Preserve historical evidence and all existing pins; a disabled compulsory router is not permission to bypass a run's integrity or resource checks.

Choose a route that meets the actual task's quality requirement with lower total resource use. Use existing code when it already completes the work. Keep consequential judgment with the current quality route unless relevant verified task evidence supports delegation.

Read [the selection contract](references/selection-contract.md) for request and dispatch semantics, and [source policy](references/source-policy.md) when adding evidence. This owner selects routes; native workers and `dynamic-workflows` own execution and lifecycle.

For new Hermes bounded local source reviews, use the task-first `work` input in [the direct consumer contract](references/hermes-direct-v3.md). Describe the task, acceptance, tools and bounded trial permission; do not preselect a model or construct proof hashes. The selector applies a reviewed task-specific preference only after capability and resource checks. Unmapped or consequential work stays parent-owned. This is provisional placement, not measured optimization or a general coding/web/DAG router. Existing explicit requests and DAG pins retain their contracts.

For qualified three-question source-review tasks, use [the bounded review Q&A contract](references/review-qa.md) and its deterministic `scripts/review_qa.py` verifier. Admission still requires the bound parent review and heldout gate.

## Bounded auxiliary comparisons

For requests comparing summarizers, title generators, or other auxiliary transformations, first inspect the effective task routes and reuse relevant evidence. Before quality trials, inspect the intended credential pool through runtime accessors and identify the account/plan selected by the probe; singleton auth and pool selection can differ. With multiple authorized accounts, an unsupported-model error applies only to the tested account: check the relevant entitled account before declaring the candidate unavailable. Pin both candidates to the same account without changing global account priority, and use minimal no-fallback requests; a catalog listing is not callability. Keep tokens, account IDs, and personal identifiers out of receipts. If the candidate remains unsupported on the intended eligible account, report an access blocker rather than a quality loss; do not switch providers or spend paid inference without authorization.

If both candidates are callable, use matched task inputs, prompts, reasoning settings, and output budgets; retain outputs and timings. Judge summaries on source fidelity, omissions, corrections, uncertainty, and continuity constraints; judge titles separately on specificity, brevity, and unsupported claims. Readiness-probe timing is not task latency, and synthetic short cases do not establish long-context compression fitness. Keep active configuration unchanged for comparison-only requests.

These bounded direct transformation probes do not require worker-selection receipts or a DAG. The following selector contract applies when actually selecting and dispatching a new model worker; it is not a prerequisite for every model comparison.

## Advanced explicit requests and other consumers

1. Identify the outcome protocol, exact input hash, required tools/context, allowed effects, failure cost, and independent acceptance check. Keep protocol qualification separate from an individual input. A JSON schema or an output file's existence does not establish content correctness.
2. Use the v3 task and catalog schemas in `references/`. Record actual callable host/transport/model/effort tuples, task evidence, resource state and unknown costs. Use a complete deterministic handler when available. For bounded reversible work with complete independent verification, an explicitly preferred candidate may be tried provisionally; this is not an established quality or savings claim.
3. Run the selector with the owning Agent Sync checkout's Python environment (`.venv` when present), satisfying its `requirements.txt`. Save the receipt with the exact catalog/task/selector snapshots:

```text
python scripts/route_selector.py select --catalog <catalog.json> --task <task.json> --out <decision.json>
```

4. Dispatch the explicit outcome: `execute_deterministic`, `selected_model`, `keep_parent`, or `defer`. Only `selected_model` permits a new model worker. Enforce the exact native tuple, verify the result, and retain the actual outcome and resource observations. Do not pass a new receipt to a consumer that supports only v2.

The selector compares total observed cost only for the matching protocol, verifier and route, within comparable units and including verification and fallback. Missing prices or quota weights remain unknown. An explicit provisional preference may guide bounded exploration; it must not be described as the cheapest route. Benchmark averages and release order cannot overturn relevant local regressions.

## Existing runs and retries

Preserve in-flight pins. V2 catalogs and receipts retain their original policy; do not rewrite them into v3 or populate missing evidence with invented scores. New evidence changes new decisions.

V3 permits at most two total model attempts. A transport retry keeps the exact route; a failed acceptance check may use only a predeclared fallback within the same total cap. Preserve the previous-decision and failure-evidence links. Return unresolved work to the parent when the contract, budget, or capability no longer permits execution. Reset credits require the user's authorization to redeem.

## Refresh and auxiliary work

Refresh affected evidence when requested or when a material availability, task, harness, tool, prompt, verifier, or resource change invalidates it. Reuse current verified findings; do not launch recurring benchmark swarms. For solution discovery, follow `outcome-first-workflow-design`: existing implementations before novel research.

Auxiliary transformations retain their purpose-specific incumbents until representative task evidence supports replacement. Native callability is transport-specific: a catalog entry or successful text request does not prove tool use, another host, or every reasoning effort. Preserve specialized non-Codex routes when their purpose remains justified. Never mutate shared configuration between children to imitate per-child routing.

## Verification

Validate schemas, replay frozen decisions, and run the selector and affected consumer tests. Exercise wrong-but-well-formed output, unavailable capabilities, unknown costs, reserve exhaustion, bounded fallback, and non-model outcomes. Use independent acceptance on useful delegated work before claiming improved quality or savings.
