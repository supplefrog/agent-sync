# Agent Sync

Syncs behaviors across your AI agents.

Keep **Hermes, Codex, and OMP** working the way you want, without updating each one separately. Each agent keeps its native capabilities and private state.

The intended experience is simple: ask for a change, let the agent check and share it where appropriate, and receive a verified result—not a list of deployment and Git chores.

## System contract and owners

The [system requirements](docs/system-requirements.md) define expected outcomes for skills, instructions, tools, reconciliation, and deployment. They are a contract to verify, not a claim of current implementation.

| Owner | Responsibility |
| --- | --- |
| Governance | Ownership, evidence, authorization, lifecycle, and system value |
| Authoring | Instruction and interface quality, scope, triggers, and useful brevity |
| Reconciliation | Drift, conflicts, dependencies, and separable change sets |
| Sync | Safe application, recovery, actual loading, and publication verification |

Each expected behavior has one accountable owner. Keep these boundaries apparent in the project; reorganize when it improves clarity without duplicating mechanisms.

`python tools/run.py audit behaviors` reports recorded behavior contracts and legacy capability gaps without inference or deployment. Contracts live in the existing [surface matrix](contracts/surface-matrix.json); inferred requirements remain distinct from user-confirmed requirements. See [behavior auditing](docs/behavior-auditing.md) for reconstruction and evidence limits.

[Requirement status and evidence](docs/requirement-status.md) maps R01–R18 to their implementation, checks, and remaining gaps. Start maintenance from the affected owner and its still-relevant evidence; the capability ownership registry remains the admission authority.

## Start with the outcome

An existing workflow is a baseline, not a requirement to preserve. Agent Sync's [outcome-first workflow](skills/outcome-first-workflow-design/SKILL.md) asks what the system should accomplish, checks why the current implementation exists, and compares keeping, simplifying, or replacing it.

A new skill or another layer of automation is not automatically an improvement. Keep useful knowledge and safeguards; require evidence for changes that claim to improve behavior. Shared files alone do not prove that different agents behave equally well.

## Use it

In a configured Hermes, Codex, or OMP session, describe the persistent change you want and say:

> agent-sync

The agent reviews the affected source and live setup, then uses the common sync command to:

1. Check ownership, conflicts, and publication safety.
2. Share eligible changes with the appropriate agents and save reviewed recovery state.
3. Commit the selected files locally and push to the configured upstream branch.
4. Verify the installed content and remote commit before reporting `synced`.

The agent handles routine bookkeeping. New capabilities, conflicting edits, removals, unsafe content, or unclear ownership still stop for review. A failed commit, push, or verification is incomplete—not success with a follow-up task hidden in the summary.

For direct operation, run these from the checkout:

Develop independent changes in separate Git worktrees based on the published source. Commit the ready change without including unrelated work. `tools/run.py` reuses the checkout's `.venv` or the primary checkout's runtime for a linked worktree, then checks declared imports. It never installs dependencies. Set up `requirements.txt` once if that preflight fails.

```bash
python tools/run.py reconcile plan --ready COMMIT --adopt OWNER --include FILE
# Review the findings before proceeding.
python tools/run.py reconcile sync --ready COMMIT --adopt OWNER --include FILE
```

Repeated `--adopt OWNER` and `--include FILE` select admitted portable owners and exact reviewed publication files; choose whichever selectors fit the change. `--include` grants no deployment authority. Ready commits integrate onto the latest configured upstream in one persistent published worktree, then use the existing deployment and publication checks. Git merges independent edits and reports real conflicts before deployment. Other branches, indexes, and unfinished files stay untouched. The managed source manifest points agents at this published checkout. See the [worktree publication contract](docs/worktree-publication.md) for selection, failure, and retry boundaries.

Native settings maintenance uses the existing reconciler without `--ready`. Repeated `--capture-artifact HOST:ID` selects exact policy artifacts from an existing valid snapshot; shared recovery metadata dependencies still require review. Only selected roots are captured. Broad `--full` retains cohesive allowlisted recovery capture within existing authorization. Source-authored generated overlays may be published as exact includes, then restored through the native recovery owner.

Native evaluation now supports isolated Hermes skill-catalog and tool-bearing artifact probes through the existing evaluation owners. The [remaining-outcomes receipt](evals/results/remaining-outcomes-20260927.json) records the narrow comparison and mechanism evidence; it does not establish a quality gain, Codex readiness, or whole-fleet parity.

Ready callers check frozen source commits before waiting up to 120 seconds for the common Git publication lock. A failed deployed or published attempt must resume with the same ready commit and selection before another scope publishes. Generated binding hashes are composed for the selected scope; policy and selected readback changes still require manifest review. Explicit legacy working-file maintenance uses `--shared-checkout`; it is no longer the default shared-source path.

This is an explicit operation, not a background watcher. Editing a file does not automatically publish it.

