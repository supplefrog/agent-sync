---
name: lean-code-repair
description: Use for small, isolated code repair tasks where the user wants Hermes to stay cost-efficient through lean context and disciplined workflow. Trigger when running benchmark/harness/subagent-style repair workers, fixing a localized bug in a small repo or task sandbox, comparing off-context versus coding-context workflows, or deciding whether coding_context off/auto/focus is appropriate for a bounded repair task.
---

# Lean Code Repair

Use this skill when the task is a small, bounded code repair and the objective is to reduce unnecessary context/tool overhead without losing basic engineering discipline.

Scope boundary: this skill is about **Hermes coding context and worker prompt shape only**. Do not use it to choose models, set reasoning effort, or change provider/model routing.

## Decision rule

Use the lean/off-context worker shape only when most of these are true:

- The task is localized: a small sandbox, benchmark fixture, kata, or a repo with an obvious failing test.
- The prompt already provides the issue and target repository.
- Broad repo discovery is unlikely to be the hard part.
- The worker can run tests locally.
- The task is being run through a benchmark, harness, or intentionally narrow repair worker.

Do not use the lean/off-context worker shape when any of these are true:

- The task may span many files or subsystems.
- The agent needs project conventions, git state, package scripts, or context files.
- The user asks for open-ended real repo work rather than a narrow worker run.

## Worker context configuration

This skill does not spawn subagents by itself. Use it from a parent agent, benchmark harness, or worker profile that creates the small repair worker with the desired context config.

For controlled benchmark/harness/subagent-style small repair workers, set the worker context explicitly rather than relying on a skill to fight runtime context:

```yaml
agent:
  coding_context: off
```

Why config matters: Hermes resolves coding context before the model decides which skills to load. A skill can steer workflow, but it cannot remove context/tool posture that was already injected into the session.

## Worker prompt template

For benchmark/harness workers, use the original tested mini-style worker prompt unchanged. Do not rewrite it into new durable parent-agent instructions and do not layer an additional reporting style on top.

Template: `templates/original-mini-worker-prompt.md` (load it with `skill_view(name='lean-code-repair', file_path='templates/original-mini-worker-prompt.md')` or read it from this skill directory in a harness).

Treat that file as a child-worker prompt template, not as general behavior guidance for this parent session.

Avoid adding extra final-report requirements unless the benchmark specifically wants to measure reporting. Extra reporting can raise output tokens without improving repair quality.

Lean-context pitfalls:

- broad refactors,
- unrelated cleanup,
- adding tests or infrastructure unless clearly useful,
- reading the whole repo by default,
- escalating context before the first lean attempt has evidence of being insufficient.

## Context escalation policy

Escalate from `coding_context: off` only when there is evidence:

- The worker cannot locate the relevant code quickly.
- The failing behavior depends on project conventions or hidden integration paths.
- Tests fail after a plausible minimal fix.
- The task requires multi-file architectural reasoning.
- The output shows confusion, repeated tool calls, or speculative edits.

Context escalation options:

1. Retry with `coding_context: auto` so Hermes can provide its coding brief/workspace snapshot when the task is in a code workspace.
2. Retry with `coding_context: focus` when you deliberately want a coding-focused tool/skill surface.
3. Let the parent Hermes do repo discovery first, then hand a narrower patch task back to the lean worker.

## Interpreting Hermes coding-context modes

- `off`: no coding posture; cheapest context-wise. Good for tiny controlled repair workers.
- `auto`: adds coding posture only in interactive code workspaces.
- `focus`: `auto` plus coding-toolset/schema narrowing and non-coding skill demotion.
- `on`: force coding posture everywhere. Rarely needed for this workflow.

`coding_context: auto` decides whether to add coding context. This skill intentionally does not cover model routing or reasoning settings.

## Reporting

Do not add a separate reporting policy in this skill. The worker prompt template already contains the tested final-summary instruction. The parent harness should record context posture and usage metrics outside the worker response.
