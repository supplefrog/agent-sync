# Recoverable task closeout

Use this helper only for files with evidence of exclusive task ownership. Prefer the existing project's artifact tracking if it has one. It does not scan the workspace or infer stale status, ownership, references, completed work or permissions. The agent decides those first. Use distinct task IDs and scratch paths for concurrent work; never register a shared/current deliverable as scratch.

```text
python <skill-dir>/scripts/task_artifacts.py register --root <project> --task <id> --file <relative-file> --kind scratch --reason <ownership-and-stale-reason>
python <skill-dir>/scripts/task_artifacts.py register --root <project> --task <id> --file <deliverable> --kind keep --reason <retention-reason>
python <skill-dir>/scripts/task_artifacts.py plan --root <project> --task <id>
python <skill-dir>/scripts/task_artifacts.py archive --root <project> --task <id> --apply --references-checked
python <skill-dir>/scripts/task_artifacts.py restore --root <project> --task <id> --apply
```

Repeat `--file` for an explicit list of regular files. No recursive folder registration or purge exists. `archive`/`restore` without `--apply` preview only; registration writes the ownership record. The `--references-checked` flag records that the caller checked completion, references and active users; it is not evidence or user approval by itself.

Records live at `<project>/.task-artifacts/<id>.json`. Recovery copies live at `.task-artifacts/recovery/<id>/<original-relative-path>`. The helper verifies hashes, uses exclusive recovery creation, records intent before removing the original, and retains backup bytes on failure. Retry an interrupted archive using the same task/record after inspecting source and recovery state; never re-register to hide changed content. Restore refuses to replace changed files and retains recovery copies. Keep this local recovery/ownership area out of publication and link its exact record from the handoff. For a Git project, use the project's existing ignore policy or a task-scoped local Git exclude; do not silently publish recovery or create a global exclusion.

A project-wide operation lock serializes cooperating helpers. Registration rejects paths already claimed by another task. A killed process can leave `operation.lock`; inspect its PID and unfinished journal before removing that exact stale lock. Never remove a lock whose owner is still active. Non-cooperating editors can race between the last file check and unlink; exclusive task ownership and pausing other writers on those exact files are preconditions, not guarantees the helper can manufacture. Links, junctions, traversal, control paths and destination collisions are refused. Empty source directories are left in place; remove only verified empty task-created directories with native tools.

Archive is reversible removal from the working area. Purging its recovery bytes or deleting native chat history requires action-time authorization and lies outside this helper. A local recovery copy is not a backup against disk loss.
