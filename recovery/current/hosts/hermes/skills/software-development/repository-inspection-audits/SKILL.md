---
name: repository-inspection-audits
description: Use when inspecting repositories or building audit checks.
version: 1.0.1
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [repository, inspection, audit, validation, metrics]
---

# Repository Inspection and Audits

Use this umbrella for repository-wide inspection, measurement, compliance, evidence, and validator work.

## Routing

- Audit/compliance CLI design, manifests, ledgers, snapshots, complete fixtures, cross-host evidence, and run/session authority: `references/repository-audit-validation/SKILL.md`.
- Hermes memory-vs-skill persistence-routing audit: `references/repository-audit-validation/references/persistence-routing-audits/SKILL.md`.
- LOC, language, file-count, and code/comment composition with pygount: use the top-level `codebase-inspection` skill.
- Frozen-review drift and concurrency probes: `references/frozen-review-drift-and-concurrency.md`.

## Shared workflow

1. Define the inventory or contract and authoritative repository scope.
2. Exclude generated, dependency, cache, and build trees where they would distort results.
3. Inspect test setup and cleanup before running unfamiliar migration/updater suites: search for `git init`, `git config`, commits, checkout/reset, and deletion paths. Run repository-mutating fixtures in an isolated copy with its own `.git`, not the user's working checkout; path-string comparisons can misclassify the real repository as a fixture. Canonicalize both paths before comparing Git's toplevel with the process cwd. Then build a complete valid baseline fixture before mutating one rule per negative test.
4. Prefer exact source paths, schema versions, artifact hashes, and live CLI output.
5. Distinguish absent, stale, configured, passing, and runtime-verified evidence.
6. Run the real production command and verify generated snapshots/reports are reproducible.

Keep metric inventory separate from compliance verdicts unless the contract explicitly connects them.

For manifest-driven updates, preserve the original revision, local changes, and user-artifact hashes before apply; a backup branch alone does not capture ignored files or uncommitted content. After an old-to-new jump, verify the target manifest's files and dependencies, not just the version banner. If a second pass is necessary, retain the original rollback handle separately because the newest backup may contain only an intermediate installation. Diagnose same-version drift with a manifest-scoped diff and compare materialized entrypoint content with its canonical target before reapplying; platform-compatible file representations can differ from upstream without missing functionality.

## Intact-system agent/conversational-OS evaluations

When evaluating a complete agent system against a durable conversational-OS outcome, do not assess isolated components as transplantable parts. Preserve the system boundary and trace one end-to-end identity across ingress, event persistence, executor selection, model/runtime execution, tools, sandbox, adapters, scheduler, UI/streaming, self-modification, cloning, and recovery.

1. Establish the intact baseline first: repository scope, git state, manifests, documented architecture, runtime prerequisites, and available credentials. Record what was actually run separately from what source/docs claim.
2. Build a capability matrix with three labels: **source-verified** (implementation and wiring inspected), **test-verified** (real local test/build passed), and **runtime-verified** (real end-to-end path exercised). Never promote source-only claims to runtime capability.
3. Follow the durable identity: identify where agent identity, conversation history, event head/cursor, executor/harness config, model binding, sandbox ownership, secrets, adapter records, and scheduler state live. Test or trace whether an executor swap preserves history and whether switching is per-agent, per-conversation, or actually multiplexed.
4. Trace event integrity end to end: ingress acceptance, turn ownership, model/tool events, stream events, host/custom events, wakeups, replay/fork, and UI consumption. Inspect both local and remote/HTTP transports; a local watcher does not prove multi-client streaming.
5. Audit mutable-vs-trusted boundaries explicitly: what the agent can edit, where secrets are resolved, whether local-process mode is isolated, how approval requests are handled, what snapshots preserve, and whether rollback leaves canonical history intact.
6. Separate implemented recovery from roadmap language. Look for explicit docs/source gaps around sandbox cloning, agent cloning/lineage, migration, cross-process adoption, service lifecycle events, and canary validation. Resolve contradictions between marketing/index pages and engineering status docs in favor of executable source and the more specific status document.
7. For third-party coding runtimes, require a concrete adapter checklist: executable/image, credentials, prompt/history projection, native thread/session resume, tool-call mapping, server-request/approval policy, streaming, durable protocol/custom events, sandbox/network policy, crash cleanup, fork/replay tests, and a CLI/config preset. Absence of a vendor name in source is evidence of no native support, not evidence that a generic adapter already works.
8. End with the smallest honest pilot: one identity, one conversation, one low-risk task, one sandbox, event inspection, fork/replay, then executor swap. Add adapters, scheduler wakeups, snapshots, and cloning only after the core identity/replay seam passes.

