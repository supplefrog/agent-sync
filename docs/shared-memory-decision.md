# Shared memory decision

## Decision

No external-memory provider is admitted for ordinary use or cross-host sharing. Hermes uses compact built-in `MEMORY.md`/`USER.md`, exact session retrieval, skills, repositories, and authoritative task state. Honcho and Hindsight runtime state have been removed. Codex and OMP remain unmodified.

This supersedes the earlier tools-only-Honcho no-change disposition below. Controlled tests established that Honcho and Hindsight can perform useful memory operations, but the later real-history utility audit found no repeatable external-only downstream win across the user's coding, research, browser/desktop, scheduling, or planning work. Most relevant state had a better authority: repository/docs, task receipts, skills, curated memory, or exact session search.

## Decision trace

| Option | What was actually evaluated | Result |
|---|---|---|
| Current Honcho + `session_search` | Honcho service/backfill health and three authorized transcript-fact probes; `session_search` ran the same three transcript probes. No matched synthetic suite was run in this trial. | Current state remains unchanged; not a comparative winner. |
| Hindsight 0.9.1 Local Embedded | Four bounded synthetic facts recalled through the real Hermes `hindsight_recall` tool with production observation-only defaults, covering exact/semantic/strict contradiction/provenance/restart/removal plus irrelevant-query silence and Windows lifecycle. | Candidate-only gate failed on silence, tool-visible provenance, and lifecycle reliability. |
| Cross-host shared provider | No fresh Hermes/Codex/OMP adapter comparison because Hindsight failed pre-admission. | Not run; no provider admitted. |

The current evidence supports **external memory off**, not “memory can never help” and not a comparative provider winner. Reopen only for a repeated material miss that the incumbent authorities cannot recover and that a bounded provider trial demonstrably fixes.

## Outcome contract

Shared memory may store durable facts, preferences, and decisions. It must not become a second authority for:

- raw transcripts, which remain in native session stores and `session_search`;
- procedures, which remain in skills;
- project state, which remains in repositories;
- task state, which remains in Hermes Kanban.

Recall must be automatic only at the discovery level: when prior context is relevant, query the appropriate source on demand and return a small provenance-scoped result. Do not inject broad memory every turn.

## Historical local evidence (superseded deployment)

The public-safe results are `evals/results/shared-memory-local-20260815.json` and `evals/results/shared-memory-hindsight-trial-20260816.json`. They contain counts and verdicts only; no transcript bodies or credentials.

- Honcho's API, database, gateway, and Redis were healthy; the deriver was running.
- The queue had no pending or errored work. Processed rows were 112 reconciler, 4 representation, 1 summary, and 5 webhook tasks.
- Honcho contained 794 backfill messages across 105 sessions.
- An exact-dedupe dry run loaded 1,056 source message IDs and found all 553 eligible messages already present, with zero missing messages and zero errors.
- Three recent exact-fact probes produced 0/3 hits through `honcho_search`; the profile card also contained one stale environment state. The same three facts were found 3/3 through `session_search`.
- The supported Windows-native Hindsight Local Embedded path started version 0.9.1 on loopback with embedded PostgreSQL and OpenAI Codex OAuth; no API key was copied.
- The corrected isolated tools-only bank used four synthetic facts. Recall ran through `HindsightMemoryProvider.handle_tool_call("hindsight_recall", ...)` with verified production settings: low budget, 1,024-token limit, and default observation-only filtering.
- Exact recall, semantic recall, strict corrected contradiction, and fresh-process restart persistence passed. The corrected Thursday 14:00 schedule was returned and the obsolete Tuesday 09:00 schedule was absent.
- Irrelevant-query silence failed: exact, semantic, contradiction, and irrelevant queries each returned three results.
- Tool-visible provenance failed: the real Hermes recall result exposes numbered memory text but not source or tags.
- Retains took 2.16–3.25 seconds. Warm recalls took 0.50–0.51 seconds, the first exact recall after restart took 1.71 seconds, and the cold version probe took 41.90 seconds.
- Windows lifecycle behavior remained unclean: the corrected daemon stop succeeded, but provider shutdown emitted unclosed aiohttp warnings and embedded PostgreSQL plus its database directory outlived profile deletion until bounded manual termination and removal.
- Removal ultimately passed: the isolated bank was deleted, post-delete recall was empty, the profile/database/config/packages were removed, and Honcho remained active and available **at the time of that trial**. Honcho was retired after the later utility audit described in the current decision above.

The smallest supported decision is therefore no promotion and no comparative winner. Hindsight's synthetic exact-recall success is promising but not comparable to the authorized transcript probes, and its silence, provenance, and lifecycle failures block canonical-service and cross-agent adapter promotion.

## Host disposition

### Hermes

Retain:

- `session_search` for source-grounded transcript recall;
- compact built-in memory for explicit current facts and preferences;
- skills, repositories, documents, and task receipts as their respective authorities.

No external provider, automatic injection, provider startup behavior, or provider data store remains active.

### Codex

Defer integration. Live `codex mcp list --json` showed `claude-context`, `node_repl`, `parallel`, and `tavily`, with no Honcho or Hindsight server. Codex session and memory state remains runtime-owned.

### OMP

Defer integration. OMP 17.2.13 supports native `local`, `hindsight`, and `mnemopi` memory backends, but the live configuration is `memory.backend: off`. Enabling OMP Hindsight now would point at the same unavailable candidate service and would not prove shared-store fitness.

## Rollback and reopening

Retirement was exercised: disposable provider profiles, Hindsight runtime/config residue, the Honcho checkout, configuration, containers, network, and data volumes were removed. `hermes memory status` reports provider none and built-in memory enabled. Codex and OMP were never changed.

Reopen only after a repeated real task failure whose needed context is absent from the active thread and cannot be recovered from repository/docs, task state, curated memory, skills, or exact session search. Test that exact gap against the incumbent. Occasional proven benefit stays on-demand; broad selective integration requires repeated benefit with low contamination. Automatic injection requires separate evidence that its per-turn context and stale-steering risk are worthwhile.
