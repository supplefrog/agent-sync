# Operational infrastructure fit

Use this when evaluating gateways, routers, aggregators, schedulers, or other infrastructure whose feature breadth can obscure runtime risk.

## Start from the operational job

Name the end state and work class: casual, bounded/stateless, long-running/stateful, externally mutating, or system-of-record. Identify what must remain stable for the complete job.

Separate outcomes from means. Discovery, benchmarking, cataloguing, dashboards, config writing, and integration installers earn credit only when they improve the end state. If the selected runtime already performs their useful role, count the extra surface as redundant rather than as another capability win.

Ask whether the candidate removes a layer or adds another stateful dependency with its own lifecycle, security, and failure modes.

## Validate the real interception path

For compression proxies, retrieval sidecars, MCP add-ons, and similar context middleware, separate four claims:

- the library can transform a supplied payload;
- the released CLI exposes an integration for the named host;
- the active provider/model route actually traverses that integration;
- recovery is available to the model before lost detail affects the answer.

Prove each required claim on the exact installed release and active provider path. Inspect the shipped command help and effective host configuration; do not infer support from repository modules, stale plugin prose, or a broad compatibility table. A wrapper that redirects only one provider does not cover sessions using another provider, even when the host itself is listed as supported.

Benchmark marginal value with a representative local fixture before promotion. Record cold and warm latency separately, input/output size or tokens, preservation of injected anomalies, dependency/install footprint, and any persistent files created. A successful synthetic transform proves compressor mechanics only; it does not prove end-to-end answer quality, provider-billed savings, or safe concurrent operation.

Check when compression occurs. An MCP tool the model calls only after receiving a large tool result may add schema and transcript overhead without reducing the first context charge. Prefer host-native pre-model interception or a verified provider proxy when automatic savings are required; retain on-demand MCP only when content can be compressed before insertion into model context.

Before enabling a wrapper, test whether it mutates shared host configuration while running. Classify a shared-config wrapper as an experiment when concurrent unrelated sessions can observe temporary routing or tool changes. Use process-scoped overrides when available.

Run the evaluation from an isolated environment without writing live configuration. Afterward, inspect candidate-owned state, remove probe artifacts when admission fails, and distinguish package-manager cache from a persistent installation.

## Availability is not dependability

Availability asks whether some backend can answer. Dependability asks whether the answer is sufficiently consistent, attributable, recoverable, and safe for the work.

For model routers, verify:

- stable logical model identity across a session;
- same-model provider failover before cross-model substitution;
- explicit session affinity and known expiry behavior;
- visible capability degradation and fail-closed pool exhaustion;
- tool-call and structured-output compatibility on the real client path;
- context, parameter, moderation, privacy, and retention differences between providers;
- quota-driven quality changes and latency variance;
- stable-provider or qualified local-model anchoring for consequential work;
- verification before routed output mutates durable state or external systems.

More providers, automatic scoring, or hidden fallback can improve request completion while making behavior less reproducible. Treat that as a trade-off, not an unconditional reliability gain.

## Decision labels

- **Primary foundation:** proved for long-running or consequential work without silent capability degradation.
- **Bounded sidecar:** isolated low-stakes or stateless work whose output is verified before reuse.
- **Explicit fallback:** invoked under a visible failure policy; model/provider changes remain attributable.
- **Experiment:** no production, durable-state, or external-action authority.

If a candidate is useful only at an edge case, record that edge case and its reopening condition. Do not inflate a working mechanism into system-wide usefulness.

## Free-tier routing edge case

A pool of free providers can hide rate limits but cannot create an SLA or stable model contract. Do not use adaptive cross-model routing as the default for serious long-running agents unless a stable provider anchors the workflow. Reconsider it only for isolated low-stakes or stateless tasks with an explicit logical model, same-model provider failover, fail-closed exhaustion, and verification before durable or external effects.