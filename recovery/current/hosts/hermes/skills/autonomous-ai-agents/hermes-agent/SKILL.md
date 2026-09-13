---
name: hermes-agent
description: "Configure, troubleshoot, extend, or contribute to Hermes Agent."
version: 3.0.0
author: Hermes Agent + Teknium
source: https://github.com/NousResearch/hermes-agent
license: MIT
metadata:
  hermes:
    tags: [hermes, setup, configuration, cli, desktop, gateway, development]
    homepage: https://hermes-agent.nousresearch.com/docs
---

# Hermes Agent

Use this skill for Hermes setup, configuration, operation, troubleshooting, extension, and contribution. Start with discovery; a recipe for one host or frontend is not evidence for another.

## Discover before acting

1. **Host:** identify native Windows, WSL2, Linux, or macOS. Do not treat a Unix-like shell as proof that Hermes itself runs in WSL/Linux.
2. **Product surface:** identify Hermes Desktop, classic CLI, Ink TUI, web dashboard, gateway/messaging adapter, or a combination. Confirm the failing component rather than transferring commands or UI behavior between surfaces.
3. **Active Hermes home and profile:** prefer runtime-provided state, `HERMES_HOME`, the selected profile, and the current product's settings over assumed paths. Generic `~/.hermes` examples do not override an observed active home, including native Windows app-data locations. Never modify another profile unless explicitly requested.
4. **Install and version:** establish whether this is Desktop-managed, package-installed, or a source checkout. Before retaining or running a command, check the installed CLI's relevant `--help` and current docs.
5. **Scope:** distinguish read-only diagnosis from an authorized configuration, state, installation, or source change.

## Authority

The current documentation is authoritative: <https://hermes-agent.nousresearch.com/docs>. Use its surface-specific pages and the installed CLI help; use source only when implementation behavior or contribution work requires it. This skill is routing guidance, not a frozen command catalogue.

The locally supported agent roster is **Hermes, Codex, and OMP**. Provider integrations documented by Hermes are model/auth backends, not proof that a same-named agent is installed or supported. Route Codex- or OMP-specific work to their own installed owner when available; do not infer agent roster from the provider list.

## Essential boundaries

- Preserve the active profile and product surface. Back up or inspect before destructive state changes, and verify writes against the exact target.
- Keep secrets in the supported secret store or `.env`; keep non-secret settings in `config.yaml`. Never print credentials to diagnose auth.
- OAuth and API-key authentication are distinct. In particular, OpenAI API auth and OpenAI Codex OAuth are not interchangeable; verify provider ID, auth state, and an actually available model before changing model or auxiliary-provider settings.
- Preserve cache-stable prompt prefixes and tool schemas where the runtime requires a new session for changes. Do not attempt unsupported live mutation of tool schemas or stable system-prompt structure. This does **not** prohibit loading a skill, reading new evidence, adding ordinary conversation context, or using supported context/compression mechanisms.
- A security switch is only a conditional diagnostic or explicitly requested configuration choice. It never grants permission to bypass approvals, redaction, authorization, sandboxing, or other safeguards. Prefer the safest setting that can establish the cause, minimize scope and duration, and restore protection after a controlled diagnostic.
- Commands and paths in linked legacy references may drift. Verify them against current docs, installed `--help`, and the actual host before use.

## Route by task

- Setup, config, models/providers, profiles, tools/skills, sessions, dashboard, gateway, cron, voice, or process spawning => [Operations](references/operations.md)
- Host/frontend-specific failure or stale behavior => [Platform troubleshooting](references/platform-troubleshooting.md)
- Approval, redaction, privacy, network/tool restriction, or security diagnosis => [Security diagnostics](references/security-diagnostics.md)
- Source change, architecture, tool/slash-command work, or tests => [Contributor guide](references/contributing.md)
- Persistent native MCP setup or debugging => first use the [official MCP docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp), then consult [Native MCP legacy detail](references/native-mcp.md) only after version verification
- Event-driven gateway subscriptions => first use the [official webhook docs](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/webhooks), then consult [Webhook legacy detail](references/webhooks.md) only after version verification

## Surface gates

- **Native Windows Desktop:** use Desktop settings and Windows-native paths/processes. Do not prescribe WSL paths, `systemctl`, `tmux`, or Linux package commands unless the affected Hermes process actually runs in WSL/Linux.
- **WSL2/Linux:** use Linux service, shell, audio, and tmux recipes only after confirming that environment owns the Hermes process and active home.
- **Classic CLI vs Ink TUI:** confirm which frontend is running before changing launch flags, wrappers, or slash-command handlers.
- **Dashboard:** treat it as a separate browser/admin surface; its optional chat path may depend on the TUI. Verify dashboard flags and endpoints for the installed version.
- **Gateway/messaging:** use adapter-specific setup, authorization, logs, restart, and delivery checks. A Desktop or CLI restart is not automatically a gateway restart.

Finish with a surface-matched verification: read back config/state, restart only the component whose startup snapshot changed, and reproduce the original operation on that same host, profile, and frontend.
