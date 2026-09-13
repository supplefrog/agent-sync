# NVIDIA NIM / OpenCode Zen worker probe notes (2026-05)

Session-specific reference for benchmarking cheap/free Hermes child/delegation workers. Do not treat the exact model verdicts as permanent; re-run live checks before using them.

## OpenCode Zen key setup and verification

- Hermes provider id: `opencode` for Zen, `opencode-go` for Go.
- Env vars used by Hermes overlays:
  - `OPENCODE_ZEN_API_KEY`
  - `OPENCODE_ZEN_BASE_URL` (normally `https://opencode.ai/zen/v1`)
  - `OPENCODE_GO_BASE_URL` for Go if testing that route.
- Store secrets in `~/.hermes/.env`; do not put raw keys in command args or reports.
- After setting a Zen key, `/models` probes from WSL may still return Cloudflare `403 error code: 1010` across `opencode.ai` and `api.opencode.ai` URL variants. Report this as an environment/request-path block, not proof that the key or product is bad.

## NVIDIA NIM discovery pattern

Use the official OpenAI-compatible endpoint:

```text
https://integrate.api.nvidia.com/v1
```

Live `/models` discovery matters because available NIM IDs change and some listed IDs may not be callable for the account. Search specifically for current families instead of relying on older shortlists:

- `gemma` including `google/gemma-4-31b-it`, `google/gemma-3n-e4b-it`, etc.
- `qwen` including `qwen/qwen3-coder-480b-a35b-instruct` and newer `qwen/qwen3.5-*` IDs.
- `llama-4` / `llama4` such as `meta/llama-4-maverick-17b-128e-instruct`.
- `nemotron`, but validate content quality; some nano/super/nemotron entries can return empty content despite HTTP 200.
- coding models: `qwen3-coder`, `codestral`, `deepseek-coder`, `granite-code`, `codegemma`, `starcoder`.
- free-coding shortlist/display names the user may provide, mapped to live IDs before testing. In the 2026-05 probe this included:
  - GPT OSS 20B → `openai/gpt-oss-20b`
  - GPT OSS 120B → `openai/gpt-oss-120b`
  - Llama 3.1 8B → `meta/llama-3.1-8b-instruct`
  - Ministral 14B → `mistralai/ministral-14b-instruct-2512`
  - Mistral Small 4 → `mistralai/mistral-small-4-119b-2603`
  - Stockmark 100B → `stockmark/stockmark-2-100b-instruct`
  - Step 3.5 Flash → `stepfun-ai/step-3.5-flash`
  - DeepSeek V4 Flash/Pro → `deepseek-ai/deepseek-v4-flash`, `deepseek-ai/deepseek-v4-pro`
  - Llama 4 Maverick → `meta/llama-4-maverick-17b-128e-instruct`
  - MiniMax M2.7 → `minimaxai/minimax-m2.7`

## Codex OAuth and GPT-OSS

For this user's current ChatGPT/Codex OAuth account, GPT-OSS is not exposed through `openai-codex`. Hermes normalizes `openai/gpt-oss-20b` to `gpt-oss-20b`, but the provider returns:

```text
The 'gpt-oss-20b' model is not supported when using Codex with a ChatGPT account.
The 'gpt-oss-120b' model is not supported when using Codex with a ChatGPT account.
```

Do not assume OpenAI Codex OAuth can call OpenAI OSS models. Use NIM or another provider that explicitly lists and accepts the OSS ID.

## Low-context model override risk

Hermes rejects models below 64k context (`MINIMUM_CONTEXT_LENGTH = 64_000`) for tool-calling reliability. `model.context_length` can override detection, but setting a 16k model to `64000` only bypasses the guard; it does not increase the model's real context. Downsides:

- Hermes may build prompts/compression thresholds as if 64k is safe.
- Tool schemas, memory, skills, and file snippets can exceed the real window.
- Failures may appear later as provider errors, truncation, or weird behavior rather than clean startup rejection.

Only test sub-64k models in an isolated experimental profile with memory off, narrow toolsets, small prompts, and explicit user acceptance. Do not change `default` for this.

## GPT-OSS reasoning-output behavior

NIM `openai/gpt-oss-120b` can be fast and format-reliable only when the output budget is not starved by hidden/structured reasoning. In the 2026-05 probe, `120b` passed repeated strict JSON tasks when `max_tokens` was 120–600, but a simple two-bullet task with `max_tokens=200` failed most runs by spending the budget on reasoning first and returning empty or truncated visible content. Treat small `max_tokens` caps as unsafe for OSS worker probes even for concise tasks.

Hermes preserves provider reasoning separately (`reasoning_content` / `reasoning_details`) and strips inline `<think>`-style blocks from final visible output, but verbose/progress/session paths can still show reasoning noise. If using GPT-OSS as an experimental child route, prefer mitigating at the parent/child-result boundary: pass only the child's final visible response to the parent, drop `reasoning`, `reasoning_content`, and `reasoning_details` from child summaries, and suppress child reasoning progress events where possible. Do not truncate raw model output before Hermes processes it; that increases the chance of no visible answer.

`/reasoning none|minimal|low` did not reliably suppress NIM GPT-OSS reasoning in this path during the probe. Do not assume Hermes reasoning-effort config controls GPT-OSS on NIM unless a fresh verbose run confirms lower reasoning tokens.

## Probe tasks that caught real differences

