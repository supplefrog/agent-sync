# Public-safe recovery

Agent Sync backs up the declarative state needed to rebuild the current Hermes, Codex, and OMP setup without copying an agent home.

## Fast restore

From a clone outside live skill-discovery directories, select the agent you want:

```bash
python tools/recovery.py verify
python tools/recovery.py bootstrap --host hermes          # dry-run
python tools/recovery.py bootstrap --host hermes --apply  # selected target + postflight
```

Use `--host codex` or `--host omp` for the other supported agents. Supply `--root HOST=PATH` to select an explicit target home rather than the platform default. Selecting a host scopes live reads, writes, skill destinations, and native prerequisite/readback checks; it does not select a model provider. The whole public snapshot is still integrity-checked before selecting effects.

Omitting `--host` retains the original full configured-machine recovery. Use that only when all declared hosts and shared skill destinations are intended. A friend's install should use bootstrap, not the source-publishing reconciliation command.

`bootstrap` performs preflight, renders the admitted fleet, rejects skill collisions or instruction conflicts, applies admitted skills and allowlisted state, then verifies the fleet, recovery diff, and typed host-delta readback. Selected-host mode checks required native prerequisites before target writes and skips the global multi-host instruction profile; full-machine mode retains that check. It does not install runtimes or authenticate accounts; install only the selected runtime and its declared prerequisites locally.

Before fleet apply, bootstrap also rejects a retired skill or an admitted skill that still exists in a host-local discovery root. Remove a retired artifact or migrate an admitted old copy first; otherwise a stale implementation can return or Hermes/Codex/OMP can see two owners for the same skill name even when their bytes happen to match.

Existing instruction or hook files are never replaced silently. A differing text file is a conflict. `--force-text` is an explicit operator decision after reviewing the diff.

## What is stored

`recovery.json` is the allowlist. `recovery/current/manifest.json` binds every committed artifact to its target, strategy, byte count, SHA-256 digest, and policy digest. `host-deltas.json`, validated by `contracts/host-deltas.schema.json`, is the typed inventory of intentional native differences and recovery outcomes.

The current snapshot contains:

- selected behavior, model, tool, display, safety, routing, retention, and context/compression settings, including the native LCM threshold;
- Hermes `SOUL.md` and Codex `AGENTS.md`;
- user-authored Codex hook scripts and their hook declarations;
- custom MCP declarations that contain no credential values, including OMP MCP declarations;
- public plugin selections and enablement where the source is reproducible or an external prerequisite is declared;
- complete reviewed Hermes-local [native skill packages](native-skill-recovery.md), with support files and parked-package enablement preserved separately;
- the two thin OMP skill adapters that consume Agent Sync's canonical workflow owners without copying their state machines;
- no OMP `RULES.md`, because OMP already inherits the same Codex output rule and the duplicate delta was retired.

Config restore is a deep merge. Only allowlisted paths are written, while unknown or sensitive fields already present on the target remain untouched. If selected values already match, restore does not rewrite the file merely to normalize TOML/YAML formatting.

Portable path markers use `{{agent-signal:HOME}}`, `{{agent-signal:HERMES_HOME}}`, `{{agent-signal:CODEX_HOME}}`, `{{agent-signal:OMP_HOME}}`, and `{{agent-signal:AGENT_SIGNAL_ROOT}}`. They are intentionally distinct from shell variables such as `${HOME}`, so source code and hook patterns are not rewritten accidentally.

Codex Desktop's `notify` executable is not portable declarative state: its path contains a generated runtime-cache build identifier. It is excluded from capture and the receiving Desktop installation owns it. Restore leaves any existing target notification setting untouched.

Each host-delta entry records its host, surface, owner, desired state, source identity, version or artifact hash, enablement, external prerequisites, restore method, redaction policy, and deterministic readback. Command readbacks are selected from a fixed Agent Sync allowlist; the manifest cannot introduce executable argv. Fleet binding is derived from tracked `registry.json` plus admitted canonical skill trees, so a fresh clone does not need generated `render/` output before host-delta validation. `python tools/host_deltas.py verify` validates the schema, checks recovery/fleet bindings, and emits one of these statuses:

- `restored` — this run wrote the allowlisted state and readback succeeded;
- `verified` — state already matched and readback succeeded;
- `prerequisite-missing` — the public manifest is complete but a required external runtime/source is absent;
- `excluded-private` — the state is deliberately outside the public contract; or
- `failed` — required recoverable state did not pass readback.

## What is deliberately excluded

The snapshot never includes:

- API keys, OAuth tokens, passwords, cookies, credentials, connection secrets, or authorization headers;
- `.env`, auth stores, keyrings, pairing state, or channel/user identifiers;
- memories, profiles about the user, transcripts, sessions, conversation databases, or histories;
- logs, caches, package/runtime binaries, native pipes, generated plugin runtime environments, and volatile build hashes;
- unreproducible local marketplace/plugin source trees; public enablement may be recorded only when its source identity and prerequisite are explicit;
- generated `render/`, worktrees, test caches, raw evaluation runs, or backup copies;
- project-local instruction files, which stay owned by their project and are only discovered dynamically.

Secret-like values, absolute user-home paths, blocked filenames, path traversal, and unreviewed symlink/reparse-point crossings fail capture. Exact content-bound public example reviews and explicitly declared read-only `capture_mount` entries are the narrow exceptions; neither grants restore writes through a link.

## Updating the reviewed snapshot

A snapshot imports live state into the repository and is therefore an explicit review action, not a background sync:

```bash
python tools/recovery.py snapshot
python tools/recovery.py verify
python tools/recovery.py diff
python tools/public_check.py

git diff -- recovery.json recovery/current contracts/recovery*.json
```

`diff` must report no changes and no conflicts against the source machine after capture. The manifest is written last, stale files are removed only from its previous managed inventory, and no persistent backup directory is created. When capture runs through `python tools/reconcile.py sync --capture-recovery`, the recovery snapshot and every host-delta recovery-artifact binding are refreshed and validated in the same transaction.

## Restore safety

- Dry-run is the default.
- All config and text conflicts are preflighted before the first mutation.
- Each file write is atomic.
- If a later target-file write fails, the file-restore phase rolls back every earlier target it changed.
- Config restore preserves non-allowlisted state.
- Text restore accepts an absent target, an equal target, or an exact reviewed stock-text `replace_sha256`; unrelated differences remain conflicts.
- Fleet apply rejects unmanaged same-name collisions and modified managed skills.
- Reconciliation rollback covers every fleet action selected by preflight, including removal of a previously managed skill whose canonical owner was retired.
- Postflight requires zero recovery changes/conflicts, an exact fleet manifest, a valid current instruction profile, and successful required host-delta readback.

The file-restore phase is rollback-safe, but `bootstrap --apply` composes fleet apply and recovery apply rather than pretending the two independent subsystems are one disk transaction. Its preflight and postflight fail closed, and re-running it is idempotent after interruption. A full machine recovery still requires runtime installation, authentication, and any declared native prerequisites. No credentials, private memory, sessions, or provider-hidden state can be reconstructed from this public repository.
