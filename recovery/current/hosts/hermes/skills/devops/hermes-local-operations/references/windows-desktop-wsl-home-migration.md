# Windows Desktop migration from an existing WSL Hermes home

Use when the user already has a working Hermes TUI/state in WSL and wants Hermes Desktop on Windows to use that state rather than completing a fresh provider setup.

## Operator stance

If the user asks for migration, do the migration. Do not hand them long copy/paste blocks unless a destructive approval gate or missing access requires it. First inspect source and target, make backups, then copy and verify.

## Discovery

Identify the WSL source and Windows Desktop target:

```bash
hermes config path
hermes config env-path
hermes profile list

# Common locations seen on Windows + WSL installs
/root/.hermes
/home/<wsl-user>/.hermes
/mnt/c/Users/<WinUser>/AppData/Local/hermes
```

Check which contains the real state:

```bash
for d in /root/.hermes /home/*/.hermes /mnt/c/Users/*/AppData/Local/hermes; do
  [ -d "$d" ] || continue
  echo "-- $d"
  test -f "$d/config.yaml" && echo config=yes || echo config=no
  test -f "$d/.env" && echo env=yes || echo env=no
  test -f "$d/auth.json" && echo auth=yes || echo auth=no
  test -f "$d/state.db" && ls -lh "$d/state.db"
  test -d "$d/profiles" && find "$d/profiles" -mindepth 1 -maxdepth 1 -type d | sed 's#.*/##' | sort | paste -sd, -
  test -d "$d/skills" && find "$d/skills" -type f | wc -l
 done
```

## Backup before migration

Create a timestamped backup directory outside the live Hermes home. At minimum, preserve both source and target critical files:

```bash
stamp=$(date +%Y%m%d-%H%M%S)
backup=/mnt/c/Users/<WinUser>/AppData/Local/hermes-migration-backups/$stamp
mkdir -p "$backup/source-critical" "$backup/target-critical"

cp -a /path/to/source/.hermes/{config.yaml,.env,auth.json,state.db,SOUL.md,skills,memories,profiles,cron,plugins,hooks,scripts} "$backup/source-critical/" 2>/dev/null || true
cp -a /mnt/c/Users/<WinUser>/AppData/Local/hermes/{config.yaml,.env,auth.json,state.db,SOUL.md,skills,memories,profiles,cron} "$backup/target-critical/" 2>/dev/null || true
```

## Copy pattern

Prefer merging state/config into the Windows Desktop home while preserving Desktop app payload files such as `hermes-agent`, `hermes-setup.exe`, and desktop build metadata. Exclude caches, sandboxes, transient locks, WAL/SHM, and active process files:

```bash
tar -C /path/to/source/.hermes \
  --exclude='./cache' --exclude='./audio_cache' --exclude='./image_cache' --exclude='./sandboxes' \
  --exclude='./state.db-shm' --exclude='./state.db-wal' --exclude='./auth.lock' \
  --exclude='./processes.json' --exclude='./logs/*.log' \
  -cf - . | tar --overwrite -C /mnt/c/Users/<WinUser>/AppData/Local/hermes -xf -
```

If `state.db` is locked by the currently running Desktop process, stage it instead:

```bash
cp -f /path/to/source/.hermes/state.db /mnt/c/Users/<WinUser>/AppData/Local/hermes/state.db.from-wsl-migration
```

Then install a tiny Windows-side finalizer that waits for the Desktop DB lock to release, backs up current `state.db`, swaps in the staged DB, and removes `state.db-wal` / `state.db-shm`. This lets the user close Desktop normally instead of forcing the process down mid-conversation.

## Verification

Verify hashes for critical text/config/auth files and staged DB:

```bash
sha256sum /path/to/source/.hermes/config.yaml /mnt/c/Users/<WinUser>/AppData/Local/hermes/config.yaml
sha256sum /path/to/source/.hermes/.env /mnt/c/Users/<WinUser>/AppData/Local/hermes/.env
sha256sum /path/to/source/.hermes/auth.json /mnt/c/Users/<WinUser>/AppData/Local/hermes/auth.json
sha256sum /path/to/source/.hermes/SOUL.md /mnt/c/Users/<WinUser>/AppData/Local/hermes/SOUL.md
sha256sum /path/to/source/.hermes/state.db /mnt/c/Users/<WinUser>/AppData/Local/hermes/state.db.from-wsl-migration
```

Report exactly what was copied, what was staged because of a live lock, where backups are, and whether the user must close/reopen Desktop to finish the DB swap.

## Pitfalls

- Do not point Desktop at a live WSL `~/.hermes` over `\\wsl$` as the first recommendation; SQLite locks, permissions, and Linux-vs-Windows paths are fragile. Prefer one-time copy into the Windows Desktop home when Desktop is the desired UI.
- Do not complete a fresh provider wizard before checking whether Desktop is simply reading an empty Windows Hermes home.
- Do not delete/replace the entire Windows Desktop home blindly; it can contain app payload files that are not part of WSL `~/.hermes`.
- Avoid copying cache/sandbox/log/WAL/SHM files.
- If the user is frustrated with instructions, switch to action mode immediately: inspect, back up, migrate, verify, and keep the final summary short.
