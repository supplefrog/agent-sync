# Windows Desktop gateway WebSocket stalls during long tasks

Session pattern: user reports that the "gateway disconnects randomly" while long tasks are running in Hermes Desktop.

## Evidence pattern

Inspect Windows process tree and Hermes logs before assuming the old messaging gateway service is crashing.

Useful process evidence:

- Desktop Electron main process: `Hermes.exe` without `--type=`.
- Dashboard backend: `python.exe -m hermes_cli.main dashboard --no-open --host 127.0.0.1 --port 0`.
- Per-session workers: `python.exe -m tui_gateway.slash_worker --session-key ...`.
- Heavy foreground task may appear under a worker, e.g. `python.exe -m pytest ...`, with high RSS/CPU.

Log signatures in `%LOCALAPPDATA%\\hermes\\logs\\agent.log`:

```text
tui_gateway.ws: ws write slow (loop stalled >10.0s) peer=127.0.0.1:<port> — frame left in flight
ConnectionResetError: [WinError 10054] An existing connection was forcibly closed by the remote host
tui_gateway.ws: ws send failed peer=127.0.0.1:<port> error_type=WebSocketDisconnect
tui_gateway.ws: ws closed peer=127.0.0.1:<port> reason=send_failed_after_response ... detached_sessions=1
```

Follow-up reconnects can fail at startup with:

```text
tui_gateway.ws: ws closed ... reason=ready_send_failed messages=0 ...
```

## Interpretation

This is the Desktop/TUI JSON-RPC WebSocket path (`tui_gateway/ws.py`), not necessarily the standalone messaging gateway service (`hermes gateway run`). Long/heavy foreground tasks can stall the local WebSocket event loop or create enough frame backlog that the Electron renderer drops the socket. The backend may keep the running slash worker alive; the UI loses the live stream and reconnects/detaches.

Relevant code landmarks:

- `tui_gateway/ws.py` — `WSTransport.write`, `_WS_WRITE_TIMEOUT_S`, `handle_ws`, close reasons.
- `tui_gateway/server.py` — `_close_sessions_for_transport`, `_detached_ws_transport`, `_WS_ORPHAN_REAP_GRACE_S`, orphan reaping.
- `apps/shared/src/json-rpc-gateway.ts` — renderer WS client close/error state and pending request rejection.
- `apps/desktop/src/app/gateway/hooks/use-gateway-boot.ts` — Desktop reconnect behavior after closed/error state.

## Immediate mitigation

For long/heavy commands, prefer tracked background processes with completion notification, or run the job outside the Desktop chat, rather than foreground-streaming huge output through the Desktop gateway.

## Product fix direction

Do not just raise user-facing timeouts unless logs prove a timeout. Better fixes are:

- throttle/coalesce high-volume gateway progress frames;
- prevent stale in-flight frames from flooding a closed socket;
- make reconnect reattach to the still-running session when possible;
- preserve live task state in the UI after reconnect instead of silently creating a new path;
- improve diagnostics so the UI distinguishes "backend died" from "renderer WebSocket dropped while worker continues".
