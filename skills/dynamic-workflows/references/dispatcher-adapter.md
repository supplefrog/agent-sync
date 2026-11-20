# Workflow dispatch through T3 and Paseo

Read the [runtime contract](runtime-contract.md) first. The same V3 plan, state, route selector and acceptance step apply to both dispatchers.

## Choose a dispatcher and worker

An active T3 controller uses `t3-workflow` and discovers the available provider instances with T3’s `orchestrator_capabilities`. Use the exact available instance, model and advertised reasoning option. Keep T3’s inherited approval mode. A standalone controller can use its existing native adapter when it covers the task. Use `paseo-workflow` for shared delegation outside T3 when an eligible native route cannot provide the chosen worker. Use the existing Paseo skill to discover the configured local dispatcher and its saved worker profiles. Start the configured daemon on demand if it is stopped. Use the selected profile's exact model, effort and approval mode.

Match the task to the advertised worker capability and the user's request. Prefer the current agent when alternatives offer the same fit and launching a peer adds no value. Different workers on the same dispatcher share the same interface. The T3 target must already be available in T3. Preserve the approval and account boundaries.

This adapter currently accepts small inline text tasks with read risk, no tools or effects, one attempt and an independent complete verifier. Verify the whole native child activity, including any tools it actually used. Use a native adapter for tasks with tool or effect requirements that this dispatcher record cannot establish. Use subscription model targets from the configured workers and current positive quota in `codex-main`. Unknown costs require explicit route preference and a zero reserve, as in the V3 selector. Declare that preference as `["t3-dispatch"]` in T3 or `["paseo-dispatch"]` for the shared adapter. Match explicit model constraints against the native model ID, including any provider prefix.

## Refresh availability

Save the selected target from the live dispatcher in a local JSON file with these fields.

| Field | T3 | Paseo |
| --- | --- | --- |
| `dispatcher` | `t3` | `paseo` |
| `scope` | `environmentId:projectId:parentThreadId` | `serverId:workspaceId` from Paseo status and workspace list |
| `instance` | `providerInstanceId` | Configured provider ID |
| `model` | Advertised model ID | Profile model ID |
| `effort` | Selected advertised effort | Profile `thinkingOptionId` |
| `option` | Advertised option ID such as `reasoningEffort` | `thinkingOptionId` |
| `mode` | `inherit` | Profile `modeId` |

Run `python scripts/worker_dispatch.py prepare <target.json> --root <runs-root>/.worker-dispatch`, using the same runs root passed to `workflow_state.py init`. For T3 pass `--capabilities <readback.json>` from the active parent. The adapter returns a current observation, a single new probe, or a pending attempt. Save a new probe response as a local request file and launch it once using the instructions below. When the worker is terminal, save the app data to a result file and run `python scripts/worker_dispatch.py complete <cache-file> <attempt> <result.json>`. The challenge renews this exact target for 24 hours from the native observation. Reconcile a pending attempt with the dispatcher before launching more work. If native readback establishes that the probe failed or no child was created, clear it with `probe-failed <cache-file> <attempt> --reason <reason>`.

Use the same procedure for a probe and a task.

- **T3.** Send the returned command to the named native tool. Read the exact child task's `task_status` and its original thread's `t3_thread_read` with `view: activity`, `limit: 100` and `maxCharsPerItem: 20000`. Save the actual response objects as `{"environment": "<environmentId>", "status": <task_status>, "activity": <t3_thread_read>}`. The adapter checks the pinned parent, project, route, initial assignment, child run, terminal state and complete local activity. Keep normal T3 approvals.
- **Paseo.** Execute `python scripts/worker_dispatch.py paseo-launch <request.json> --home <configured-paseo-home>`. This starts the configured local daemon on demand and returns the Paseo agent ID. Once it settles, run `python scripts/worker_dispatch.py paseo-read <target.json> <agent-id> <request.json> --home <configured-paseo-home>` and save the result. The helper checks the exact agent and workspace, archives the settled agent and records the app status and logs. For a workflow task, use the existing `dispatcher-launch.json` as the request file.

The workflow relies on the controller collecting real app data. Route observations establish the application-selected route. T3 may omit the provider-reported executed model. Tool-free readback is a completion check. The dispatched worker still runs under the app's usual permissions, so keep assignments small and effect-free.

## Run and resume

1. Initialize with `--target-surface t3-workflow` or `--target-surface paseo-workflow`. For each ready task, use `dispatch --execution-context-file <context.json>` with the actual `active_t3` boolean, the `dispatcher_scope` identity and the `dispatcher_observation` returned by the refresh command.
2. Follow the normal parent or defer action when selected. For a model action, claim the task, then run `broker-launch <run> <task-id> --launch-token <token>`. For T3 supply `--capabilities` with current parent readback. The command saves the single launch intent and includes a unique attempt marker. Invoke it through the chosen app and immediately record the returned native handle with the normal `start` command and the same claim token.
3. If the launch response is lost, reconcile the existing child by the T3 request ID or the Paseo child assignment and title. Preserve an ambiguous claim until reconciliation. A deadline or approval is a pending state. Only abort a launch after native readback establishes that no child was created. Use native cancellation when stopping a child.
4. Save the app readback to `tasks/<task-id>/dispatcher-result.json` and its exact answer to the task output file. Finish with the original handle, claim token and `--handle-closed` once native work is terminal. The workflow checks the app data and binds the result and output bytes. Verify the result against the plan independently before using it.

A successful refresh can admit a new decision or renew an existing decision's exact launch target. Existing decisions retain their original target, evidence and transport. If the route expires before launch, refresh that same target and continue from the existing claim or decision. A resumed active child continues on its original dispatcher.
