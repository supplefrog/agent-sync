# Platform and Surface Troubleshooting

Load this reference only after identifying the host, Hermes process location, active home/profile, install type/version, and affected frontend.

## Common sequence

1. Reproduce on the reported surface and collect its current status/error without exposing secrets.
2. Confirm the relevant tool/skill/provider/platform is enabled for that profile and surface.
3. Check the surface-specific docs and installed `--help` before applying a recipe.
4. Inspect the logs owned by that component; do not assume a generic `~/.hermes/logs` path when an active home is known.
5. Make the smallest authorized correction, restart only if that component snapshots the setting, and reproduce.

## Native Windows Desktop

Use [Desktop](https://hermes-agent.nousresearch.com/docs/user-guide/desktop) and [native Windows](https://hermes-agent.nousresearch.com/docs/user-guide/windows-native) docs. Treat Windows-native paths, process management, installer state, file encoding, permissions, and Desktop settings as primary. A bash-like tool shell does not make the installed Desktop process WSL-based.

Do not prescribe `systemctl`, Linux `/usr/local` paths, ALSA/PulseAudio, `tmux`, `sudo`, or WSL configuration unless process evidence shows Hermes is running there. For malformed config symptoms, inspect the exact active file and encoding without rewriting unrelated settings; a UTF-8 BOM was a known legacy cause of some Windows parse/request failures, but confirm the current error and parser behavior before changing bytes.

## WSL2 or Linux

Use [WSL2](https://hermes-agent.nousresearch.com/docs/user-guide/windows-wsl-quickstart) or relevant Linux docs only when that environment owns the process and active home.

- Service-manager remedies (`systemctl --user`, linger, WSL systemd settings) apply only to an installed gateway service using that manager. Verify service existence/status first.
- WSL microphone diagnosis may involve WSLg, PulseAudio/ALSA, and distro packages. For the matching audio-bridge symptom, see [Conditional troubleshooting recipes](conditional-recipes.md). Never apply distro-specific package removal/install commands without confirming distro, package ownership, audio devices, and current voice docs.
- `tmux` is a conditional interactive-process technique, not a native Windows or Desktop recipe. Confirm installation and current CLI behavior first.

## Frontend distinctions

- **Desktop:** diagnose app settings, connection, managed runtime, and Desktop logs/health using Desktop docs.
- **Classic CLI:** identify the classic prompt-toolkit interface before diagnosing classic slash handlers or skin/status behavior.
- **Ink TUI:** confirm explicit TUI launch/config before rebuilding UI assets or changing wrappers. Do not force TUI globally to repair one classic-CLI command. For the historical sessions-handler mismatch, consult [Conditional troubleshooting recipes](conditional-recipes.md) and verify the current source seam.
- **Dashboard:** use [dashboard docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard). Confirm installed flags, bind/port, dependencies, and documented health/status route; do not assume a historical port or endpoint.
- **Gateway:** diagnose the actual adapter, authorization/pairing state, service status, delivery target, and gateway logs. Desktop/CLI restarts do not necessarily restart it.

## Symptom routes

### Tool or skill absent

Check current tool/skill inventory, profile/platform enablement, requirements, and docs. If the change affects tool schemas or startup discovery, create a supported new session/restart. Loading an existing skill or reading new evidence is normal and does not violate prompt-cache stability.

### Model/provider failure

Run the supported doctor/status/auth diagnostics for the installed version, inspect selected provider/model, and distinguish OAuth from API-key auth. A GitHub CLI login is not proof of a provider-specific Copilot flow; Codex OAuth is not OpenAI API auth. Do not invent fallback model names.

### Config change appears stale

Determine which process read the setting and whether docs/source say it is startup-snapshotted. New CLI session, TUI restart, Desktop restart, dashboard restart, and gateway restart are different actions. Read back resolved config after restart.

### Voice failure

Gate first by Desktop/CLI/gateway and native Windows/WSL/Linux. Verify voice feature configuration, provider requirements, and visible input/output devices before changing packages. Messaging transcription and interactive microphone capture are different paths.

### Gateway or adapter failure

Check service/process status, listener/bind configuration, authorization/pairing, adapter credentials, intents/event subscriptions, reachability, and current logs. Apply Discord/Slack or other adapter-specific settings only to that adapter and verify with an inbound and outbound test appropriate to the user's scope.

### Auxiliary-model failure

Confirm the task's provider, auth method, endpoint, and available model list. Configure an auxiliary provider only from values supported by current docs/config and current auth. Report whether failure belongs to vision, compression, search, or another auxiliary route rather than changing all routes.
