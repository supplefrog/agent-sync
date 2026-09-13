---
name: repository-audit-validation
description: Design, implement, and verify repository-wide audit or compliance tools that validate manifests, ledgers, portable artifacts, and snapshot evidence using complete fixtures and real CLI checks.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [testing, validation, audit, fixtures, verification]
---

# Repository Audit Validation

Use this skill when the task is to build or review a repo-level checker, convergence audit, admission gate, or snapshot generator that validates multiple artifacts against a contract.

## Core approach

1. Define the contract surface first:
   - registry or manifest
   - portable artifact list
   - evidence ledger
   - snapshot or report output
2. Validate in the order that produces the clearest failures:
   - schema/version checks
   - required IDs and records
   - artifact existence and path binding
   - host or CLI version claims
   - snapshot hash/output integrity
3. Make the happy-path fixture fully complete.
   - Include every artifact the checker expects.
   - Then mutate one rule at a time for negative cases.
4. Keep errors specific.
   - A test should prove the mechanism that failed, not just the exit code.
5. Verify the checker as a real CLI.
   - run the narrow regression tests
   - run the full test file
   - run the production command against the repo root

## Fixture rule

For repo-wide validators, the minimal valid fixture must include all referenced portable artifacts, even when the assertion under test is about a different condition.

Why this matters:

- missing unrelated files can trigger a broader validation failure first;
- that hides the intended red case;
- and the resulting test becomes brittle or misleading.

Prefer one helper that creates a valid repo skeleton, then mutate only the targeted field.

## Snapshot outputs

If the tool emits a snapshot or audit artifact, verify:

- timestamp or run metadata is present;
- hash fields match the real files;
- the output path is deterministic enough for automation;
- the snapshot can be regenerated without hidden state.

## Cross-host and scheduled-surface audits

For multi-agent routing, installation, or release-monitor audits, validate the effective runtime rather than trusting declarative claims:

- Validate active machine-readable policy against its checked-in schema, including required metadata, route shape, provider, model, and reasoning effort.
- Treat `(provider, model, effort)` as one route identity; checking model and effort while omitting provider permits silent transport drift.
- Verify each host independently. A `manual-merge`, `native`, or `configured` installer status is not evidence that the live instruction surface or discovery path contains the behavior; read back the effective files/config and inspect fresh-process visibility.
- For scheduled monitors, check that the configured path resolves under the scheduler's containment rules and inspect a real execution record. Enabled state, a live gateway, passing unit tests, or a non-null schedule do not prove the job has run.
- Keep absent/never-executed evidence distinct from passing evidence; do not promote based on unit tests alone.

## Persistence and provenance ledgers

When the audited artifact persists metadata, provenance, cursors, or lifecycle assertions:

- prove semantic value boundaries at every public write seam; column names alone do not prevent payload retention;
- test decoded/canonical locator rules and the exact timestamp representation rather than broad “string-shaped” acceptance;
- enumerate migration intermediate states and require conflicts to fail closed without dropping recovery evidence;
- include diagnostic handles in the trust boundary—prefer database-enforced read-only access;
- bind independent admission review to exact artifact hashes, and distinguish delayed obsolete reviews from the current artifact.

See `references/persistence-ledger-boundary-validation.md` for the adversarial probe and migration-state matrix.

## Authoritative run/session evidence

When auditing an agent run, delegated worker group, or compliance workflow backed by event logs:

1. Inspect the complete top-level JSONL stream, then enumerate every nested worker JSONL. Treat normalized inventories as indexes only; they may be metadata-only or stale.
2. Parse event types explicitly and record exact file paths, session/worker IDs, message/custom-event IDs, and ISO timestamps for the parent goal, latest user request, substantive final verdict, and terminal `session_exit` or cancellation event.
3. Cross-check later user requests in the authoritative history database by session ID. A later database record can reopen an apparently completed JSONL task; never infer closure from an earlier assistant claim alone.
4. Classify each worker separately: substantive completion, closed without verdict, rejected then corrected, cancelled, or active. A `session_exit` with `reason=dispose` proves termination, not success; missing final text is indeterminate.
5. Determine active state from the latest authoritative event, not only inventory fields such as `ended_at`. If a stream is truncated or stale, report that limitation instead of guessing.
6. Separate temporary execution evidence (session JSONL, worker logs, staging/evaluation artifacts) from durable user work (live instructions, skills, configuration, or repositories). Treat transcript claims of promotion as claims unless the durable target is independently inspected.
7. Report concisely: parent goal, worker purpose/status, latest unresolved request, completion/cancellation evidence, active-task conclusion, workspace/dependencies, and next action. Do not reproduce raw prompts, credentials, emails, IPs, or bulk transcript bodies.

## Support files

- See `references/repo-audit-fixtures.md` for a reusable note on fixture completeness and the audit-tool failure that motivated it.
