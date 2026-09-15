---
name: repository-inspection-audits
description: Use when inspecting repositories or building audit checks.
version: 1.0.2
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [repository, inspection, audit, validation, metrics]
---

# Repository Inspection and Audits

Use this umbrella for repository-wide inspection, measurement, compliance, evidence, and validator work. Load only the branch relevant to the requested audit; specialist pilot procedures are not prerequisites for ordinary repository inspection.

## Routing

- Audit/compliance CLI design, manifests, ledgers, snapshots, complete fixtures, cross-host evidence, and run/session authority: [repository audit validation](references/repository-audit-validation/SKILL.md).
- Hermes memory-vs-skill persistence-routing audit: [persistence routing audits](references/repository-audit-validation/references/persistence-routing-audits/SKILL.md).
- LOC, language, file-count, and code/comment composition with pygount: use the top-level `codebase-inspection` skill.
- Frozen-review drift and concurrency probes: [frozen review](references/frozen-review-drift-and-concurrency.md).
- Complete agent/conversational-OS systems, durable identity, executor swaps, event integrity and recovery: [intact-system evaluation](references/intact-system-evaluation.md). Establish the repository/git/manifest baseline first; distinguish source, test and real runtime evidence.
- Verification gates with mutable criteria, freeze receipts, role isolation, pilot manifests or typed test-author artifacts: [grounded-verification probes](references/grounded-verification-adversarial-probes.md).
- Pilots claiming provider execution, checkpoint forks, image identity or container security: [winner-pilot verification](references/winner-pilot-verification.md), including all helper containers and separate process/concurrency layers.
- An assigned Kanban task: [delegated handoff](references/delegated-kanban-handoff.md). Use native `kanban_*` tools, not CLI or direct persistence. Missing task context in ordinary chat is not a board defect. Complete implementation to release a pre-created review child; otherwise use same-card review when required. A refusal returns to the parent without an equivalent-command bypass.

## Shared workflow

1. Define the inventory or contract and authoritative repository scope. For manifest-driven capture, independently enumerate the current owner trees before comparing declared files; a clean manifest diff cannot reveal newly installed packages or previously excluded paths whose content and license changed. Classify additions, removals, and exclusions before refreshing hashes.
2. Exclude generated, dependency, cache, and build trees during traversal, before collecting or printing paths; filtering only after enumeration floods review with installed dependencies.
3. Inspect test setup and cleanup before running unfamiliar migration/updater suites: search for `git init`, `git config`, commits, checkout/reset, and deletion paths. Run repository-mutating fixtures in an isolated copy with its own `.git`, not the user's working checkout; path-string comparisons can misclassify the real repository as a fixture. Canonicalize both paths before comparing Git's toplevel with the process cwd. Then build a complete valid baseline fixture before mutating one rule per negative test.
4. Prefer exact source paths, schema versions, artifact hashes, and live CLI output.
5. Distinguish absent, stale, configured, passing, and runtime-verified evidence. For recovery audits, separate captured source from installable capability: inspect local-file dependencies in manifests and lockfiles, and identify required artifacts omitted by capture policy before claiming the restored route works.
6. Run the real production command and verify generated snapshots/reports are reproducible. Compare fresh source and restored discovery sets, not just counts or declared-file hashes; equal counts can hide a missing package replaced by an unexpected one.

Keep metric inventory separate from compliance verdicts unless the contract explicitly connects them.

For manifest-driven updates, preserve the original revision, local changes, and user-artifact hashes before apply; a backup branch alone does not capture ignored files or uncommitted content. After an old-to-new jump, verify the target manifest's files and dependencies, not just the version banner. If a second pass is necessary, retain the original rollback handle separately because the newest backup may contain only an intermediate installation. Diagnose same-version drift with a manifest-scoped diff and compare materialized entrypoint content with its canonical target before reapplying; platform-compatible file representations can differ from upstream without missing functionality.
