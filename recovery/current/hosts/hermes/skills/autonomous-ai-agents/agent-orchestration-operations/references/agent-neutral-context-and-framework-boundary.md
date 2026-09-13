# Agent-neutral context and framework boundary

Use when orchestration is collapsing into one long chat, a task must move between agent hosts, or a framework/runtime is being considered for durable execution.

## Durable handoff contract

The shared unit is an agent-neutral work packet, not a transcript:

- outcome and acceptance checks;
- hard constraints, approvals, and irreversible boundaries;
- current lifecycle state and dependencies;
- material decisions and unresolved questions;
- artifact/evidence references with provenance and freshness;
- next allowed action and owning authority.

Kanban plus referenced artifacts is authoritative. A chat, reasoning trace, compaction summary, or stakeholder brief is a lossy view. Project only the fields and evidence needed by the current producer, reviewer, or host. Integrate new evidence at handoff, record omissions/uncertainty, then allow the originating agent-created thread to retire. Verify that another supported host can resume without the original chat.

## Cross-surface mutation handoff

When the user has modified instructions, skills, tools, plugins/hooks, configuration, model/routing, or context policy across multiple agents, load `cross-agent-surface-engineering`. It owns the effective-stack inventory, coherent-owner selection, matched baseline/candidate trials, retirement gate, and fresh-host promotion. This orchestration skill owns scheduling that audit and enforcing its receipt before promotion; do not duplicate its procedure here.

OpenAI's GPT-5.6 guide is decision-changing evidence for invoking that retirement gate: it says intent inference reduces the need to prescribe every step and reports directional internal coding-agent gains from leaner prompts. Treat those figures as motivation, not transferable proof; run the owner's local matched evaluations. Source: https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6

## Framework boundary

Reuse LangGraph/Temporal patterns—durable checkpoints, explicit state, resumable interrupts, idempotent tasks, scoped subgraphs, and replay safety. Keep Kanban as fleet authority. Admit LangGraph only as a task-local executor after it beats the existing native/DAG path on a concrete workflow. LangChain's model/tool/agent abstractions are not the portable contract.

Official references:

- https://docs.langchain.com/oss/python/langgraph/use-subgraphs
- https://docs.temporal.io/develop/python/integrations/langgraph

## Architecture review

Run one bounded adversarial pass for material architecture or irreversible direction: present the strongest credible alternative, attack authority boundaries and failure modes, and seek decision-changing evidence. Stop when objections are resolved or converted to explicit risks/tests. Do not add adversarial theater to routine implementation.

## Stakeholder surface

Push material starts, direction changes, review transitions, genuine blockers/decisions, promotions, and completions to the originating stakeholder surface. Batch routine/no-impact events. Keep briefs free of code, diffs, logs, and internal task vocabulary unless requested.

When Desktop tool receipts are the noise source, distinguish UI rendering from assistant prose. Current Desktop exposes **Settings → Appearance → Tool Call Display → Product/Technical**; Product hides raw payloads but still shows product-level edit/tool receipts. Verify current source before relying on this behavior. Do not add prompt hacks to suppress UI-owned receipts; treat any hide-all/stakeholder mode as a Desktop UX change while preserving approvals and errors.

## Required probes

- quota-limited work resumes after replenishment without a user nudge;
- material events reach the originating stakeholder surface;
- one task resumes in another supported host from its packet;
- stale/lossy summaries cannot overwrite authority;
- any broad surface mutation carries the `cross-agent-surface-engineering` admission/retirement receipt;
- routine execution stays non-adversarial and quiet.
