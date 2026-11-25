# Neon Model Overrides

Notes for running Gemini / Antigravity (`Neon`) effectively in T3 Code and Orchestrator setups:

- **Batch tool calls:** Issue independent reads, searches, and file writes/edits in parallel in the same turn, and chain related shell verification checks cleanly.
- **Built-in web search first:** Use native Google Search before reaching for external web-search MCPs; only use external crawlers (e.g., Parallel/Tavily) when raw full-page extraction from specific URLs is needed.
- **Orchestrator discipline:** Respect the Orchestrator vs. standalone budget split—reserve standalone Neon passes for hard reasoning or multi-file coding work rather than trivial lookups.
- **Explicit media boundary:** Never route sexually explicit video or frames through Gemini/Neon or Claude multimodal endpoints; use OpenAI/Codex (`Sol`) or a local VLM per `sequence-director`.

<!-- temp-pref:t3code-pr-16532 -->
- **Temporary local Chrome / computer-use delegation (until `pingdotgg/t3code#16532` merges):** For tasks requiring the user's already-open local Chrome (signed-in tabs) or desktop computer use while running in T3 Code, delegate via `delegate_task` to `codex` (`gpt-6.2-sol`, `options: { serviceTier: "priority" }` fast mode). Prefer T3 Preview (`preview_*`) when local Chrome/CUA isn't needed. Auto-remove this bullet once `https://github.com/pingdotgg/t3code/pull/16532` merges.
<!-- /temp-pref:t3code-pr-16532 -->
