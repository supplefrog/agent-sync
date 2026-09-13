---
name: delegation-workflows
description: Design and run Hermes subagent workflows when independent tasks benefit from parallelism, isolation, or fresh review context. Covers parent-vs-child risk routing, task partitioning, bounded prompts, concurrency, integration, and verification. Use for deliberate multi-agent execution; do not trigger for simple linear work or as a reason to delegate judgment the parent should keep.
version: 1.3.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [delegation, subagents, parallel, orchestration, verification]
    related_skills: [plan, code-change-verification, hermes-model-routing-evals, lean-code-repair]
---

# Delegation Workflows

Delegation is useful when it reduces wall time, isolates context, or obtains an independent check. It is harmful when it fragments one coherent task, delegates high-risk judgment to a weaker route, or creates review theater.

The parent owns decomposition, risk, integration, and verification.

## 1. Decide whether to delegate

Delegate when most of these are true:

- tasks are independent or have a clear dependency boundary;
- each child can receive complete, bounded context;
- output is mechanically or directly verifiable;
- mistakes are reversible and cheap;
- parallelism or fresh context materially helps.

Keep work in the parent when any of these dominate:

- architecture, product, security, auth, provider, credential, or persistent-config judgment;
- ambiguous root-cause analysis;
- tightly coupled edits to the same files/state;
- tasks requiring repeated user interaction;
- external side effects whose success is difficult to verify;
- coordination overhead exceeds the work.

A strong parent may still delegate bounded evidence gathering for a high-risk decision, but it should not outsource the decision itself.

## 2. Partition by ownership, not arbitrary size

Good child boundaries produce independent artifacts or findings:

- inspect separate subsystems;
- research independent sources;
- implement plan tasks that touch disjoint files;
- run alternative experiments on isolated fixtures;
- review a completed diff with fresh context.

Bad boundaries split one state transition across several agents or have multiple children edit the same files concurrently.

Respect dependencies. Run tasks in parallel only when no child needs another child’s result. Otherwise serialize the dependent stage.

When one user message contains distinct substantial requests with separate success criteria, split those scopes into separate child contexts by default. Classify and route each scope by its own difficulty, dependencies, and deadline; keep coupled work and trivial follow-ups together. Keep the parent focused on shared constraints, decisions, verified summaries, and final integration rather than importing each child’s exploration logs or intermediate reasoning.

This is context isolation, not automatic parallelism: independent scopes may run concurrently, while dependent scopes remain separate but serialized. If a scope needs durable state, interaction, or more history than an ephemeral child can safely carry, use a tracked external process/worktree or another durable owner instead of bloating the parent thread.

## 3. Write self-contained child prompts

Each child prompt should preserve the user's source wording as closely as possible. Start from a near-verbatim excerpt that defines the child scope; add only context the child cannot retrieve and that materially changes execution. Prefer observable output and acceptance evidence over interpretive framing, motivational prose, role-play, or speculative instructions. For capable current models, default to minimal steering. Research and validate before turning a model-specific prompting belief into durable policy.

When additional context is required, keep it factual and source-like:

- **Goal:** the user's bounded outcome, preferably quoted or minimally trimmed.
- **Context:** paths, direct facts, and prior decisions the child cannot retrieve.
- **Constraints:** actual authorization and safety boundaries, not process preferences invented by the parent.
- **Verification:** concrete output, evidence, or acceptance checks.
- **Failure behavior:** report missing context rather than guessing.

Do not make children rediscover a plan or conversation the parent already read. Pass only the needed excerpt, not the entire parent context.

For code tasks, give the repository path and tell the child whether it may edit. Avoid forcing TDD, commits, or elaborate final reports unless they are part of the task’s acceptance criteria.

## 4. Choose execution shape

