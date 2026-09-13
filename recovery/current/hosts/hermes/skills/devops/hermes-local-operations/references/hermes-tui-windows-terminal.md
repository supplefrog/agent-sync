# Hermes Ink TUI from Windows Terminal / PowerShell into WSL

Use this reference when Hermes runs in WSL but the user launches it from Windows Terminal/PowerShell and sees classic CLI behavior, static slash-command output, missing colors, or broken multiline key behavior.

## Frontend selection: classic CLI vs Ink TUI

Hermes chat has two terminal frontends:

- Plain `hermes` normally starts the classic prompt_toolkit CLI.
- `hermes --tui` starts the Ink TUI.
- `HERMES_TUI=1 hermes` starts the Ink TUI without requiring the flag each launch.

The TUI selector in Hermes is effectively:

```python
use_tui = getattr(args, "tui", False) or os.environ.get("HERMES_TUI") == "1"
```

If `/sessions` appears as a static list/table instead of the scrollable/delete-capable picker, first check whether the process is running the classic CLI rather than the Ink TUI. Prefer setting `HERMES_TUI=1` in the wrapper/profile when the user wants Ink globally; do not patch Hermes source just to force a local behavior that updates will overwrite.

## PowerShell wrapper with `env -i`

When a Windows PowerShell profile launches Hermes through WSL with `/usr/bin/env -i`, only explicitly listed variables survive. This is useful for preventing Windows Node/npm shims from polluting WSL, but it also strips terminal/color variables.

For the user's current WSL/PowerShell shape, include these env vars in the wrapper array before `/usr/local/bin/hermes`:

```text
TERM=xterm-256color
COLORTERM=truecolor
FORCE_COLOR=3
CLICOLOR=1
HERMES_TUI=1
```

Keep `TERM=xterm-256color` for Windows Terminal/PowerShell unless the real terminal is Kitty and WSL has Kitty terminfo installed. Do not set `TERM=kitty` just to get better colors; `TERM` declares terminal capabilities. Check with:

```bash
infocmp kitty >/dev/null 2>&1; echo $?
infocmp xterm-256color >/dev/null 2>&1; echo $?
```

`xterm-256color` plus `COLORTERM=truecolor` and `FORCE_COLOR=3` is usually the safer Windows Terminal default.

## Direct WSL launches

For direct WSL shell launches, put `export HERMES_TUI=1` in a shell startup file such as `~/.bashrc` or `~/.profile` if the user wants Ink TUI by default. Verify with:

```bash
bash -lc 'printf "HERMES_TUI=%s TERM=%s COLORTERM=%s FORCE_COLOR=%s CLICOLOR=%s\n" "$HERMES_TUI" "$TERM" "$COLORTERM" "$FORCE_COLOR" "$CLICOLOR"'
```

## Windows Terminal multiline shortcuts

Do not add global Windows Terminal `sendInput` bindings as the first fix for Hermes multiline shortcuts. Terminal-level `Shift+Enter`/`Ctrl+Enter` bindings may work in plain PowerShell but still be swallowed or reinterpreted by Hermes/Ink, and CSI-u style escape sequences can print weird characters in other CLI/TUI apps. Treat multiline/submit shortcut behavior as application support unless the app documents a terminal binding.

Safe approach:

1. First verify the application-supported behavior (`hermes --tui`, `/help`, official docs/source, or config knobs).
2. If Hermes does not support the requested shortcut, say so and avoid local Hermes source patches unless the user explicitly asks for an update-unsafe experiment or upstream patch.
3. For multiline text inside Hermes, prefer paste/bracketed paste as the lowest-risk workaround.
4. If editing Windows Terminal settings anyway, back up `settings.json`, avoid global escape-sequence experiments, and test in other TUIs before keeping the binding.

Typical Store Windows Terminal settings path:

```text
/mnt/c/Users/<USER>/AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json
```
