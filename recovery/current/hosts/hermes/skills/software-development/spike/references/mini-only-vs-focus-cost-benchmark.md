# Mini-only vs Hermes focus cost benchmark

Session-specific reference for benchmarking a mini-swe-style repair harness exposed through Hermes against Hermes `agent.coding_context=focus`.

## Question

The user was not asking which model/provider solves best. The target was cost optimization while preserving issue-repair quality using the user's daily driver model.

Correct axis:
- `focus_plain`: Hermes `agent.coding_context=focus`, daily model fixed.
- `mini_only`: Hermes surface with `agent.coding_context=off`, lean explicit tools, mini-swe-style issue-repair workflow prompt, daily model fixed.

Do **not** compare `focus + mini overlay` as the primary cost test; adding an overlay to focus obviously adds prompt/tool overhead and answers a different question.

## Benchmark setup that worked

Daily model stack:
- provider: `openai-codex`
- model: `gpt-5.5`
- reasoning efforts tested separately: `low`, `medium`

Mini-only Hermes config shape:

```yaml
model:
  provider: openai-codex
  default: gpt-5.5
agent:
  max_turns: 60
  coding_context: off
  reasoning_effort: low   # or medium in a separate run
  tool_use_enforcement: true
terminal:
  backend: local
  cwd: .
```

Run with a lean explicit tool surface, e.g. `-t terminal,file,todo`, and a mini-swe-style workflow prompt: inspect, reproduce with tests, edit minimally, rerun tests, check edge cases, summarize files/commands.

Use temp `HERMES_HOME`s and disposable copies of task repos. Copy only `auth.json` into temp homes for authenticated provider access; do not mutate the user's real Hermes config/session state.

## Observed results on three small Python bugfix repos

All variants passed 3/3. Mini-only preserved repair quality and reduced cost/latency.

### Low reasoning

| Variant | Pass | Avg input toks | Avg output toks | Avg reasoning toks | Avg API calls | Avg tool calls | Avg wall |
|---|---:|---:|---:|---:|---:|---:|---:|
| focus low | 3/3 | 239,789 | 1,378 | 238 | 12.7 | 17.0 | 84.2s |
| mini-only low | 3/3 | 36,252 | 974 | 35 | 7.0 | 9.0 | 51.9s |

Approximate savings for mini-only low: ~85% lower input tokens, ~29% lower output tokens, ~85% lower reasoning tokens, ~45% fewer API calls, ~47% fewer tool calls, ~38% lower wall time.

### Medium reasoning

| Variant | Pass | Avg input toks | Avg output toks | Avg reasoning toks | Avg API calls | Avg tool calls | Avg wall |
|---|---:|---:|---:|---:|---:|---:|---:|
| focus medium | 3/3 | 260,635 | 2,149 | 836 | 14.0 | 17.3 | 102.1s |
| mini-only medium | 3/3 | 51,923 | 1,337 | 297 | 8.7 | 10.3 | 63.0s |

Approximate savings for mini-only medium: ~80% lower input tokens, ~38% lower output tokens, ~64% lower reasoning tokens, ~38% fewer API calls, ~40% fewer tool calls, ~38% lower wall time.

## Quality notes

Mini-only preserved the quality signals the user cared about:
- ran/reproduced failures before or during fix;
- reran pytest after edit;
- checked edge cases beyond the provided tests;
- generally changed only source files.

Hermes focus also solved the tasks, but sometimes touched tests unnecessarily in this sample (`test_config_merge.py`, `test_slugify.py`). Mini-only changed only source files across low/medium runs.

## Practical recommendation

For routine issue repair where the user wants low cost while preserving quality:

```yaml
agent:
  coding_context: off
  reasoning_effort: low
```

Use lean explicit tools plus the mini-style repair prompt. Escalate to `medium` only when low fails, the repo is larger/ambiguous, or the bug genuinely needs deeper reasoning.

## Pitfalls from the session

- If the user asks to optimize harness cost, do not switch providers/models or introduce alternate models unless explicitly requested.
- If the user says "mini vs focus", test `mini_only` vs `focus_plain`; `focus + mini overlay` is a different, predictably more expensive condition.
- Treat pass rate as a gate, not the objective, when all variants solve. The deciding metrics are token usage, API/tool calls, wall time, changed-file cleanliness, and verification discipline.
