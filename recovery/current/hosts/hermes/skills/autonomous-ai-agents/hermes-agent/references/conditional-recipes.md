# Conditional troubleshooting recipes

Read only for a matching WSL audio or classic-CLI/TUI failure. These are retained historical mechanisms, not evidence that the current install still uses them. Confirm current source, installed help, process location, distro and affected package ownership before using commands. Substitute the discovered checkout/interpreter; never use Linux paths for native Windows Desktop. Package removal or wrapper changes still require authorized scope. Current docs take precedence when the mechanism has changed.

## WSL microphone / ALSA bridge

For Hermes CLI voice in WSL, Windows Terminal usually is not the thing that appears in Windows microphone privacy. WSLg exposes the Windows mic through PulseAudio at `/mnt/wslg/PulseServer`; Hermes uses `sounddevice`/PortAudio through ALSA, so WSL needs ALSA→PulseAudio routing.

Quick checks:
```bash
PULSE_SERVER=unix:/mnt/wslg/PulseServer pactl list short sources
PULSE_SERVER=unix:/mnt/wslg/PulseServer /usr/local/lib/hermes-agent/venv/bin/python3 - <<'PY'
import sounddevice as sd
print(sd.query_devices())
print('default', sd.default.device)
PY
```

On openSUSE WSL, if `sounddevice` shows no devices while `pactl` shows `RDPSource`, swap the ALSA backend from PipeWire to PulseAudio:
```bash
zypper --non-interactive remove pipewire-alsa
zypper --non-interactive install alsa-plugins-pulse
```
Then ensure the Hermes Windows PowerShell wrapper passes:
```text
PULSE_SERVER=unix:/mnt/wslg/PulseServer
```
Verify with:
```bash
PULSE_SERVER=unix:/mnt/wslg/PulseServer /usr/local/lib/hermes-agent/venv/bin/python3 - <<'PY'
import sounddevice as sd, numpy as np
print(sd.query_devices())
data = sd.rec(int(0.25*16000), samplerate=16000, channels=1, dtype='int16')
sd.wait()
print('voice_input_ok peak', int(np.max(np.abs(data))))
PY
```

## Classic CLI versus TUI command ownership

- Hermes has two interactive frontends:
  - Classic prompt_toolkit CLI: the default `hermes` UI with the familiar yellow-accent terminal skin.
  - Ink TUI: starts only with `hermes --tui` or `HERMES_TUI=1` for chat invocations.
- If a user wants the Ink overlay UI globally, use `hermes --tui` or set `HERMES_TUI=1` in their wrapper/shim.
- If the user says the interface changed to a plain/Ink-looking TUI and they want the old yellow-accent default UI back, remove `HERMES_TUI=1` from the wrapper/shim and fix the specific classic-CLI slash command instead of forcing Ink globally.
- For `/sessions` specifically, the classic CLI should open the curses session browser for bare `/sessions` or `/sessions browse`; `/sessions list` should remain the static table. If bare `/sessions` prints a static table in the classic UI, patch `HermesCLI._handle_sessions_command` in `cli.py` rather than changing the launcher to force Ink.
- If the Ink TUI source has changed but behavior is stale, rebuild it: `npm --prefix /usr/local/lib/hermes-agent/ui-tui run build`, then restart Hermes.
