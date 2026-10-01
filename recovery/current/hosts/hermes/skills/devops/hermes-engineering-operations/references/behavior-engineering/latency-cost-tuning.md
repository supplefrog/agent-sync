# Latency and cost tuning

Use when a Hermes request feels slow or when changing reasoning, service tier, model route, tool exposure, or profile composition to improve responsiveness.

## Separate the latency layers

Measure these independently:

1. model time to first tool call;
2. tool startup and execution time;
3. model time after the tool result;
4. UI delivery/rendering time.

For computer use, `hermes computer-use doctor` establishes driver health and gives a rough driver-startup baseline. It does not measure model-to-tool latency. Compare the diagnostic's own runtime with a fresh end-to-end prompt that causes the model to run it.

## Cost and capability boundary

- A preference for speed, low latency, or fewer deliberation turns is not authorization to enable priority/fast service tiers, paid APIs, or any other cost-bearing option. Ask explicitly before making such a change.
- Do not lower reasoning effort, switch models, or remove tools merely because the setting is faster. Treat each as a quality/capability tradeoff and evaluate it independently.
- Preserve the user's original configuration until a candidate is approved and has repeatable evidence. Keep a direct rollback.
- Do not present a combined benchmark as evidence for one component. If service tier and reasoning effort both changed, the result attributes to neither.

## Evaluation

1. Record the exact baseline route, reasoning, service tier, verbosity, prompt/tool surface, and fresh/cached state.
2. Change one variable at a time. Run several equivalent probes because provider latency is noisy.
3. Report individual samples plus a robust summary; distinguish cold start, warm reuse, and provider variance.
4. Grade correctness and tool choice before latency. Reject a faster arm that asks unnecessary questions, skips verification, or loses needed capability.
5. Read back the effective config and run a fresh-session behavioral probe after promotion.
6. Restore the baseline immediately when authorization is missing or evidence is inconclusive.

## Input and compaction accounting

Identify the actual provider endpoint, model and billing/subscription route. Distinguish observed usage, estimated API-equivalent prices and invoices; API caching documentation does not prove OAuth-route behavior. On subscriptions, lead with tokens and quota evidence rather than per-token dollars.

Inspect existing usage and installed diagnostic help before launching probes. Reconcile offline prompt-size inventory with live request assembly. Read the installed usage normalizer before summing ordinary input, cache reads and writes; raw provider input may already include cache buckets. Keep parent, workers, compression/expansion auxiliaries and retrieved context in the whole-task account. State whether the cohort uses request time or session start. Missing recorded writes are uncertainty, not proof of no writes.

Preserve useful stable prefixes and history. Reduce unnecessary new content/repeated injection before rewriting stable instructions. Keep loading requirements distinct from execution triggers, and preserve operational contracts and linked paths when shortening entrypoints. A label such as legacy is not proof of obsolescence or permission to demote a capability.

Use the smallest faithful matched workload that can change the decision. Record observed input/cache/output counts, calls, latency and correctness, including cold loads and relevant continuations; report investigation overhead separately. Compute token-weighted cache reuse from summed counts. Do not pad prompts or create warmups merely to raise a cache percentage. Byte/schema-character reductions do not prove billed savings, natural discovery or quality. Do not publish native-versus-LCM savings without matched runs. Include compression auxiliaries, later reuse and recovery quality before changing compaction thresholds.

Keep unobserved dollars null. Distinguish enforced output/request/time limits from requested answer length. Use existing verified launchers for bounded checks; no extra orchestration is required for a small cost review.

## Tool-schema and profile tuning

- Use `hermes prompt-size` and request-time tool assembly to identify real schema cost before disabling anything.
- MCP and plugin tools may already be deferred by Tool Search; do not claim savings from removing schemas that were not on the request path.
- List the capability lost beside every proposed core-tool removal. Small savings rarely justify losing broadly useful functions.
- Prefer one capable conversational surface over capability-fragmented bots. Check demand loading's cache-prefix lifecycle and retrieval work before claiming lower uncached cost.
- A separate profile is appropriate only for a deliberately isolated role with self-contained prompts, such as scheduling. Keep the full default profile intact unless the user explicitly chooses otherwise.

## Completion

Report what changed, what remained unchanged, measured evidence, cost implications, rollback, and whether a restart or fresh session is required. Never describe a cost-bearing setting as a harmless latency optimization.