Use `references/intact-system-evaluation.md` for the evidence matrix, executor-swap checklist, and pilot template.

## Grounded-verification contract audits

When reviewing a machine-readable verification gate with freeze receipts, role isolation, pilot manifests, and result reports:

1. Verify the corrected positive fixture and current pilot evidence, but treat every claimed hash, test count, verdict, and report as a claim to re-execute.
2. Run the real focused suite, the valid/negative CLI paths, the pilot evaluator, and the repository-wide suite when practical. Record actual counts instead of repeating embedded result claims.
3. Add adversarial probes that mutate criteria and the pilot manifest, recompute the current hash, delete decision events, mutate the freeze receipt and its digest, rewrite the source reference, rewrite hash-chain fields, and hide each held-out blocker independently.
4. Distinguish a hash mismatch from a trust-anchor failure. A receipt digest stored inside the same mutable contract is not an immutable anchor: mutate the receipt, update its contract digest, set its original hash to the altered current hash, and confirm the gate still rejects. If it passes, report a blocking self-authorized-freeze finding.
5. Bind the source identifier to the authoritative task/card, not merely to criterion fields that all agree with the same attacker-controlled reference. Test a coordinated rewrite to the previously used or adjacent task ID.
6. Derive or independently attest metrics such as false positives and false negatives. Schema minimums are not metric integrity; mutate each reported metric and verify rejection or provenance validation.
7. Inventory **all** related grounded fixtures, result reports, verdicts, and docs—not only the newest pilot report—and check each for generation drift. A corrected contract with stale reports (wrong source ID, blocker count, event count, test count, validation count, trust root, or artifact hash) is an evidence-integrity blocker unless the file is explicitly marked historical/superseded. Do not let a current pilot report's clean hashes hide an older checked-in verdict that still claims authority.
8. Re-execute reported test suites and record actual counts/timings separately from embedded claims. Treat changed counts, roots, or hashes as report drift requiring regeneration or explicit archival marking; do not silently normalize them in the audit.
9. For held-out state, mutate one condition at a time and require the validator to reject an unchanged reported manifest when deterministic evidence no longer derives that blocker.
9. For typed independent-test-author receipts, run the artifact/receipt substitution matrix in `references/grounded-verification-adversarial-probes.md`. A digest stored in the same mutable contract (or a receipt whose digest is also mutable) is not an immutable artifact trust anchor; coordinated content substitution must be rejected or reported as a blocking integrity defect.

## Winner-pilot and grounded-runtime verification

When independently verifying a proposed agent/conversational-OS pilot, treat a green self-authored receipt as a claim, not proof. The pilot evaluator and its evidence writer are often the same code path, so add independent probes at the boundaries that the pilot claims to validate:

