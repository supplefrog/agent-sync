# Post-hoc knowledge and graph-linked practice

This is an optional source implementation over the existing atomic lesson store. It reuses pinned upstream teacher-prose coverage, batching, proposition/chain merge, identity union, chain simplification and graph derivation. It does not start an extractor, auditor, provider client, background watcher or new teaching runtime.

Enroll a **new private workspace-relative** `knowledgeRoot` explicitly in each participating lesson's trusted configuration. It must be physically separate from every lesson state, export and external native graph directory. The same private knowledge root can be shared by explicitly enrolled lessons. Absence means no knowledge reads or writes. Existing read-only `graphRoot` enrollment remains supported instead; do not set both. This new writable enrollment is not covered by a prior export-folder-only activation grant. No existing graph is modified or migrated automatically.

The private `knowledge.json` record contains native-shaped node/chain/coverage assertions, extraction batch identities, findings and identity verdicts. It uses the existing versioned atomic file store and4MiB refusal boundary. The native graph's logical contracts are reused; this atomic container is not a claim of flat-JSONL storage compatibility with a live standalone profile. It contains no credentials or usage estimates. Its derived graph contains teacher propositions, never plan-node mastery or a learner score.

## Existing host command lane

All commands go by JSON stdin to the existing fixed CLI/config, qualified to the owning conversation. `op` is `knowledge`, with the configured `chatId` and the following `action`:

1. `status`: derived covered/uncovered teacher-prose counts and estimated tokens. Learner messages, tool calls, tool results and hidden question commitments are excluded by upstream coverage selection.
2. `prepare`: include `expectedRevision` and optionally `budget` (default8000 estimated tokens). Select the oldest uncovered teacher passages without splitting a passage, persist their fingerprints/owner, and return labeled `TEACHER [messageId]` lines plus `batchId`. Source overflow refuses rather than truncates. This is a snapshot operation, not a model call.
3. `findings`: include `batchId`, declared `authorship` (`host-agent` or explicitly synthetic fixture), and upstream-shaped `findings:{propositions,chains}`. Propositions carry local `id`, `name`, `statement`, `aliases` and an actual teacher `messageId` in this batch. Chain endpoints must resolve locally or in the enrolled graph. Findings are immutable once recorded. Source edits invalidate stale batches.
4. `audit`: include `batchId`. Returns the new propositions and a first page of fresh existing identities, omitting teacher source, learner data, proposed chains and new passage IDs. It returns the exact `graphRevision` for merge. The existing-identity page has explicit `total/nextOffset`; it is not presented as the entire graph. Use `graph` lookup for further/search pages. Oversized audit contexts refuse rather than truncate.
5. `merge`: include `batchId`, that `graphRevision`, declared `authorship`, and `verdicts:{links:[{id,linkTo}]}`. Audit links must resolve uniquely to existing graph identities. Absent links create new propositions. The actual upstream deterministic merger joins aliases/provenance, resolves chains, simplifies redundant arguments and appends coverage. The entire record commits atomically. A changed audit revision or already-covered overlapping batch refuses. An identical completed merge is a no-op; different replay judgments refuse.
6. `graph`: search/page the derived proposition catalogue with plain `query` (optional), `offset` (default0) and `limit` (default50, maximum100). A later page must include its captured `graphRevision`; changed graphs refuse stale pagination. Results explicitly report `total/nextOffset`, with a256KiB output boundary. This is lookup, not automatic equivalence judging. The inline diagram separately uses the actual upstream chain derivation. No understanding/mastery claim is inferred from coverage.

The host supplies the extraction and identity judgments. A separate authorized auditor context is required to reproduce upstream's source-blind model separation. A projection excluding source cannot make the same model forget source it already saw; no actor isolation or automatic dispatch is claimed. No additional model turns are authorized by these commands or this document.

## Learner review and practice

Normal lesson exports include only this lesson's proposition neighborhood and its own teacher-passage provenance. The existing inline card provides expandable statements/source passages and a diagram through the existing native Markdown/Mermaid renderer. This is source-implemented and compiled, not actual loaded/rendered host proof. It does not send an answer, infer mastery or wake an agent.

An explicitly enrolled practice lesson uses the fresh derived proposition catalogue for `problem.target` canonical IDs/names. Practice can read that knowledge source but cannot prepare findings or merge. Existing committed-solution hiding, thinking, hints, conclusion and explicit Next are unchanged. Topic-only practice needs neither graph setting.

No raw lesson, private knowledge record, judgments, projections or local configuration belong in the public source manifest.
