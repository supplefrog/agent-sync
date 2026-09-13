# Winner-pilot verification probes

Use this reference when a pilot claims durable conversational state, executor/provider usage, evidence gating, checkpoint forks, image identity, or container security.

## Receipt-authority probe

Read the receipt writer and the receipt consumer separately. Identify fields that are written by the same process that later asserts them (`passed`, provider-used flags, evidence lists, terminal status, artifact hashes). In a temporary interpreter process, substitute the claimed provider/model/executor with a fake implementation that returns a plausible result. A passing provider/evidence check under substitution is a blocking self-attestation defect.

Example shape:

```python
module.create_claimed_provider = fake_provider
state = run_normal_pilot_path()
assert state["receipt"]["provider_used"] is not True
```

The probe must use the real production seam, not a reimplementation of the evaluator.

### Metadata-spoofing variant

Repeat the substitution with a fake provider/factory whose returned object is fake but whose mutable identity fields copy the expected values—for example, set `fake_factory.__module__ = "deepagents.graph"` when the gate checks only `__module__`. If the task completes and the receipt matches an independently probed distribution/module/version, the probe has demonstrated self-authentication, not independent execution. Reject the claim unless the attestation binds to independently verified package/code identity or a trusted execution source.

## Interrupted-state probe

Test the transition immediately before and after the external executor call:

1. Persist a task as `running`.
2. Close/restart the runtime without writing a completion receipt.
3. Run the normal recovery entry point.
4. Require resume, safe retry, or explicit recoverable failure.

A restart that selects only `pending` work and leaves `running` work untouched is a durable-lifecycle blocker. An in-memory worker checkpointer proves neither process restart nor crash recovery.

## Fork probe

Verify both directions:

- source state and source lineage do not change when a fork is created;
- mutating the fork (new turn, task, or status) does not alter the source.

Inspect whether the implementation uses a native checkpoint parent/configuration or merely copies serialized values into a new thread. A copied state can be a valid branch implementation, but it must be described and tested as such; a lineage label alone is not fork isolation proof.

## Evidence probe

Classify evidence as one of:

- **structural:** a non-empty field or URI string;
- **dereferenceable:** the URI resolves to content in the declared store;
- **independently attested:** content is bound to a trusted receipt/hash/source outside the mutable result.

Do not report structural evidence as provenance or live research. Test that invalid, nonexistent, and forged local URIs are rejected when the pilot claims an evidence gate.

## Container workflow probe

Inventory every container command, not only the main workload:

- user/root identity;
- network mode;
- capabilities and privilege escalation;
- root filesystem mode;
- CPU, memory, PID limits;
- named volumes and host bind mounts;
- environment variables and secret sources.

A root setup/export helper with default networking or a host bind mount is outside a workload-only sandbox contract unless it is separately constrained and inspected.

## Image and source binding probe

For a build receipt and runtime receipt:

1. Record the current tag digest before execution.
2. Compare it with the build receipt before starting the workload.
3. Prefer running by immutable digest rather than a mutable tag.
4. Compare the digest after execution as a consistency check.
5. Check source cleanliness with untracked files included; generated staging directories must not be silently accepted.

A digest recorded only after running a tag is observational evidence, not an enforced image identity.

## Command receipt fields

Record independently of embedded JSON:

- command and interpreter path;
- return code;
- actual test count and duration;
- source commit and full status output;
- image ID/digest and labels;
- container/volume inventory before and after;
- whether generated evidence was rewritten by the runner.

Keep “current run passed” separate from “the verification mechanism would reject a false result.”

## Mutable-tag and gate-completeness probes

A winner receipt that records an image digest after running a mutable tag is not an image-identity proof. Before execution, resolve the tag and compare it to the immutable digest in the build receipt and the task’s expected digest; preferably run the workload by digest. Re-check the digest after execution and treat any drift as a blocker. If the build receipt itself changes during review, preserve both observations and investigate concurrent rebuilds rather than accepting the newest receipt.

For a multi-check runner, verify the gate schema independently. It must require the full expected check-name set and count, reject missing or extra checks according to the contract, and validate receipt provenance. `all(result["checks"].values())` is insufficient because a self-authored result can omit failing or unimplemented checks and still pass.

## Crash-recovery and concurrent-ingress probes

Exercise the transition after durable `running` state and before the external executor returns. Terminate or simulate termination at that boundary, restart through the normal recovery entry point, and require resume, safe retry, cancellation, or explicit `needs_review`. A restart that only filters `pending` work leaves `running` work stranded.

Run duplicate-turn ingress through separate runtime instances/processes sharing the production checkpointer, not only concurrent calls on one object. Require a durable uniqueness/idempotency result or bounded retry behavior; a raw SQLite `database is locked` error is not turn-id deduplication proof.

## Helper-container security

Inventory setup, ownership, export, and cleanup containers as part of the workflow. A hardened workload does not satisfy a no-network/no-host-mount contract if a root helper uses default networking or a host bind mount. Record each helper’s user, network mode, capabilities, privilege escalation, rootfs mode, mounts, secrets, and resource limits, or state that the helper is outside the security boundary.