1. **Inventory before execution.** Read the runner, image builder, Dockerfile, tests, receipts, and evidence. Record the authoritative source commits, full working-tree cleanliness (including untracked files), image tag and digest, and all containers/volumes before the run.
2. **Re-execute the real seam.** Run the exact focused test command with the specified interpreter and the exact sandbox runner. Record actual return codes, test counts, elapsed time, image digest, and post-run cleanup separately from embedded receipt fields.
3. **Challenge authority.** Search for checks that merely inspect fields written by the system under test. Monkeypatch or substitute the claimed provider/executor/model in a temporary process; if a fake provider can still produce `deep_agents=true`, “completed,” or evidence URIs, the receipt is not an independent gate.
4. **Probe metadata spoofing, not only ordinary substitution.** A fail-closed check on a mutable attribute such as `callable.__module__`, a distribution name, a version string, or a receipt field can be bypassed by a fake implementation that copies the expected metadata. In the real production seam, run a fake provider/factory whose returned object is fake but whose claimed module/distribution metadata matches the expected value. If it completes and emits an indistinguishable attestation, classify the attestation as self-authenticated and blocking; bind it to an independently verified code/package identity or trusted execution receipt instead.
5. **Validate evidence semantically.** A non-empty citation/URI string is not provenance. Require dereferenceable or otherwise independently attestable evidence, and distinguish a deterministic local placeholder from real research/tool output.
5. **Exercise interrupted lifecycle states.** Do not test only terminal restart. Simulate a process crash after durable state changes to `running` and verify restart either resumes, retries safely, or transitions to an explicit recoverable state. Inspect whether worker/agent checkpoints are durable (`InMemorySaver` is not restart recovery).
6. **Test fork isolation in both directions.** Confirm the canonical source remains unchanged after fork creation and after mutating the branch. A copied state plus a lineage label is not automatically a native checkpoint fork; inspect the persistence/config semantics.
7. **Audit every container in the workflow.** Inspect the workload container and all setup/export/helper containers for user, network, capabilities, rootfs, resource limits, volume/bind mounts, and secrets. A hardened workload does not make a root helper with default networking and a host bind mount part of the same security contract.
8. **Require immutable artifact binding.** A mutable image tag with a digest recorded after execution is observation, not pinning. Compare the runtime digest to the build receipt before starting, or run by digest. Build cleanliness checks must include untracked files and generated staging content.
9. **Report current success separately from verifier weaknesses.** It is valid for current commits, tests, image identity, and cleanup to pass while the pilot remains non-ship due to untested crash recovery, self-authenticated evidence, or unenforced identity/security claims.
10. **Separate execution layers and consent boundaries.** For concurrency-corrected pilots, verify three distinct claims separately: (a) one-process regression tests, (b) repeated same-conversation ingress/completion probes through the real runtime seam, and (c) multi-process/shared-checkpointer behavior. Never promote (a) to (b) or (c); explicitly label multi-process persistence as unverified unless separate runtime instances/processes sharing production persistence were exercised. If a required command is blocked before execution by an approval/consent boundary or unavailable runtime, record it as **not executed**, do not infer its output, and do not reissue the same action through another tool. Keep this verification gap separate from code defects, while withholding a full-ship verdict when the requested gate was not actually run.

See `references/winner-pilot-verification.md` for the reusable adversarial probe checklist and command patterns.

## Delegated Kanban terminal handoff

When this audit is run by a delegated Kanban worker, preflight the authoritative board close path before starting. Do not assume the `hermes kanban complete`/`block` CLI can mutate a task from a child context. Inspect supported syntax with `hermes kanban --help`, `hermes kanban complete --help`, and `hermes kanban block --help`; a read-only `hermes kanban show <task-id>` may itself be refused by child-context initialization guards. If authorized, make at most one supported completion/block attempt using the CLI's `--summary`/`--metadata` or typed block-reason fields. If the child-context guard rejects CLI mutation, stop retrying alternate syntax or equivalent commands; never bypass the guard through SQLite/direct persistence. Return the evidence, exact refusal, verifier decision, and durable artifact paths to the parent/orchestrator, explicitly label the board transition as not performed, and leave board closure to the parent/orchestrator. A read-only repository audit must not edit files just to manufacture a terminal board receipt. See `references/delegated-kanban-handoff.md` for the concrete handoff recipe and refusal boundary. In a delegated child context, a successful repository audit and a board transition are separate outcomes: preflight the supported CLI syntax, make at most one authorized mutation attempt, and if the exact delegated-child mutation guard appears, stop retrying and report the refusal plus the verified handoff to the parent/orchestrator. Treat that guard as an operational handoff blocker, not as a repository-verification failure.
