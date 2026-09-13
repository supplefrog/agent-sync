# Semantic merge checklist

## Before editing

- Read `AGENTS.md` in the target worktree and its repository parent.
- Record target HEAD, source HEAD, merge base, and `git status --short --branch`.
- Save the conflict list: `git diff --name-only --diff-filter=U`.

## Per conflicted file

1. Read the working hunk and surrounding callers.
2. Compare `git show :2:path` (target) and `git show :3:path` (incoming).
3. Search each newly referenced symbol, field, status, and helper in the target tree.
4. Inspect schema declarations plus additive migration and drift-rebuild code together.
5. Resolve by invariant and production path, not by side preference.

## Verification sequence

```text
python -m py_compile <affected production modules>
python -m pytest -q <direct regression tests> <nearby subsystem tests>
git grep -n -E '^(<<<<<<<|=======|>>>>>>>)' -- <resolved files>
git diff --check
```

For persistence/lifecycle work, include:

- a normal transition and durable read-back;
- a protected/refusal case;
- stale, late, or duplicate callback behavior;
- reload/migration behavior when schema or ownership state changed.

For moved tests, place coverage beside the current subsystem layout and preserve the original behavioral matrix rather than the old path name.

## Completion rule

Only report ready when the targeted tests pass, the conflict index is resolved, no markers remain, and the diff is scoped. If tests fail, report the real blocker and do not label the merge verified.
