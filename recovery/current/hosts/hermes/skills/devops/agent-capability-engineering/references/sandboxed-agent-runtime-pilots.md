# Sandboxed agent-runtime pilots

Use when an intact agent runtime must be exercised with real credentials or models without promoting it into live configuration.

## Build and identity

1. Pin the upstream source commit and refuse **all** working-tree changes, including untracked files, before building. A clean tracked diff is insufficient when untracked generated files can enter a build context or alter workspace resolution.
2. Build from a source archive rather than a developer checkout containing ignored `dist/`, caches, or `node_modules`. If runtime packages consume generated workspace outputs, build those outputs explicitly in the image; a successful dependency install does not prove the source archive is runnable.
3. Preserve the upstream workspace layout when package metadata uses relative sibling sources. Archive the intact monorepo and install from the package's original relative path; copying only one package can silently break `uv`/workspace source resolution or replace the evaluated commit with mismatched registry dependencies.
4. Pin the base image by digest and record the resulting immutable image ID. At execution, read the build receipt first, require the mutable tag to resolve to that ID, create/run the workload **by immutable ID**, and inspect the created container's `Image` field before starting it. Recording the tag's ID after execution does not prevent tag drift.
5. Keep source staging disposable. Build wrappers must surface captured stdout and stderr on failure; a wrapper that raises only the exit code destroys the evidence needed to classify packaging versus runtime failures.
6. Prebuild interpreter/kernel dependencies into the immutable image when runtime bootstrap would require a writable home or network. Verify the final non-root user can traverse and execute every interpreter target; managed virtual environments may symlink into a root-private directory unless their install root is explicitly relocated.
7. Require an exact named check manifest, not merely `all(values)` or an expected count. Missing checks, renamed checks, duplicates hidden by a map, and extra unreviewed checks must fail closed.
8. Do not accept self-issued flags such as `used_real_runtime=true`, or mutable metadata such as `callable.__module__` / `__qualname__`, as runtime proof. A forged callable can copy those strings and emit a matching receipt. Bind execution to the immutable package identity instead:
   - fingerprint the expected callable at process initialization with distribution/version, qualname, serialized code-object hash, and on-disk source-file hash;
   - immediately before use, compare the currently imported callable to that fingerprint, reload its defining module from the immutable package source, verify the reloaded callable again, and invoke the verified local object rather than a mutable global;
   - serialize only the short import/reload/verification phase when workers fan out concurrently—concurrent `importlib.reload()` calls can produce false mismatches—then release that lock before worker execution;
   - fail closed to durable `needs_review` on missing/unreadable source, any identity mismatch, or reload failure, and prove a forged module/qualname callable is never invoked;
   - from a separate hardened container/process, independently compute the same distribution, code, and source hashes and require task receipts to match.

This binds an ordinary monkeypatch/substitution probe to the packaged callable; it does not claim resistance to arbitrary code execution that can replace the verifier itself. Keep the capability claim narrow: callable binding proves the packaged execution seam, not live provider quality.

## Credential boundary

- Reuse an existing credential only through a temporary, provider-scoped store. Transform it locally without printing token values or placing secrets in command arguments.
- Seed a disposable state volume, mount no unrelated host state, and delete the credential/state volume after receipts are copied.
- Disable runtime telemetry explicitly when the candidate supports it.
- Never bake credentials into an image or retain them in evaluation evidence.

## Minimum process/filesystem boundary

Run the candidate as a non-root UID with:

- read-only root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- bounded PIDs, memory, and CPU;
- tmpfs only where runtime scratch is required;
- separate scoped volumes for state and workspace;
- no host project, agent home, or broad credential mount.

Inspect the live workload container configuration and store the receipt. Apply the same default-deny posture to setup, export, and attestation helpers: `network=none`, read-only rootfs, all capabilities dropped, `no-new-privileges`, and only the mounts they need. If a root setup helper genuinely requires one capability (for example `CHOWN`), add only that capability; if a root export helper is needed for a Windows bind mount, copy only the named non-secret receipt without metadata preservation. A hardened workload does not excuse an unconstrained root helper.

A Docker bridge is **not** an enforced network policy: unrestricted outbound access leaves the network-security gate open. Full admission requires an internal-only agent network plus an independently enforced destination/protocol allowlist or another verified egress boundary.

## Protocol-level acceptance

Test relationships, not labels:

1. Read initial model/session state through the supported RPC/API.
2. Make one real provider call.
3. Submit steering while the first run is active. Verify acceptance, then wait for the steering run and action queue to become quiescent before sending another prompt; queued steering may be a separate agent run rather than part of the first `agent_end`.
4. In a second turn, read state created by the first turn without reassigning it and write an exact artifact.
5. Admit a recursive child, capture its stable child ID, require an exact child artifact, and preserve the parent lifecycle notification.
6. Copy canonical session evidence before deleting disposable volumes.

Treat each layer separately:

- RPC success proves command acceptance only.
- Assistant prose proves neither tool execution nor state continuity.
- Exact workspace contents prove the requested side effect.
- Persisted session/lifecycle records prove identity, lineage, and delivery.
- Container inspection proves only the configured process/filesystem boundary, not network allowlisting or application-level approval policy.

## Durable approval and failure recovery

For side-effecting or self-modifying work, verify approval at the state-transition boundary rather than in a worker prompt:

