# Windows Desktop gateway WS disconnects during long foreground tasks (2026-06)

## Symptom

Hermes Desktop reports gateway disconnect/reconnect while a long foreground task is running. The backend turn may continue, but the renderer loses the live stream and the session can become WS-detached.

Observed log pattern:

```text
tui_gateway.ws: ws write slow (loop stalled >10.0s) peer=127.0.0.1:<port> — frame left in flight
ConnectionResetError: [WinError 10054] An existing connection was forcibly closed by the remote host
tui_gateway.ws: ws closed peer=127.0.0.1:<port> reason=send_failed_after_response messages=<n> parse_errors=0 dispatch_crashes=0 send_failures=1 reaped_sessions=0 detached_sessions=1
```

Typical process shape:

```text
Hermes.exe
python.exe -m hermes_cli.main dashboard --no-open --host 127.0.0.1 --port 0
python.exe -m tui_gateway.slash_worker --session-key ...
python.exe -m pytest ...   # or another long foreground command
```

## Diagnosis workflow

1. Confirm this is Desktop/TUI JSON-RPC WS, not the old messaging gateway service:
   - active backend is `python -m hermes_cli.main dashboard ...`
   - relevant logs are `agent.log`, `desktop.log`, `tui_gateway_crash.log`
   - look for `tui_gateway.ws:` lines.
2. Search for the exact WS disconnect signatures:
   - `ws write slow (loop stalled >10.0s)`
   - `send_failed_after_response`
   - `WebSocketDisconnect`
   - `ConnectionResetError: [WinError 10054]`
3. Inspect active child processes for long foreground work under `tui_gateway.slash_worker`.
4. Check config only after log evidence; short `agent.gateway_timeout` or `terminal.timeout` is usually not the cause when the close reason is WS send failure.

## Root-cause class

Long/high-output foreground turns can emit JSON-RPC frames from multiple worker paths while the uvicorn event loop is stalled/catching up. If writes to a single Starlette WebSocket overlap, the renderer can see resets/disconnects. Server-side disconnect handling detaches non-`close_on_disconnect` sessions so the turn is preserved, but Desktop may lose the live stream until reconnect/resume.

## Fix pattern

Narrow source fix: serialize per-socket WS sends in `tui_gateway/ws.py` with an `asyncio.Lock` around `send_text()`, while preserving the existing behavior that slow writes are left in flight rather than latching the transport closed.

Regression test pattern in `tests/test_tui_gateway_ws.py`:

- keep `test_ws_write_loop_stall_does_not_latch_transport`
- add a concurrent-writer test that records `max_active_sends` from two `transport.write()` calls and asserts it never exceeds `1`.

Verification used:

```bash
.venv/Scripts/python.exe -m pytest tests/test_tui_gateway_ws.py -q -o addopts=
.venv/Scripts/python.exe -m pytest tests/test_tui_gateway_server.py tests/test_tui_gateway_ws.py -q -o addopts=
```

## Upstreaming notes

Duplicate-search terms that found no existing issue/PR in this case:

- `websocket disconnect long task desktop`
- `ws write slow loop stalled desktop`
- `tui_gateway.ws send_failed_after_response`
- `Gateway connection closed long task`
- `desktop reconnect detached session slash_worker`
- `WebSocketDisconnect tui_gateway desktop`

A maintainer-grade issue should include the log signatures, active process shape, expected vs actual behavior, and suspected files: `tui_gateway/ws.py` and `tui_gateway/server.py`.