- **One direct tool call:** do not spawn a child.
- **Several mechanical calls with processing:** use `execute_code`.
- **Independent reasoning/inspection tasks:** use one `routed_delegate_task` call when available; use `delegate_task` only for a homogeneous fallback batch.
- **Durable or long-running work:** use tracked background processes, cron, or an explicit external agent—not ephemeral delegation.
- **Interactive work:** keep it in the parent or use an appropriate PTY/external-agent workflow.

Limit fan-out to the number of genuinely independent workstreams. More agents create duplicated context and reconciliation cost, not automatic quality.

Treat child contexts as temporary. A returned final summary or stopped process does not prove its persisted session/thread record was deleted. When the surface returns a deletable session/thread handle, preserve the required artifact or receipt, invoke the native delete/close primitive after integration, and verify absence; stop/cancel paths also close the handle. When deletion is unavailable, release/close what the surface supports, retain only the distilled result, and do not describe stop, archive, or process exit as deletion. Never delete user-created, shared, active, or still-referenced sessions.

## 5. Model/routing discipline

For every new routed task, use `routed_delegate_task` when available. Classify only the minimum intelligence tier, whether latency blocks the user, and failure cost; the tool invokes `openai-delegation-route-research`, selects the qualifying exact provider/model/reasoning tuple, disables route fallback, and pins the receipt by parent session plus task ID. Reuse a task ID only for an identical retry. Cost is the default priority after the intelligence floor; task time wins only for latency-sensitive work. Do not choose a model manually unless the user explicitly overrides it.

The routed tool is a version-guarded user plugin over Hermes's native child builder/finalizer. If its host seam, selector, provider, receipt, or task binding cannot be verified, it fails closed without rewriting shared config. Built-in `delegate_task` remains the rollback path and still uses one configured route for every child, so use it only for homogeneous tasks supported by that route. Never mutate global config between child launches to imitate per-task routing.

Verify live account availability before changing defaults. Preserve the incumbent or fail closed when no candidate meets the intelligence floor or the target surface cannot enforce the selected route. Auxiliary assignments remain purpose-specific and outside the delegation catalogue.

Do not silently change delegation config during unrelated work.

## 6. Integrate and verify

Child results are self-reports. The parent should:

1. compare each result with the original task and other child findings;
2. resolve contradictions using source evidence or direct execution;
3. read back shared files or fetch returned external handles;
4. run the relevant acceptance checks itself when practical;
5. integrate only the parts that survive verification.

For code changes, use `code-change-verification` when the final diff is nontrivial or high-risk. Choose review depth deliberately:

- **Balanced (default when independent review materially helps):** one fresh reviewer returns separate specification and quality verdicts.
- **Strict:** specification must pass before a separate quality reviewer starts. Use only when the user requests two-stage review or the failure cost clearly justifies the extra invocation.

Send material findings back to the producer or a bounded fix worker. The parent may make a trivial, directly verifiable correction when that is cheaper and does not compromise reviewer independence. Cap review/revision at three cycles and escalate sooner when material findings do not decrease across consecutive cycles; never loop until a reviewer gives up. Do not add reviewers when the parent can verify the result more cheaply.

## 7. Failure and escalation

If a child fails:

- determine whether the issue is missing context, wrong partitioning, route availability, tool access, or task difficulty;
- fix the cause before retrying;
- avoid repeated retries on the same unavailable provider;
- collapse the task back into the parent when coordination is the problem;
- escalate context/model only when evidence shows the cheaper path is insufficient.

Do not convert one transient provider failure into a permanent routing rule.

## Output discipline

Ask children for the shortest result the parent can verify: structured findings, file paths, commands and exit codes, or a concrete artifact handle. Avoid narrative status reports that merely restate the prompt.

## Pitfalls

- Parallelism does not help tightly coupled work.
- Fresh context can remove crucial project context as easily as it removes bias.
- Independent review is valuable only when findings are evidence-backed and checked.
- A child claiming tests passed is not equivalent to the parent observing the command or CI result.
- Orchestration should remove bottlenecks, not become the bottleneck.
