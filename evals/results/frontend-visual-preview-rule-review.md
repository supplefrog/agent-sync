# Frontend visual-preview publication gate

## Scope and evidence limits

Canonical owner: `skills/frontend-ui-engineering/SKILL.md` (3.1.0); adjacent owner: `references/taste-selection.md`. Reviewed `references/motion-design.md` without editing it: its playback/performance checks are internal verification, not user delivery. The new entrypoint gate covers motion with a playable artifact without duplicating the motion procedure. No project-specific emboss setting becomes a portable preference. No fop-learning, global config, or memory edits.

This is a source-contract walkthrough and deterministic structural check, not an autonomous model evaluation, natural-trigger experiment, or visual-quality comparison. No paid model evaluation was run. The parent owns the real visual demo independently.

## Trigger/load check

The effective Hermes instruction surface supplied to this run requires loading matching or partially relevant skills before replying. The existing discovered frontend description explicitly covers modifying production interfaces/pages: a numerical appearance refinement matches before any UI edit. `skill_view(name='frontend-ui-engineering')` succeeded and resolved the shared user skill root's `frontend-ui-engineering/SKILL.md`, version 3.0.0. That proves availability/loadability, not reliable future autonomous selection. The live body still exempts routine repairs from taste selection and lacks the new publication gate. Canonical source has the broader pending frontend/prototype trigger; this task did not change its description or host instructions. No UI edit was performed by this worker.

## Failure replay and nearby cases

Walkthrough method: apply the actual baseline and candidate decision rules to the same supplied facts. These are reasoned instruction-contract outcomes, not executed browser or model outputs.

| Prompt/facts | Baseline | Candidate decision |
|---|---|---|
| User approves a numerical emboss refinement on an existing UI; internal browser screenshots/tests pass; no result shown to user | Routine repair/approved direction skips style selection; delivery checklist does not require user-visible preview | Render representative changed content, deliver a viewable artifact, and await approval before deployment-triggering push. Requested number and internal checks do not approve unseen treatment. |
| Repair a data retry/cache bug while preserving the UI appearance | No new taste-selection exercise required | No visual preview or taste selection required. Run relevant functional/regression checks and use existing publication authorization. If the repair changes appearance, reclassify it. |
| User already saw and explicitly approved the exact rendered treatment | Approved direction skips style selection | Do not demand another identical preview; retain evidence of that approval, verify implementation matches it, and publish only within existing authorization. |
| User explicitly waives preview/review for the visual tweak | Delegation permits a provisional direction | Explicit waiver satisfies this gate; other checks and publication authorization remain. |
| User delegates style choice or says to skip comparisons, without waiving preview/review | Can choose provisional style | Choose one treatment, not a compulsory comparison board; still deliver its rendered preview for approval before publication. |
| Change animation timing numerically; only static screenshot exists | Motion owner checks playback internally | Deliver a playable recording/interactive preview of changed behavior; keep motion/accessibility/performance checks. A still alone is insufficient. |

## Executed checks

- `python tools/validate.py skills/frontend-ui-engineering`: `PASS .../skills/frontend-ui-engineering/SKILL.md`; `1/1 skills valid`.
- `git diff --check -- skills/frontend-ui-engineering/SKILL.md skills/frontend-ui-engineering/references/taste-selection.md`: no output, passed.
- Python checked every local Markdown link in both touched source files: passed.
- `python tools/fleet.py render`: rendered 17 admitted skills to `render/fleet`; no live deployment.
- `python tools/fleet.py diff`: proposes frontend-ui-engineering plus unrelated learn-from-youtube, openai-delegation-route-research, outcome-first-workflow-design, and skill-creator updates. Do not apply that broad diff for this task.
- `python tools/recovery.py diff` and `python tools/instruction_profile.py`: blocked by `snapshot policy hash mismatch`.
- `python tools/reconcile.py plan --adopt frontend-ui-engineering --no-capture-recovery`: `ERROR: snapshot policy hash mismatch`.
- `python tools/reconcile.py sync --adopt frontend-ui-engineering --no-capture-recovery --message 'fix(frontend): require delivered visual preview before publication'`: `{"failed_step":"preflight-or-reconcile","reason":"snapshot policy hash mismatch","result":"incomplete"}`.

## Ownership and deployment blockers

The checkout was already dirty, including both touched source files, the rest of the frontend reference bundle, recovery policy, instruction contracts, reconciliation tooling, and other owners. Pre-task bytes of the two touched files were preserved in the Hermes scratch directory; `frontend-visual-preview-rule.patch` records only this task's delta, not the full dirty Git diff. No unrelated edits were staged, reverted, or included.

The current owning `tools/reconcile.py` automatically gathers all changed admitted owners (lines 810–817), selects their dirty skill files (840–841), and blocks unrelated unreviewed repository files (844–846); `--adopt` and `--include` are not a strict deployment-only filter. Even after the recovery policy mismatch is resolved by its owner, a scoped deployment must address this scope conflict without silently publishing the other pending changes. No tool bypass, live-copy edit, alternate worktree deployment, broad recovery capture, commit, or push was performed.

Canonical source is repaired and checked; deployment/publication is incomplete. Fresh loading still returns the old live skill. No cross-host behavior parity is claimed. Rollback is the reverse of the task-only patch, subject to rechecking subsequent edits; never reset the whole already-dirty owner files.
