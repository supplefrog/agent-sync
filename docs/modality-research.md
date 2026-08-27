# Modality research ledger

This is the current design comparison, not a claim that every row is already converged. `contracts/surface-matrix.json` is the machine-readable contract; compact run results are the proof.

| Modality | Portable candidates compared | Selected direction | Rejected or deferred | Current gate |
|---|---|---|---|---|
| Instructions and style | identical global file; per-host prompts; one semantic contract with host-native placement | Small `surfaces/core.md`; Codex tree scoping and Hermes personality/session behavior stay native | File identity as parity; duplicated policy; replacing scoped instructions with one global prompt | Staged; convergence development and held-out suites are running on both hosts |
| Skills and procedures | copied prompt fragments; host plugins; Agent Skills tree plus discovery adapters | One Agent Skills-compatible `skills/` tree; link only admitted directories | Copying into divergent stores; plugin-only portable core; exposing the whole staged tree | Staged; standard format and trigger/admission behavior require cross-host proof |
| Tools and MCP | force all tools through MCP; host-native only; shared tool contract with MCP where practical | Portable intent and acceptance tests; MCP for viable shared external tools; retain native core tools | Universal core-tool schema; replacing better native tools solely for symmetry | Unassessed; research contract exists, implementation suites not yet admitted |
| Routing and delegation | fixed model names; one weak worker; risk-tier intent mapped per host | Shared task-risk and verification policy; model IDs, effort, fallbacks, pools, and collaboration remain host-native | Fixed weak route for judgment; pretending Codex and Hermes expose identical orchestration | Unassessed; Hermes and Codex mechanisms are mapped, behavior suite is pending |
| Memory and context | synchronize raw state; no portability; public semantic/evidence layer plus local private memory | User/session memory stays host-local; repository preserves only public contracts, findings, and contradictions | Publishing `USER.md`, `MEMORY.md`, thread state, sessions, or transcripts | Unassessed; held-out privacy case exists, full modality suite is pending |
| Policy and security | universal hook schema; instruction-only policy; portable outcomes with native enforcement | Shared safety outcomes and adversarial tests; native sandbox, approvals, hooks, redaction, and managed policy | Universal hook translation; secret-bearing config; claiming equal guarantees without tests | Unassessed; held-out hook boundary exists, enforcement suite is pending |
| Planning and automation | universal task object; lowest-common-denominator checklist; portable plan contract with native durable execution | Outcomes, dependencies, and checks are portable; Hermes cron/goals/gateway and Codex plan/non-interactive flow remain native | Removing durable Hermes features; calling an unsupported scheduler equivalent | Unassessed; scheduler delta development case exists, durability suite is pending |
| Lifecycle and update | copy-on-install; whole-tree discovery; admitted-only links plus version/hash audit | Registry-gated links, declarative adapters, compact summaries, `audit.py`, public scan, rollback | Activating staged candidates; raw transcript commits; evidence without artifact hashes | Staged; deterministic tests pass and cross-host convergence evidence is running |

## Current primary-source anchors

| Surface | Hermes v0.19.0 / upstream `1161cc0b` | Codex CLI 0.146.0-alpha.3.1 / source `20dafe2…` |
|---|---|---|
| Instructions | [configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) | [AGENTS.md](https://github.com/openai/codex/blob/20dafe201d91d4405eef05ecd1db0257f13a9ac8/docs/agents_md.md) |
| Skills | [CLI and skills lifecycle](https://hermes-agent.nousresearch.com/docs/reference/cli-commands) | [skills](https://github.com/openai/codex/blob/20dafe201d91d4405eef05ecd1db0257f13a9ac8/docs/skills.md) |
| Tools / MCP | [MCP](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp) | [MCP refresh implementation](https://github.com/openai/codex/blob/20dafe201d91d4405eef05ecd1db0257f13a9ac8/codex-rs/app-server/src/mcp_refresh.rs) |
| Routing | [configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) | [model manager](https://github.com/openai/codex/blob/20dafe201d91d4405eef05ecd1db0257f13a9ac8/codex-rs/app-server/src/models.rs) |
| Memory | [memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory) | [memory reset test](https://github.com/openai/codex/blob/20dafe201d91d4405eef05ecd1db0257f13a9ac8/codex-rs/app-server/tests/suite/v2/memory_reset.rs) |
| Policy | [configuration and safety controls](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) | [config](https://github.com/openai/codex/blob/20dafe201d91d4405eef05ecd1db0257f13a9ac8/docs/config.md), [execution policy](https://github.com/openai/codex/blob/20dafe201d91d4405eef05ecd1db0257f13a9ac8/docs/execpolicy.md), [sandbox](https://github.com/openai/codex/blob/20dafe201d91d4405eef05ecd1db0257f13a9ac8/docs/sandbox.md) |
| Planning / lifecycle | [CLI commands](https://hermes-agent.nousresearch.com/docs/reference/cli-commands) | [plan item behavior](https://github.com/openai/codex/blob/20dafe201d91d4405eef05ecd1db0257f13a9ac8/codex-rs/app-server/tests/suite/v2/plan_item.rs), [config manager](https://github.com/openai/codex/blob/20dafe201d91d4405eef05ecd1db0257f13a9ac8/codex-rs/app-server/src/config_manager.rs) |

## Stage rule

A modality advances from `unassessed` to `staged` only when a candidate artifact and development suite exist. It advances to `confirmed` only when current baseline-versus-candidate and fresh held-out summaries pass on every required host with matching artifact hashes. A contradiction, unsupported mapping, or useful native asymmetry stays explicit.
