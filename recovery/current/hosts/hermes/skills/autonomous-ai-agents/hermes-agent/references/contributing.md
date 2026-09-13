# Contributing to Hermes Agent

Load this reference only for source inspection or an authorized Hermes source/docs change. Current developer authority: <https://hermes-agent.nousresearch.com/docs/developer-guide/> and the live repository at <https://github.com/NousResearch/hermes-agent>.

## Establish the source surface

1. Identify the exact checkout, revision, install type, host, and product surface affected.
2. Reproduce against that surface. Desktop, classic CLI, Ink TUI, dashboard, and gateway can share core code while retaining distinct launchers and handlers.
3. Inspect current source before naming files, registries, APIs, or commands. The legacy project-layout and extension snippets removed from the entrypoint may no longer match the checkout.
4. Keep source edits separate from active profile state unless the task explicitly requires migration/config fixtures.

## Cache and context boundary

Preserve cache-stable prompt prefixes and stable tool-schema boundaries where the runtime depends on them. Do not mutate a provider request's tool schema or stable system-prompt structure mid-conversation through an unsupported path; use the runtime's supported reset/rebuild boundary.

This is not a prohibition on context evolution. Skill loading, retrieved evidence, user messages, tool results, context files, supported compression, and other ordinary conversation evidence may enter context through their supported mechanisms. Test both caching-sensitive stability and on-demand skill/evidence behavior when touching prompt construction.

## Extension rules

- Follow current architecture and contributor docs; do not rely on the removed “three files” or registry recipes without source verification.
- Resolve profile-safe state paths through the current Hermes home/path API; never hardcode `~/.hermes` or this user's Windows path in product code.
- Keep secrets in supported secret storage and test fixtures; never use live profile credentials.
- When adding or changing a tool, verify requirement gating, schema stability, error serialization, authorization, and every consuming surface required by current source.
- When changing a slash command, inspect the current command registry and each relevant frontend/gateway consumer instead of assuming automatic parity.
- Preserve message/provider invariants demonstrated by current code and tests; do not perpetuate an undocumented legacy rule solely because it appeared in the old skill.

## Scoped testing

For a focused source change:

1. Add or run the regression test for the reported behavior.
2. Run targeted tests for the changed subsystem.
3. Run nearby subsystem tests when shared behavior is touched.
4. Run a broader local suite only when it is practical and known-clean; CI owns the authoritative supported matrix.
5. Report unrelated baseline/platform failures separately rather than hiding them or treating every one as caused by the patch.

Before invoking pytest, inspect the checkout's contributor docs and test configuration. Historical commands such as clearing baked-in pytest options with `-o 'addopts='` may still be useful, but must be verified in the current repository. Tests must redirect `HERMES_HOME` to an isolated temporary location; verify that isolation rather than assuming it.

## Product verification

Test the changed behavior on every named surface in scope, not every Hermes frontend by default. A classic-CLI handler test does not verify Desktop, TUI, dashboard, or gateway behavior. For cache/tool changes, include a stable-prefix/schema check and a supported new-session/rebuild check; for skill/context changes, include successful on-demand loading or evidence incorporation.

Document exact tests run, results, untested platform/surface paths, and CI coverage still required.
