---
name: cross-agent-surface-engineering
description: Use for persistent-surface changes across Hermes, Codex, and OMP. Compare variants behavior by behavior, synthesize the strongest portable owner, retain only justified host adapters, and verify fresh discovery before cleanup.
version: 2.0.0
author: Local User
license: UNLICENSED
compatibility: Requires an Agent Signal checkout and access to the affected live hosts.
metadata:
  hermes:
    tags: [hermes, codex, omp, cross-agent, convergence]
    related_skills: [fleet-sync, skill-creator, hermes-self-engineering]
---

# Cross-Agent Surface Engineering

Use this for persistent instructions, skills, config, plugins, hooks, routing, or source that affects more than one of the supported hosts: Hermes, Codex, and OMP. Ordinary host use, project code, and one-host status inspection stay with their narrower owners.

## Canonical owner

Agent Signal is authoritative. Locate its checkout from the managed skill root's `.agent-signal-fleet.json` and `source_snapshot`, as described by `fleet-sync`; otherwise require a checkout containing `fleet.json`, `registry.json`, and `tools/fleet.py`. Live host directories are deployments or adapters, not editable canonical sources. `agent-surface-bridge` is prior evidence only.

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

Read `contracts/instruction-surfaces.json`, `contracts/surface-matrix.json`, `contracts/ownership.json`, the selected model profile, and `recovery/current/manifest.json`. Then inspect the live target config, docs, source, discovery roots, precedence, and enabled plugins for the exact host, profile, and working directory. Official current host docs beat stale repository prose; reviewed Agent Signal ownership beats live copies and generated caches.

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

Use the narrowest owner. Inside Agent Signal, read `skills/capability-curator/SKILL.md` for admission and `skills/surface-convergence/SKILL.md` for semantic parity; their registry status remains authoritative, so do not pretend a staged skill is globally admitted. Portable procedures belong in one Agent Skill, portable judgment in the shared instruction surface, and runtime mechanics in thin adapters or the native host.

### 5. Stage and evaluate

Keep candidates outside all live discovery roots. Preserve license and provenance. Modify the portable owner first, then only necessary adapters. For material behavior changes, run the owning admission gate with representative, near-miss, adversarial, held-out, and regression cases on each affected host. Normalize model, provider, reasoning, prompt/tool/context assembly, runtime, and adapter fingerprints. Harness failure is inconclusive; missing-host evidence cannot claim parity.

Structural removal of byte-identical copies needs deterministic identity and fresh-discovery checks, not evaluation theater. A broken unique mechanism is not a winner merely because no other variant implements it.

### 6. Promote and clean up

Use `fleet-sync` for admitted portable skills. Never force through an unmanaged collision, edit a generated plugin cache, or delete a live variant before preflight. Keep adapters only for runtime discovery, precedence, host command/config format, or an irreducible native protocol.

Host checks:

- **Hermes:** verify the parsed `skills.external_dirs` value and fresh skill loading; a quoted serialized array can silently disable discovery.
- **Codex:** use `codex debug prompt-input` to confirm the effective skill. For local-marketplace plugins, edit source, refresh through the native remove/re-add lifecycle, and verify `codex plugin list --json`; never patch the installed cache.
- **OMP:** current OMP loads Agent Skills from project walk-up and user-home `.agent/skills` and `.agents/skills`. Verify a fresh no-session process. Keep a native OMP skill only when it adds real OMP execution or precedence glue rather than copied policy.

After promotion, rerun recovery/profile/fleet verification and one real target behavior. Record the canonical owner, migrated and discarded behaviors, retained native deltas, exact checks, rollback, and restart/reset requirement.

## Safety boundaries

Never copy credentials, sessions, memories, logs, caches, private user data, or provider-hidden prompts into Agent Signal. Do not modify another profile without explicit authorization. Do not infer parity from identical files, and do not lower one host to the weakest common mechanism.
