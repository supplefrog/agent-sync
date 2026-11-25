# Codex Model Overrides

Guardrails for OpenAI Codex models (`codex` / `Sol`):

- **Verification & rigor:** Verify every claim, fix, and build with actual command or test output before reporting completion; cite only observed paths, symbols, and outputs, and optimize for total system cost over local patches.
- **Use Git, not backups:** Never create `.bak` copies or duplicate project folders before editing. Stage and commit cleanly to Git, and push personal repos without prompting per step or inventing sync blockers.
- **Delete scratch threads:** Close/clean up auto-created helper or subagent threads and temporary worktrees once their task is done.
- **Visual verification:** Never assume UI/UX or HTML output looks right from code alone—preview rendered output in the browser when building interfaces.
- **Public repo privacy:** Scrub all private local paths, usernames, account data, tokens, and unrelated thread notes before posting comments, issues, or PRs on public GitHub repositories.
