# Hermes direct task routing

## Router-owned delegation

With the `routed-delegation` plugin enabled, send bounded local source reviews through `routed_delegate_task` with `work` below. Existing explicit V3 requests and `routed_workflow` retain their contracts. The pre-tool hook blocks ordinary worker spawning; existing-worker list/steer/stop controls remain available. Do not bypass a routing decision with native spawn, subprocesses or legacy V2 requests.

The router selects an executor from task-specific evidence before execution. Missing evidence permits a bounded trial only for low-risk independently verifiable work with established callability. `keep_parent`, parent, deterministic, and defer decisions return parent actions, not permission to start an inherited worker. The parent verifies worker output; task failure does not authorize an unbounded retry ladder.

Keep native `delegation.model`, `provider`, and `reasoning_effort` empty, with `fallback_providers: []`, as the compatibility baseline rather than a global cheaper-model pin. These settings alone do not invoke the selector. Without the enabled plugin, ordinary delegation retains Hermes-native behavior. V2 fields remain compatible for existing runs, but are not the default for new work and cannot be combined with `route_request`.

## Task-first local source reviews

Pass `id`, `goal`, optional `context`, and a `work` object containing:

- `task_class: "bounded-source-evidence-review"`, actual `tools` (read_file/search_files or none), and required `context_tokens`;
- plain-text `acceptance`, retained in the worker context, frozen input and parent handoff;
- actual `effects` and `failure_cost` (only none/low permits this provisional lane);
- `authorized`, `max_requests` (1–32), `placement_reason`, and `accept_unknown_quota`;
- optional `quotas` with actual bucket/unit/remaining/reserve declarations. Missing telemetry stays unknown, never unlimited.

`authorized` is the caller's scoped trial declaration, not proof of user permission or an approval bypass. It must be true only within the user's authorization. No paid API route or fallback is allowed here. Do not label consequential work low-risk to force admission. This lane cannot query upstream issues: its tools are local-only. Fetch upstream evidence with the parent's appropriate tools or retain that task with the parent.

The controller builds the internal V3 binding with **no model/effort pin and no caller preference list**. The selector filters candidates by callable route, tools/context/effects, matching regressions and resources, then applies the catalog's reviewed `task_preferences[task_class]` when comparable measured costs are absent. An unknown class returns `keep_parent`; it never clones the parent silently. `reviewed_task_preference_unmeasured` is a transparent provisional prior, not a quality qualification or cheapest-route claim. Refresh stale availability with a bounded explicit capability check; do not extend timestamps without observation. A capability probe does not establish useful-work acceptance.

The direct consumer preserves one attempt, exact native model/effort, frozen tool schemas and native lifecycle. This task-first interface is not yet supported by DAG plans or other hosts. Existing pins are not rewritten; changed source identities can require explicit reconciliation, never silent rerouting. A fresh process is required after plugin changes.

## Legacy explicit bounded evidence workers

Use `task_request.evidence_review_template` for an authorized local source-inspection or review child. It derives the routine V3 fields from the candidate, outcome protocol and parent acceptance record. Supply actual quota/reserve declarations, a request cap, and a placement reason (for example, isolating a source-heavy stage from parent context). Do not declare a semantic check deterministic.

The optional `budget.evidence_trial` contains `authorized`, `max_requests` (1–32), `placement_reason`, and `accept_unknown_quota`. It permits one low-risk, no-effect, parent-reviewed trial on the Hermes direct consumer, with only `read_file` and `search_files` (or no tools), an explicit single-route preference, and no paid API fallback. The adapter narrows the constructed child's actual tools; request `toolsets: ["file"]`, not shell access labeled read-only. The parent persists the returned findings and checks every material claim.

Unknown quota may be accepted only through this explicit authorization with no declared protected reserve. Known exhaustion, mismatched quota units, protected reserves, unavailable capabilities and matching regressions still block. The execution-request construction cap starts after the separate non-sending compatibility probe; it does not measure subscription consumption or bound internal HTTP retries. Emitted tool schemas (including parameters, descriptions, and strictness) are compared with a frozen projection of the narrowed native schemas; child-schema mutation and native tool overrides are rejected before the request leaves the guard. Freeze expectations before invoking the builder, not from its first output. No cheapest-route claim follows. Requests without this option keep their existing policy. DAG evidence trials are not admitted until that consumer has equivalent enforcement.

The native context check uses model metadata when LCM intentionally leaves an auxiliary child's window unbound at zero; it does not modify LCM state or ignore a positive undersized window. Evidence workers freeze the narrowed tool snapshot across native turn and compaction refreshes; checking only construction misses later toolset rebuilds. Retain emitted-schema checks even with the native refresh freeze. Plugin changes require a fresh process: disk evidence does not establish that an active chat hot-reloaded the adapter.

## Native compatibility

The plugin accepts the extended shared-budget API or adapts the tested split-native finalizer. The adapter keeps a batch-wide budget and invokes native memory, completion hooks, cost rollup, and locking once without global monkeypatches. Full results remain separate from bounded parent summaries. A changed finalizer body fails closed until reviewed; formatting and comments alone do not change its structural comparison. This temporary coupling is tracked [upstream](https://github.com/NousResearch/hermes-agent/pull/90870#issuecomment-5619573754).

The installed plugin directory may be linked directly to the canonical checkout. Check the resolved path before editing or reporting deployment. Verify native plugin discovery, the routing hook, and runtime compatibility in a fresh process; an already-running session may retain the old module until restart.

The template contains exactly `schema_version: 3`, `task_class`, `requirements`, `verifier`, `effects`, `failure_cost`, `deterministic`, and `budget`, as defined in [the task schema](route-task-v3.schema.json). Omit controller fields: `task_id`, `input_sha256`, `as_of`, `continuation`, and requirements `host`/`transport`. A deterministic descriptor also omits `input_sha256`. The tool fills them through [task_request.py](../scripts/task_request.py); the parent supplies the remaining explicit fields and checks referenced evidence.

Requirements `tools` lists the exact native tool names exposed to the child. `toolsets` selects native toolsets; Hermes may intersect these with parent capabilities and retain inherited MCP tools. Execution is rejected if the resulting child tools differ from the declared names. An inline text task can request `toolsets: ["none"]` and `tools: []`; it is executable only when the native child actually has no tools. No tool capability follows from a successful text call.

The controller binds goal, context, requested settings, iteration limit and the native execution envelope: derived role/depth, resolved toolsets, hashes of injected workspace context and prefill, and launch profile including SOUL/config file hashes. It checks the constructed child before launch and again during request construction. Native source hashes bind the selected runtime contract. Disk hashes do not prove hot reload or provider-resolved identity; native upgrades require fresh evidence and a new catalog.

The admitted catalog is `references/current-task-route-catalog.json`. Availability, protocol qualification and resource observations remain separate. Unknown subscription weights stay unknown. An explicit provisional preference is permitted only by the selector's bounded verification and resource rules; it is not a measured cheapest-route claim.

Only a model decision starts a child. Deterministic, parent and defer decisions return explicit parent actions with their frozen request and receipt. The tool does not launch an arbitrary executor reference. A model completion includes an independent acceptance handoff; inspect the result and run that check before using its work.

A direct task ID owns one attempt. Repeating it cannot launch again. This consumer does not execute V3 continuations or a hidden retry ladder. Old V2 pins and existing lifecycle/accounting limitations retain their original meaning.
