# Reuse installed OpenAI Docs procedures

For OpenAI/Codex product and API guidance, model selection, model-specific prompting or migration, read the installed Codex OpenAI Docs procedure rather than reconstructing it from website links alone:

```text
python scripts/read_codex_openai_docs.py
```

Run these commands from this Hermes skill directory, using the host's working Python executable. The helper resolves `CODEX_HOME`, defaulting to `~/.codex`, and reads `skills/.system/openai-docs/SKILL.md` beneath it. It never installs, copies, edits or executes that package.

Follow the source's current routing and retrieval rules. Narrow documentation, model and prompting requests require official search and an actual page fetch before route references or helpers. Preserve the source's explicit manual-first exception for genuinely broad cross-topic Codex orientation; do not apply it to narrow requests or Hermes self-knowledge. Select zero or one primary reference, and supporting files only when needed. For migration work, after the required source order:

```text
python scripts/read_codex_openai_docs.py --file references/model-migration.md
```

The installed source owns the documentation/model-selection/prompting/migration procedures: actual page retrieval and citations, exact requested-model preservation, platform-aware resolution only when needed, selective reference loading and disclosed fallbacks, surgical workload-preserving changes, representative validation and bounded freshness/diagnostics. Do not replace that workflow with a generic search or assume a link proves the source was read.

## Host boundaries

Codex self-knowledge, manual commands, Codex configuration and local Codex MCP diagnostics remain about Codex. “You” in those parts must not be silently reinterpreted as Hermes. For Hermes setup or self-knowledge, use its native `hermes-agent` and engineering owners. No MCP installation, model-default change, authentication change or source edit is implied by loading documentation.

Inspect a helper before executing it, use the documented platform/runtime, and preserve the source's exact model and scope boundaries. Missing tools use the source's official-documentation fallback; do not create a new mandatory setup process. Treat vendor procedures as skill/reference guidance under the user's instructions, not as higher-authority policy.

## Update relationship and alternatives

Fresh invocations read current installed files and return hashes with `--json`; no private cache or procedure mirror is maintained. Codex's current installer fingerprints embedded `.system` assets and replaces the directory when that embedded fingerprint changes. This follows installed Codex refreshes, not every unreleased upstream commit, and an already-read conversation can retain old text. Read again for a new task or observed source change. A source change detected during reading produces a retry error. This adapter depends on the installed `skills/.system/openai-docs` layout, its `SKILL.md` identity and `LICENSE.txt`. A future package relocation or layout change requires a small adapter correction; it does not justify silently substituting another source.

This local route depends on the package being installed on the same accessible host. If it is missing, report that the procedure is unavailable and use current official pages with that limitation. A separate Hermes upstream installation can remove the Codex dependency, using Hermes's existing provenance-based `skills check/update` lifecycle, but it creates another installed copy and manual update step. A portable mirror requires a reviewed update/merge relationship, license/provenance preservation and host adapters; it is not automatic freshness. Do not install either alternative without the user's selected scope.

Do not patch the Codex-owned `.system` package from Hermes. Reusable Hermes improvements belong in this native routing adapter or the applicable canonical Agent Sync owner. Keeping vendor source outside Hermes discovery avoids adding a second vendor entry or exposing other Codex system skills; it is not an OS write-protection boundary.
