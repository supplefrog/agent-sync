# Bot Mode behavior parity

Use this reference when a fresh canonical **Bot Chat** behaves differently from a fresh ordinary Hermes session, or when diagnosing what Bot Mode does and does not own.

## Keep the concepts separate

- **Profile:** configuration and persistence boundary for one Hermes agent persona.
- **Canonical Bot Chat:** one Bot-Mode-managed conversation per profile, primarily the stable endpoint for agent-to-agent messages.
- **Regular session under a bot profile:** an ordinary conversation using that profile's identity, tools, skills, and config.
- **Telegram topic/thread:** a regular isolated Hermes session routed through a profile's gateway; it is not the canonical Bot Chat.
- **Bot Mode orchestration:** not implied by Bot Chat. A canonical mailbox plus `message_agent` does not itself create task threads, retain task ownership, monitor delegates, or provide a unified user-facing task queue.

Do not infer that retiring Kanban or another control plane proves Bot Chat replaced its user-facing workflow. Built-in todos, sessions, Goals, cron, delegation, and background jobs are execution primitives; evidence must show that an owning orchestrator actually composes them into the promised UX.

## Diagnose parity before changing prompts

1. Record the exact observed failure and the user's actual question. For several direct questions, check whether each was answered rather than whether adjacent facts were correct.
2. Compare fresh surfaces with profile, model/provider, reasoning effort, SOUL, memory, tools, and user prompt held fixed. Distinguish direct observation from an operator report; model output is stochastic, so use repeated trials only when authorized and worthwhile.
3. Inventory Bot-Chat-only differences before blaming general personality or memory. Current Bot Mode may inject a teammate protocol/roster and the `message_agent` schema only into canonical Bot Chats; verify the installed source because this can change.
4. Test one causal difference at a time. A Bot-Chat-only prompt/tool surface is a suspect, not a root cause, until isolation shows it changes the behavior.
5. Before editing SOUL, memory, or a skill, check whether the existing instruction already requires the desired behavior. If it does, treat the event as noncompliance or a surface-specific regression; do not stack a generic guardrail on top.
6. If a durable instruction change is still justified, classify it before writing: presentation order belongs to communication/style; evidence selection and decisions belong to judgment; task-class procedure belongs to a skill.
7. Preserve rollback and verify in a fresh process/session where the relevant prompt is rebuilt. Do not ask the user to supervise repeated prompt edits.

## Upstream reporting

Keep semantic quality regressions separate from product-orchestration requests. Search existing issues first, state controlled evidence versus user report explicitly, and avoid disposable comparison sessions when the operator has not approved them. A narrow example is [NousResearch/hermes-agent#98321](https://github.com/NousResearch/hermes-agent/issues/98321); verify its current state before relying on it.
