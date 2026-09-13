# Windows Desktop stuck-busy / failed resume after update

## Symptom class

Desktop after update may show:

- Stop button on every opened chat even though the user believes no prompt is running.
- `session.resume` / opening existing chats fails or leaves the view stranded.
- Pressing Stop, typing a prompt, and Enter opens a new chat but appears to do nothing.
- Provider routing may have recently fallen back to OpenRouter/no-provider even though the intended setup is OpenAI Codex OAuth.

## Concrete evidence pattern from June 2026

Process inspection showed a healthy Desktop tree plus many stale workers:

- `Hermes.exe` Electron main + renderer processes.
- backend: `python.exe -m hermes_cli.main dashboard --no-open --host 127.0.0.1 --port 0`.
- multiple `python.exe -m tui_gateway.slash_worker --session-key ...` children for old session keys.

`/api/status` from the active backend port reported `active_sessions: 1` after cleanup, matching the current chat.

Config/status checks showed the current intended route was:

```yaml
model:
  default: gpt-5.5
  provider: openai-codex
  base_url: https://chatgpt.com/backend-api/codex
```

The session database showed recent rows where good/current sessions had `billing_provider=openai-codex` and `model_config.provider=openai-codex`, while some older rows had missing provider metadata. That means current config can be fixed while specific old chats may still resume through bad persisted runtime metadata.

## Recovery sequence

1. Confirm the active backend and port from process command lines / Desktop logs.
2. Query `http://127.0.0.1:<port>/api/status` and note `active_sessions`.
3. Verify current provider route with `hermes config path`, `hermes status --all`, and `config.yaml`.
4. Inspect `tui_gateway.slash_worker` processes. If many old workers are present, identify the current session key and kill only worker process trees whose command lines do not match it.
5. Recheck the process tree and `/api/status`; active sessions should match reality.
6. If old chats still fail, inspect session runtime metadata in `state.db` (`sessions.model`, `billing_provider`, `model_config.provider`) before blaming the live provider config.

## Pitfalls

- Do not kill all `Hermes.exe` / backend processes as the first move if the user is currently talking to the agent through Desktop; that would terminate the working session.
- Do not record “OpenRouter is broken” or “resume is broken” as durable knowledge. The useful durable pattern is narrow cleanup plus provider-route verification.
- A current working provider config does not guarantee every old session row carries valid provider metadata.