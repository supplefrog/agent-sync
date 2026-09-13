# Context-capacity benchmarking

Use this reference when comparing model windows, provider-native compaction, local summarization, retrieval/external memory, or session continuation. The goal is not to crown the mechanism with the largest advertised number; it is to identify which working-set and continuity regimes each mechanism handles without unsupported claims.

## Keep the quantities separate

Record these independently for every arm:

- **Underlying model window:** the model-family capacity reported by the provider or an authoritative SDK for the same wire model. This is not automatically the capacity admitted by a particular product route or account.
- **Route-admitted working window:** the provider-enforced or live-resolved input capacity for the active route/account. A client-only alias that is stripped before transport is a policy tier, not evidence of separate model weights.
- **Local fallback trigger:** the runtime-resolved trigger after subtracting reserved output/reasoning space from the route window, applying the effective compression ratio, then applying model/provider overrides, floors, and absolute caps. `window × ratio` alone is often wrong.
- **Native compaction trigger:** the exact value sent to the provider after safety clamps. A config literal is only an input to this resolver.
- **Raw residency:** how much original input remained in the request that answered the questions.
- **Effective task capacity:** what can be continued through compaction, retrieval, or persisted state. Do not describe this as a larger native context window.
- **Recovery state:** the actual artifact persisted and replayed after process/session reconstruction.

When runtime code has model-specific overrides, output reservations, floors, or clamps, execute that resolver against the active config. Show the configured window, admitted window, output reservation, ratio/override, and final trigger. Then corroborate it with the runtime log from the compaction event. Never infer the live threshold from the global ratio or an advertised maximum alone. A successful large-prompt probe proves accepted capacity, not a model-quality curve at intermediate lengths.

## Design separate experiments

Do not make one synthetic recall run carry every claim. Use distinct probes for:

1. **Raw-window quality:** answer and synthesize while all source material remains resident.
2. **Compaction quality:** cross the actual trigger, confirm a checkpoint/summary was emitted, then answer from the compacted representation without silently resending the source.
3. **Boundary value:** test workloads below the base trigger, between the base trigger and base maximum, above the base maximum, near the larger-window trigger, and—when relevant—above that trigger.
4. **Lifecycle recovery:** persist the real state, end the process, construct a fresh runtime, replay the state, and verify identity plus exact recall. Reusing an in-memory object or a constant session ID is not restart proof.
5. **Resource behavior:** collect provider-reported input/output/cache tokens, quota or cost units when exposed, latency samples, artifact size, and extra sessions/processes. Estimated tokens must remain labeled estimates.
6. **Task quality:** pair exact canaries with at least one dense cross-document/code synthesis task. Eight isolated identifiers can prove exact recall but not global reasoning over a large working set.
7. **Mechanism arbitration:** force a tool-heavy boundary where the previous provider request is below the native threshold but the next assembled request crosses both the native threshold and the local pre-API guard. Verify from logs and emitted items which mechanism actually ran. Native configuration is not native-compaction evidence if local preflight intercepted the request before the provider saw it.

A compacted base arm and an uncompacted large-window arm are useful, but they are not matched mechanisms: one measures checkpoint fidelity and the other raw residency. Equal answers establish that both passed that fixture, not that one is universally superior.

## Match what can be matched

Hold constant where applicable:

- underlying model snapshot and provider route;
- system prompt, tools/schema, reasoning effort, output budget, and question bank;
- fixture bytes and placement of early/middle/late evidence;
- threshold policy being evaluated;
- cleanup and artifact-retention rules.

If an alias changes only the admitted context window, record that explicitly. If thresholds differ because the experiment intends to test different residency policies, name those policies instead of presenting the arms as a direct winner/loser pair.

## Do not manufacture lifecycle evidence

Fields such as `restart_recovery`, `session_identity_stable`, `checkpoint_replayed`, `cache_hit`, and `extra_visible_sessions` are assertions. Populate them only from observed checks. If the evaluator cannot measure one, use `null`/`unproven`; do not default it to `true`.

Likewise:

- one run is a smoke, not a latency benchmark;
- the median of two requests inside one arm is not a stable comparative latency estimate;
- passing unit/integration tests validates code contracts, not model recall or task quality;
- a manually assigned resource rank is not cost evidence;
- a generated token estimate is not provider usage accounting.

Use repeated trials sufficient to expose variance before making performance claims; report the count and dispersion. Preserve failed or malformed baseline evidence, but disqualify it from matched winner selection until repaired.

## Decision rules

- A larger window should remain eligible whenever a task may require raw simultaneous context beyond the base window, even if a smaller arm passes a sub-window fixture.
- Compaction is preferable for indefinite sequential continuity only when checkpoint fidelity, replay, and failure fallback are demonstrated.
- Treat provider-native compaction as opaque working-memory continuity unless the provider exposes an inspectable representation. Pair it with retained raw transcripts, reviewed artifacts, or a retrieval store whenever exact old details must remain auditable.
- Provider/SDK default thresholds are capacity-safety baselines, not proven quality sweet spots. Pin the source revision/date, and do not turn a current percentage or static fallback into a universal recommendation.
- If a global native threshold suppresses the intended benefit of a larger-window variant, test and report that interaction before promotion.
- Prefer a conditional operating policy when winners differ by working-set size, exact-detail requirements, latency, or resource budget.
- No universal winner is a valid result. Do not use an arbitrary resource rank or unmatched threshold to break a tie.
- After promotion, reconstruct the runtime and read back the effective resolved values. The benchmark threshold and the live threshold must match unless the difference is intentional and documented.

## Minimum transparent receipt

Publish enough payload-free detail for another engineer to understand the result:

| Field | Required detail |
|---|---|
| Stack | host, runtime revision, provider/transport, model snapshot/alias |
| Input | fixture hash/bytes/messages, estimated tokens, provider-measured tokens if available |
| Thresholds | context window, global ratio, model override, local trigger, configured native value, final native value |
| Procedure | exact command or structured invocation, request count, trial count, output budget |
| Residency | full prompt, checkpoint/summary only, retrieval, or mixed |
| Quality | per-case results plus dense-synthesis result |
| Lifecycle | checkpoint emitted/persisted, fresh-process replay, session/state assertions |
| Resources | latency distribution, input/output/cache tokens, quota/cost when available |
| Limits | blocked, unmeasured, hard-coded, estimated, or inferred fields |

Present three closing blocks: **proven**, **not proven**, and **decision by workload**. Correct a receipt when live resolver output contradicts its threshold math; do not defend the stale document merely because repository verification passed.
