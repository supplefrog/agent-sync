# Native skill recovery

Agent Sync can preserve reviewed host-local skill customizations without promoting them into the shared skill fleet. The host remains the editing owner; `recovery/current/` is a captured recovery artifact, not a second source to edit.

## Captured Hermes packages

The explicit text-artifact allowlist now covers the inventoried Hermes catalogue: 101 packages and 859 package files, plus bundled-origin metadata. [The inventory](../recovery/hermes-local-inventory.json) records every included file and exclusion. Examples include:

- `mcp/native-mcp`: narrowed server setup and connection troubleshooting.
- `research/research-source-operations`: paper lookup, source acquisition, supporting scripts and references.
- `research/grounded-citations`: citation ledger and consolidated paper-owner routing.
- `research/osint-investigation`: public-records helpers and consolidated paper-owner routing.
- `mlops/llm-operations`: the complete umbrella and nested provider references, retained while disabled.

The settings snapshot separately preserves skill enablement, including the parked standalone arXiv, Collective Wisdom, and LLM Operations entries. Capturing a disabled package does not enable it, execute its scripts, or authorize downloads/model inference.

The initial five-package capture was expanded to preserve the curated installation, including disabled content and modified defaults. Shared admitted skills remain owned by `skills/`; host-local copies are recovery artifacts only. Legacy restricted PowerPoint support content, binary/generated files, private state, and uncaptured runtime dependencies remain excluded. The rewritten MIT PowerPoint entrypoint, license, five Python helpers, tests, and advanced authored text are captured; the old restricted files are not relicensed or reintroduced. This is not a byte-for-byte machine image. Never infer completeness from a successful restore of an incomplete allowlist.

### Advanced PowerPoint dependency limit

The advanced authoring source depends on the locally repacked `advanced/vendor/pptxgenjs-4.0.1-no-image-size.tgz`. Binary archives and `node_modules` are outside this text-only snapshot. A receiving host must separately obtain that exact reviewed archive and verify SHA-256 `5da3292648212b2c310c7dfce39cd2c86f20055a3e4dbf43b54701bc8166e220` against the captured `advanced/vendor/provenance.json` before installing the locked dependencies. `npm ci` cannot reconstruct the advanced route from this snapshot alone. Do not substitute the unmodified upstream archive: it is not the recorded dependency graph. Basic Python operations require their separately installed Python dependencies; actual rendering and visual review remain unverified until a renderer is available.

## Native plugins and prerequisites

Plugin selections and override controls are captured independently of source. LCM includes 70 reviewed runtime/manifest/license/bundled-skill files, with its original native patch records retained as provenance. No LCM database, conversation history, vector index, or session sidecar is copied. Snapshot hashes bind canonical public text; source inventory hashes record source bytes, which may have different line endings.

`routed-delegation` stays at `integrations/hermes/routed-delegation`: its repo-relative imports require a native plugin directory link to that owner, not a copied plugin folder. Set up that prerequisite on the receiving host before `bootstrap --host hermes --apply`. Hermes and native Python dependencies must already be installed and authenticated locally where needed. Native Hermes source patches remain explicit prerequisites rather than an automatic runtime installer.

An explicitly reviewed `capture_mount` permits reading linked native source. It never authorizes restore writes through that link. A matching linked installation verifies cleanly; a differing owner must be reviewed and edited at its source. Restoring to an ordinary new plugin directory remains supported.

Use the [selected-host recovery procedure](recovery.md) and the [verification receipt](hermes-recovery-verification.md). Hermes-only recovery does not configure Codex or OMP. The receiving agent must adapt OS-specific executable settings rather than assume every Windows integration is available elsewhere.

## Keeping local edits recoverable

When a task changes a reviewed native package, include its complete scripts, references, templates, and applicable license notices in the recovery inventory. Add new support files explicitly, and review removed files instead of silently dropping knowledge. Do not copy bytecode, dot-state, usage/curator records, logs, caches, sessions, source data, or credentials.

Run the normal reconciliation path after the edit: review the proposed recovery capture, public-safety findings, and exact publication scope; then sync and verify. Existing allowlisted file edits are captured by that path. New or previously unreviewed files need allowlist review first. A local edit alone does not update the remote hub.

Restore conflicts remain review-required. Reviewed `replace_sha256` values permit replacement of an exact stock-text version, not arbitrary local edits. Inspect unexpected differences at the owner; do not use a broad force operation simply to claim a clean clone.

## Provenance and redistribution

Preserve the original package authors, license metadata, and linked sources. Locally adapted entrypoints and routing have been modified; this snapshot is not an assertion that upstream endorses those changes.

- Hermes-derived content: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent), MIT, copyright (c) 2025 Nous Research.
- OSINT adaptation: [ShinMegamiBoson/OpenPlanter](https://github.com/ShinMegamiBoson/OpenPlanter), MIT, copyright (c) 2026 OpenPlanter Contributors. The installed Hermes optional-skill documentation identifies the adaptation as MIT.
- LLM provider references identify Hugging Face and Orchestra Research as authors and declare MIT in their preserved entrypoints. The Orchestra source is [orchestra-research/AI-Research-SKILLs](https://github.com/orchestra-research/AI-Research-SKILLs), MIT, copyright (c) 2025 Claude AI Research Skills Contributors. The locally authored umbrella is retained as local workflow content; it does not replace any upstream licensing.

### MIT license notice

Copyright (c) 2025 Nous Research

Copyright (c) 2026 OpenPlanter Contributors

Copyright (c) 2025 Claude AI Research Skills Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
