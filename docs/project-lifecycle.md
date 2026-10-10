# Project lifecycle

`breadcrumb-records` is the existing shared owner for proportionate project promotion, organization, continuation and closeout. The short managed standing rule loads it when work grows or reaches a handoff. This is model guidance, not a background watcher. Its optional helpers automate explicit file recovery and native Codex association after the agent resolves scope and ownership.

Promote work when continuity, related outputs, reused sources, another maintainer or consequential operational context makes a durable root useful. Reuse an existing project first. A casual idea and a bounded correction do not need a new project. Follow the project's ecosystem and keep one discoverable continuation record; use an ADR only for a decision a maintainer may revisit. Preserve reusable, evidenced procedures at their existing instruction owner, and project-specific context beside the work.

This follows the qualitative continuity and shared-source criteria in [OpenAI's Projects guidance](https://learn.chatgpt.com/docs/projects), the externalized state and verification practices in [long-horizon Codex guidance](https://developers.openai.com/blog/run-long-horizon-tasks-with-codex), and the significant-decision scope in [AWS's ADR process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html). These sources do not prescribe a universal folder tree or a mandatory set of planning files.

## Native association and recovery

See [host adapters](../adapters/project-lifecycle.md) for current native contracts, the Codex preview/apply helper, and unsupported states. Codex's installed experimental API can persist project membership independently of the thread's cwd. Hermes exposes different project/session operations; those instructions are source-inspected but live association was not tested in this change. Neither association nor moving files establishes permissions, active runtime cwd or UI refresh. Never edit conversation databases as the automatic fallback.

The [artifact helper](../skills/breadcrumb-records/references/task-artifacts.md) registers exact owned files, previews recovery, archives with hashes and restores without overwriting new work. Ownership, completion, references and active users remain agent checks. It rejects changed files, overlapping claims, control paths and links; retains a journal and recovery across interruption; and provides no purge. Unrelated and unfinished files remain with their owners.

## Conflict audit

| Surface | Decision and reason |
| --- | --- |
| Shared `breadcrumb-records` | Extend the admitted continuity owner instead of adding a competing lifecycle skill. Preserve the original record CLI/schema. |
| Shared `project-prior-art` | Preserve conditional reuse research; clarify that conventions and consequential decisions belong beside the project. |
| Hermes native `session-librarian` | Replace only the blanket reconfirmation paragraph through the native review queue. Existing authorization now covers reversible workstream organization; destructive and profile/access gates remain. |
| Codex local `project-bootstrap` | Retired at the user's request on 2026-10-10. `breadcrumb-records` remains the continuation owner; the AGENTS-first layout, line quotas, repeated blanket status checks and prescribed next command were intentionally discarded. The earlier retention decision is historical. |
| Prior retirements | `advise-project-approach`, `conversational-communication` and the disabled `one-three-one-rule` were retired/disabled before the original lifecycle change. The dated evaluation receipt preserves those earlier decisions and records subsequent Codex-local retirements separately. |
| Frontend owners and accepted comparison evidence | Preserve unchanged; this change contains no frontend selection or taste revision. |

The native skill's captured recovery artifact and manifest hashes record the reviewed paragraph change. No plugin cache is edited. [Evaluation receipt](../evals/results/project-lifecycle-2026-10-05.json) distinguishes automation tests, explicitly loaded behavioral probes and untested host behavior. Private task fixtures and native receipts stay outside publication.