Run at least these before recommending a free/cheap worker:

1. Strict concise output: `Return exactly this JSON and nothing else: {"ok":true,"n":7}`.
2. Coding microtask: implement `f(xs)` returning sum of squares of even ints and compute `[1,2,3,4] -> 20`.
3. Raw OpenAI-compatible `tools` call: provide an `add(a,b)` function and ask the model to add 2 and 5.
4. Real Hermes one-shot: `HERMES_TUI=0 hermes chat --provider nvidia -m <model> -Q -q 'Return exactly: {"ok":true}'`.
5. Real Hermes tool-use check: enable `-t terminal`, ask it to run `printf tool_ok`, and verify verbose logs show a real `terminal` tool call and final JSON.

Use `HERMES_TUI=0` for non-interactive subprocess benchmarks if the user's wrapper normally sets Ink TUI; do not mutate the wrapper.

## Example findings from this session

These are historical evidence, not durable permanent rankings:

| Model | Result pattern observed |
|---|---|
| `openai/gpt-oss-20b` | Fast experimental NIM worker candidate: very low raw latency, correct coding microtask, real tool calls, and successful Hermes terminal-tool use. However strict-output reliability was weaker than 120B in later probes (2/5 exact with a tight token cap), and NIM exposes reasoning fields that can consume output budget or show side-channel/noise in Hermes. Not available through this user's `openai-codex` OAuth account. |
| `openai/gpt-oss-120b` | Better experimental default than 20B when format reliability matters: later probes showed 5/5 strict JSON, 5/5 coding, 5/5 raw tool calls, and sub-2s raw latencies. Still exposes reasoning side-channel/noise and still depends on NIM free-tier availability. Not available through this user's `openai-codex` OAuth account. |
| `meta/llama-3.1-8b-instruct` | Very fast and passed raw strict/coding/tool probes, but Hermes rejected it because catalog context was below the 64k minimum. Do not override this casually; only consider in a narrow low-context profile if the user explicitly accepts it. |
| `mistralai/ministral-14b-instruct-2512` | Fast, correct coding, and raw tool-call capable, but tends to wrap JSON in markdown fences. Treat as format-tolerant fallback, not first choice for strict structured workers. |
| `deepseek-ai/deepseek-v4-flash` | Capable and real tool calls, but latency varied from subsecond to 20s+ raw and actual Hermes tool run took multiple seconds per API call. If initial latency is worse than `gpt-5.4-mini`, stop chasing it for cheap-worker use. |
| `deepseek-ai/deepseek-v4-pro` | Returned 429 in this account during the probe. |
| `deepseek-ai/deepseek-coder-6.7b-instruct` | Listed by `/models` but 404/not found for this account. |
| `qwen/qwen3-coder-480b-a35b-instruct` | Do not treat as a quality fallback by size alone. It passed earlier strict/coding/tool probes, but later repeated trivial probes timed out; the user noted it is free-to-them, so the relevant issue is latency/availability, not cost. Do not claim it is smarter than `gpt-5.4-mini` without direct evidence. Use only opportunistically after fresh latency checks. |
| `meta/llama-4-maverick-17b-128e-instruct` | Good strict JSON and coding, but emitted tool-like JSON as text instead of a real tool call in the raw test. Treat as no-tool fallback unless re-tested. |
| `google/gemma-4-31b-it` | Timed out on a trivial strict-output probe in this environment. Re-test later before excluding permanently. |
| `google/gemma-3n-e4b-it` | Fast and solved coding, but wrapped JSON in fences and failed the raw tool path due provider/parser behavior. No-tool fallback only. |
| `qwen/qwen3.5-122b-a10b`, `nvidia/nemotron-3-nano-30b-a3b`, `nvidia/nvidia-nemotron-nano-9b-v2` | HTTP 200 but empty content on basic tasks. Do not route workers there without a fresh successful probe. |
| `nvidia/nemotron-mini-4b-instruct` | Very fast, but wrong coding answer and fake/partial tool-call text. Only trivial fallback, not coding/delegation. |

## Routing lesson

For this user's preference profile, do not conclude from one weak free model that all free providers are unusable. The right policy is:

- Big model plans and supervises.
- Cheap/free worker can implement bounded, low-risk tasks only after live completion + tool-use + Hermes one-shot checks pass.
- Free-provider durability is an operational risk; repeat latency/availability probes before making it the default.
- Use the user's current benchmark/free-model shortlist when they provide one; old family-based shortlists miss good candidates such as GPT-OSS 20B/120B and may over-focus on heavier models.
- For cheap/free coding workers, prefer fast models that pass real tool calls and Hermes one-shots over larger models with better headline benchmarks but worse latency/availability. In this session `openai/gpt-oss-120b` became the better experimental free-tier profile candidate because it kept OSS speed while passing stricter output probes; `openai/gpt-oss-20b` remained the faster but less format-reliable option. Do not present `qwen/qwen3-coder-480b-a35b-instruct` as a quality fallback without fresh evidence; even when free-to-user, it was latency-variable and not established as smarter than `gpt-5.4-mini` for Hermes children.
- If a candidate's initial latency is already worse than a known cheap baseline such as `gpt-5.4-mini`, stop deeper probing unless there is a clear capability reason. Do not spend time rescuing slow free-tier candidates for routine worker routing.
- Do not apply `delegation.provider` / `delegation.model` changes without explicit approval. Recommend profile-specific overrides first.
