---
name: skill-evaluation
description: Check whether an existing agent skill is packaged correctly, works on the target host, or improves real task outputs. Use for skill reviews and with-and-without comparisons.
license: UNLICENSED
---

# Skill Evaluation

Identify the skill revision, the target host and required tools, and what the user needs the skill to accomplish. Reuse existing evidence when it covers the same revision, claim, and effective setup. Record the specific mismatch before repeating a check.

## Check the package and host

Review the pinned source, license, instructions, and any code or tools the task will use. Keep drafts and third-party candidates outside live skill directories. Inspect frontmatter, triggers, permissions, scripts, and dependencies. Report blocking findings and advisory warnings. Fix a blocking defect before running the affected comparison. Use a supported OS sandbox for untrusted code.

Check discovery and the required tools on the requested host. A packaged harness profile can flag compatibility issues. Use native catalogue and execution evidence for a host or tool the profile does not cover. If a required tool is missing, report the limitation and leave that outcome unassessed.

## Compare task outputs

Freeze a representative task, inputs, expected deliverables, hard failures, and the rule for deciding whether an improvement matters. Use matched fresh runs with and without the skill on the target host and model, with equivalent access to the tools the task requires.

Inspect the actual outputs and independently check the required files and assertions. Verify from the run that the skill was read and the necessary tools worked. Grade outputs blind when judgment matters. For a broad quality claim, use held-out tasks and a predeclared budget. Treat a missing run, failed harness, or contaminated baseline as inconclusive. A tie on one task establishes a tie for that task.

Report the package result, observed host compatibility, per-task outcome, and evidence links. State what remains unassessed. For authoring and revision, use Skill Creator (`skill-authoring`).
