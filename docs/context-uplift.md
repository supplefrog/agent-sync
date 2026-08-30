# Context uplift decision

## Decision

Hermes now uses the existing `gpt-5.6-sol` route with:

```yaml
compression:
  in_place: true
  codex_responses_native: true
  codex_responses_compact_threshold: 200000
```

For the current 272K base window and 50% local trigger, Hermes resolves the native server threshold to **127,808 tokens**. The local compressor remains the fallback.

## Evidence

A public-safe synthetic fixture placed eight exact-recall canaries across 1,362 messages (about 236.8K estimated tokens). Raw transcripts and provider payloads stayed outside Git.

| Strategy | Recall | Same session | Extra visible sessions | Context behavior |
|---|---:|---:|---:|---|
| Current rotating local compressor | 5/8 | No | 1 | Local summary plus tail |
| Native in-place, base model | 8/8 | Yes | 0 | Opaque compaction checkpoint replay |
| Native 900K alias | 8/8 | Yes | 0 | No checkpoint; full 236K prompt replay |
| `hermes-lcm` intact | Blocked | Intended | 0 | Core 103/103 passed; Windows externalized-storage/recovery suite failed |

The base native strategy won because 900K produced no recall gain and retained the full prompt. LCM remains a useful mechanism donor but is not deployable intact on this Windows host at revision `10cbb78347ec86f3004153b24767324ded9e37b4`.

See [context-uplift-2026-08-30.json](../evals/results/context-uplift-2026-08-30.json) for the payload-free receipt and [context-uplift-suite.json](../evals/context-uplift-suite.json) for the frozen synthetic cases.

## Safety and rollback

The failed foreground router was removed from the live plugin directory and remains unadmitted. Promotion created no sessions: count stayed 395 before and after.

Rollback:

```text
hermes config set compression.in_place false
hermes config set compression.codex_responses_native false
hermes config set compression.codex_responses_compact_threshold 200000
```

Then start a fresh runtime and verify the effective values and unchanged session count.

## Next capability pilots

1. Prime Agent intact as an optional executor behind Hermes, with one composer and isolated state.
2. Parallel versus Tavily on a frozen primary-source research suite.
3. Browser Use versus Playwright MCP versus Chrome DevTools MCP on deterministic login-free tasks.

The full 18-capability disposition matrix is [capability-scout-2026-08-30.json](../evals/results/capability-scout-2026-08-30.json).
