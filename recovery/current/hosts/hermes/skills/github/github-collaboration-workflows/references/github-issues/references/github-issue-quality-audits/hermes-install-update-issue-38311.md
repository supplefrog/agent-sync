# Hermes install/update issue audit example: #38311

Session pattern worth reusing:

- User asked to audit an existing GitHub issue and delete/recreate it only if Codex did a poor job.
- `gh` was unavailable, so REST API read-only calls were enough to fetch issue metadata/body/comments/events/labels and search duplicates.
- The issue was kept because it was actionable: environment, logs, workaround, expected behavior, and maintenance asks were all present.
- Source inspection strengthened the audit:
  - installer/update paths had npm install surfaces where native Node modules can fail;
  - openSUSE/browser dependency guidance existed, but native Node build-tool preflight was not clearly covered;
  - Python venv/dependency sync behavior made stale/missing `PyYAML` plausible;
  - `PyYAML`/`yaml` imports existed on early/core paths.
- Related issues were not duplicates when platform/root-cause differed.
- Recommended labels were reported but not applied because no authenticated GitHub token/`gh` was available.

Reusable judgment:

Keep and label an issue when the report is specific, reproducible enough, and points at plausible code surfaces. Prefer edit-in-place over delete/recreate unless the report is misleading or unrecoverable.
