# Windows Desktop resume / image.attach timeouts (2026-06)

## Symptom pattern

User reported after update/restart:

- `Resume failed — request timed out: session.resume`
- `Prompt failed — request timed out: image.attach`
- Desktop sometimes opened a new chat instead of continuing the current chat.
- Stop/busy indicator appeared even when no useful prompt was running.

Process evidence showed the Desktop backend was alive but had stale `tui_gateway.slash_worker` children for old session keys. In one state, `/api/status` reported `active_sessions: 0` while a slash worker was still running.

## Root-cause class

There were two separate but interacting classes:

1. **Provider/session-runtime mismatch**
   Older/newly-created sessions could route `gpt-5.5` through `nous` or OpenRouter-like fallback instead of `openai-codex`, producing `HTTP 404: Model 'gpt-5.5' not found` or unusable routing. Check current `config.yaml` and the session row's `model_config.provider` / `billing_provider` before assuming auth is broken.

2. **Image attach waiting on lazy agent initialization**
   `tui_gateway.server` had `image.attach` call `_sess()`, which starts/waits for AIAgent build. Image staging only needs the session object and queued attachment list. During resume/startup, this can exceed the Desktop JSON-RPC timeout before the prompt is submitted. The minimal fix was to use `_sess_nowait()` for `image.attach`, leaving actual agent build to `prompt.submit`.

## Diagnostic commands

Inspect Desktop/backend/session workers from Git Bash via PowerShell:

```bash
powershell.exe -NoProfile -Command 'Get-CimInstance Win32_Process | Where-Object { $_.Name -match "Hermes|python" -or $_.CommandLine -match "hermes|tui_gateway|dashboard|slash_worker" } | Select-Object ProcessId,ParentProcessId,Name,CommandLine | Format-List'
```

Find backend port:

```bash
powershell.exe -NoProfile -Command 'Get-NetTCPConnection -OwningProcess <backend-pid> -ErrorAction SilentlyContinue | Select LocalAddress,LocalPort,State,OwningProcess | Sort LocalPort | Format-Table -AutoSize'
```

Check status:

```bash
curl -fsS --max-time 3 http://127.0.0.1:<port>/api/status
```

Inspect recent session provider persistence:

```bash
python - <<'PY'
import sqlite3, json
p=r'{{agent-signal:HERMES_HOME}}\state.db'
con=sqlite3.connect(p); con.row_factory=sqlite3.Row
for r in con.execute("select id,title,model,billing_provider,model_config,started_at,message_count from sessions order by started_at desc limit 10"):
    try: mc=json.loads(r['model_config'] or '{}')
    except Exception: mc={}
    print(r['id'], 'msgs', r['message_count'], 'model', r['model'], 'billing', r['billing_provider'], 'provider', mc.get('provider'), 'title', (r['title'] or '')[:60])
PY
```

## Safe cleanup pattern

If backend status says no active session but old slash workers remain, kill only stale/orphan `tui_gateway.slash_worker` trees, not the whole Desktop tree unless a full restart is intended.

PowerShell pattern, preserving one known-good session key:

```powershell
$keep="<current-session-key>"
$procs=Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "tui_gateway\.slash_worker" -and $_.CommandLine -notmatch [regex]::Escape($keep) }
$all=@()
foreach($p in $procs){
  $all += [int]$p.ProcessId
  $kids=Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $p.ProcessId }
  foreach($k in $kids){ $all += [int]$k.ProcessId }
}
$all=$all | Sort-Object -Unique
foreach($id in $all){ Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
```

If `/api/status` reports `active_sessions: 0`, kill all `tui_gateway.slash_worker` trees.

## Regression test shape

Add a server-level regression proving `image.attach` does not wait for lazy agent build:

- Insert a fake session with `agent_ready = threading.Event()` that is never set.
- Monkeypatch `_start_agent_build` to raise if called.
- Call `image.attach` with a fake image path.
- Assert it returns attached immediately and did not start build.

Nearby checks:

```bash
python -m pytest tests/test_tui_gateway_server.py::test_image_attach_does_not_wait_for_lazy_agent_build \
  tests/test_tui_gateway_server.py::test_image_attach_appends_local_image \
  tests/test_tui_gateway_server.py::test_image_attach_accepts_unquoted_screenshot_path_with_spaces -q
```

## Product-fix direction

- `image.attach` should use `_sess_nowait()` because it only queues an attachment.
- `image.attach_bytes` already uses `_sess_nowait()` and is the working reference.
- Keep `prompt.submit` responsible for starting/waiting on AIAgent initialization.
- Treat `session.resume` timeout separately; don't hide it by only increasing client timeouts.