For approved configured defaults, use `python tools/run.py reconcile plan --reconcile-defaults`, then the same `sync --reconcile-defaults` selection. `--maintenance-host` narrows native targets; its default comes from [core.md](surfaces/core.md), the sole desired-value owner. Exact Codex/Hermes settings capture also reconciles approved defaults automatically after scoped checks. The adapter preserves provider and other parsed settings, captures the selected settings, and records timestamped observations. It does not change running sessions. `--no-capture-recovery` conflicts with a default-setting operation. OMP retains its setup without an approved default mapping.

## What stays protected

- **One maintained source per capability.** Shared procedures live here; agent-specific integrations adapt them rather than maintain competing versions.
- **Native differences.** Settings, permissions, discovery, and runtime features stay with their owning agent. Cross-agent sharing does not mean copying every setting everywhere.
- **Private and project-local state.** Credentials, memories, conversations, logs, and caches are excluded. Project-specific instructions stay in their project.
- **Review and recovery.** Staged candidates do not become active merely because they are in the repository. Conflicts are not overwritten, retirement needs review, and sync never rewrites remote history.
- **Evidence proportional to the claim.** Broken commands need direct reproduction and verification. Claimed improvements in model behavior need comparative checks on the affected setup, including cases that should remain unchanged.

## What is active

The current managed setup covers Hermes, Codex, and OMP on the configured Windows machine. Admitted skills are rendered into managed copies in a shared discovery root; agents do **not** load every candidate directly from this working tree.

[The registry](registry.json) records which skills are admitted or staged. The deterministic reconciliation tools and the admitted [cross-agent workflow](skills/cross-agent-surface-engineering/SKILL.md) govern changes. `capability-curator` and `surface-convergence` remain staged, not running services or promotion authorities. Hermes automatic curation is disabled in the current setup; age or usage alone does not authorize deleting knowledge.

Runtime-specific support, limitations, and evidence are recorded in the [surface matrix](contracts/surface-matrix.json) and [instruction profiles](docs/instruction-profiles.md). This is a maintained setup, not a claim that every capability has been proven on every agent or machine.

## Set up or recover

You can ask an agent:

> Clone this hub outside live skill-discovery directories and restore only Hermes on this machine. Inspect prerequisites and conflicts first, preserve my credentials and private state, then verify the selected setup. Do not configure Codex or OMP.

Use `--host hermes` with the existing recovery bootstrap; `--host codex` or `--host omp` selects those agents instead. This is a selection on the existing recovery path, not a separate installer. The agent still needs to install/authenticate its runtime through the runtime's supported flow when absent.

Reviewed [native skill packages](docs/native-skill-recovery.md) now travel with the settings snapshot, including the local MCP/arXiv consolidation and the disabled LLM Operations package. Shared admitted skills retain their separate canonical source. A clone reproduces the declared, reviewed inventory—not every file in the author's live agent home.

Clone outside an agent's live skill-discovery directories. In particular, do not clone into `~/.agents`: that can expose staged skills before they have been approved.

This repository contains a configured machine inventory and allowlisted recovery snapshot, not universal defaults. Review [fleet setup](docs/fleet.md) and [recovery](docs/recovery.md) before applying them to another machine. Install the required agent runtimes and authenticate separately; Agent Sync does not restore credentials or private conversation state.

To inspect recovery before applying it:

```bash
python tools/run.py recovery verify
python tools/run.py recovery bootstrap --host hermes  # dry-run; selected agent only
```

After reviewing the proposed changes and satisfying the reported prerequisites:

```bash
python tools/run.py recovery bootstrap --host hermes --apply
```

Restore merges only allowlisted settings and preserves unknown or sensitive fields. Conflicting instruction or hook files require explicit review. A verified restore covers the declared recoverable state, not a full disk image.

Omit `--host` only when intentionally recovering the complete configured source-machine fleet. See [recovery](docs/recovery.md) for explicit target roots and prerequisite reporting. Never run `reconcile.py sync` as a substitute for installing a friend's copy: sync publishes reviewed source changes; bootstrap restores a selected target.

## Find the implementation

| If you need to inspect… | Start here |
| --- | --- |
| Shared skills and their deployment status | `skills/`, [registry.json](registry.json) |
| Standing instructions and agent-specific mappings | [surfaces/core.md](surfaces/core.md), `adapters/` |
| Sync, ownership, and review boundaries | [tools/reconcile.py](tools/reconcile.py), [architecture](docs/architecture.md) |
| Managed skill distribution | [fleet guide](docs/fleet.md) |
| Saved settings and native recovery requirements | [recovery guide](docs/recovery.md), [host-deltas.json](host-deltas.json) |
| Tests, decisions, and limits of the evidence | `tests/`, `evals/`, `evidence/`, [verification guide](docs/grounded-verification.md) |

Low-level installation, fleet, evaluation, and recovery tools support maintenance and testing. They are not competing definitions of a completed sync. Their detailed procedures belong in the linked guides rather than the normal usage path.

## License

MIT; see [LICENSE](LICENSE). Individual skills and third-party material may have their own licensing terms. Check their metadata and preserve provenance before reuse or redistribution.