1. Persist `awaiting_approval` before dispatch and prove blocked work produces no worker artifact.
2. Persist a stable decision ID; duplicate delivery of the same approval must add neither another lineage event nor another execution.
3. Move to executable state only after the durable decision exists. After restart, the approval and task state must agree.
4. On executor error or ambiguous completion, persist `needs_review` before returning the error. Do not invent partial success from an artifact or model text when terminal receipts are missing.
5. Verify restart preserves `needs_review`; cancellation/retry decisions must be idempotent and append one durable lineage event. A cancelled or review-held task must not be redispatched as ordinary pending work.
6. Treat persisted `running` state as a crash-recovery problem, not as pending work. Hold a separate per-conversation execution-owner lock through worker execution while releasing the shorter mutation lock so new turns can still arrive. After an owner crash, reacquiring that execution lock makes leftover `running` tasks provably orphaned; move them to `needs_review` without rerun. For runtimes sharing one local checkpoint filesystem, use an OS file lock plus SQLite timeout/transaction discipline rather than per-instance mutexes. This is still not a distributed guarantee; prove the production database/queue lock separately.
7. For fan-out failure, distinguish tasks with confirmed terminal receipts from tasks whose outcome is ambiguous. Conservatively reviewing all work is safe but not evidence that every worker failed.

Cross-check human/operator stdout against the durable result receipt. A stale pre-restart status variable can make a successful receipt appear active or cancelled work appear unfinished; any disagreement is a verification failure until the summary is fixed and rerun.

## Bounded runtime self-modification proof

A staged file, model statement, task label, or changed state field does not prove self-modification. For a bounded runtime-policy change:

1. Define an allowlisted typed policy schema with explicit value bounds. Reject unknown keys and require durable approval before the task can execute.
2. Record the base policy version when staging. Promotion must fail to `needs_review` if another policy was promoted first; never last-write-wins over a newer runtime.
3. Apply the promoted value at the real consumer boundary. Observe the production call or behavior—for example, a delegating recorder that captures executor configuration while still invoking the real executor. Merely reading the new value back from state is self-fulfilling evidence.
4. Persist previous and promoted policy receipts, restart the runtime, and prove the promoted behavior remains active.
5. Roll back only when the current policy still equals the promoted revision. Persist a stable rollback decision ID; duplicate rollback delivery adds no event and performs no second mutation.
6. Keep the claim narrow. A verified configuration-policy mutation is not evidence of autonomous code/tool rewriting. Code, tool, prompt, or skill changes still require isolated worktrees/images, held-out evaluation, independent review, immutable promotion, and revision rollback.

## Recursive-agent receipt semantics

Do not collapse artifact production, model completion, supervisor state, explicit child communication, and lifecycle fallback into one pass:

- **Artifact produced:** proves only the requested side effect; the worker may still be active or stuck.
- **Model turn ended:** final assistant text proves the model stopped generating, not that the supervisor committed a terminal worker state.
- **Terminal lifecycle:** the canonical worker registry/event store reaches exactly one durable terminal state without evaluator shutdown intervention.
- **Explicit reply:** the persisted inter-agent message contains the requested payload from the child.
- **Fallback notification:** the runtime reports that the child completed without replying and includes its identity and last result.
- **Silent artifact:** the child wrote output but no parent notification exists.

Require the terminal lifecycle plus either an explicit reply or an honest fallback. An exact explicit reply is strongest. A structured fallback is degraded-but-recoverable evidence, not equivalent instruction adherence. A silent artifact fails the parent-notification contract.

Capture canonical state **before cleanup**. Stop, kill, EOF, or supervisor teardown may synthesize a fallback notification; a receipt emitted only during cleanup does not prove normal completion delivery. If the model produced an artifact/final answer while the registry remains `running`, treat that as a lifecycle failure even when forced shutdown later reports completion.

Some RPC message-list views omit persisted custom lifecycle records. When a notification is absent from the convenience API, inspect the canonical session JSONL/event store before concluding delivery failed. Match the structured envelope and exact detail fields; never pass because the expected token appears in the original user prompt, generated tool source, polling output, or artifact contents.

For intermittent child lifecycle or delivery, one passing rerun is insufficient. Repeat the production seam across explicit reply, omitted reply, artifact-before-final, timeout/cancel, and process restart; record outcome frequency. A candidate cannot own durable fleet status until every admitted child deterministically reaches one terminal state and one parent-visible receipt without shutdown fallback.

## Cleanup, independent review, and reporting

- Give an independent reviewer the exact source commits, expected image identity, intended behavior, and real rerun commands. Verify the reviewer’s findings rather than treating its verdict as authority.
- Any material pilot, test, Dockerfile, dependency, runner, or receipt change invalidates an in-flight review of the previous artifact. Rebuild when image inputs changed, record the new identity, mark the old review superseded, and request a fresh review against the exact current package.
- When an asynchronous review returns, compare its expected image/package identity and test/check manifest with the current artifact **before** applying its verdict. A stale verdict is not authoritative for the new build, but its findings are still useful bug-class evidence: map each finding to a current fix or reproduce it against the current artifact rather than dismissing it solely because the hash is old.
- When several reviews can complete out of order, maintain a machine-readable review-lineage receipt keyed by delegation/review ID and exact image/package identity. Record verdict, blocking classes, evidence path, and `current`, `superseded`, or `resolved/narrowed` status; require exactly one current authoritative review and verify every referenced evidence path. Include the lineage receipt in the hashed decision package so delayed notifications cannot silently rewrite the selection narrative.
- Copy only non-secret event/session receipts and exact output artifacts.
- Stop containers and remove disposable volumes even on failure.
- Report partial success by layer. Do not convert a near-pass, fallback, or repaired contender into an intact upstream pass.
- Keep unresolved network, restart, approval, or delivery gaps explicit in the substrate decision.
