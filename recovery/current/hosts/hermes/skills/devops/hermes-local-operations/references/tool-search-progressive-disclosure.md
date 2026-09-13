# Hermes Tool Search / Progressive Disclosure Notes

Use this reference when investigating Hermes tool-schema bloat, lazy loading, or issue/PR discussions around Tool Search.

## Current core shape observed in Hermes v0.15.x

Hermes core may include `tools/tool_search.py` wired from `model_tools.py` into request-time tool assembly. This is the upstream progressive-disclosure path, distinct from external tool-slimming plugins.

Key properties to verify in the local install:

```bash
hermes --version
python - <<'PY'
from pathlib import Path
root = Path('/usr/local/lib/hermes-agent')
print((root/'tools/tool_search.py').exists())
print('tool_search' in (root/'model_tools.py').read_text())
PY
hermes prompt-size
```

Expected implementation characteristics:

- bridge tools are `tool_search`, `tool_describe`, and `tool_call`;
- MCP and non-core plugin tools are deferrable;
- core Hermes tools are deliberately never deferred;
- default config is typically `tools.tool_search.enabled: auto` with a threshold gate;
- setting `enabled: on` should only be done in an experimental profile first.

## Safe experiment pattern

Do not modify `default` first. Use an isolated profile and prefer upstream core Tool Search before third-party/plugin slimming.

```bash
hermes profile create toolsearch-exp --clone-from dev --no-alias \
  --description "Experimental profile for upstream Tool Search / progressive MCP-plugin tool disclosure."

hermes --profile toolsearch-exp config set tools.tool_search.enabled on
hermes --profile toolsearch-exp config set tools.tool_search.threshold_pct 0

hermes --profile toolsearch-exp prompt-size
hermes --profile toolsearch-exp tools list --platform cli
```

Rollback:

```bash
hermes --profile toolsearch-exp config set tools.tool_search.enabled off
# or remove the profile entirely
hermes profile delete toolsearch-exp
```

## Dry-run / no-config probe

For a no-write probe, call core assembly in memory with `ToolSearchConfig('on', ...)` and compare raw vs assembled schemas. Use the profile's real `HERMES_HOME` for in-process Python probes; `hermes --profile ...` is a CLI flag, while imported config code reads `HERMES_HOME`/Hermes home directly.

```bash
HERMES_HOME={{agent-signal:HERMES_HOME}}/profiles/toolsearch-exp python - <<'PY'
import sys
sys.path.insert(0, r'{{agent-signal:HERMES_HOME}}/hermes-agent')
from hermes_cli.config import load_config
from model_tools import get_tool_definitions
from tools.tool_search import classify_tools, estimate_tokens_from_schemas, assemble_tool_defs, ToolSearchConfig, load_config as load_ts

cfg = load_config()
enabled = cfg.get('toolsets') or (cfg.get('agent') or {}).get('enabled_toolsets')
disabled = (cfg.get('agent') or {}).get('disabled_toolsets')
raw = get_tool_definitions(enabled, disabled, quiet_mode=True, skip_tool_search_assembly=True)
visible, deferrable = classify_tools(raw)
assembled = get_tool_definitions(enabled, disabled, quiet_mode=True, skip_tool_search_assembly=False)
print('tool_search_config', load_ts())
print('raw_count', len(raw), 'visible_core_count', len(visible), 'deferrable_count', len(deferrable), 'deferrable_tokens', estimate_tokens_from_schemas(deferrable))
print('assembled_count', len(assembled), 'assembled_names', [t['function']['name'] for t in assembled])
PY
```

Interpretation:

- If existing profiles already have `tools.tool_search.enabled: auto` and `threshold_pct: 10`, that is usually the recommended production state; do not force `on` globally unless the user accepts extra bridge-tool latency for small plugin surfaces.
- `deferrable == 0`: upstream Tool Search cannot reduce current tool schema payload; bloat is in core tools, skills, memory, or system prompt.
- `activated == False` in `auto`: deferrable schemas are below threshold for the active model context.
- If `prompt-size` and `tools list` disagree with profile expectations, inspect actual request-time assembly before concluding profile splitting is working.

## Workflow safety probes

Verify both the current real profile and a synthetic deferrable-tool case.

Current profile checks should prove core tools remain directly visible:

```python
required = {
    'file/coding core': {'terminal','read_file','write_file','patch','search_files','execute_code'},
    'skills/config core': {'skill_view','skills_list','terminal'},
    'planning/memory core': {'todo','session_search','memory','clarify'},
    'delegation core': {'delegate_task','terminal'},
}
assembled_names = {t['function']['name'] for t in assembled}
for label, names in required.items():
    print(label, names <= assembled_names, sorted(names - assembled_names))
print('nondeferrable_missing', sorted({t['function']['name'] for t in visible} - assembled_names))
```

If there are no real MCP/plugin tools, register throwaway in-process fake plugin tools (do not write files/config) to exercise the bridge path: add two `registry.register(..., toolset='fake-plugin', ...)` tools, resolve `enabled=['hermes-cli','fake-plugin']`, and confirm the fake tools disappear from `assembled_names` while `tool_search`/`tool_describe`/`tool_call` appear. Then call `dispatch_tool_search({'query': 'calendar meeting tomorrow', 'limit': 5}, current_tool_defs=raw)` and `dispatch_tool_describe({'name': fake_name}, current_tool_defs=raw)` to prove discovery and schema hydration work.

Finally run at least one real one-shot chat in the experimental profile with TUI env unset for non-interactive shells:

```bash
env -u HERMES_TUI -u HERMES_VOICE hermes --profile toolsearch-exp chat -q \
  'Use the terminal tool to run: printf toolsearch-exp-terminal-ok. Reply with exactly the command output.'
```

## Third-party slimming plugin caution

External keyword/BM25 tool-slimming plugins can show good offline reductions, but they may hide core tools and depend on hooks or patches. Test them only after upstream Tool Search is insufficient, and only with:

- experimental profile;
- dry-run/no-core-patch mode first, if supported;
- workflow probes proving required tools stay visible;
- explicit user approval before installing packages, enabling plugins, or patching Hermes core.
