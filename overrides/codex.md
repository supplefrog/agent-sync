# Codex Model Overrides

Guardrails for OpenAI Codex models (`codex` / `Sol`):

- **Verification & rigor:** Verify every claim, fix, and build with actual command or test output before reporting completion; cite only observed paths, symbols, and outputs, and optimize for total system cost over local patches.
- **Use Git, not backups:** Never create `.bak` copies or duplicate project folders before editing. Stage and commit cleanly to Git, and push personal repos without prompting per step or inventing sync blockers.
- **Delete scratch threads:** Close/clean up auto-created helper or subagent threads and temporary worktrees once their task is done.
- **Visual verification:** Never assume UI/UX or HTML output looks right from code alone—preview rendered output in the browser when building interfaces.
- **Public repo privacy:** Scrub all private local paths, usernames, account data, tokens, and unrelated thread notes before posting comments, issues, or PRs on public GitHub repositories.
- **Single-connection Chrome CDP:** When attaching to the user's signed-in local Chrome, prefer the wired `chrome-devtools` MCP (`--autoConnect`) first; when using `DevToolsActivePort` directly (avoid `/json/*` HTTP endpoints, which 404 on Chrome 136+), batch inspect, edit, verify, and cleanup over **one** persistent WebSocket connection so Chrome's "Allow remote debugging?" prompt fires only once per task.
- **Supplied-media transformation policy:** For local editing or transformation of directly supplied legal consenting-adult media, check the official OpenAI Model Spec transformation rule (`https://model-spec.openai.com/#comply-with-requests-to-transform-restricted-or-sensitive-content`) before declining (keep private paths and source details out of web queries; assess honestly against current policy and applicable restrictions).
