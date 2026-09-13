---
name: debugging-hermes-tui-commands
description: "Use when a Hermes slash command is missing, misrouted, inconsistent across classic CLI, Ink TUI, Desktop, or gateway, or persists config without updating live UI. Trace registry, execution, RPC, and frontend ownership before patching."
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [debugging, hermes-agent, tui, slash-commands, typescript, python]
    related_skills: [systematic-debugging, runtime-debugger-tools, inspecting-hermes-desktop-dom, hermes-local-operations]
---

# Debugging Hermes Slash Commands

Hermes slash commands cross several surfaces. A command can exist in the canonical Python registry yet use different execution paths in classic CLI, Ink TUI/Desktop, and messaging gateways. Diagnose the active surface and route before editing.

## Owner boundary

- Use `systematic-debugging` for the causal investigation.
- Use this skill for slash-command architecture, parity, dispatch, autocomplete, and live UI state.
- Use `runtime-debugger-tools` only when logs and source tracing cannot reveal runtime state.
- Use `inspecting-hermes-desktop-dom` for Electron renderer/DOM evidence.
- Use `hermes-local-operations` for installed-runtime, wrapper, profile, and Windows/WSL faults that do not require a source change.

Do not patch the installed Hermes checkout merely to make a transient local problem disappear. Prefer supported config/launch behavior; upstream durable source fixes from a separate worktree.

## Establish the live source and surface

Run `hermes --version` first. Locate the active install without assuming Linux, WSL, or a username-specific path:

```bash
python -c "from pathlib import Path; import hermes_cli,inspect; print(Path(inspect.getfile(hermes_cli)).resolve().parents[1])"
```

Call that result `<repo-root>`. Confirm it contains the relevant paths before using it. Determine whether the failure occurs in:

- classic prompt_toolkit CLI (`cli.py`);
- Ink TUI (`ui-tui/`), including Desktop when it uses the Ink client/backend;
- TUI JSON-RPC gateway (`tui_gateway/`);
- messaging gateway (`gateway/`);
- more than one surface.

Reproduce the smallest command and record whether the failure is discovery, parsing, execution, rendering, persistence, or live state.

## Current architecture

```text
hermes_cli/commands.py                 canonical CommandDef registry
hermes_cli/slash_exec.py               shared registry-owned executors
cli.py                                 classic CLI dispatch

gateway/run.py                         messaging-platform dispatch

tui_gateway/methods_complete.py        complete.slash catalog
ui-tui/src/app/slash/registry.ts       Ink-local/native command registry
ui-tui/src/app/createSlashHandler.ts   local/native/fallback routing
             ↓ slash.exec
tui_gateway/methods_tools.py          RPC handler and command classification
tui_gateway/server.py                 persistent _SlashWorker/session runtime
```

Treat source as authoritative because the gateway is periodically split into method modules.

Ink commands follow three routes:

1. **local/native** — handled in the TypeScript command registry;
2. **fallback `slash.exec`** — executed through the TUI gateway and persistent slash worker;
3. **`command.dispatch` fallback** — aliases, skills, bundles, plugins, or send/prefill behavior when appropriate.

`ui-tui/src/__tests__/slashParity.test.ts` protects registry route parity and ensures mutating commands do not fall through the worker path.

## Investigation

1. Read the `CommandDef` in `hermes_cli/commands.py`: canonical name, aliases, surface gates, argument hints, subcommands, and executor metadata.
2. Search exact command/alias occurrences across `cli.py`, `hermes_cli/slash_exec.py`, `gateway/`, `tui_gateway/`, and `ui-tui/src/`.
3. In Ink, inspect `app/slash/registry.ts`, the matching command module, and `createSlashHandler.ts` to determine local/native/fallback ownership.
4. For autocomplete, inspect both `tui_gateway/methods_complete.py` and the Ink slash registry/fuzzy scoring. A registry entry alone does not prove the desired client presentation.
5. For RPC execution, inspect `tui_gateway/methods_tools.py` around `@method("slash.exec")`; inspect `_SlashWorker` in `tui_gateway/server.py` for subprocess/session behavior.
6. For persisted settings, trace both config read/write and the active UI store (`uiStore`/`patchUiState`) plus every renderer of that state. A saved value that appears only after restart is a live-state bug, not a persistence success.
7. Compare the analogous working command and run the narrowest existing test before changing code.

## Change rules

- Add or update `CommandDef` once in the canonical registry; do not create parallel metadata tables without evidence they are required.
- Put surface-independent formatting/execution in `hermes_cli/slash_exec.py` when the command fits that contract.
- Keep truly interactive Ink behavior in the TypeScript command owner; do not send mutating commands through worker fallback.
- Preserve argument text and alias semantics. Check collisions such as `/q` and multiline/space fidelity.
- When state must update immediately, patch the live store and thread it through streaming, transcript, pending, and restored render paths as applicable.
- Keep changes scoped to the failed route. Do not use a slash-command fix for unrelated UI cleanup.

## Verification

From `<repo-root>`, choose tests matching the touched route:

```bash
python -m pytest tests/hermes_cli/test_commands.py -q
python -m pytest tests/hermes_cli/test_commands_execute.py -q
python -m pytest tests/gateway/test_gateway_command_dispatch_minimal.py -q
python -m pytest tests/tui_gateway/ -q
npm --prefix ui-tui run test -- --run src/__tests__/slashParity.test.ts
npm --prefix ui-tui run typecheck
npm --prefix ui-tui run build
```

Do not claim all surfaces passed when only one slice ran. Then exercise the original command in the affected frontend and verify:

- expected discovery/autocomplete;
- correct alias and argument handling;
- intended behavior and rendered output;
- immediate live state when relevant;
- persisted state after restart when relevant;
- no leaked worker/process after cancellation or reconnect if lifecycle code changed.

For Desktop-specific changes, verify the packaged/live Desktop seam rather than assuming a source TUI run proves it.
