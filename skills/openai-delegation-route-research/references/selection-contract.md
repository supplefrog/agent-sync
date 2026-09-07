# Task-aware selection contract

New requests use `route-task-v3.schema.json`, `gpt-route-catalog-v3.schema.json`, and `route-decision-v3.schema.json`. V2 schemas/catalogs remain readable under their original policy. The selector is a deterministic policy function over trusted, frozen inputs; it does not acquire evidence, verify external artifact bytes, launch workers, or edit configuration.

## Inputs and responsibility

The parent supplies the actual task class, stable outcome-protocol hash, separate exact `input_sha256`, required host/transport/tools/context, effects, failure cost, independent verifier, resource snapshot, and attempt policy. The protocol defines success criteria and the workload envelope covered by qualification; a broad label such as coding cannot replace it. Exact input hashes protect replay, retries and artifact reuse without preventing protocol evidence from applying to a new input in its admitted scope. The parent checks referenced evidence and artifact hashes before admitting a catalog or task request. Worker-authored success claims are not trusted qualification records.

Each candidate binds the exact native route and runtime contract to scoped, dated callability evidence. Quality records match the task contract, verifier, route and evidence scope. A recorded local regression excludes that task cell. Category benchmark priors help discovery; they cannot certify an untested local route.

## Selection and dispatch

1. A complete matching deterministic handler with independent verification and no irreversible effects yields `execute_deterministic` without a model call.
2. Otherwise enforce exact callability, context/tools/effects, relevant task evidence or a complete low-risk verifier, and resource bounds.
3. Compare complete observed generation, verification and fallback costs only for matching protocol, verifier and route bindings, within the same unit and quota bucket. A cost from another task is unknown for this decision. Unknown or incomparable costs require the request's explicit preference/parent/defer policy. Never convert an API price into subscription quota or treat OAuth usage as free.
4. Emit `selected_model` only for an eligible route; unresolved cases stay with the parent or defer. `dispatch_decision` replays the frozen inputs before returning an explicit dispatch kind. Native consumers must reject unsupported receipt versions and unsupported route surfaces.

Catalog evidence is a curated input, not an automatic training pipeline. Retain negative, inconclusive, operational and quality outcomes separately. A passed schema or worker completion alone must not update quality qualification. Claim cost improvements only against comparable observed task totals with acceptance quality preserved.

## Pins and recovery

Save the exact task, catalog, selector identity and decision before launch. A resume replays those inputs; it must not silently adopt current availability, budget, scores or prompts. An execution retry keeps the model/effort pin. A failed verifier permits only the predeclared fallback to a distinct exact route, with at most two total model attempts and the original task/verifier/effects contract. Resource state may be refreshed for a new attempt without rewriting the prior receipt. An exhausted cap or insufficient resources stops new model dispatch.

Existing v2 workflow/task adapters preserve their old schema semantics until their v3 consumer path is verified. The standalone v3 policy can be used through an explicit native parent dispatch while that migration proceeds; this does not establish every host's automatic integration.
