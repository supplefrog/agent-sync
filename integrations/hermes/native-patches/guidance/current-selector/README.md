# Current selective skill loading and authorized maintenance

Native base: `6590f13a1ba21b18224a0f53ef2ead004b5fa7d6`. Installed local commit:
`bfb88d3cff115387c172c22818107b7395ad7c97` on `local/selective-skill-guidance`.

The interactive skill catalog loads requested or materially useful knowledge and required
protocols. General topical overlap alone requires no load. The catalog, skill tools,
one-shot branch, compaction reload rule, and approval checks remain available.
Successful task completion alone requires no skill or instruction write. Memory writes
require an explicit user request and native approval.

## Update preservation

Keep this change committed on the local branch with native
`updates.parked_branch_strategy: update_in_place`. The existing updater merges ordinary
`origin/main` updates into that branch while preserving local commits. A deliberate branch
or release-channel switch can leave the branch; it is outside this preservation claim.
Overlapping upstream edits can produce a visible merge conflict that must be resolved
without restoring the broad skill-loading or success-based learning clauses.

The regression tests in this patch guard those clauses through actual prompt construction.
Do not reapply historical whole-file prompt builders or the older update-engine bundle.

## Exact-base recovery and rollback

On a clean native checkout at the recorded base, require the before-hash in manifest.json,
check this patch on a disposable copy, create the local branch, and apply
`git -c core.autocrlf=false apply selector.patch`. Require both after-hashes, run the native
test command, and commit the two paths. Retain the existing update-in-place setting.
For rollback, require the after-hashes and check `git apply --reverse` on a copy first.
Stop and rebase on revision or hash drift. Preserve unrelated native edits.

Native settings are captured separately in `recovery/current/hosts/hermes/config.json`:
curator and periodic background review off; memory and skill nudges off; memory writes
approval-gated; skill writes approval-gated; existing memory reads enabled.

Start a fresh Hermes process to load changed modules and standing instructions.
Existing sessions retain cached prompts; they were not interrupted.

## Verification and limits

- The two new prompt regressions failed on the base and passed on the candidate.
- The native isolated runner passed 180 tests, with four Windows skips, across prompt
  construction, skill discovery, native Git update preservation, and write approvals.
- Pinned Ruff 0.15.10 and all 11 native `scripts/check` checks passed.
- Exact patch application/reversal, target hashes, and a later upstream merge passed on
  a disposable Git copy. Installed readback is recorded in the selected repair receipt.
- These are source, mechanism, and installation checks. No new provider inference,
  model-quality, latency, or cost claim is made.

The previous d0288be selector evidence is retained in manifest.json as historical evidence.
MIT provenance and license remain in ../LICENSE.
