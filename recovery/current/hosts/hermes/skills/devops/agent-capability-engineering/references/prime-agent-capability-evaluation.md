# Prime Agent capability evaluation notes

Use when Prime Intellect's Prime Agent is a candidate host, executor, or source of runtime primitives. Re-check official source/docs before any decision; these notes were verified against repository `main` on 2026-08-16 and are not a support guarantee.

## Primary sources

- Repository and installer: https://github.com/PrimeIntellect-ai/prime-agent
- Architecture: https://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/docs/architecture.md
- RLM runtime: https://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/docs/rlm.md
- Long-running agents: https://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/docs/long-running-agents.md
- Windows setup: https://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/docs/windows.md

## Mechanisms worth comparing

1. Persistent IPython/RLM workspace: programmatic filtering and state survive context compaction; child handles, tools, skills, and derived evidence can remain variables instead of repeated prompt text.
2. Daemon-backed continuity: detach/reattach, worker recovery, schedules, goals, heartbeats, and retained child registries.
3. Recursive child handles and family messaging: independent contexts, parent-scoped visibility, retained results, and explicit lifecycle cleanup.
4. Bounded autonomous continuation: turn/token/time budgets plus quality gates; exhaustion or compaction is not completion.
5. Continual Harness refinement: supplemental prompts, memory, skills, and subagent specifications evolve while the base prompt remains immutable and snapshots support rollback.
6. Steering/follow-up queues plus JSON/RPC/ACP surfaces that can make Prime an optional executor behind another authority.

## Admission boundary

Treat Prime as a candidate intact control core, optional executor, or source of runtime primitives according to the current outcome; do not preserve an incumbent task system by default. Reopen prior owner decisions when they assumed Hermes, Kanban, another scheduler, or another composer was canonical. Compare Prime intact before extraction, and permit replacement only when one authority plus verified bridges beats both the incumbent and credible alternatives.

When the target stack is OMP, test a **Prime-on-OMP** path explicitly before defaulting to a sidecar or stripping Prime down to one convenient feature. Because OMP is Pi plus extensions and Prime is Pi-derived, first diff each project against the relevant Pi lineage and map compatibility at the session, tool, event, RPC, extension, sandbox, logging, child-lifecycle, and persistent-workspace seams. Shared ancestry is a promising integration lead, not proof that current forks remain drop-in compatible.

The target is Prime's advanced execution semantics with OMP's batteries included: persistent programmatic workspace, retained/recursive children, long-running detach/recovery, bounded continuation, steering, and governed refinement, while preserving OMP extensions, providers, sandbox, logging, and interaction surfaces. Do not quietly narrow the requirement to "persistent REPL only." Classify each Prime mechanism as already present in OMP, superior in OMP, cleanly portable, coupled to Prime internals, or unwanted. Avoid duplicate session trees, memory/skill stores, daemons, and sandboxes unless a matched pilot proves the second owner necessary.

Treat sandboxing as an ordinary required boundary, not a reason by itself to adopt a production-scale whole-OS substrate. If the effective OMP stack already provides enforceable sandboxing and action logs, verify those exact boundaries and retain them; compare Exo-like whole-OS snapshots only when kernel/OS mutation, hostile multi-tenancy, disposable machine images, or cluster deployment is genuinely required.

`/refine`-style changes are proposals: the producing trajectory must not approve its own persistent mutation. Require provenance, rollback, fresh-host readback, held-out failures, cleanup, and matched baseline/candidate evidence.

At the verified snapshot, the stable installer documented Linux/macOS; the Windows page required a Bash environment such as Git Bash, MSYS2, Cygwin, or WSL. This is not evidence of native-quality Windows daemon/kernel behavior. Official RLM documentation states workers execute with user permissions rather than as security sandboxes. Re-test platform lifecycle, detach/recovery, cleanup, context efficiency, security boundaries, and end-to-end task success before adoption. An external container can supply process/filesystem isolation, but bridge networking is not an enforced egress policy; keep the full sandbox gate open until network destinations and protocols are constrained.

## Verified pilot notes (commit `2c34b82f`, 2026-08-17)

A Windows-hosted WSL Docker pilot exercised Prime's real RPC and `openai-codex` OAuth path with a pinned source build. The following contracts were observed and should be rechecked against newer commits:

- Prime's source archive omits generated workspace outputs; build packages explicitly before running the CLI from an immutable image.
- Prime kernel storage uses `PRIME_AGENT_KERNEL_VENV`, separate from the coding-agent state directory. If uv manages Python, relocate `UV_PYTHON_INSTALL_DIR` outside a root-private home so the non-root runtime can traverse the venv's interpreter symlink.
- Steering acceptance does not imply immediate quiescence. A queued steer may execute as a separate agent run after the first `agent_end`; wait for its run and an empty action queue before submitting another prompt.
- `rlm()` returns an `RLMSpawnHandle` object; use its attributes such as `.rlm_child_id`, not dictionary subscripting.
- A child may complete without following an explicit `agent_message.send` instruction. Prime can persist a structured fallback notification containing child identity and the last assistant result. Record this as degraded instruction adherence, not as an exact reply pass.
- Canonical custom lifecycle notifications may exist in the session JSONL even when an RPC convenience message-list view omits them. Verify the persisted `custom_message` / `agent_message` envelope and detail fields.

See `references/sandboxed-agent-runtime-pilots.md` for the reusable isolation and receipt contract. These notes are evidence about that snapshot, not a claim of complete conversational-OS admission: automatic intent split/attach/dedup, crash recovery with external side effects, enforced egress policy, and a one-composer UI remained separate gates.

## Relationship to LangChain layers

Evaluate adjacent LangChain products by layer rather than as one package:

- **Deep Agents** is a batteries-included agent harness: filesystem, context management, skills/memory, subagents, and approval middleware. Much of this may duplicate a Prime-enhanced OMP.
- **LangGraph** is the lower-level durable orchestration runtime: checkpointed state, resumability, interrupts, streaming, and deterministic/agentic workflow composition. It may remain useful as a multi-task control plane even when Deep Agents is not the primary agent.
- **LangChain** supplies model/tool abstractions and integrations.
- **LangSmith** is optional tracing/evaluation/deployment infrastructure, not required to use the open-source runtime.

Do not present Deep Agents' default ephemeral, stateless, single-handoff subagents as substitutes for Prime's retained recursive workers. The decision is usually whether Prime-enhanced OMP still needs LangGraph for durable multi-task coordination and crash-safe human interrupts—not whether it needs a second generic harness.

## Smallest-solution comparison

For each proposed Prime strength, compare:

- retain the current native owner;
- simplify or generalize that owner;
- adapt only the portable contract;
- use Prime as an optional task-local executor;
- replace the owner only with superior matched evidence;
- remove the capability if maintenance/cost exceeds verified benefit.

Do not reproduce vendor benchmarks unless an unresolved result would change the decision. Prefer targeted pilots for Windows lifecycle, context efficiency, child cleanup, provenance/readback, adapter latency, and usable-result quality.
