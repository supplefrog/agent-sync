# Codex auxiliary routing and request-surface probes

Use this reference when evaluating Hermes auxiliary/delegation/review routing with OpenAI Codex OAuth or Codex Responses request knobs.

## Durable lessons

- Treat the live Codex model endpoint as authoritative. Hermes may have fallback/offline catalog entries that are not available to the user's account.
- For this user's current Plus-backed Codex OAuth account, Spark-class Codex models are not available; do not route tests through Spark or interpret Spark failures as normal quota exhaustion.
- `codex-auto-review` can be used for review-style tasks when the task slot supports an explicit provider/model, e.g. `auxiliary.curator.provider=openai-codex` and `auxiliary.curator.model=codex-auto-review`.
- Background memory/skill self-review is not the same as the curator aux slot: it forks the parent runtime. If the user asks to force background self-review onto `codex-auto-review`, that is a code/config capability question, not just an aux config change.
- For compression/summarization, compare faithfulness first and latency second. A faster summarizer that invents the selected model or adds unsupported conclusions is worse than a slower concise model.

## Minimal probe pattern

When checking whether Codex Responses request fields are accepted, use the user's Codex OAuth token, the chatgpt.com Codex base URL, and Codex-shaped headers from Hermes' `_codex_cloudflare_headers()`. The Codex backend requires streaming.

High-level Python shape:

```python
from openai import OpenAI
from hermes_cli.auth import resolve_codex_runtime_credentials
from agent.auxiliary_client import _codex_cloudflare_headers
from agent.codex_runtime import _consume_codex_event_stream

creds = resolve_codex_runtime_credentials(refresh_if_expiring=True)
client = OpenAI(
    api_key=creds["api_key"],
    base_url=creds.get("base_url") or "https://chatgpt.com/backend-api/codex",
    default_headers=_codex_cloudflare_headers(creds["api_key"]),
)
stream = client.responses.create(
    model="gpt-5.4-mini",
    instructions="Reply OK only.",
    input=[{"role": "user", "content": "OK?"}],
    store=False,
    stream=True,
    extra_body={"text": {"verbosity": "low"}},
)
final = _consume_codex_event_stream(stream, model="gpt-5.4-mini")
```

## Interpreting `usage_limit_reached`

Do not assume `usage_limit_reached` means the user's visible account quota is exhausted. In the observed Codex Responses case:

- usage endpoint reported `allowed: true`, `limit_reached: false`, low primary/weekly use;
- baseline streaming Responses succeeded;
- `extra_body={"text":{"verbosity":"low"}}` also succeeded later;
- Spark returned a clean unsupported-model error when tested directly.

So the right interpretation was: transient/stale backend routing/quota state or a request-path mismatch, not proof that `extra_body.text.verbosity` is unsupported.

## Hermes config caveat

Direct SDK/Codex Responses can accept top-level `text` and `extra_body.text` in a streaming request, but Hermes' Codex Responses transport may still block clean top-level config through its request whitelist. Verify both layers separately:

1. backend acceptance via direct streaming probe;
2. Hermes config/transport acceptance via the actual Hermes path.
