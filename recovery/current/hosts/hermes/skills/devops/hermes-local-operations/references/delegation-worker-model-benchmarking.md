# Delegation worker model benchmarking

Use this when evaluating cheap/free models for Hermes child/delegation workers.

## Durable lessons

- Do not rely on model-list visibility alone. Some providers expose model IDs that later fail on the first real request or return HTTP 200 with empty content. Always run at least one real completion and one real tool/delegated child call before recommending a delegation model.
- When scanning free/cheap providers, search for current model families explicitly (`gemma`, `qwen`, `llama-4`, `nemotron`, and coding-model names) rather than reusing an older shortlist. Missing a current family such as Gemma 4 is a benchmark-quality failure, even if older Gemma/Nemotron IDs are present.
- Keep any provider out of worker benchmarks when the user's quota is reserved for another service. Remove its API key only from the benchmark subprocess environment, not from the user's shell/config.
- If the user's normal launcher sets `HERMES_TUI=1`, one-shot `hermes chat -Q` benchmark subprocesses may need `HERMES_TUI` unset in the subprocess env. Do not change the persistent launcher or profile just to run a benchmark.
- Prefer a temporary `HERMES_HOME` for delegation override tests. Copy only the minimum auth/env files needed, write a small temporary `config.yaml`, and delete the temp home afterward. This avoids mutating the default profile while still exercising the real `delegate_task` path.
- Free/high-demand providers can pass simple tasks but still be poor default workers because latency spikes dominate real child-agent usability. Treat latency as a first-class pass/fail dimension, especially tool-use latency.
- For low-risk Hermes child workers, a cheap authenticated first-party model is usually more operationally reliable than a free aggregator/NIM route, even when the latter is nominally capable.
- Do not patch local Hermes source to add delegation routing behavior unless the user is explicitly contributing upstream. Local changes under the installed Hermes tree are likely to be reverted on `hermes update`; prefer supported config/profile/CLI routing instead.
- Current supported default-worker path: set `delegation.provider`, `delegation.model`, and optionally `delegation.reasoning_effort` for normal `delegate_task`. Treat normal `delegate_task` as the low-risk worker route after this. For high-risk fresh-context work, keep it in the parent or launch an explicit one-shot/profile with the high-intelligence model; do not invent unsupported per-call `risk=` behavior.
- Verify delegation config from a fresh Hermes process. Existing interactive sessions may have cached delegation config/tool metadata and can continue using the old child model until restart.

## Minimal benchmark shape

1. Inspect live auth and model availability (`hermes auth list`, provider `/models` endpoints, Codex OAuth model list if relevant).
2. Exclude providers the user has reserved for other infrastructure.
3. For each candidate, run fresh one-shot Hermes invocations for:
   - exact concise JSON output;
   - a small coding/reasoning microtask;
   - real tool use with a verifiable filesystem side effect;
   - actual delegation compatibility through `delegate_task` using temporary `HERMES_HOME`.
4. Record wall-clock latency, failure mode, strict JSON compliance, and verbosity/reasoning leakage.
5. Recommend a routing policy, not just a winner: safe default, fallback only, do-not-use, and when to keep the big model.

## Reporting guidance

Report evidence separately from policy. A useful matrix includes task pass/fail, seconds, and weirdness notes. Do not apply `delegation.*` config changes without explicit approval.