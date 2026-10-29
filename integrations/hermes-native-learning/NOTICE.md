# License and source provenance

AGPL-3.0-only. See LICENSE. This integration derives state contracts, question behavior, plan algorithms and interaction decisions from LearnHarness by Amos Blomqvist and contributors:

- https://github.com/amosblomqvist/learnharness
- v0.3.4, commit `6cba9c8c5afe8a63f47ea4ebae6e91d8a205cebb`
- original sources: `src/core/question-core.ts`, `input-events.ts`, `contracts/chat.ts`, `contracts/probe.ts`, `native-messages.ts`, `plan-tree.ts`, `src/agent/tools/mermaid-plan.ts`, and practice contracts/pure functions.

`src/vendor/runtime` contains extracted pure algorithm/contract portions, with local import adaptation. `src/adapter.mjs`, `practice-state.mjs`, `store.mjs`, and inline clients are the existing state/UI port. The portable configuration, command wrapper, desktop entry and synthetic controls are integration changes. This is not the upstream pi/Electron runtime. Preserve upstream attribution and provide corresponding source when distributing the bundle under the license.

`reference/` retains the pinned upstream prober, planning, teaching-cycle and practice prompt text (Markdown), with source paths/hashes in REFERENCE-SOURCES.json. Host-specific command adaptation and unsupported-tool restrictions are in the opt-in skill; these source prompts do not install tools or authorize extra model actors. The workflow projection, paused-practice discussion and SDK rich-prose composition are additional integration changes.

`src/vendor/runtime/target-pure.ts` retains the exact resolveTargetId function body from pinned src/core/chains.ts, with only a type alias/import adaptation. The read-only native proposition projection follows the existing LearnHarness reader's v1 format/first-identity semantics, but fails closed on malformed data instead of skipping it. It is not a second graph store or extractor.

Delivery owner is the user's existing Agent Sync project. The earlier proposed standalone fork publication is superseded; this package does not grant a push, activation or settings import. Upstream LearnHarness attribution remains intact. No endorsement by upstream Hermes, T3 or LearnHarness is implied.

The T3 adapter is original integration code over the retained learning components. It follows the cited MCP Apps/T3/Codex public interfaces in t3/SOURCES.json and loads an explicitly selected existing MIT-licensed MCP SDK1.32.0 at runtime; that SDK and T3/Codex application source are not vendored or bundled. The generated T3 resource contains only this integration and the already attributed LearnHarness pure/UI code.

`src/vendor/runtime/{coverage,graph,chains,session-clusters,clusters}.ts` additionally retain the complete pinned upstream pure core file bodies, with SPDX/provenance headers. Teacher-prose selection, batching, identity union, argument simplification and graph derivation are reused rather than redesigned. `knowledge.mjs` adapts their storage ports to the integration's existing atomic file store; it does not copy the upstream global filesystem composition, destructive legacy purges, model pipeline or Electron runtime. Its optional private knowledge record is not an automatic migration of a standalone/native JSONL graph. See docs/KNOWLEDGE.md for data, role separation and permission limits.

SDK compatibility was inspected against Hermes `5b32cfc230078417fc523e12b9aabbc9b59f684b` and the official Desktop Plugin SDK documentation: https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk . Runtime compatibility must be rechecked on the actually loaded version. React and the SDK are host imports, not vendored copies.

`job-pure.ts` retains pinned job contracts, result-steer and usage helpers, excluding the unrelated runtime probe-handoff helper/import. `notes-pure.ts` retains the pinned notes chunking function. `demo-pure.ts` retains the pure srcdoc bridge and resize/error reducer from the pinned demo card, excluding its React component. Integration code adds explicit enrollment, result identity/generation checks, browser containment and honest host-verification wording. These adapted pure portions and their original paths are recorded in REFERENCE-SOURCES.json. No upstream actor runner, Electron runtime, model client or global composition was copied.
