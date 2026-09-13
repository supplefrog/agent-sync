# Hermes Operations

Load this reference for setup, configuration, models/providers, profiles, tools/skills, sessions, dashboard, gateway, cron, voice, or additional Hermes processes.

## Preflight

Record the host, product surface, active `HERMES_HOME`, profile, install type/version, and requested mutation scope. Rediscover the active home rather than hardcoding another profile's or installation's location.

Use <https://hermes-agent.nousresearch.com/docs> and the installed command's `--help` as the command authority. The current documentation has dedicated pages for [Desktop](https://hermes-agent.nousresearch.com/docs/user-guide/desktop), [CLI](https://hermes-agent.nousresearch.com/docs/user-guide/cli), [TUI](https://hermes-agent.nousresearch.com/docs/user-guide/tui), [native Windows](https://hermes-agent.nousresearch.com/docs/user-guide/windows-native), [WSL2](https://hermes-agent.nousresearch.com/docs/user-guide/windows-wsl-quickstart), [configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration), and [messaging](https://hermes-agent.nousresearch.com/docs/user-guide/messaging). Do not use a command retained here without confirming it is present in the installed version.

## Operation routing

| Need | First authority and check |
|---|---|
| Install/onboard | Current installation or surface-specific docs; native Windows and Unix/WSL installers are different |
| Configuration | Configuration docs; inspect the resolved current value and exact active file before setting it |
| Models/providers | [Provider docs](https://hermes-agent.nousresearch.com/docs/integrations/providers), current model UI/CLI, and auth status |
| Tools/skills | [Tools](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools) or [skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) docs; confirm platform enablement and whether restart/new session is required |
| Profiles | [Profiles docs](https://hermes-agent.nousresearch.com/docs/user-guide/profiles); make profile selection explicit before reads or writes |
| Sessions | [Sessions docs](https://hermes-agent.nousresearch.com/docs/user-guide/sessions); never delete user-created, shared, active, or referenced sessions without explicit scope |
| Dashboard/browser UI | [Dashboard docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard); verify current launch flags, bind address, port, and health endpoint |
| Gateway/messaging | Adapter docs plus gateway status/logs for the actual host and service manager |
| Cron/automation | [Cron docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron); verify schedule, profile, delivery target, and a controlled run |
| MCP | [Official MCP docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp), then [legacy native-MCP detail](native-mcp.md) if implementation history is needed |
| Webhooks | [Official webhook docs](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/webhooks), then [legacy webhook detail](webhooks.md) if implementation history is needed |
| Voice | [Voice docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/voice-mode), gated by frontend and host audio stack |

## Provider and agent boundaries

Hermes supports generic model providers and authentication methods documented in the provider guide. That catalog is not an installed-agent roster. The supported local agent roster for this environment is Hermes, Codex, and OMP; a provider or endpoint name does not establish a fourth agent owner.

For authentication:

1. Identify the exact provider ID selected by the active profile.
2. Determine whether it expects OAuth/device-code, API key, token, or custom endpoint configuration.
3. Inspect auth status without revealing secrets.
4. Select only a model shown by the current UI/CLI/provider docs.
5. Reproduce with the same surface/profile.

OpenAI direct API configuration requires API credentials. Codex OAuth/device-code uses the Hermes provider route documented for Codex; one does not prove the other is configured. Apply the same distinction to auxiliary model settings.

## Process and frontend gates

- Prefer the built-in delegation mechanism for bounded subtasks when available. For a justified additional process, use [Additional Hermes processes](processes.md): preserve authorized scope, output ownership, bounded stopping and verified session cleanup without asking again for routine approved worker execution.
- Noninteractive one-shot, interactive PTY, and worktree flags must be confirmed with current CLI help before use.
- `tmux` recipes are Linux/WSL-only and require `tmux` plus a Hermes process running there. They are invalid defaults for native Windows Desktop.
- Classic CLI, Ink TUI, Desktop, dashboard, and gateway share core state in supported configurations but have different launchers, UI handlers, restart boundaries, and feature exposure. Verify the exact surface.
- For scheduled or durable work, prefer current Hermes cron/gateway facilities over an unmanaged spawned process when the documented feature fits.

## Mutation and verification

1. Read the resolved state and preserve rollback material appropriate to risk.
2. Change only the active profile/component the user authorized.
3. If the setting is startup-snapshotted, restart or open a new session only for that component; do not broadly restart unrelated surfaces.
4. Read back the exact target and reproduce the requested behavior.
5. Report the host, profile, surface, changed key/file, and remaining uncertainty.
