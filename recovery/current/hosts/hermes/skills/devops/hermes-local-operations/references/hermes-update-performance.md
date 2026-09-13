# Hermes update performance triage

Use when the user asks whether Hermes updates can be made faster, whether update stashing can be disabled, or why `hermes update` spends time in dependency/build phases.

## Current behavior to verify in source/docs

Official config docs place update settings under `updates` in `config.yaml`:

```yaml
updates:
  pre_update_backup: false
  backup_keep: 5
  non_interactive_local_changes: stash  # stash | discard
```

`updates.non_interactive_local_changes: discard` does **not** prevent creating an autostash. It only changes what happens after a successful non-interactive update:

- `stash`: create autostash, update, restore local changes.
- `discard`: create autostash, update, drop the stash after success.
- failed update: preserve the stash either way.

So describe `discard` as avoiding restore/re-dirtying time, not as avoiding the stash step. Warn that it discards local installed-tree source edits after successful updates.

## Useful inspection commands

```bash
hermes update --help
hermes config path
python - <<'PY'
from pathlib import Path
import subprocess, yaml
p = Path(subprocess.check_output(['hermes','config','path'], text=True).strip())
data = yaml.safe_load(p.read_text(encoding='utf-8-sig')) or {}
print(p)
print(data.get('updates'))
PY
```

If source is available, inspect `hermes_cli/main.py` around `cmd_update`, `_install_python_dependencies_with_optional_fallback`, `_update_node_dependencies`, `_build_web_ui`, and `_run_npm_install_deterministic`.

## Dependency/build phases

After a real pull, current update flow can run:

1. Python editable install, usually through managed `uv`: `uv pip install -e .[all]`.
2. Refresh active lazy backends.
3. Node dependency refresh:
   - repo root install with desktop workspace skipped,
   - selected `ui-tui` and `web` workspaces.
4. Web UI build when needed.
5. Desktop build check/build only if desktop artifacts exist.

There is no supported config knob that skips dependency/build phases. `hermes update --check` is the supported fast check-only path.

## Practical speedup direction

For real speedups, prefer an upstream/code change over local config folklore:

- skip Python dependency reinstall when lock/relevant dependency metadata did not change, with a cheap verification fallback;
- skip Node install when `package-lock.json` and `node_modules/.package-lock.json` already match, reusing the TUI-style lock comparison idea;
- keep web/desktop builds content- or mtime-gated rather than unconditional.

When using logs, separate actual build time from dependency install time. Web Vite builds may only be a few seconds; npm root/workspace installs are often the heavier part.