# Hermes direct task routing

Use `routed_delegate_task` with `route_request` for a new task-aware direct delegation. The existing tier fields remain V2 and cannot be combined with this field. Automatic DAG migration is separate.

The template contains exactly `schema_version: 3`, `task_class`, `requirements`, `verifier`, `effects`, `failure_cost`, `deterministic`, and `budget`, as defined in [the task schema](route-task-v3.schema.json). Omit controller fields: `task_id`, `input_sha256`, `as_of`, `continuation`, and requirements `host`/`transport`. A deterministic descriptor also omits `input_sha256`. The tool fills them through [task_request.py](../scripts/task_request.py); the parent supplies the remaining explicit fields and checks referenced evidence.

Requirements `tools` lists the exact native tool names exposed to the child. `toolsets` selects native toolsets; Hermes may intersect these with parent capabilities and retain inherited MCP tools. Execution is rejected if the resulting child tools differ from the declared names. An inline text task can request `toolsets: ["none"]` and `tools: []`; it is executable only when the native child actually has no tools. No tool capability follows from a successful text call.

The controller binds goal, context, requested settings, iteration limit and the native execution envelope: derived role/depth, resolved toolsets, hashes of injected workspace context and prefill, and launch profile including SOUL/config file hashes. It checks the constructed child before launch and again during request construction. Native source hashes bind the selected runtime contract. Disk hashes do not prove hot reload or provider-resolved identity; native upgrades require fresh evidence and a new catalog.

The admitted catalog is `references/current-task-route-catalog.json`. Availability, protocol qualification and resource observations remain separate. Unknown subscription weights stay unknown. An explicit provisional preference is permitted only by the selector's bounded verification and resource rules; it is not a measured cheapest-route claim.

Only a model decision starts a child. Deterministic, parent and defer decisions return explicit parent actions with their frozen request and receipt. The tool does not launch an arbitrary executor reference. A model completion includes an independent acceptance handoff; inspect the result and run that check before using its work.

A direct task ID owns one attempt. Repeating it cannot launch again. This consumer does not execute V3 continuations or a hidden retry ladder. Old V2 pins and existing lifecycle/accounting limitations retain their original meaning.
