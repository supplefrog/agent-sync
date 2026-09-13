# Codex Responses `text.verbosity` in Hermes

Session evidence from Hermes Agent v0.16.0 on Windows with provider `openai-codex`, model `gpt-5.5`.

## What was verified

A minimal probe using `AIAgent(..., request_overrides=...)` found:

- Baseline Codex Responses request succeeded.
- `request_overrides={"text": {"verbosity": "low"}}` failed before HTTP with:

```text
Codex Responses request has unsupported field(s): text.
```

- `request_overrides={"extra_body": {"text": {"verbosity": "low"}}}` was accepted by Hermes and reached the Codex backend successfully.
- A later retest with correct Codex OAuth headers succeeded for baseline, `extra_body.text.verbosity=low`, and direct top-level `text.verbosity=low`; the earlier `429 usage_limit_reached` was transient/stale backend quota/routing state, not evidence that `extra_body` was unsupported.
- A local config/source path now exists on this setup: `model.request_overrides.extra_body.text.verbosity: low` is merged into `AIAgent.request_overrides` at startup. Verify this path after Hermes updates because it is a local source patch, not yet an upstream first-class knob.

## Source evidence

`agent/codex_responses_adapter.py` normalizes Codex Responses requests with an allowlist that includes `extra_body` but not top-level `text`:

```py
allowed_keys = {
    "model", "instructions", "input", "tools", "store",
    "reasoning", "include", "max_output_tokens", "temperature",
    "tool_choice", "parallel_tool_calls", "prompt_cache_key", "service_tier",
    "extra_headers", "extra_body", "timeout",
}
...
unexpected = sorted(key for key in api_kwargs if key not in allowed_keys)
if unexpected:
    raise ValueError(
        f"Codex Responses request has unsupported field(s): {', '.join(unexpected)}."
    )
```

## Current practical guidance

- Do not tell the user Hermes has a clean `agent.text_verbosity` knob unless current source/config proves it.
- Do not conflate this with `display.*`, `agent.verbose`, or `agent.reasoning_effort`.
- Be precise about levels:
  - `agent.system_prompt` / SOUL/personality changes are prompt-level text instructions.
  - `extra_body` is request-level SDK/API payload plumbing, not prompt text.
  - Top-level Responses fields such as `text.verbosity` are provider-native request fields when the transport supports them.
- If using a workaround, prefer a reversible test/probe and state that it is low-level request plumbing, not first-class config.
- Report request acceptance separately from behavioral effect. A backend returning a normal provider error such as `429 usage_limit_reached` after receiving the payload proves the request path reached the backend; it does not prove `verbosity=low` changed answer length.
- If asked which Codex OAuth models are supported, prefer live discovery with the Codex CLI OAuth token over Hermes fallback catalogs. In Python from the Hermes repo, use `_read_codex_tokens()` from `hermes_cli.auth` and `get_codex_model_ids(access_token=...)` from `hermes_cli.codex_models`; distinguish live endpoint results from fallback/offline entries.
- If asked to file upstream, check issue #20203 first: <https://github.com/NousResearch/hermes-agent/issues/20203>. In this session, evidence was added as comment <https://github.com/NousResearch/hermes-agent/issues/20203#issuecomment-4736166044>.

## Desired upstream shape

A clean implementation should add a first-class config value, validate `low|medium|high`, and map it into the correct Responses request shape only for compatible providers/transports. It should preserve current behavior when unset and avoid sending provider-specific fields to unsupported backends.
