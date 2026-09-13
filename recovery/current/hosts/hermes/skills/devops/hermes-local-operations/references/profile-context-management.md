# Profile and context management absorbed notes

Clone the current/default profile, then slim the clone. Preserve `default` as the full fallback until reduced profiles have been used successfully.

Use official invocation:

```bash
hermes --profile lite
hermes --profile dev
hermes --profile browser-agent
```

Avoid adding aliases/launchers unless explicitly requested.

## Practical profile shapes

### `lite`

Purpose: low-bloat daily chat/config/file work.

Keep terminal, file, code execution, skills, todo, memory, session search, and clarify. Usually disable web/browser/vision/search, media/social/smart-home tools, delegation, cronjob, and generation toolsets.

### `dev`

Purpose: coding and subagent delegation.

Keep web lookup when needed, terminal/file/code execution, skills/todo/memory/session search/clarify, and delegation. Usually disable browser unless UI testing is central, media/social/smart-home tools, TTS/image/video generation, and cron unless scheduling is the task. Set delegation child model/provider, timeout, max iterations, concurrency, and spawn depth explicitly.

### `browser-agent`

Purpose: terminal-driven browser automation through an external browser agent CLI, with Hermes itself kept lean.

Keep terminal, file, code execution, vision if screenshots are needed, skills/todo/memory/session search/clarify. Usually disable Hermes browser/web/search if the external browser CLI provides browsing.

## Verification output pattern

After editing profiles, list profiles, effective enabled toolsets per profile, profile-specific config, external CLI dependencies, and exact commands such as:

```text
hermes --profile lite
hermes --profile dev
hermes --profile browser-agent
```

## Lazy-loading note

Treat lazy tool loading as a research/verification question. If reliability is unclear, recommend profile-level isolation as the stable workaround.
