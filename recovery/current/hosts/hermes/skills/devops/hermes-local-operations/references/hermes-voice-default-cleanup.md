# Hermes voice/STT/TTS default cleanup

Use when a prior voice-mode experiment left Hermes launching with voice env, STT/TTS config, or TTS tools that add context or change TUI behavior.

## Goal

Return Hermes to a text-first launch path without patching installed Hermes source:

- no wrapper-level `HERMES_VOICE*` defaults
- no wrapper-level PulseAudio env needed only for voice
- `stt.enabled: false`
- `voice.auto_tts: false`
- no `tts` toolset in the active CLI/profile toolset list
- no voice/STT/TTS plugin enabled unless the user explicitly wants one

## Sequence

1. Identify the launch path the user actually uses, especially PowerShell functions/wrappers that enter WSL.
2. Remove voice-only environment variables from that wrapper, commonly:
   - `HERMES_VOICE=1`
   - `HERMES_VOICE_AUTOSUBMIT=0`
   - `PULSE_SERVER=unix:/mnt/wslg/PulseServer`
3. Keep unrelated TUI/color/sanitized-path settings intact if they are still wanted:
   - `HERMES_TUI=1`
   - `TERM=xterm-256color`
   - `COLORTERM=truecolor`
   - `FORCE_COLOR=3`
   - `CLICOLOR=1`
   - WSL-native Node/PATH cleanup
4. Use supported config for persistent behavior where available:
   - `hermes config set stt.enabled false`
   - confirm `voice.auto_tts` is false rather than assuming TTS is off from wrapper env alone
5. Inspect active profile/toolset config and remove/avoid `tts` in `platform_toolsets.cli` or enabled toolsets unless the user wants text-to-speech tools available.
6. Check `plugins.enabled` and bundled/installed plugin names for voice/STT/TTS/speech/audio matches before proposing a plugin approach.

## Verification checklist

A good final verification reports the effective values, not just the edit:

```json
{
  "stt.enabled": false,
  "voice.auto_tts": false,
  "cli_has_tts_toolset": false,
  "plugins.enabled": []
}
```

Also verify the wrapper text/env no longer contains:

- `HERMES_VOICE`
- `HERMES_VOICE_AUTOSUBMIT`
- `PULSE_SERVER`

If the wrapper uses `/usr/bin/env -i`, remind the user to open a new PowerShell window or otherwise relaunch Hermes so the old process environment is gone.

## Dictation/context interpretation notes

When the user asks whether STT reduces or increases context bloat, separate the UX paths rather than treating all voice input as equivalent:

- Auto-submit STT is the bloat-prone path: recognized speech is submitted immediately as the next user turn, including filler words, false starts, overlapping speech, and transcription errors.
- Dictation STT with `HERMES_VOICE_AUTOSUBMIT=0` is different: the Ink TUI handles `voice.transcript` by inserting the transcript into the composer/input box with `setInput(...)`; the user can edit it before pressing Enter. Only the edited composer contents should become the submitted prompt.
- The visible `voice transcript: ...` line in current Ink TUI is emitted via frontend `sys(...)` as a local system/display message. Do not assume it is sent to the LLM as a user turn. Check the `prompt.submit` backend path and persisted session history before claiming it affects model context.
- The confusing part is UX clutter: even if the line is not model context, it looks like transcript history and can make users think raw speech was included.

Relevant source paths to inspect before answering from memory:

- `ui-tui/src/app/createGatewayEventHandler.ts`: `voice.transcript` handler; dictation path calls `setInput(...)` and `sys('voice transcript: ...')`, while auto-submit calls `submitRef.current(text)`.
- `ui-tui/src/app/useSubmission.ts`: ordinary Enter path; `prompt.submit` sends the composer contents.
- `tui_gateway/server.py`: `prompt.submit` / `_run_prompt_submit` backend path; agent receives submitted text plus backend conversation history.

## Pitfalls

- Do not treat disabling voice as the inverse of enabling voice only. Context bloat can come from config, active toolsets, plugins, wrapper env, and auto-submit behavior separately.
- Do not remove `HERMES_TUI=1` or terminal color env when the user's goal is only to stop voice/STT/TTS defaults.
- Do not patch the installed Hermes source for dictation/no-autosubmit behavior as a first response. Local source edits are update-fragile.
- Do not claim a clean plugin solution exists until inspecting the current plugin hooks. If hooks do not expose the Ink TUI transcript/composer path, report that limitation and stop rather than building a brittle shim.
- Do not overstate uncertainty: if source shows dictation inserts into composer and does not call submit, say so; if persistence/model-context inclusion is still unverified, label only that part as needing a session-history check.
