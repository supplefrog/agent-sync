---
name: skill-authoring
description: Create or revise an agent skill from a task, then test its real outputs and use the evidence to improve the draft. Use for skill authoring or changes to an existing skill.
license: Apache-2.0
---

<!-- Adapted from Anthropic's Skill Creator. -->

# Skill Creator

Use the task as the source of intent. Identify what the skill should enable, when it should apply, and the outputs and boundaries the user cares about. Read the supplied examples and existing owner first. Ask when uncertainty would change the deliverable or behavior.

Extend the existing owner when it already covers the task. Before revising, inspect current behavior with the existing guidance and identify the gap. Change the smallest decision rule, procedure, or tool that addresses it.

## Draft

Write a discoverable `SKILL.md` with a name matching the folder and a description that tells the agent what the skill does and when to use it. Put frequently needed decisions in the entrypoint. Link conditional details, repeatable scripts, and reusable assets where they are needed. Validate any bundled script by running the operation it supports. Keep the draft and training artifacts outside installed skill roots while testing.

## Run and grade

Choose realistic task prompts and inputs that could expose the intended improvement. Put an outcome and constraints in each prompt. Save them using the [evaluation schema](references/schemas.md). Use the same model, tools, fixture and limits in separate fresh sessions. Pair a new skill with a no-skill baseline. Pair a revision with its frozen predecessor and include a no-skill control when the question is whether the workflow needs a skill at all.

Use the host's supported runner and preserve the execution mechanisms the task requires. For standalone comparisons, use `skill-evaluation` when it fits. Collect actual outputs, tool calls, skill exposure, timing and available usage. Reuse comparable evidence for the exact revision. If a route is blocked, validate what can be checked offline and leave the comparison open.

In each iteration:

1. Store each run's files under `iteration-N/eval-ID/{with_skill,without_skill}/run-1/outputs/`. Increment the run number for repeats. Keep the user prompt in `eval_metadata.json` in the run directory. When comparing a prior revision, keep its identity in the run metadata. Preserve the inputs and previous iteration.
2. Freeze required assertions and meaningful controls before the quality trials. Run deterministic checks where possible. Read [the bundled grader](agents/grader.md) to inspect the produced files, verify claims and record each assertion in `grading.json` with `text`, `passed` and `evidence`. Grade blind to the arm where practical. Use the [comparator](agents/comparator.md) and [analyzer](agents/analyzer.md) for a consequential tradeoff or ambiguous comparison.
3. Record observed timing and token counts in the run's `timing.json` using the [run schemas](references/schemas.md). With complete measurements, run `python -m scripts.aggregate_benchmark <iteration-dir> --skill-name <name>` from this package. Surface missing metrics as unknown.
4. Use the [output reviewer](scripts/generate_review.py) with `python scripts/generate_review.py <iteration-dir> --skill-name <name> --static <review.html>`, or use the native viewer workflow where supported. Pass `--benchmark` when available. Review files and findings with the user when their judgment determines the result.

## Revise and rerun

Trace grade failures and feedback to a decision or repeated piece of work. Fix the owner of that behavior and keep the rule useful on new examples. Rerun the matched inputs in a new iteration and use `--previous-workspace` to review changes. Expand to held-out tasks when the adoption decision needs stronger evidence. Stop when the observed gap closes, improvement stalls, or the user concludes the review. Refine or remove additions that do not help.

When the description itself is the issue, test realistic intended and near-miss prompts. The bundled [trigger loop](scripts/run_loop.py) is specific to Claude Code and requires a supported, authorized local Claude route. Use equivalent current-host evidence elsewhere. [Package the checked draft](scripts/package_skill.py) when the user needs a distributable skill.

[Upstream provenance](NOTICE.md)
