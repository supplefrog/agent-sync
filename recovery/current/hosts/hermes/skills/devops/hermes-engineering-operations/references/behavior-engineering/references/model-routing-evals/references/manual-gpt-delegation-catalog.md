# Manual GPT delegation catalogue

Use this path when the user maintains a GPT-only delegation catalogue and invokes refresh after hearing that a new GPT family is available. It replaces scheduled release polling and recurring local model tournaments for that catalogue; it does not replace empirical testing for unrelated main or auxiliary route changes.

## Contract

- Provider/model scope: exact GPT model and reasoning-level tuples available through the user's OpenAI provider.
- Refresh trigger: explicit user invocation after a new GPT family appears. Never schedule polling.
- Source fields per exact tuple: Artificial Analysis Intelligence Index, Output Speed (tokens/s), and Cost per Task (USD).
- User assigns tuples to one or more task brackets: `routine`, `standard`, `demanding`, `highest-stakes`.
- The conversational parent assigns one bracket per new delegation task using written rules. Split independent mixed-difficulty work and classify each child separately.
- Deterministic code compares only tuples in the assigned bracket. It runs once before launch; messages, tools, and resumes reuse the pinned result.
- Exact user model/reasoning choices are hard overrides when present in the active catalogue.

## Selection

1. Remove a tuple when another has at least as much intelligence and speed, no greater cost, and is strictly better on at least one metric.
2. For each remaining pair, percentage difference is `abs(a-b) / max(abs(a), abs(b))`.
3. Intelligence within 3 points and speed within 15%: lower Cost per Task wins.
4. Otherwise, intelligence within 3 points and cost within 15%: higher Output Speed wins.
5. Otherwise, higher Intelligence Index wins.
6. If all three are close, lower cost wins.
7. Resolve any remaining pairwise or aggregate tie deterministically from the exact model/reasoning identifiers; never call an LLM to choose the model.

## Data collection

Prefer the rendered Artificial Analysis comparison page because the user can inspect it. If raw extraction is blocked, use a user-provided table, screenshot, or export, or another attributed view reproducing the same Artificial Analysis fields. Never invent missing values or substitute blended token price, latency, or local benchmark results. Do not transfer a model-level speed/cost value to another reasoning level unless the source explicitly shows that variant.

## Receipt and verification

Emit a versioned receipt before launch containing the exact provider/model/reasoning/surface, bracket and override, selected metrics, catalogue/request/runtime hashes, alternatives/exclusions, and a decision hash. Treat it as an integrity lockfile, not a quality proof or cryptographic signature. Pin once; reject conflicting rewrites and tampering.

Verify:

1. catalogue and task schema validation;
2. deterministic boundary tests for all brackets, 3-point/15% margins, all-close cost priority, dominance, exact ties, malformed/non-GPT/duplicate tuples, overrides, and fail-closed cases;
3. one real selector CLI run;
4. external adapter validation;
5. native Hermes receipt validation, pin reuse, resume stability, and tamper rejection;
6. fresh live-provider callability before promotion.

Hermes' native receipt credential guard recursively rejects suspicious key names, including keys containing `token`. Keep the catalogue's source label `Output Speed (tokens/s)`, but use a neutral emitted receipt key such as `artificial_analysis_output_speed`; test the emitted receipt through the native validator rather than only the external adapter.
