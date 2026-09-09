# Agent Signal

Agent Signal maintains shared skills, instructions, and recovery records for **Hermes, Codex, and OMP**. It gives useful agent improvements one maintained home, while keeping each agent's native strengths and private state separate.

The intended experience is simple: ask for a change, let the agent check and share it where appropriate, and receive a verified result—not a list of deployment and Git chores.

## Start with the outcome

An existing workflow is a baseline, not a requirement to preserve. Agent Signal's [outcome-first workflow](skills/outcome-first-workflow-design/SKILL.md) asks what the system should accomplish, checks why the current implementation exists, and compares keeping, simplifying, or replacing it.

A new skill or another layer of automation is not automatically an improvement. Keep useful knowledge and safeguards; require evidence for changes that claim to improve behavior. Shared files alone do not prove that different agents behave equally well.

## Use it

In a configured Hermes, Codex, or OMP session, describe the persistent change you want and say:

> Reconcile with Agent Signal.

The agent reviews the affected source and live setup, then uses the common sync command to:

1. Check ownership, conflicts, and publication safety.
2. Share eligible changes with the appropriate agents and save reviewed recovery state.
3. Commit the selected files locally and push to the configured upstream branch.
4. Verify the installed content and remote commit before reporting `synced`.

The agent handles routine bookkeeping. New capabilities, conflicting edits, removals, unsafe content, or unclear ownership still stop for review. A failed commit, push, or verification is incomplete—not success with a follow-up task hidden in the summary.

For direct operation, run these from the checkout:

```bash
python tools/reconcile.py plan
# Review the findings before proceeding.
python tools/reconcile.py sync
```

Sync includes allowlisted recovery capture by default. `--no-capture-recovery` disables capture; unresolved recovery findings can still block the operation. Additional reviewed repository files are selected with repeated `--include FILE` arguments, not a blanket `git add .`. After resolving a failure, rerun sync to resume the checked work. See the [reconciliation contract](docs/architecture.md#unified-reconciliation) for the scope and failure rules.

This is an explicit operation, not a background watcher. Editing a file does not automatically publish it.

## What stays protected

- **One maintained source per capability.** Shared procedures live here; agent-specific integrations adapt them rather than maintain competing versions.
- **Native differences.** Settings, permissions, discovery, and runtime features stay with their owning agent. Cross-agent sharing does not mean copying every setting everywhere.
- **Private and project-local state.** Credentials, memories, conversations, logs, and caches are excluded. Project-specific instructions stay in their project.
- **Review and recovery.** Staged candidates do not become active merely because they are in the repository. Conflicts are not overwritten, retirement needs review, and sync never force-pushes.
- **Evidence proportional to the claim.** Broken commands need direct reproduction and verification. Claimed improvements in model behavior need comparative checks on the affected setup, including cases that should remain unchanged.

## What is active

The current managed setup covers Hermes, Codex, and OMP on the configured Windows machine. Admitted skills are rendered into managed copies in a shared discovery root; agents do **not** load every candidate directly from this working tree.

[The registry](registry.json) records which skills are admitted or staged. The deterministic reconciliation tools and the admitted [cross-agent workflow](skills/cross-agent-surface-engineering/SKILL.md) govern changes. `capability-curator` and `surface-convergence` remain staged, not running services or promotion authorities. Hermes automatic curation is disabled in the current setup; age or usage alone does not authorize deleting knowledge.

Runtime-specific support, limitations, and evidence are recorded in the [surface matrix](contracts/surface-matrix.json) and [instruction profiles](docs/instruction-profiles.md). This is a maintained setup, not a claim that every capability has been proven on every agent or machine.

## Set up or recover

Clone outside an agent's live skill-discovery directories. In particular, do not clone into `~/.agents`: that can expose staged skills before they have been approved.

This repository contains a configured machine inventory and allowlisted recovery snapshot, not universal defaults. Review [fleet setup](docs/fleet.md) and [recovery](docs/recovery.md) before applying them to another machine. Install the required agent runtimes and authenticate separately; Agent Signal does not restore credentials or private conversation state.

To inspect recovery before applying it:

```bash
python tools/recovery.py verify
python tools/recovery.py bootstrap  # dry-run
```

After reviewing the proposed changes and satisfying the reported prerequisites:

```bash
python tools/recovery.py bootstrap --apply
```

Restore merges only allowlisted settings and preserves unknown or sensitive fields. Conflicting instruction or hook files require explicit review. A verified restore covers the declared recoverable state, not a full disk image.

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
