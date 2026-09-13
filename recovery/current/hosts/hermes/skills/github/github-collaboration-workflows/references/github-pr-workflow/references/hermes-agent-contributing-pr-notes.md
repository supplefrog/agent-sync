# Hermes Agent compressed contributing notes

Use for `NousResearch/hermes-agent` PRs before reading the full `CONTRIBUTING.md`. Refresh from the live file when this reference is missing, clearly stale, or the PR touches areas not covered here.

## PR discipline

- Search before building: issues plus all-state PRs with symptom, approach, and touched-path terms.
- Search source too; tracker can lag code.
- If an open PR already addresses the issue, prefer review/improvement over a competing PR. Close your duplicate if a better one appears.
- For larger work, comment on the issue before starting so others do not duplicate effort.
- Keep PRs focused: one logical bug/fix per PR, no unrelated cleanup.
- Use Conventional Commits: `fix(scope): summary`, `feat(scope): summary`, etc.
- PR body should state what changed, why, how to test, tested platform, and related issue.
- Do not check PR-template boxes for steps not actually done. If using a targeted alternative to a template item, leave the generic box unchecked and explain the actual check run.

## Verification

- Hermes-wide Python changes: prefer `scripts/run_tests.sh` because it matches CI's hermetic runner.
- Desktop-only TypeScript/Electron changes: targeted `npm --prefix apps/desktop ...` checks are acceptable and cheaper; include exact commands/results.
- Add regression tests for bug fixes. Prefer extending an existing subsystem test harness unless a new focused harness gives materially better coverage.
- Manual repro/platform testing matters for UI timing bugs; include the tested OS.
- CI can skip irrelevant areas. Read required-check status, not just one failed optional build.

## Cross-platform reminders

- Hermes supports native Windows, Linux, macOS, and WSL2. If code touches OS/files/processes/shell, check cross-platform implications.
- Run/consider `scripts/check-windows-footguns.py` for OS/process/path changes.
- Avoid POSIX-only assumptions in Python paths/processes/signals; use `pathlib`, `psutil`, `shutil.which`, and explicit Python invocation.
- Windows tests that use `patch.dict(os.environ, ..., clear=True)` and reach `get_hermes_home()` must provide `HERMES_HOME` or `LOCALAPPDATA`; `HOME` alone is not sufficient on Windows and `Path.home()` can fail.

## Architecture/style reminders

- Bug fixes and cross-platform compatibility are top contribution priorities.
- Prefer skills/plugins/config over new core tools or new user-facing env vars.
- Comments should explain non-obvious tradeoffs, not narrate obvious code.
- New behavioral config belongs in `config.yaml`; `.env` is for secrets.
