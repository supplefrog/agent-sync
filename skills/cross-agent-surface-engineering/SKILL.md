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

Inspect the changed owner and affected neighbors first. Use the applicable read-only checks from the owning checkout:

```text
python tools/recovery.py diff
python tools/instruction_profile.py
python tools/fleet.py diff
python tools/reconcile.py plan
```

Read the affected entries in `contracts/instruction-surfaces.json`, `contracts/surface-matrix.json`, `contracts/ownership.json`, the selected model profile, and `recovery/current/manifest.json`. Inspect the corresponding live discovery and precedence; broaden only for a demonstrated dependency, conflicting evidence, or invalidated assumption. Official current host docs beat stale repository prose; reviewed Agent Sync ownership beats live copies and generated caches. Keep unrelated drift out of a scoped deployment.

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

Reuse source-linked evidence while its relevant source, runtime, and tool identities still match. Revalidate the affected claim when a binding changes; do not require another whole-agent audit for an independent correction. Missing or inconclusive evidence remains explicit.

Structural removal of byte-identical copies needs deterministic identity and fresh-discovery checks, not evaluation theater. A broken unique mechanism is not a winner merely because no other variant implements it.

### 6. Promote and clean up

For authorized Agent Sync changes or an explicit reconciliation, run `python tools/reconcile.py plan` in the owning checkout; inspect destinations and findings, then run `python tools/reconcile.py sync` for the authorized scope. Sync checks and shares eligible changes, commits them locally, pushes to the configured remote branch, and verifies selected installed content and the remote commit. Scoped readback does not establish native host discovery or behavioral parity. Do not call a local copy or recovery capture “synced.” A temporary verification hold ends when its named checks pass; continue the already-authorized deployment and publication without asking again. Stop only for a remaining failed check, scope conflict, or explicit no-publication instruction. The agent handles these steps as one authorized job, not separate user reminders.

For a scoped change, name admitted owners with repeated `--adopt OWNER` and reviewed exact publication files with repeated `--include FILE`; use `--no-capture-recovery` when native settings are outside the authorized change. Explicit selected recovery capture remains review-required until an artifact-level selection contract exists. Broad `--full` retains cohesive recovery capture within existing authorization; the unselected default sync remains broad. `--include` selects commit content only, not admission or deployment authority. Complete independently separable authorized changes while leaving unrelated drift pending. A blocker must identify a dependency, conflict, or authorization boundary. Preserve existing pins unless changing them is authorized. Capture justified native settings without copying them indiscriminately across hosts. Novel, conflicting, unsafe, retirement, or ambiguous findings still require their existing review; project-local and ephemeral work stays local. A failed check, commit, push, or readback is incomplete. Preserve the pending work and rerun the same sync after resolving the cause; never rewrite remote history or erase another task's edits.

Use `fleet-sync` for admitted portable skills. Never force through an unmanaged collision, edit a generated plugin cache, or delete a live variant before preflight. Keep adapters only for runtime discovery, precedence, host command/config format, or an irreducible native protocol.

Host checks:

- **Hermes:** verify the parsed `skills.external_dirs` value and fresh skill loading; a quoted serialized array can silently disable discovery.
- **Codex:** use `codex debug prompt-input` to confirm the effective skill. For local-marketplace plugins, edit source, refresh through the native remove/re-add lifecycle, and verify `codex plugin list --json`; never patch the installed cache.
- **OMP:** current OMP loads Agent Skills from project walk-up and user-home `.agent/skills` and `.agents/skills`. Verify a fresh `omp --mode rpc --no-session` process with the read-only `get_available_commands` request, then close stdin for clean shutdown. `get_commands` is unsupported and its error may omit the request ID; `omp read skill://...` alone has no initialized skill catalog. Keep a native OMP skill only when it adds real OMP execution or precedence glue rather than copied policy.

After promotion, verify the affected installed content and deployment claims; check a real target behavior before making a behavioral claim. Reuse still-bound checks and rerun recovery/profile/fleet verification where the change affects them. Report drafted, checked, locally deployed, and remotely synchronized states separately; include-only publication does not establish host verification. Record the canonical owner, migrated and discarded behaviors, retained native deltas, exact checks, rollback, and restart/reset requirement.

## Safety boundaries

For a request to clone one agent from this hub, use the existing recovery bootstrap's `--host` selection and target-local roots; do not introduce an installer framework or apply the whole source-machine fleet. Read `docs/recovery.md` for the selected-host contract. Verify the selected agent's recovered files, discovery, and prerequisites; never call another host's successful checks proof of readiness.

When preserving a curated host, inventory skill and plugin packages, support files, native patches, enablement, and origin metadata; review licensing before extending `recovery.json`. Capture native customizations without promoting them into the shared fleet. Follow `docs/native-skill-recovery.md`; a passing allowlist does not prove complete coverage. Exercise a disposable target and fresh discovery, including dry-run filesystem invariance: nominally read-only native CLI commands may initialize a profile.

Automatic learning is an intended capability, not drift merely because it spends inference or proposes frequent updates. Distinguish enforced ownership/approval/rollback boundaries from uncertain output quality; reproduce a safeguard failure before recommending a restriction on that basis. Curator, background review, and notification settings are separate controls.

Hermes skill proposals use its existing write-approval queue, not live edits. During reconciliation, review `skill-proposals` findings with `skill-creator`; use `tools/hermes_skill_review.py show ID` for the private payload and review token. Approve checked native changes through that helper; promote shared/new owners from canonical source, then discard the proposal. Rejected or unresolved candidates stay out of live discovery; unrelated sync is not approval. Commands and limits: `docs/hermes-skill-proposals.md` in the owning checkout. Do not publish proposal bodies.

Never copy credentials, sessions, memories, logs, caches, private user data, or provider-hidden prompts into Agent Sync. Do not modify another profile without explicit authorization. Do not infer parity from identical files, and do not lower one host to the weakest common mechanism.
