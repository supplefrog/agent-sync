# Hermes voice mode on WSL: minimal local setup

Use this reference when enabling CLI/TUI voice mode for a local Hermes install running inside WSL. It complements the protected bundled `hermes-agent` skill and the official voice docs.

## Minimal default stack

Prefer the no-key stack first unless the user asks for a premium/cloud voice provider:

- STT: `local` (`faster-whisper`)
- TTS: `edge`
- Record key: default `ctrl+b`
- Optional convenience: `voice.auto_tts: true` so `/voice on` also speaks responses.

## Important discovery step

Hermes may run from its packaged venv, so system `python` / `pip` can be misleading. Inspect the shebang and use the Hermes venv Python for module checks:

```bash
readlink -f "$(command -v hermes)"
sed -n '1p' "$(command -v hermes)"
/usr/local/lib/hermes-agent/venv/bin/python - <<'PY'
mods = ['faster_whisper', 'edge_tts', 'sounddevice', 'numpy']
for m in mods:
    try:
        __import__(m)
        print(f'{m}=installed')
    except Exception as e:
        print(f'{m}=missing:{type(e).__name__}:{e}')
PY
```

## Package-manager discipline on WSL

Do not assume Ubuntu/apt just because the host is WSL. Check `/etc/os-release` and available package managers first:

```bash
. /etc/os-release; printf '%s %s\n' "$ID" "$VERSION_ID"
for c in apt apt-get zypper dnf yum pacman apk; do command -v "$c" && echo "pkgmgr=$c"; done
```

Examples:

```bash
# Debian/Ubuntu
apt-get update && apt-get install -y ffmpeg portaudio19-dev libopus0

# openSUSE Tumbleweed
zypper --non-interactive install ffmpeg-8 portaudio-devel libopus0
```

## Config commands

```bash
hermes config set stt.enabled true
hermes config set stt.provider local
hermes config set stt.local.model base
hermes config set tts.provider edge
hermes config set voice.auto_tts true
```

## Verification

Use Hermes' own voice helpers for a grounded readiness check:

```bash
command -v ffmpeg
command -v ffplay
/usr/local/lib/hermes-agent/venv/bin/python - <<'PY'
from tools.voice_mode import detect_audio_environment, check_voice_requirements
from tools.tts_tool import check_tts_requirements
from hermes_cli.config import load_config
import json
cfg = load_config()
print(json.dumps({
    'voice': cfg.get('voice'),
    'stt': cfg.get('stt'),
    'tts_provider': cfg.get('tts', {}).get('provider'),
    'audio_env': detect_audio_environment(),
    'voice_reqs': check_voice_requirements(),
    'tts_available': check_tts_requirements(),
}, indent=2, default=str))
PY
```

Expected success shape: `voice_reqs.available: true`, `stt_available: true`, and `tts_available: true`. In WSL, `detect_audio_environment()` may report a PulseAudio bridge notice such as `PULSE_SERVER=unix:/mnt/wslg/PulseServer`; that is acceptable when requirements pass.

## Windows PowerShell wrapper defaults

For this user's usual WSL-from-Windows launch path, the PowerShell `hermes` function often calls `/usr/local/bin/hermes` via `wsl.exe --exec /usr/bin/env -i ...`. Because `env -i` strips state, put audio bridge and TUI env directly in the wrapper when needed:

```powershell
'HERMES_TUI=1',
'PULSE_SERVER=unix:/mnt/wslg/PulseServer',
```

Do **not** describe `HERMES_VOICE=1` as a supported, universal equivalent to `/voice on`. Source check from this session: `ui-tui/src/app/useMainApp.ts` and `ui-tui/src/app/useConfigSync.ts` read `process.env.HERMES_VOICE === '1'`; `tui_gateway/server.py` uses it as a runtime flag; the classic CLI path initializes voice mode off and does not read it. So:

- Ink TUI: `HERMES_VOICE=1` may initialize the TUI/runtime voice bit for that frontend path.
- Classic CLI: reliable supported behavior is still to run `/voice on` in the session.
- `HERMES_VOICE_AUTOSUBMIT=0`: controls TUI dictation insertion after transcription only; it does not turn voice mode on.
- `HERMES_VOICE_TTS=1`: enables spoken replies in the TUI runtime; omit it when the desired default is STT/dictation only.

Keep the existing color and PATH hygiene env from the WSL/TUI wrapper (`TERM=xterm-256color`, `COLORTERM=truecolor`, `FORCE_COLOR=3`, `CLICOLOR=1`, WSL-native Node/npm PATH). Apply to both PowerShell Core and Windows PowerShell profile shims when both exist:

- `%USERPROFILE%\Documents\PowerShell\profile.ps1`
- `%USERPROFILE%\Documents\WindowsPowerShell\profile.ps1`

## Dictation/no-autosubmit behavior

Current TUI voice behavior may submit `voice.transcript` directly as the next turn. If the user wants “transcribe into the input instantly, without autosubmit”, first check whether upstream now exposes a config/env option. If no supported option exists, use a small local TUI patch rather than inventing an external launcher:

1. Add an env flag in the wrapper:

```powershell
'HERMES_VOICE_AUTOSUBMIT=0',
```

2. In `ui-tui/src/app/useMainApp.ts`, initialize TUI voice state from env so the status bar matches runtime defaults:

```ts
const [voiceEnabled, setVoiceEnabled] = useState(process.env.HERMES_VOICE === '1')
const [voiceTts, setVoiceTts] = useState(process.env.HERMES_VOICE_TTS === '1')
```

3. In `ui-tui/src/app/createGatewayEventHandler.ts`, in the `voice.transcript` case, gate the existing `setInput(''); submitRef.current(text)` behavior:

```ts
if (process.env.HERMES_VOICE_AUTOSUBMIT === '0') {
  setInput(current => (current.trim() ? `${current.trimEnd()} ${text}` : text))
  sys(`voice transcript: ${text}`)
  return
}
```

4. Rebuild and verify:

```bash
npm --prefix /usr/local/lib/hermes-agent/ui-tui run build
npm exec eslint -- src/app/useMainApp.ts src/app/createGatewayEventHandler.ts  # from ui-tui cwd
```

Warn the user that this is a local source patch and can be overwritten by `hermes update`. If upstream later supports a real config key, prefer the supported config over this patch.

## Usage reminder

After config changes, start/restart Hermes and run:

```text
/voice on
```

Then press `Ctrl+B` to record. If `voice.auto_tts` is true, TTS should be enabled automatically when voice mode is enabled. With `HERMES_VOICE_AUTOSUBMIT=0`, transcription should appear in the composer for review/editing; press Enter manually to submit.
