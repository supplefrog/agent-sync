# Desktop voice conversation ignores `voice.auto_tts=false`

Use when the user reports surprise TTS/read-aloud from Hermes Desktop, especially after turning off “Read Responses Aloud” / `voice.auto_tts`.

## Symptom

Desktop voice conversation speaks assistant replies aloud even when:

```yaml
voice:
  auto_tts: false
tts:
  provider: edge
```

The surprise is usually not from the standalone “Read aloud” menu item. It comes from Desktop voice-conversation mode.

## Triage

1. Inspect the active profile config and any profiles the user launches:

```bash
hermes config path
hermes config get stt || true
hermes config get voice || true
hermes config get tts || true
```

2. Check whether `voice.auto_tts` is already false. If yes, inspect Desktop source before blaming config.

Relevant source paths seen in v0.16.0:

- `apps/desktop/src/app/session/hooks/use-hermes-config.ts`
  - reads `config.voice?.max_recording_seconds`
  - reads `config.stt?.enabled !== false`
  - does **not** expose `voice.auto_tts` to the composer
- `apps/desktop/src/app/chat/composer/hooks/use-voice-conversation.ts`
  - `speak()` calls `playSpeechText(text, { source: 'voice-conversation' })`
  - the response streaming effect calls `speak(chunk)` for voice-conversation chunks
- `apps/desktop/src/lib/voice-playback.ts`
  - sends `/api/audio/speak` and plays the returned audio

3. Check upstream before filing:

```bash
gh issue list --repo NousResearch/hermes-agent --state all --search '"voice.auto_tts" OR "auto_tts" OR "Read Responses Aloud" OR "voice conversation" TTS' --limit 30
```

Known matching issue at time of capture: `NousResearch/hermes-agent#44263`.

## Config-only mitigation

There may be no clean config-only “STT on, TTS off” path for Desktop voice conversation in affected versions. The blunt mitigation is to disable STT in each launched profile, removing the voice-conversation entry point:

```bash
hermes config set stt.enabled false
for p in browser-agent dev lite oss; do
  hermes --profile "$p" config set stt.enabled false
done
```

Then verify:

```bash
python - <<'PY'
from pathlib import Path
import yaml, json
base = Path.home() / 'AppData/Local/hermes'
paths = [('default', base/'config.yaml')]
for p in sorted((base/'profiles').iterdir()):
    if (p/'config.yaml').exists():
        paths.append((p.name, p/'config.yaml'))
rows = []
for name, path in paths:
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    rows.append({
        'profile': name,
        'stt.enabled': data.get('stt', {}).get('enabled'),
        'voice.auto_tts': data.get('voice', {}).get('auto_tts'),
        'tts.provider': data.get('tts', {}).get('provider'),
    })
print(json.dumps(rows, indent=2))
PY
```

Run `hermes config check` for changed profiles. Restart Desktop or reload the active profile.

## Upstream evidence to include

When commenting/filing upstream, include:

- Hermes version and Desktop/OS.
- Config values for `stt.enabled`, `voice.auto_tts`, `tts.provider`.
- The source-path observation that Desktop reads STT/max-recording but not `voice.auto_tts` in `use-hermes-config.ts`.
- The source-path observation that `use-voice-conversation.ts` unconditionally calls `playSpeechText` for response chunks.
- The limitation of the workaround: disabling `stt.enabled` stops surprise TTS but also disables speech input.
