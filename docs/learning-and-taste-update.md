# Reusable learning and taste-selection update

## Changed owners

- [Video and mixed-source learning](../skills/learn-from-youtube/SKILL.md): generalized trigger, separate evidence-channel coverage, standalone teaching rather than an orientation, and [source-fidelity](../skills/learn-from-youtube/references/source-fidelity.md) / [source-triage](../skills/learn-from-youtube/references/source-triage.md) references. The stable identifier avoids breaking existing discovery and callers; there is no duplicate video-learning skill.
- [Skill creator](../skills/skill-creator/SKILL.md): checked skill improvement during collaborative work, rather than waiting for a separate save request. Task evidence stays local; portable rules go to their owner. Unproven causal/model-specific conclusions remain candidates.
- [Frontend owner](../skills/frontend-ui-engineering/SKILL.md): user-led visual choice, conditional design guidance and proportionate verification. [Taste selection](../skills/frontend-ui-engineering/references/taste-selection.md) defines the interaction; the [portable template](../skills/frontend-ui-engineering/templates/taste-picker.html) is a working example, not a default style pack.
- Standing reminders: [Hermes](../recovery/current/hosts/hermes/SOUL.md) and [Codex](../recovery/current/hosts/codex/AGENTS.md). [Shared ownership](../surfaces/core.md), the active profile hashes and host-delta bindings track these exact changes. OMP has shared skill discovery but no managed always-loaded instruction overlay; no new one was installed here.
- [Corrected research](frontend-taste-evidence.md): direct Astra practitioner comparison and conflicting reports, with search coverage and limitations.

## Verification scope

Executed checks before deployment:

- All registered skills validate with `python tools/validate.py`.
- `python -m unittest tests.test_tools`: 23 tests pass, including the existing VTT parser and tooling regressions. The stale-artifact diagnostic in the output is an expected negative test.
- [Browser checker](../tools/check_taste_picker.py) passes for the portable template and local Hermes-adapted preview: real 360/1000px rendering, keyboard selection, local control updates without messages, all reaction actions, reset and portable choice text. The adapter is tested with a stub, not by sending an unsolicited live conversation turn.
- Screenshots were inspected for legibility and mobile overflow. This is not user taste approval or complete accessibility certification.
- The live instruction-profile check passes within existing standing-context budgets. No model defaults, credentials, permissions or schedules were changed.

Source-level routing review, not a model benchmark:

| Case | Required outcome retained |
|---|---|
| Local bilingual lecture plus slides | Video-learning trigger; separate audio/ASR/visual coverage; targeted uncertainty checks |
| Several videos and papers; choose what to study | Triage first, inspect selected scope deeply; no claim to have read every source |
| Brief transcript summary or translation | Existing simple extraction/transformation path, not a compulsory coursebook |
| Disputed frame description versus native slide | Reinspect both evidence channels; no fabricated timestamp or dialogue |
| Simple control repair inside an existing UI | No new style-selection ceremony; verify affected behavior |
| New UI with unresolved taste | Small same-content visual comparison, links and meaningful reactions |
| User delegates visual choice | One reversible provisional direction, not a blocked questionnaire |
| Verified reusable workflow versus speculative model claim | Update the narrow owner for the former; label and test the latter before generalization |

These reviews establish explicit contract coverage. They are not naturally triggered multi-host model trials or evidence of improved Astra output. The browser tests establish the actual template mechanism; no paid model evaluation was run.

## Research and visibility follow-up

The existing Hermes-native [iterative research owner](../recovery/current/hosts/hermes/skills/research/iterative-blind-research/SKILL.md) now requires direct investigation of a user's reported failure, exact model/version matching, practitioner evidence plus counterevidence, and an explicit distinction between source audits and output-quality comparisons. A narrow/failed search cannot establish absence of evidence. The native change was reviewed and applied through Hermes's existing skill-approval queue before recovery capture; it was not installed as a duplicate shared research skill.

The shared [communication owner](../skills/conversational-communication/SKILL.md) calls for brief pre-action visibility without repetitive tool narration, and style suited to the user and context. Explicit deliverable requirements take precedence over conversational tone. The [authoring owner](../skills/skill-creator/SKILL.md) directs writers to distill corrections into behavioral rules, retaining details only when they change a decision or boundary.

The user confirmed that messages were visible in Desktop. Installed-runtime commentary callback tests passed: three selected tests, with sixty deselected. This work corrects communication instructions, not a demonstrated rendering defect; no runtime/config patch was made.

## Boundaries

This update does not implement a new notebook app, activate the existing research loop's live collectors, store personal learner profiles, or redesign an existing coursebook. An existing source/evidence system should remain the backend rather than be duplicated by a teaching skill. No session or source-media history was removed.

Use the reconciliation result and fresh discovery readback for deployment status. The source instruction update does not retroactively replace the cached system prompt of an already-running conversation.
