# Mini-only vs focus Hermes benchmark

Session learning: when optimizing Hermes model routing for cost while preserving quality, compare the missing variant only and reuse previous results.

## Benchmark shape

A useful small repair suite used:

- 3 deterministic Python bug-fix tasks:
  - size parser
  - config merge
  - slugify/unicode normalization
- Each task had tests runnable with `pytest -q`.
- Each variant ran in an isolated task copy and isolated `HERMES_HOME`.
- The harness wrote one JSON object per task to `summary.jsonl` with:
  - `variant`, `reasoning`, `task`, `passed`, `pytest_summary`
  - elapsed seconds
  - changed files from git diff
  - token/API/tool usage queried from the run home `state.db`
  - stdout/stderr tails for quick sanity checks

## Useful harness details

The mini-only variant used:

```yaml
model:
  provider: openai-codex
  default: gpt-5.5
agent:
  max_turns: 60
  coding_context: off
  reasoning_effort: low|medium
  tool_use_enforcement: true
terminal:
  backend: local
  cwd: .
display:
  show_cost: true
```

Invocation pattern:

```bash
cd "$task_dir"
HERMES_HOME="$run_home" HERMES_DISABLE_UPDATE_CHECK=1 \
  hermes chat -q "$prompt" -t terminal,file,todo -Q --yolo \
  >"$results/${variant}_${task}.stdout.txt" \
  2>"$results/${variant}_${task}.stderr.txt"

python -m pytest -q >"$results/${variant}_${task}_pytest.txt" 2>&1 || true
git diff -- . >"$results/${variant}_${task}.diff" || true
```

Usage extraction queried latest session fields from the run home `state.db`:

```sql
select input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
       reasoning_tokens, api_call_count, message_count, tool_call_count
from sessions
order by started_at desc
limit 1;
```

## Observed lesson from the run

On the 3-task deterministic repair suite, mini-only preserved solve rate while greatly reducing token use:

| Variant | Reasoning | Solve rate | Input | Cache read | Output | Reasoning tokens | API calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| mini_only | low | 3/3 | 108,757 | 32,256 | 2,923 | 106 | 21 |
| mini_only | medium | 3/3 | 155,768 | 29,184 | 4,011 | 892 | 26 |
| focus_plain | medium | 3/3 | 781,906 | 96,768 | 6,448 | 2,509 | 42 |
| focus_mini_overlay | medium | 3/3 | 857,435 | 166,400 | 7,169 | 1,945 | 49 |

Interpretation for this task class:

- `mini_only low` was the best cost/quality setting on this suite.
- Adding a mini workflow overlay on top of `coding_context: focus` increased token/API usage without improving solve rate.
- Do not generalize this to all tasks; rerun with harder tasks before changing broad defaults.

## Reporting pattern

Keep the final answer compact:

1. State the run location.
2. Show a table of the newly tested variant.
3. Show only the relevant previous comparison rows.
4. Give a direct recommendation and caveat.

Avoid overexplaining solve-rate basics when the user already says they know the solve-rate tradeoff; focus on cost deltas and whether quality was preserved.
