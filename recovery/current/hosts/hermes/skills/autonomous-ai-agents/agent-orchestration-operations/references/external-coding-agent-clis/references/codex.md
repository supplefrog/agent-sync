# OpenAI Codex CLI

Use when the user explicitly requests Codex or the Windows Codex installation provides a capability advantage.

## Live verification

On this setup Hermes is Windows-native and the terminal is Git Bash. Prefer the installed Windows `codex` directly; do not create WSL wrappers or npm reinstallations unless the live binary is absent and the user asks to install it.

```bash
command -v codex
codex --version
codex --help
```

Codex CLI auth can exist under the user’s Codex home even when `OPENAI_API_KEY` is absent. Check auth status through supported CLI behavior; do not print or copy auth/config secrets.

Known locations to inspect when needed:

- `%USERPROFILE%\.codex\config.toml`
- `%USERPROFILE%\.codex\AGENTS.md`
- `%USERPROFILE%\.codex\skills\`

Treat cached marketplace/plugin files as candidates, not proof a plugin is installed or useful to Hermes.

## Invocation

Use the repository as `workdir`. For bounded noninteractive work, prefer the current `codex exec` syntax shown by live help:

```bash
codex exec '<bounded task with acceptance checks>'
```

Use PTY only when the chosen mode is interactive. For long bounded work, run it as a tracked background process with completion notification and inspect logs through Hermes process tools.

Codex may require a git repository. For disposable scratch work, initialize an isolated temporary repo rather than weakening repository checks.

## Prompt shape

Provide:

- outcome and non-goals;
- relevant files/current diagnosis;
- repository conventions;
- exact verification commands;
- whether edits, commits, pushes, or review-only behavior are allowed.

Do not ask Codex to rediscover context Hermes already established.

## wmux visibility and launch

On Windows, distinguish the Codex desktop app from Codex CLI inside a wmux-owned PTY. Inspect process ancestry and wmux's structured pane/surface inventory; an executable name alone does not prove terminal ownership. Check the installed `wmux doctor`, `list-panes --json` and `list-surfaces --json` interfaces before using them.

Resolve the terminal's actual PTY identifier from that inventory and verify which identifier the installed `send`, `send-key` and `read-screen` commands accept. A layout pane identifier may acknowledge delivery without reaching the terminal. Launch with the verified absolute Codex launcher path if a restored shell has stale PATH, then require both a running CLI in wmux's state and visible terminal/process evidence. Do not change global PATH merely to repair one stale shell. Leave workspace and hook trust decisions to the user.

## Windows toolchain pitfall

Codex can ship an embedded Node/npm path. The user’s normal Windows Node toolchain is fnm. If PowerShell npm resolves under an OpenAI/Codex bin directory, inspect profile initialization order and activate fnm before PATH-sensitive helpers. Do not use Codex-embedded npm for unrelated global package management.

## Safety

- Inspect `git status` before and after.
- Use separate worktrees for parallel agents.
- Avoid unrestricted modes unless explicitly justified.
- Verify all Codex claims from Hermes: diff, tests, commits, push, and PR state.
- Do not import Codex skills/plugins wholesale. Use `external-skill-intake` and adapt only procedures that add real value.
