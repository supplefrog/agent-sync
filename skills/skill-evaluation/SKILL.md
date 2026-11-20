---
name: skill-evaluation
description: Check whether an existing agent skill is packaged correctly, works on the target host, or improves real task outputs. Use for skill reviews and with-and-without comparisons.
license: UNLICENSED
---

# Skill Evaluation

Identify the skill revision, the target host and required tools, and what the user needs the skill to accomplish. Reuse existing evidence when it covers the same revision, claim, and effective setup. Record the specific mismatch before repeating a check.

For Agent Sync, locate the published checkout through the shared skill root's `.agent-signal-fleet.json`, using `source_snapshot` without `render/fleet`. Follow the runner and report contracts in [Skill Evaluation](https://github.com/supplefrog/agent-sync/blob/main/docs/artifact-pilot.md).

## Check the package and host

Review the pinned source, license, instructions, and any code or tools the task will use. Keep drafts and third-party candidates outside live skill directories. Use NVIDIA SkillEvaluator Tier 1 with Agent Sync's keyless QC policy. Report blocking findings and advisory warnings. Fix a blocking defect before running the affected comparison. Use a supported OS sandbox for untrusted code.

Check discovery and the required tools on the requested host. A packaged harness profile can flag compatibility issues. Use native catalogue and execution evidence for a host or tool the profile does not cover. If a required tool is missing, report the limitation and leave that outcome unassessed.

## Compare task outputs

Freeze a representative task, inputs, expected deliverables, hard failures, and the rule for deciding whether an improvement matters. Use matched fresh runs with and without the skill and with equivalent access to the tools the task requires. For local file tasks supported by the Agent Sync runner, prefer OMP. Use an isolated NVIDIA trial when it supports the chosen runtime and authorized model route.

Inspect the actual outputs and independently check the required files and assertions. Verify from the run that the skill was read and the necessary tools worked. Grade outputs blind when judgment matters. For a broad quality claim, use held-out tasks and a predeclared budget. Treat a missing run, failed harness, or contaminated baseline as inconclusive. A tie on one task establishes a tie for that task.

Report the package result, observed host compatibility, per-task outcome, and evidence links. State what remains unassessed. For authoring and revision, use Skill Creator (`skill-authoring`). For a fleet rollout, hand revision-bound release evidence to Fleet Admission and use Fleet Sync after approval.
