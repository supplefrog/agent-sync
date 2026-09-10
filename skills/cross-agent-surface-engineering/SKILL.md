---
name: cross-agent-surface-engineering
description: Use for agent-sync requests and cross-host surface changes across Hermes, Codex, and OMP. Compare variants behavior by behavior, synthesize the strongest portable owner, retain only justified host adapters, and verify fresh discovery before cleanup.
version: 2.0.0
author: Local User
license: UNLICENSED
compatibility: Requires an Agent Sync checkout and access to the affected live hosts.
metadata:
  hermes:
    tags: [hermes, codex, omp, cross-agent, convergence]
    related_skills: [fleet-sync, skill-creator, hermes-self-engineering]
---

# Cross-Agent Surface Engineering

Use this for cross-host placement, parity, or reconciliation across Hermes, Codex, and OMP. A request to `agent-sync` means complete the checked deployment, commit, push, and remote readback for the current authorized changes; no separate reconciliation phrase or routine confirmation is needed. Review unrelated dirty work before including it, and preserve approval gates for new or high-stakes actions. Known-owner wording edits use `skill-creator`; ordinary host use and project code stay with their narrower owners.

## Canonical owner

Agent Sync owns the source of its managed artifacts. Locate its checkout from the managed skill root's `.agent-signal-fleet.json` and `source_snapshot`, as described by `fleet-sync`; otherwise locate a checkout containing `fleet.json`, `registry.json`, and `tools/fleet.py`. Edit that source before deploying its managed copies. Independently owned native surfaces retain their own source. `agent-surface-bridge` is prior evidence only.

## Procedure

### 1. Define the behavior contract

State the observable outcome, trigger, affected hosts and versions, hard failures, acceptable native differences, rollback, and checks. Do not choose a file or mechanism before the behavior is clear.

### 2. Inventory the effective surfaces

From the owning checkout, run:

```text
python tools/recovery.py diff
python tools/instruction_profile.py
python tools/fleet.py render
python tools/fleet.py diff
```

Read the affected entries in `contracts/instruction-surfaces.json`, `contracts/surface-matrix.json`, `contracts/ownership.json`, the selected model profile, and `recovery/current/manifest.json`. Inspect the corresponding live discovery and precedence; expand to config, plugins, docs, or source only for unresolved dependencies. Official current host docs beat stale repository prose; reviewed Agent Sync ownership beats live copies and generated caches. Keep unrelated drift out of a scoped deployment.

### 3. Compare behaviors, not whole skills

For every variant, enumerate independently:

- trigger and user-visible outcome;
- procedure and decision rules;
- scripts, templates, and deterministic mechanisms;
- safety, lifecycle, recovery, and verification guarantees;
- host-native discovery, precedence, command, or file-format glue;
- provenance, license, current tests, and known failures.

Classify each unique behavior as:

- **portable winner** — migrate into the canonical owner;
- **host adapter** — retain only the smallest host-native glue;
- **irreducible native strength** — leave with the host and route to it;
- **discard** — redundant, stale, broken, unsafe, unsupported, or negative steering.

The canonical result may merge compatible winning behaviors from several variants. Do not pick a whole skill merely by version, and do not union conflicting instruction sets. A variant may be removed only after every unique behavior is migrated, retained natively, or explicitly rejected with evidence.

### 4. Assign one owner per concern

Use the narrowest source owner: portable procedures in an Agent Skill, standing preferences in the applicable instruction surface, and runtime mechanics in a supported config or native adapter/source. Registry state records deployment eligibility; it does not grant authorization or prove model quality. Staged comparison guides are optional evidence, not required approval hops or promotion authorities.

### 5. Stage and evaluate

Keep unselected candidates outside live discovery roots and preserve license/provenance. Modify the portable owner first, then necessary adapters. Verify mechanism corrections directly; compare model behavior when claiming a quality gain. Record model, provider, reasoning, runtime, and prompt/tool/context identities. Explicit instruction injection does not establish natural triggering. Test every host included in a parity claim; missing or failed host evidence remains an explicit limit.

Structural removal of byte-identical copies needs deterministic identity and fresh-discovery checks, not evaluation theater. A broken unique mechanism is not a winner merely because no other variant implements it.

### 6. Promote and clean up

For authorized Agent Sync changes or an explicit reconciliation, run `python tools/reconcile.py plan` in the owning checkout; inspect destinations and findings, then run `python tools/reconcile.py sync`. Sync checks and shares eligible changes, commits them locally, pushes to the configured remote branch, and verifies both the agents and remote commit. Do not call a local copy or recovery capture “synced.” A temporary verification hold ends when its named checks pass; continue the already-authorized deployment and publication without asking again. Stop only for a remaining failed check, scope conflict, or explicit no-publication instruction. The agent handles these steps as one authorized job, not separate user reminders.

Review additional dirty repository files before naming their exact paths with repeated `--include FILE`; never collect all files blindly. This selects commit content only, not admission or deployment authority. Capture justified native settings without copying them indiscriminately across hosts. Novel, conflicting, unsafe, retirement, or ambiguous findings still require their existing review; project-local and ephemeral work stays local. A failed check, commit, push, or readback is incomplete. Preserve the pending work and rerun the same sync after resolving the cause; never force-push or erase another task's edits.

Use `fleet-sync` for admitted portable skills. Never force through an unmanaged collision, edit a generated plugin cache, or delete a live variant before preflight. Keep adapters only for runtime discovery, precedence, host command/config format, or an irreducible native protocol.

Host checks:

- **Hermes:** verify the parsed `skills.external_dirs` value and fresh skill loading; a quoted serialized array can silently disable discovery.
- **Codex:** use `codex debug prompt-input` to confirm the effective skill. For local-marketplace plugins, edit source, refresh through the native remove/re-add lifecycle, and verify `codex plugin list --json`; never patch the installed cache.
- **OMP:** current OMP loads Agent Skills from project walk-up and user-home `.agent/skills` and `.agents/skills`. Verify a fresh `omp --mode rpc --no-session` process with the read-only `get_available_commands` request, then close stdin for clean shutdown. `get_commands` is unsupported and its error may omit the request ID; `omp read skill://...` alone has no initialized skill catalog. Keep a native OMP skill only when it adds real OMP execution or precedence glue rather than copied policy.

After promotion, rerun recovery/profile/fleet verification and one real target behavior. Record the canonical owner, migrated and discarded behaviors, retained native deltas, exact checks, rollback, and restart/reset requirement.

## Safety boundaries

Never copy credentials, sessions, memories, logs, caches, private user data, or provider-hidden prompts into Agent Sync. Do not modify another profile without explicit authorization. Do not infer parity from identical files, and do not lower one host to the weakest common mechanism.
