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

Exact native recovery also supports repeated `--artifact HOST:ID` on `snapshot`, `diff`, and `restore`. Each identity must already exist in the reviewed policy; empty, duplicate, wildcard, and path selections fail. Only selected host roots are required. Scoped capture first verifies the entire existing snapshot and preserves unselected records and content; it cannot create a sparse initial snapshot. Full capture and restore remain the default.

## What is stored

`recovery.json` is the allowlist. `recovery/current/manifest.json` binds every committed artifact to its target, strategy, byte count, SHA-256 digest, and policy digest. `host-deltas.json`, validated by `contracts/host-deltas.schema.json`, is the typed inventory of intentional native differences and recovery outcomes.

The current snapshot contains:

- selected behavior, model, tool, display, safety, routing, retention, and context/compression settings, including the native LCM threshold;
- Hermes `SOUL.md` and Codex `AGENTS.md`;
- the independent Codex PreToolUse destructive-command guard and its declaration; deliberately retired GSD update hooks are excluded;
- custom MCP declarations that contain no credential values, including OMP MCP declarations;
- public plugin selections and enablement where the source is reproducible or an external prerequisite is declared;
- complete reviewed Hermes-local [native skill packages](native-skill-recovery.md), with support files and parked-package enablement preserved separately;
- the two thin OMP skill adapters that consume Agent Sync's canonical workflow owners without copying their state machines;
- OMP native `AGENTS.md` generated from the shared core, the checked reduced `SYSTEM_TEMPLATE.md`, request-description hook, and selected settings/provider transport fields. Stock OMP is restored from upstream; no stock binary, stock tool implementation, credentials, or private history are copied. Codex inheritance stays disabled; fresh OMP18.8.9 context and loopback-request checks load the shared core exactly once.

Config restore is a deep merge. Only allowlisted paths are written, while unknown or sensitive fields already present on the target remain untouched. If selected values already match, restore does not rewrite the file merely to normalize TOML/YAML formatting.

Portable path markers use `{{agent-signal:HOME}}`, `{{agent-signal:HERMES_HOME}}`, `{{agent-signal:CODEX_HOME}}`, `{{agent-signal:OMP_HOME}}`, and `{{agent-signal:AGENT_SIGNAL_ROOT}}`. They are intentionally distinct from shell variables such as `${HOME}`, so source code and hook patterns are not rewritten accidentally.

Codex Desktop's `notify` executable is not portable declarative state: its path contains a generated runtime-cache build identifier. It is excluded from capture and the receiving Desktop installation owns it. Restore leaves any existing target notification setting untouched.

Recovery-artifact host-delta bindings use the selected artifact digest rather than the aggregate snapshot-manifest digest. The existing verified legacy binding can migrate only while it still matches the current snapshot; stale bindings fail. Exact capture refreshes selected bindings while preserving unrelated entries.

Each host-delta entry records its host, surface, owner, desired state, source identity, version or artifact hash, enablement, external prerequisites, restore method, redaction policy, and deterministic readback. Command readbacks are selected from a fixed Agent Sync allowlist; the manifest cannot introduce executable argv. Fleet binding is derived from tracked `registry.json` plus admitted canonical skill trees, so a fresh clone does not need generated `render/` output before host-delta validation. `python tools/host_deltas.py verify` validates the schema, checks recovery/fleet bindings, and emits one of these statuses:

- `restored` â€” this run wrote the allowlisted state and readback succeeded;
- `verified` â€” state already matched and readback succeeded;
- `prerequisite-missing` â€” the public manifest is complete but a required external runtime/source is absent;
- `excluded-private` â€” the state is deliberately outside the public contract; or
- `failed` â€” required recoverable state did not pass readback.

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

For exact reviewed recovery, use repeated `--artifact HOST:ID` with `snapshot`, `diff`, or `restore`, and repeated `--capture-artifact HOST:ID` with `reconcile.py sync`. Scoped capture verifies the full existing snapshot first. It also accepts new policy artifact rows when every new identity is explicitly selected and removing those rows exactly reproduces the prior policy digest. Existing policy fields and artifact metadata must remain unchanged; removals and unselected additions fail. The resulting full snapshot is verified against the current policy before capture completes. Scoped capture cannot initialize a sparse snapshot. The corresponding selected `diff` must be clean; unrelated live drift can remain pending. Shared manifest or host-delta files with unrelated changed fields require explicit whole-file publication review and `--include`; artifact selection does not authorize those unrelated fields.

For full capture, `diff` must report no changes and no conflicts against the source machine after capture. The manifest is written last, stale files are removed only from its previous managed inventory, and no persistent backup directory is created. When capture runs through `python tools/reconcile.py sync --capture-recovery`, the recovery snapshot and every host-delta recovery-artifact binding are refreshed and validated in the same transaction.

