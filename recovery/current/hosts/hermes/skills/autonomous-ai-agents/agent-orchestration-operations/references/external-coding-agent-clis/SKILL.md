---
name: external-coding-agent-clis
description: Operate terminal-side autonomous coding agents such as OpenAI Codex and Claude Code for bounded implementation, review, or isolated parallel work. Use when the user explicitly requests an external coding CLI or it provides a verified capability advantage over Hermes; do not delegate by default when Hermes can complete and verify the task more cheaply.
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [coding-agent, cli, delegation, worktree]
    related_skills: [delegation-workflows, code-change-verification]
---

# External Coding-Agent CLIs

External agents are separate harnesses with their own auth, context, tools, skills, sandbox, and state. Choose one deliberately; do not treat them as interchangeable model calls.

## Decision rule

Use an external coding CLI when:

- the user names it;
- its auth/plugins/platform integration materially help;
- fresh isolated context is useful for a bounded task;
- parallel work can be isolated in separate worktrees;
- an independent review is worth the process cost.

Keep work in Hermes when the task is tightly coupled to the current investigation, Hermes already owns the necessary context, or external coordination would add more overhead than capability.

## Workflow

1. Define a bounded outcome and acceptance checks.
2. Inspect repo guidance and git state.
3. Verify the exact CLI binary, version, auth presence, and supported noninteractive/PTY mode from live `--help`.
4. Use a clean working directory/worktree for parallel or risky work.
5. Pass the child only the context it needs: goal, paths, constraints, and tests.
6. Run bounded one-shot mode when available; use tracked background/PTY mode only for long or interactive work.
7. Monitor without interrupting healthy work.
8. Independently inspect files, diff, tests, commits, pushes, and URLs before trusting the final summary.
9. Clean up worktrees/processes and preserve only useful artifacts.

Do not use unrestricted/yolo modes unless the task, sandbox, and user intent justify the risk.

## Provider-specific references

Load only the selected CLI reference and verify current flags:

- `references/codex.md`
- `references/claude-code.md`
- `references/claude-desktop-third-party-gateways.md` for stable picker, Auto mode, gateway routing, and plugin boundaries in Claude Desktop 3P deployments

Provider references are operational starting points, not authority over live CLI help.

## Parallel work

Use separate worktrees/directories. Do not let two agents edit the same files or branch concurrently. Keep architecture and integration decisions in the parent. Each worker should own an independent artifact or task with a direct test.

## Verification

Treat every external-agent result as a self-report. The parent must verify externally significant claims:

- `git status` and diff;
- targeted tests/build/lint;
- commit/branch/head SHA;
- remote PR/issue state;
- generated artifact existence/content.

Use `code-change-verification` for nontrivial final diffs and `github-pr-workflow` when publishing upstream.

## Porting external-agent playbooks into Hermes

When comparing a Codex or Claude skill against Hermes-native delegation, port the workflow intent, not the vendor mechanics:

- keep: bounded prompts, isolated worktrees, independent child contexts, cheap-vs-capable routing, and parent-side verification;
- map those ideas onto Hermes primitives (`delegate_task`, batch `tasks`, `leaf` vs `orchestrator`, `delegation.max_concurrent_children`, `max_spawn_depth`);
- reject assumptions that belong to a different CLI, such as per-child `toolsets`, mandatory PTY launch advice, or fixed review loops that Hermes does not require for every task;
- check Hermes docs/live source before copying a playbook into a skill, because the current Hermes behavior is the authority.
