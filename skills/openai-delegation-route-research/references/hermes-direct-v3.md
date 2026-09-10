# Hermes direct task routing

## Router-owned delegation

With the `routed-delegation` plugin enabled, send every new worker request through `routed_delegate_task` with a V3 `route_request`, or through `routed_workflow` for a DAG. Its `pre_tool_call` hook blocks ordinary `delegate_task` spawning and directs the caller to the router; it is not transparent redispatch. Existing-worker `list`, `steer`, and `stop` controls remain available. Do not bypass the gate with subprocesses or legacy V2 requests.

The router selects an executor from task-specific evidence before execution. Missing evidence permits a bounded trial only for low-risk independently verifiable work with established callability. `keep_parent`, parent, deterministic, and defer decisions return parent actions, not permission to start an inherited worker. The parent verifies worker output; task failure does not authorize an unbounded retry ladder.

Keep native `delegation.model`, `provider`, and `reasoning_effort` empty, with `fallback_providers: []`, as the compatibility baseline rather than a global cheaper-model pin. These settings alone do not invoke the selector. Without the enabled plugin, ordinary delegation retains Hermes-native behavior. V2 fields remain compatible for existing runs, but are not the default for new work and cannot be combined with `route_request`.

## Native compatibility

The plugin accepts the extended shared-budget API or adapts the tested split-native finalizer. The adapter keeps a batch-wide budget and invokes native memory, completion hooks, cost rollup, and locking once without global monkeypatches. Full results remain separate from bounded parent summaries. A changed finalizer body fails closed until reviewed; formatting and comments alone do not change its structural comparison. This temporary coupling is tracked [upstream](https://github.com/NousResearch/hermes-agent/pull/90870#issuecomment-5619573754).

The installed plugin directory may be linked directly to the canonical checkout. Check the resolved path before editing or reporting deployment. Verify native plugin discovery, the routing hook, and runtime compatibility in a fresh process; an already-running session may retain the old module until restart.

The template contains exactly `schema_version: 3`, `task_class`, `requirements`, `verifier`, `effects`, `failure_cost`, `deterministic`, and `budget`, as defined in [the task schema](route-task-v3.schema.json). Omit controller fields: `task_id`, `input_sha256`, `as_of`, `continuation`, and requirements `host`/`transport`. A deterministic descriptor also omits `input_sha256`. The tool fills them through [task_request.py](../scripts/task_request.py); the parent supplies the remaining explicit fields and checks referenced evidence.

Requirements `tools` lists the exact native tool names exposed to the child. `toolsets` selects native toolsets; Hermes may intersect these with parent capabilities and retain inherited MCP tools. Execution is rejected if the resulting child tools differ from the declared names. An inline text task can request `toolsets: ["none"]` and `tools: []`; it is executable only when the native child actually has no tools. No tool capability follows from a successful text call.

The controller binds goal, context, requested settings, iteration limit and the native execution envelope: derived role/depth, resolved toolsets, hashes of injected workspace context and prefill, and launch profile including SOUL/config file hashes. It checks the constructed child before launch and again during request construction. Native source hashes bind the selected runtime contract. Disk hashes do not prove hot reload or provider-resolved identity; native upgrades require fresh evidence and a new catalog.

The admitted catalog is `references/current-task-route-catalog.json`. Availability, protocol qualification and resource observations remain separate. Unknown subscription weights stay unknown. An explicit provisional preference is permitted only by the selector's bounded verification and resource rules; it is not a measured cheapest-route claim.

Only a model decision starts a child. Deterministic, parent and defer decisions return explicit parent actions with their frozen request and receipt. The tool does not launch an arbitrary executor reference. A model completion includes an independent acceptance handoff; inspect the result and run that check before using its work.

A direct task ID owns one attempt. Repeating it cannot launch again. This consumer does not execute V3 continuations or a hidden retry ladder. Old V2 pins and existing lifecycle/accounting limitations retain their original meaning.
