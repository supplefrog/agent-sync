# T3/Codex MCP App adapter

This is a thin supported-host adapter over the existing state store, commands and inline controls. It neither rebuilds T3 nor starts a teacher/model itself. Hermes keeps its existing SDK contribution. T3 uses its existing **Codex provider** MCP Apps; plain html_render alone has no answer callback.

## Portable pieces

- `src/t3/server.mjs`: stdio MCP entry point, using an explicitly selected **already installed MCP SDK1.32.0**. No npm/npx/HTTP server/provider/bootstrap download runs. Both paths in its command are trusted operator configuration, never model input.
- `src/t3/boundary.mjs`: checks transport-level `_meta.threadId` against explicit private enrollment before every data/tool operation. The ID in a learner event, tool argument, browser hostContext, initialize.clientInfo or environment is not trusted. No Hermes alias is created. This is a trusted-local-MCP-client boundary, not authentication against a malicious OS user with the same filesystem access.
- `src/t3/app.mjs` and built `t3/app.html`: MCP Apps2026-01-26 handshake, parent-window-scoped JSON-RPC, reused teach/practice controls, explicit draft persistence, own-server refresh/artifact reads, confirmed owning-thread message delivery. No endpoint/token/raw state is embedded in the resource.
- `src/t3/job-port.mjs`: native Codex spawn/wait/control receipt adaptation, preserving the shared ledger/result/teacher-ack contracts and separate Hermes semantics. It prepares existing host tools only; it launches none.

`learning_view` is a read-only current-state projection and carries the MCP App resource metadata. `learning_input` and `learning_command` are **model-only**, mutating where appropriate, with no UI resource. Private commitments/context cannot be retrieved by this app through those tools. T3 enforces tool visibility on its backend. Draft saves are **app-only/mutating**, never mislabeled read-only to avoid confirmation. A standard Codex MCP tool call's own `_meta` is distinct from an `_meta` key smuggled inside arguments.

## Activation, separate from synchronization

1. Sync only the frozen portable source/manifest through Agent Sync. Do not capture profile databases, chats, credentials, grants, current owner IDs, private bindings or lesson/export/draft files.
2. Read `t3/codex-mcp.example.toml`, leave it disabled, and resolve the stable local Node24/package/existing-SDK runtime locations on that device. There is no portable hardcoded Windows path. Registering/enabling this MCP process and its filesystem scope is a separate explicit operator action, not a side effect of sync.
3. Create a **private** version1 enrollment from `t3/bindings.example.json` outside the source. The selected native Codex thread ID must come from host-written metadata (`learning_identity`), then be enrolled by the authorized operator. T3's UI thread ID need not equal its underlying Codex thread ID. No implicit first-caller enrollment, fallback owner, broad history scan or model configuration rewrite occurs.
4. Start only through the supported T3/Codex MCP declaration after access/data authority is clear. A missing SDK, mismatched SDK version, missing caller metadata, unknown owner or inactive/stopped origin session fails closed. This source work did not register/start anything.
5. The existing agent follows `t3/AGENT-PROTOCOL.md`: view; exact genuine lh.t3 input; existing state/reaction tools; real rich teaching reply; fresh view. T3 confirms app messages and mutating app tools under its normal policy. No auto-approval, model-retry or invisible wake is installed.

The operator must read the actual Codex child limits and tool definitions before any future worker invocation. The source-pinned Codex native port prepares spawn_agent/message/fork_context, wait_agent/targets, send_input/target and close_agent/target. It does not promise that every installed Codex build exposes that variant, impose Hermes limits on Codex or infer a paid child grant from an MCP registration.

The local MCP process has its normal OS-user privileges; it is not an operating-system folder sandbox. This implementation restricts tool/data paths to explicit private enrollment, while the trusted existing SDK is ordinary executable dependency code. Source sync must not silently grant or broaden that process access.

## Durable state and presentation differences

The same atomic lesson store preserves assessment, plan, commitments, answer history, reaction claims, teaching, practice and pending questions. Raw commitments stay teacher-only. The UI sends a genuine event to the owning agent through T3's confirmed ui/message; a successful send is delivery, not a save. Normal state/result/replay checks still decide persistence. Read-only refresh/reopen does not fabricate another model turn.

Unsent typing is cached in the mounted app. **Save draft privately** explicitly persists it under the raw-state root's `.t3-drafts` directory after the normal app-tool confirmation. Drafts have owner/lesson/question identity and atomic revision-CAS; stale writes refuse instead of overwriting a newer card. Refresh does not replace newer unsaved local text with an older stored copy. Typing is not sent into T3's next-turn model-context notes. Closing before explicit Save can lose local-only typing; opaque app frames cannot use ordinary localStorage and auto-save would otherwise ask permission on every change. Draft files/tombstones are retained privately; source sync never includes them.

Teacher Markdown/math/Mermaid uses T3's ordinary assistant rendering. The app reuses the authoritative plain-text controls/working traces. Saved research/PDF briefs and verified SVG images can appear in the app. The host's default MCP App CSP blocks nested demo iframes; an explicit learner request routes an existing demo to T3's native visual publisher via the model-only learning_artifact_source tool. Do not weaken CSP, fetch code, regenerate the artifact or claim live rendering/verification. App bridge payloads are bounded; large assets need the existing native visual route.

## Evidence and limits

The baseline Hermes source was independently reviewed and exercised in one real native teaching interaction. The T3 adapter has an offline static resource build from the existing esbuild0.28.2 toolchain. No new live host, child, model or learner test ran. The user explicitly accepted component-based T3 compatibility; that acceptance is not an empirical result. Normal T3 every-message confirmation, Codex-only MCP Apps and stopped-origin-session refusal are retained. This is not a universal-host or learning-outcome claim.

Source interfaces and exact pins are in `t3/SOURCES.json`. Review this successor before deployment. Current closed-trial grants do not enable it.