## Restore safety

- Dry-run is the default.
- All config and text conflicts are preflighted before the first mutation.
- Each file write is atomic.
- Mutation holds cooperative OS path locks on the snapshot and selected roots, shared with fleet and reconciliation. Locks release on process death; they are not a compare-and-swap guarantee against arbitrary writers. Target identity is checked during preflight and immediately before each write.
- If a later target-file write fails, rollback restores only files whose identity and bytes still match this operation. Concurrent edits survive; incomplete rollback retains original bytes and conflict evidence in a reported temporary backup.
- Config restore preserves non-allowlisted state.
- Text restore accepts an absent target, an equal target, or an exact reviewed stock-text `replace_sha256`; unrelated differences remain conflicts.
- Fleet apply rejects unmanaged same-name collisions and modified managed skills.
- Reconciliation rollback covers every fleet action selected by preflight, including removal of a previously managed skill whose canonical owner was retired.
- Postflight requires zero recovery changes/conflicts, an exact fleet manifest, a valid current instruction profile, and successful required host-delta readback.

The file-restore phase is rollback-safe, but `bootstrap --apply` composes fleet apply and recovery apply rather than pretending the two independent subsystems are one disk transaction. Its preflight and postflight fail closed, and re-running it is idempotent after interruption. A full machine recovery still requires runtime installation, authentication, and any declared native prerequisites. No credentials, private memory, sessions, or provider-hidden state can be reconstructed from this public repository.


### OMP reduction compatibility on upgrade

The reduced context uses supported system-template, before_agent_start and before_provider_request seams. When upgrading OMP or changing the provider transport, verify an actual private request capture with `bun tools/check_omp_reduction.ts <capture.json>` (or Node 24 with TypeScript stripping). The checker performs no inference and prints only a verdict; a changed contract requires inspection, not silent acceptance. Use a loopback-only dummy-provider assembly check when no model run is needed. `get_state` alone does not establish request-description or footer-hook behavior. Keep captures private; the tool does not log prompt or account data. No per-turn compatibility audit or reviewer swarm is added.


## Published partial rollout and a reviewed successor

An already-published rollout may be blocked by intentional local authoring. Repeating
publication, deleting its journal or using predeployment release cannot resolve it.
The normal `reconcile.py sync --ready COMMIT` route may take an explicit
`--continue-published REQUEST.json` only after the successor has passed ordinary
source/adoption/publication checks and the continuation action is authorized.

The bounded request binds schema_version1, old attempt, exact raw journal SHA256,
published_commit, successor_ready, canonical successor-options SHA256 and every
old configured target's current managed-state/content fingerprint. It is private
operational evidence, not a public release artifact or authorization credential.
The coordinator rechecks these under its existing single-writer lock, requires
clean owned worktrees, an exact remote and settled actor/Git state, retains the old
journal and any completed publisher receipt byte-for-byte, and replaces the active
slot atomically with the qualified successor. Existing backups remain untouched.

Every inherited target still needs fresh successor verification. Removed/offline
targets remain incomplete; prior verification is not reused for changed source.
Inherited native saved-state obligations are derived from every predecessor's
published artifact delta, even if its readback phase was never reached. They need
fresh current readback. A different desired value requires the exact artifact in
the qualified successor selection; target redirection remains unresolved. No
settings are restored to close history. Predeployment release cannot discard a
successor carrying published obligations through either of its admission routes.
Source-only continuation is rejected. A composition failure retains the active
successor and predecessor evidence for inspection; it does not silently release
the obligations. Native loading/restarts remain separate. None of this admits new
skills, waives measurement or public-disclosure requirements, or authorizes
overwriting unselected local owners. A request with changed bytes/state is blocked.

A settled `source-conflict` successor with inherited published obligations may
use that same bounded continuation request to bind a newly qualified descendant.
The failed attempt must be undeployed, conflict-free, have no inner publisher or
unfinished Git operation, and leave both owned worktrees at the verified public
base with no raw/index drift. The request binds its exact failed-journal digest,
new source/options and every inherited target's fresh fingerprint. Existing
selected files and owner/root scope cannot be dropped or redirected. The failed
attempt is never relabeled as published: its exact journal is retained in a
separate source-failure archive, and its receipt, backup references, prior failure
history and all published predecessors remain bound to the new successor-pending
attempt. Target state is rechecked before the atomic replacement. Existing
predeployment release cannot discard either history, and retries validate the
retained bytes and obligations. This route records consistency, not action
permission; a consumed qualification allowance is not renewed by a request.
