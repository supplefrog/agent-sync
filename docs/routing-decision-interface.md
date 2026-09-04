# GPT routing decision interface

Status: automatic selection is live for `routed_delegate_task`, exact task-thread routes, and the definitive portable routed DAG state contract used by Codex, Hermes, and OMP adapters. Built-in Hermes `delegate_task` remains one global route; persisted Hermes DAG execution uses the separate thin `routed_workflow` adapter.

## Ownership

1. A manual refresh records the current callable Codex GPT frontier and reviewed Artificial Analysis metrics.
2. For each new task, the caller classifies only the minimum intelligence tier and whether latency blocks the user.
3. `route_selector.py` filters below the intelligence floor, chooses the lowest AA task cost by default or lowest AA task time when latency-sensitive, and pins the exact route.
4. `route_adapter.py` validates the receipt and maps it to the launch surface.

Selection runs once per new task. Resumes and later messages reuse the pinned receipt.

## Inputs

- Catalogue: `skills/openai-delegation-route-research/references/current-gpt-catalog.json`
- Task request: `skills/openai-delegation-route-research/references/route-task.schema.json`
- Selection contract: `skills/openai-delegation-route-research/references/selection-contract.md`
- Auxiliary assignments: `skills/openai-delegation-route-research/references/current-aux-models.json`

The catalogue stores exact `openai-codex` model/reasoning tuples and the reviewed Artificial Analysis Intelligence Index, Time per Intelligence Index Task, Cost per Intelligence Index Task, and AA-Omniscience Hallucination Rate.

Auxiliary purposes are reviewed separately. They are not runtime delegation candidates.

## Selection

The task request supplies:

- `intelligence_tier`: `routine`, `standard`, `strong`, `demanding`, or `maximum`;
- `latency_sensitive`: true only for user-blocking or foreground dependency work;
- target surface and optional task metadata.

The selector rejects routes below the tier floor. It then chooses:

- default: lowest task cost;
- latency-sensitive: lowest task time.

Remaining metrics are deterministic tie-breakers. An explicit route override requires a reason and cannot violate the intelligence floor.

## Receipt

The version-2 receipt binds:

- selected provider, model, reasoning level, and target surface;
- task tier, latency flag, floor, and selection priority;
- all four Artificial Analysis values for the selected tuple;
- catalogue, task constraints, runtime mapping, and decision hashes.

The hashes detect accidental or silent changes. The adapter rejects changed receipts, routes, surfaces, or launch inputs for an already pinned run.

## Surface status

| Surface | Current state |
|---|---|
| Hermes `routed_delegate_task` plugin | Live: selects, atomically pins, and launches each ordinary child on the exact provider/model/reasoning tuple through the native builder/finalizer. Version-guarded; fails closed. |
| Native Hermes `delegate_task` | One configured route for all children; use only for homogeneous work. No shared-config rewrites. |
| New Hermes task thread | Active: selector receipt pins exact `hermes chat --model --provider --reasoning` flags. |
| Definitive workflow/DAG state | Live portable owner in `skills/dynamic-workflows`: selects one receipt per node; retry/resume reuse it without effort escalation. |
| Codex workflow | Live skill adapter: exact model/effort pass-through to native workers with handle-closure gate. |
| OMP workflow | Live skill + named-agent adapter: `route-<route-id>` pins exact model/effort; resolved-model fallback is rejected. |
| Hermes `routed_workflow` DAG adapter | Live: consumes the portable state owner, launches native leaf children on exact pinned routes, persists outputs, and gates interrupted retry on trusted manifest and close-witness records. It is not a reboot-surviving worker supervisor. |
| Hermes Kanban worker | Per-task reasoning and receipt inputs are not live. |
| Hermes auxiliary call | Purpose-specific static assignment; changes remain explicit config work. |
| Ordinary Codex/OMP delegation outside the DAG owner | Host-native behavior; automatic receipt routing is not claimed universally. |

## Command

```text
python skills/openai-delegation-route-research/scripts/route_selector.py select \
  --catalog <active-gpt-catalog.json> \
  --task <route-task.json> \
  --out <decision-receipt.json>
```

Catalogue refresh is manual on new GPT families. Runtime model selection is automatic. There is no release monitor, schedule, or per-task shared-config mutation.

Rollback: `hermes plugins disable routed-delegation`, start a fresh session, and use built-in `delegate_task` only for homogeneous batches. The plugin does not override the built-in tool or change delegation config.

## Live auxiliary rollback

The 2026-08-25 auxiliary promotion changed only `web_extract`, `compression`, and `curator`. Restore the prior assignments without backups:

```text
hermes config set auxiliary.web_extract.model gpt-5.4-mini
hermes config set auxiliary.web_extract.reasoning_effort ''
hermes config set auxiliary.compression.model gpt-5.4-mini
hermes config set auxiliary.compression.reasoning_effort ''
hermes config set auxiliary.curator.model gpt-5.6-sol
hermes config set auxiliary.curator.reasoning_effort ''
```

Provider and timeout values were unchanged.
