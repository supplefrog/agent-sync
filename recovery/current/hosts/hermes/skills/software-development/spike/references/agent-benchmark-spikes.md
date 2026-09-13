# Agent benchmark spikes: disposable, verifiable harnesses

Use this reference when comparing two or more coding agents on small SWE-style tasks without mutating the user's real environment.

## Isolation pattern

- Create one timestamped temp workspace outside any user repo.
- Put golden task repos under `tasks/` and copy them into `runs/<agent>_<task>/` before each run.
- Give each agent its own temp home/config/cache directory where supported.
- Keep credentials read-only; do not write provider config into the user's normal home.
- Never score against the golden task repo. Score only copied run dirs.

Suggested layout:

```text
/tmp/agent-bench-YYYYMMDD-HHMMSS/
  tasks/<task-name>/           # pristine failing repo fixtures
  runs/<agent>_<task>/         # disposable mutated copies
  runs/results/                # stdout, stderr, diffs, pytest output, JSONL summary
  homes/<agent>_<task>/        # isolated agent home/config where possible
  caches/                      # pip/uv/provider caches where practical
  venvs/                       # throwaway tool installs
```

## Task fixture shape

Each task should be a tiny repo with:

- one source file with a realistic bug;
- one test file that fails before the fix;
- a `TASK.md` with the problem statement and verification command;
- an initial git commit so `git diff` captures only the agent's changes.

Verify every fixture fails before running agents. If tests do not fail initially, the benchmark is invalid.

## Scoring rules

Do not trust agent self-reports. After each run, independently execute the verification command in the run copy and save:

- pytest/test output;
- `git diff -- .`;
- agent stdout/stderr or trajectory;
- elapsed time, exit code, model/provider, and API-call count if available.

Pitfall: do not score with substring checks like `"passed" in output`; `"1 failed, 2 passed"` is not success. Treat success as a clean test summary with no `failed`, `error`, or nonzero verification exit.

## Interpreting results

A failed first pass is often a harness/model sanity signal, not a final agent comparison. Separate:

- agent/harness failure: could not run CLI, wrong shell, temp-home leakage;
- model failure: ignores tool calls, submits without edits, fabricates test output;
- tooling failure: patch tool wrote malformed content, wrong file path, command hung;
- benchmark failure: fixture too ambiguous or scoring bug.

If both agents fail simple tasks with the same weak model, rerun with a coding-capable model before drawing conclusions about prompts or tool design.

## Reporting

Report the temp workspace path, exact models/providers, isolation measures, tasks, independent test results, and notable failure modes. Say when the result is only a harness/model sanity check.