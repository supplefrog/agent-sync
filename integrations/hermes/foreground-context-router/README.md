# Foreground Context Router

Hermes-native routing that opens fixed-budget Desktop conversations directly instead of relaying work through a parent/worker layer.

## Behavior

| Current chat | Classification | Action |
|---|---|---|
| normal (`gpt-5.6-sol`) | normal | stay |
| normal | extended | create, submit to, and foreground-open `gpt-5.6-sol-900k` |
| extended | same topic | stay for follow-ups |
| extended | clearly new + normal | open a fresh `gpt-5.6-sol` chat |
| extended | clearly new + extended | open a fresh `gpt-5.6-sol-900k` chat |
| any | low confidence, classifier failure, or attachments | stay; original send proceeds |

Context need is separate from intelligence: it estimates evidence/state volume, not task difficulty. Promotion carries at most 12,000 characters of recent user/assistant history; new topics carry none.

## Package

- `__init__.py` registers the `foreground_context_routing` auxiliary task.
- `dashboard/plugin_api.py` performs bounded Luna classification and fails closed to `normal/same`.
- `desktop/plugin.js` intercepts candidate sends, creates fixed-model sessions through gateway RPC, mounts the lazy destination before submitting exactly once, and retries foreground hydration after persistence when needed.

Canonical source lives here. The live deployment is:

`%LOCALAPPDATA%\hermes\plugins\foreground-context-router`

## Activation

The Python plugin and Desktop runtime plugin have separate enablement. `hermes plugins enable foreground-context-router` enables the Python registration/API half; first installation or backend changes then require a **Hermes Desktop restart**. The Desktop scanner discovers the JavaScript half but unified-plugin runtime contributions default off until **Settings → Plugins → Foreground Context Router** is enabled. That UI toggle hot-loads and persists separately. New chats then inherit the base global model; existing sessions keep their session-pinned model.

Required config:

```yaml
model:
  default: gpt-5.6-sol
auxiliary:
  foreground_context_routing:
    provider: openai-codex
    model: gpt-5.6-luna
    timeout: 30
```

## Known limits

- Attachments are not transferred automatically; their sends remain in the current chat rather than risking loss.
- A transport error after `prompt.submit` dispatch is ambiguous. The router consumes the origin draft, preserves the destination, and warns instead of risking a duplicate send.
- The current composer middleware API has no distinct “consumed successfully” result. A routed message executes exactly once and the destination opens, but the cleared draft can be restored in the origin chat's draft scope and reappear if that chat is revisited.
- Prompts that are clearly ordinary conversation bypass classification in normal chats. Action-like, broad, or long prompts are classified; every prompt in an extended chat is classified so unrelated topics can route out.

## Verification

```bash
python -m pytest tests/test_foreground_context_router.py -q -o "addopts="
node --experimental-vm-modules --test tests/foreground-context-router.test.mjs
python -m compileall -q integrations/hermes/foreground-context-router
node --check integrations/hermes/foreground-context-router/desktop/plugin.js
hermes plugins doctor foreground-context-router --ci
```

A fresh-process classifier probe must cover broad extended work, a focused normal task, and an unrelated normal topic from an extended chat. Final live admission requires explicit user approval and a bounded, non-delegating Desktop prompt that proves create → submit-once → foreground-open without spawning workers, touching a repository, or leaving extra sessions. Never use a whole-repository audit as a routing smoke test.

## Rollback

Disable **Foreground Context Router** under **Settings → Plugins**, then run `hermes plugins disable foreground-context-router` and restart Desktop. This stops automatic routing but intentionally leaves the economical base model configured. Restore a different global default separately only if that is the desired policy.
