# Current native skill selector and execution calibration

Rebased onto native Hermes revision `d0288be5b3330d2442e3907185b8e9d0958297bb` (0.21.5+2453.gd0288be.dirty). The exact baseline and applied hashes are in manifest.json. This replaces the earlier 9fe737a selector bundle; do not apply historical whole-file candidates to current source.

Normal-session skill loading now requires an explicit request or material specialist/local value. Duplicate catalog maintenance coaching is removed; standing authoring routing, tools, discovery, organization collisions, compact categories, and the one-shot branch remain native. Execution guidance scales checks to the affected behavior, narrows arithmetic tool use, resolves real prerequisites, preserves prior authorization, and asks only for material missing information. External-write readback and literal-preservation sections are byte-identical between baseline and candidate.

## Installation and rollback

This is an exact-base manual native prerequisite, not automatic updater enrollment. Require the recorded native revision and both before-hashes, check the patch on a disposable copy, and apply with `git -c core.autocrlf=false apply`. Require both after-hashes. Preserve unrelated native edits. Rollback requires both after-hashes, reverse-check on a copy, then `git -c core.autocrlf=false apply --reverse`; require both before-hashes. Stop and rebase on any drift.

Start a fresh Hermes process to load changed modules. Active conversations were not restarted; existing assembled prompts can persist.

## Evidence

- Baseline and candidate each passed 51 tests through the native per-file isolated runner: external skills, project skills, organization namespaces, one-shot footprint, and guidance-content filtering. UTF-8 was enabled for Windows Unicode fixtures; retries were disabled.
- Fresh public prompt-builder probes preserve one-shot output and external-state/literal-preservation section hashes. Normal output changes from broad loading to selective loading, with explicit material ambiguity and proportional verification.
- Exact patch apply/reverse and target hashes are verified separately before completion.
- Prior 9fe737a evidence reported 67 tests; those results are historical, not a count for this revision. No inference, model-quality gain, cross-provider parity, or automatic update survival is claimed.

MIT provenance and license remain in ../LICENSE.
