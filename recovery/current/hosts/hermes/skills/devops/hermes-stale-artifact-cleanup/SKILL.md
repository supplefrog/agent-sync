---
name: hermes-stale-artifact-cleanup
description: Clear old Hermes-generated backups, snapshots, stashes, and derived cache artifacts after the user says the related tasks are complete or asks to remove old backups/artifacts. Use this for cleanup prompts, but inspect and list candidates first because deletion is irreversible.
---

# Hermes stale artifact cleanup

Use when the user asks to remove old backups/artifacts from a local Hermes install after work is verified.

## Workflow

1. Confirm the Hermes home with `hermes config path`.
2. List candidates first; do not scan/delete package source files whose names merely contain “backup”.
3. Establish settlement before treating age or a filename as deletion proof:
   - Inspect later promotion/completion receipts, not only a receipt copied into an old backup.
   - For curator blobs/archives, compare content first, then review nonmatching instructions/code against current owners. Different hashes do not prove useful omissions. Delete only the reviewed set; newly generated blobs remain outside that set.
   - For update autostashes, inspect the patch and current upstream, then check the user's PRs and overlapping proposals before dropping unique work. These contain pre-update local edits, not full installation backups. The user's preference is upstream fixes rather than persistent local Hermes source patches; do not restore an old stash during cleanup. Passing historical tests alone does not establish net benefit or current applicability.
   - Keep conversation-bearing state/transcripts separate from disposable rollback artifacts unless their deletion is explicitly authorized.
4. Safe generated-artifact classes to consider when the user says they are no longer needed:
   - `state.db.bak-*`, `*.bak-before-*`, `*.backup-before-*`
   - `state-snapshots/`
   - `profiles/*/skills.backup-before-profile-sync-*`
   - `skills/.curator_backups`, `profiles/*/skills/.curator_backups`
   - derived plugin caches such as `plugins/hermes-achievements/scan_snapshot.json` and `scan_checkpoint.json` **only if** the user wants stale deleted-session references gone. These caches can preserve the last visible achievement dashboard snapshot; deleting them can force a rescan that reflects any deleted sessions.
   - old `git stash` entries in `hermes-agent` only after `git stash show --stat` and a short patch preview prove they are obsolete
5. Delete only the reviewed generated artifacts. Do not delete source files, venv package data, node_modules assets, or active config/state files. Reject symlink/junction traversal; on Python 3.11 Windows use `lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT`, not the unavailable `Path.is_junction()`.
6. Verify the exact reviewed targets are absent and protected targets remain; report freed bytes and explicit retained exceptions. Do not claim all backups are gone when newer or unreviewed artifacts remain.

## Candidate list command

```bash
python - <<'PY'
from pathlib import Path
home=Path(r'{{agent-signal:HERMES_HOME}}')
items=[]
for p in home.rglob('*'):
    if 'hermes-agent' in p.parts:  # avoid source/venv/node_modules false positives
        continue
    n=p.name.lower()
    if any(k in n for k in ['bak-before','backup-before','.bak','state-snapshots']) or n == '.curator_backups':
        if p.exists():
            size=sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) if p.is_dir() else p.stat().st_size
            items.append((str(p), 'dir' if p.is_dir() else 'file', size))
for path,kind,size in sorted(items): print(f'{kind}\t{size}\t{path}')
print('count', len(items), 'bytes', sum(x[2] for x in items))
PY
```

## Guardrails

- For broad cleanup, list first, then delete reviewed candidates.
- Do not remove active `state.db`, `config.yaml`, `.env`, `auth.json`, `skills/`, or profile directories.
- For git stashes, inspect before dropping; drop newest-first only after deciding they are obsolete.
