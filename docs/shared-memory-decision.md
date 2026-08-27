# Shared memory decision

## Decision

No comparative provider winner was established. Do not add a cross-host shared-memory adapter. Leave the current Hermes stack unchanged: tools-only Honcho remains optional semantic/profile recall, while `session_search` remains the transcript-evidence path. Leave Codex and OMP unmodified.

This is not an admission claim or comparative win for Honcho. A real Hindsight 0.9.1 Local Embedded trial passed exact recall, semantic recall, strict contradictory-update handling, restart persistence, and removal, but failed irrelevant-query silence, tool-visible provenance, and clean Windows lifecycle. Hindsight therefore did not clear its candidate-only promotion gate. The trial did not run Honcho and Hindsight against the same inputs and criteria.

## Decision trace

| Option | What was actually evaluated | Result |
|---|---|---|
| Current Honcho + `session_search` | Honcho service/backfill health and three authorized transcript-fact probes; `session_search` ran the same three transcript probes. No matched synthetic suite was run in this trial. | Current state remains unchanged; not a comparative winner. |
| Hindsight 0.9.1 Local Embedded | Four bounded synthetic facts recalled through the real Hermes `hindsight_recall` tool with production observation-only defaults, covering exact/semantic/strict contradiction/provenance/restart/removal plus irrelevant-query silence and Windows lifecycle. | Candidate-only gate failed on silence, tool-visible provenance, and lifecycle reliability. |
| Cross-host shared provider | No fresh Hermes/Codex/OMP adapter comparison because Hindsight failed pre-admission. | Not run; no provider admitted. |

The evidence supports **no change**, not “Honcho beat Hindsight.” A matched provider comparison remains unperformed and is unnecessary unless a future concrete memory outcome exposes a material gap in the current stack.

## Outcome contract

Shared memory may store durable facts, preferences, and decisions. It must not become a second authority for:

- raw transcripts, which remain in native session stores and `session_search`;
- procedures, which remain in skills;
- project state, which remains in repositories;
- task state, which remains in Hermes Kanban.

Recall must be automatic only at the discovery level: when prior context is relevant, query the appropriate source on demand and return a small provenance-scoped result. Do not inject broad memory every turn.

## Local evidence

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
- Removal ultimately passed: the isolated bank was deleted, post-delete recall was empty, the profile/database/config/packages were removed, and Honcho remained active and available.

The smallest supported decision is therefore no promotion and no comparative winner. Hindsight's synthetic exact-recall success is promising but not comparable to the authorized transcript probes, and its silence, provenance, and lifecycle failures block canonical-service and cross-agent adapter promotion.

## Host disposition

### Hermes

Retain the current split:

- `session_search` for source-grounded transcript recall;
- compact built-in memory for explicit current facts and preferences;
- Honcho in tools-only mode for optional semantic search, peer cards, and synthesis.

No provider, injection mode, or startup behavior remains changed after rollback.

### Codex

Defer integration. Live `codex mcp list --json` showed `claude-context`, `node_repl`, `parallel`, and `tavily`, with no Honcho or Hindsight server. Codex session and memory state remains runtime-owned.

### OMP

Defer integration. OMP 17.2.13 supports native `local`, `hindsight`, and `mnemopi` memory backends, but the live configuration is `memory.backend: off`. Enabling OMP Hindsight now would point at the same unavailable candidate service and would not prove shared-store fitness.

## Rollback and reopening

Rollback was exercised: delete the isolated bank, verify empty recall, remove the Hindsight profile/database/config/packages, and confirm `hermes memory status` still reports active available Honcho. Codex and OMP were never changed.

Reopen only when Hindsight can suppress irrelevant results and expose provenance through the actual Hermes tool path, and its Windows stop/restart/removal lifecycle is reliable. Promotion still requires matched authorized probes against `session_search` plus tools-only Honcho, bounded latency, no broad per-turn injection, and verified fresh-runtime adapters for Hermes, Codex, and OMP.
