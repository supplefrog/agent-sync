# Automatic GPT route selection contract

## Outcome

For each new task, choose the least expensive reviewed Codex GPT route that meets the task's intelligence requirement. When completion is latency-sensitive, choose the fastest qualifying route instead. Do not collapse intelligence, time, and cost into one weighted score.

## Catalogue refresh

Refresh manually only after the user invokes the workflow for a new GPT family. There is no scheduled polling, automatic promotion, or runtime Artificial Analysis dependency.

1. Enumerate exact callable model/reasoning tuples from the user's current `openai-codex` account.
2. Record exact Artificial Analysis intelligence, task time, task cost, and hallucination values.
3. Keep the useful nondominated frontier. An omitted available model needs evidence, such as another model being at least as intelligent and cheaper across the relevant frontier.
4. Define catalogue-specific, strictly increasing intelligence floors for `routine`, `standard`, `strong`, `demanding`, and `maximum`. Every floor must have at least one qualifying route.
5. Review auxiliary purposes separately and preserve specialized/non-Codex incumbents without task-specific replacement evidence.

## Runtime request

The caller supplies:

- `intelligence_tier`: the minimum required capability, inferred from the task rather than the desired model;
- `latency_sensitive`: true only when completion blocks the user or a foreground dependency;
- the target surface and optional task metadata.

`standard` is the default tier for ordinary professional work. `maximum` is reserved for quality-ceiling tasks, not general uncertainty.

## Deterministic selection

1. Reject candidates below the tier's intelligence floor.
2. Default: sort qualifying routes by task cost, then task time, hallucination rate, excess intelligence, and route ID.
3. Latency-sensitive: sort by task time, then task cost, hallucination rate, excess intelligence, and route ID.
4. Pin the first route in a hash-bound receipt before launch.
5. An explicit `selected_route_id` override requires a reason and still must meet the intelligence floor.
6. Unknown tiers, unreachable floors, unavailable overrides, or malformed requests fail closed.

The selector chooses the model. The caller chooses only the task tier and whether latency matters.

For DAG nodes, a bounded execution retry reuses the same receipt. Failure does not trigger a Medium → High → xhigh → Max ladder; unresolved work returns to the parent/human or becomes a separately authorized new task.

## Lifecycle

Select once per new task. Existing runs and resumes reuse their receipt. Reselect only for a new task, an explicit user change, or an authorized retry/escalation.

## Surface boundaries

- Task threads and receipt-aware workflow tasks can enforce exact model/provider/reasoning tuples. `codex-workflow` passes the tuple directly to native workers; `omp-workflow` uses exact-route named agents and verifies the resolved model.
- Native `delegate_task` currently has one configured route for all children. It is suitable only for homogeneous work on that route; shared config must not be mutated between children.
- Auxiliary assignments are purpose-specific static choices, not delegation candidates.
