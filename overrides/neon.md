# Neon Model Overrides

- **Explicit media boundary:** Never route sexually explicit video or frames through Gemini/Neon or Claude multimodal endpoints; use OpenAI/Codex (`Sol`) or a local VLM per `sequence-director`.

<!-- temp-pref:t3code-pr-16532 -->
- **Temporary local Chrome / computer-use delegation (until `pingdotgg/t3code#16532` merges):** For tasks requiring the user's already-open local Chrome (signed-in tabs) or desktop computer use while running in T3 Code, delegate via `delegate_task` to `codex` (`gpt-6.2-sol`, `options: { serviceTier: "priority" }` fast mode). When delegating Chrome CDP work, instruct Codex to batch inspect/edit/verify/cleanup over **one** persistent WebSocket connection (via `DevToolsActivePort`, not `/json/*` endpoints) so Chrome's remote-debugging consent prompt fires at most once. Prefer T3 Preview (`preview_*`) when local Chrome/CUA isn't needed.
<!-- /temp-pref:t3code-pr-16532 -->
