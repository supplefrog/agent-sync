# Agent harness benchmarking notes

Use this reference when benchmarking agent scaffolds, prompt overlays, or task harnesses (e.g. Hermes `agent.coding_context=focus` vs a mini-swe-style issue-repair overlay).

## Keep the evaluation axis fixed

If the question is about the harness, do **not** vary model/provider at the same time. Use the user's daily-driver model and reasoning setting unless the user explicitly asks for model comparison.

Bad comparison:
- mini-swe-agent + model A vs Hermes + model B

Better comparison:
- Hermes focus plain vs Hermes focus + overlay, both on the same model/provider/reasoning effort
- If mini-swe itself must be included, label model/provider differences as a confounder and do not overinterpret scaffold results.

## Recommended matrix for Hermes issue-repair harnesses

Choose the matrix from the user's actual question.

If the question is **cost while preserving quality**, compare the lean harness directly against focus:

| Variant | Purpose |
|---|---|
| `focus_plain` | Hermes built-in coding posture baseline |
| `mini_only` | Hermes surface, `agent.coding_context=off`, lean explicit tools, mini-swe-style issue-repair prompt |

If the question is **whether a workflow overlay improves focus behavior**, use:

| Variant | Purpose |
|---|---|
| `focus_plain` | Hermes built-in coding posture baseline |
| `focus_overlay` | Same model + Hermes focus + candidate workflow overlay |

Optional:

| Variant | Purpose |
|---|---|
| `auto_plain` | User's normal non-focus Hermes behavior |
| `mini_swe` | External reference harness; only fair if same/near-same model can be used |

Hold constant:
- provider/model
- reasoning effort (`low`, `medium`, etc.; run `low` and `medium` as separate matrices)
- task repos
- max turns
- tool surface unless the harness being tested intentionally changes tools

## Isolation pattern

Use disposable repos and temp Hermes homes:

```bash
BENCH=/tmp/hermes-harness-bench-$(date +%Y%m%d-%H%M%S)
mkdir -p "$BENCH"/{tasks,runs,homes}

# For authenticated provider runs, copy only auth, not the real config/session state.
mkdir -p "$BENCH/homes/run1"
cp "$HERMES_HOME/auth.json" "$BENCH/homes/run1/auth.json"
cat > "$BENCH/homes/run1/config.yaml" <<'EOF'
model:
  provider: openai-codex
  default: gpt-5.5
agent:
  coding_context: focus
  reasoning_effort: low
  tool_use_enforcement: true
terminal:
  backend: local
  cwd: .
EOF

(cd "$BENCH/runs/task1" && HERMES_HOME="$BENCH/homes/run1" hermes chat -q "$PROMPT" -Q --yolo)
```

Do not mutate the user's real repo, real `config.yaml`, real sessions, or real skills while running the benchmark.

## Metrics to capture

Score final repos by actually running tests after the agent exits. Do not trust the model's final claim.

Collect:
- pass/fail from real test command
- wall time
- changed files (`git diff --name-only`)
- whether tests were run before edit
- whether tests were run after edit
- edge-case checks beyond existing tests
- final handoff quality
- input/output/reasoning/cache tokens
- API call count and tool call count

Hermes stores session usage in the temp home's `state.db`:

```sql
select input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
       reasoning_tokens, api_call_count, message_count, tool_call_count
from sessions
order by started_at desc
limit 1;
```

## Interpreting results

For small issue-repair tasks, a mini-swe-style overlay may not improve pass rate over Hermes focus. Look for process-quality changes:
- reproducibility: did it run failing tests first?
- cleanliness: did it avoid unnecessary test edits?
- verification: did it rerun focused/full tests after editing?
- edge coverage: did it check issue-implied cases?
- handoff: did it list commands and files accurately?

If all variants pass, report the tradeoff instead of declaring a winner. The overlay may be valuable because it buys discipline at the cost of more tokens/tool calls/wall time.

## Pitfalls

- Do not let provider/model differences masquerade as harness differences.
- Do not treat transient 429/network failures as scaffold failures; rerun or mark as infrastructure noise.
- If the user asks for daily-driver comparison, use their daily model first. Only add alternate providers/models if explicitly requested.
- If the user asks to optimize cost while preserving quality, make token/API/tool-call metrics first-class outputs; pass rate is only a gate when all variants solve.
- If the user says “mini vs focus”, compare `mini_only` against `focus_plain`. `focus + mini overlay` is useful for overlay-discipline experiments but is predictably more expensive and not the right cost comparison.
- For reasoning-effort experiments, run separate matrices for `low` and `medium`; do not mix them in the same row.

## Session references

- `references/mini-only-vs-focus-cost-benchmark.md` — Hermes GPT-5.5/openai-codex `mini_only` vs `focus_plain` low/medium benchmark summary, including token/call/wall-time deltas and quality notes.