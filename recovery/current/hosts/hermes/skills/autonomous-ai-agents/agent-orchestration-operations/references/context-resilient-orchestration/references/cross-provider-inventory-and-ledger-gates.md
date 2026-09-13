# Cross-provider inventory and ledger gates

Use this reference when reconstructing work across Hermes, Codex, OMP, or another agent host.

## Provider authority patterns

- **Hermes:** inspect the live session database read-only. Follow `parent_session_id` to logical roots. An open/ended flag without recent evidence is lifecycle metadata, not proof of active work. Compression children can retain a parent chain while their cwd changes.
- **Codex:** rollout JSONL can be newer and more complete than the thread SQLite index. Group worker rollouts by native root/session identity. A database row whose rollout path is missing proves existence only; do not infer its unresolved request or completion from the title.
- **OMP:** parent and nested worker JSONL establish execution and disposal; the history database can contain later replayed requests. If history is newer than JSONL completion, preserve the contradiction rather than declaring the request closed.

For every provider, capture a reproducible high-water mark: relevant row counts/max IDs or activity times, file-set digest, sizes, and mtimes. If the store changes during inspection because audit workers are created, record the new cursor and separate those temporary workers from user work.

## Normalize without copying transcripts

A private inventory may retain:

- provider-native execution/root IDs;
- parent/spawn/import relations supported by source evidence;
- timestamps, workspace observations, archive/lifecycle state;
- source locator, bounded byte range, digest, provider/importer version;
- event-type counts and source-gap flags.

Do not retain prompt/message/tool-result bodies. Validate the output structurally with an allowed-field schema and string bounds; searching for words such as `message` is insufficient because event-type labels may legitimately contain them.

## Source-gap classes

Keep these explicit through clustering:

- lifecycle-open but stale/ambiguous;
- database row with missing raw source;
- recent raw roots absent from a stale index;
- completion claim contradicted by a later replay or live artifact;
- workspace/project metadata changed within one lineage;
- worker completed but result delivery is pending.

Do not promote a source-gap row into task authority. Titles and compressed summaries are discovery hints only.

## Ledger admission gates

A metadata ledger is not safe merely because its importer omits payload columns. Require tests for:

1. stable provider-scoped identity and distinct imports/forks;
2. idempotent replay and partial JSONL tails;
3. source replacement below a durable cursor;
4. malformed complete records with no cursor advance;
5. provider event time separate from observation time;
6. out-of-order observation bounds;
7. provider and extractor version derivations preserved independently;
8. direct metadata writes durable after reopen;
9. direct APIs rejecting free-form payload-shaped values;
10. bounded canonical locators and cryptographic digests;
11. crash/restart-safe schema migration, including partial-copy recovery;
12. payload absence after WAL close/reopen;
13. mutation APIs disabled until separately admitted.

Independent review must name exact artifact hashes. Any code/test/doc edit after review requires a new review of the changed hashes. Preserve failed reviews and corrected findings in the evidence ledger.

## Board promotion

Produce a candidate-only board first. Each item needs source handles, confidence, contradictions, dependencies, and proposed disposition. Exclude completed/archived roots, tool-only workers, and stale open metadata. Promote only after live-artifact verification and user review where the disposition changes durable task authority.
