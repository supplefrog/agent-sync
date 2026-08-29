# Context integrity ledger validation

## Scope

This is a read-only validation slice for cross-provider identity and provenance. It is not a transcript store, task manager, cleanup worker, or production orchestrator.

Native Hermes, Codex, and OMP stores remain authoritative for their own conversations, task/thread state, and lifecycle records; no Hermes board is the global task-status owner. The ledger may retain only:

- provider-native execution identities and observed versions;
- source locators, byte ranges, digests, and versioned provider/extractor derivations;
- provider event time and local observation time;
- source-linked lineage and bounded lifecycle/verification assertions;
- future action receipts and outbox state after a separate mutation admission gate.

It must not retain raw prompts, message bodies, tool results, credentials, or complete transcript payloads. Selective raw evidence escrow is outside this slice and requires an explicit retention and access policy.

## Current executable surface

`tools/context_ledger.py` exposes only:

- `init` — create the local SQLite schema;
- `ingest-jsonl` — read complete JSONL records and store locator/digest metadata;
- `stats` — report metadata row counts.

Provider mutations are hard-disabled. No live provider source is configured automatically.

## Validated invariants

`tests/test_context_ledger.py` exercises the production CLI and persistence seam:

- native execution identity is deterministic and provider-scoped;
- execution observation bounds remain ordered when sources are read out of order;
- offset-aware observation times are normalized to canonical UTC before comparison;
- imported/forked executions remain distinct unless native evidence establishes continuity;
- duplicate ingestion adds no duplicate source events;
- partial JSONL tails do not advance the cursor;
- malformed complete records fail without advancing state;
- source replacement before a durable cursor is detected even when file length is unchanged;
- provider event time and observation time remain separate;
- event-time extraction rejects arbitrary payload text before any SQL write;
- replay reconstructs equivalent source-event IDs;
- changing either provider or extractor version preserves a separate derivation without duplicating source identity;
- lineage and contradictory assertions remain independently queryable;
- direct provenance writes survive reopen;
- direct writes reject free-form locators, non-SHA-256 digests, unbounded identifiers, and free-form assertions;
- file and SQLite locators reject non-local authorities, reversed byte ranges, decoded control characters, backslashes, dot-segments, and noncanonical URI encoding;
- provider event timestamps require complete offset-aware datetime strings; numeric epochs are not accepted;
- configured event-time extraction requires object records with the requested field present and valid;
- the `unknown-legacy` migration sentinel cannot be used as a live provider version;
- interrupted legacy-cursor migration converges from old/current/legacy table combinations and rejects conflicting cursor evidence without dropping recovery state;
- the diagnostic SQLite handle is opened in `mode=ro`, accepts only `SELECT` and `PRAGMA table_info(...)`, and uses a deny-by-default SQLite authorizer that blocks attach/detach, schema, write, and write-capable pragma opcodes;
- transcript payload text is absent after WAL close/reopen and payload-like columns are absent;
- provider mutations cannot be enqueued in validation mode.

## Remaining gates

Do not connect production mutation or cleanup until all are proven:

1. pin live provider and importer versions with every observation;
2. implement narrow Hermes, Codex, and OMP read-only importers without direct writes to provider SQLite/JSONL;
3. run end-to-end identity, compaction, and replay fixtures for all three providers;
4. define retention, encryption/access, and deletion policy for selective evidence escrow;
5. map external executions to Hermes Kanban without duplicating task authority;
6. shadow lifecycle decisions and prove ambiguous activity, sharing, reference, or lineage blocks cleanup;
7. add idempotent provider APIs, readback, reconciliation, and durable receipts one reversible action at a time;
8. keep hard deletion disabled until crash, race, replay, and privacy gates pass.

## Rollback

Delete the staged ledger database and stop its importer. Native provider stores and Hermes Kanban remain unchanged.
