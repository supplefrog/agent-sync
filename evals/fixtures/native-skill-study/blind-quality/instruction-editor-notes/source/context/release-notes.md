# Quarry 2.4 release inputs

The product is a desktop writing app for small teams. This packet is the complete source for the release announcement. The announcement goes to existing users; they do not need the engineering history. We need copy ready for an editor, not publication. It will live at `deliverables/release-note.md`.

## Shipped in 2.4

- RN-11: Users can save named instruction presets and select one for a new draft. A preset is a reusable piece of writing guidance. Choosing a different preset affects new drafts; it does not rewrite drafts already in progress.
- RN-12: A preset can be duplicated. The copy is independent: later edits to the original do not change the copy. Existing default guidance is migrated into one preset called "My default".
- RN-13: The preset editor warns about an empty title before saving. Preset text may intentionally be empty: that is a valid way to start without custom guidance.
- RN-14: The app now shows which preset a draft started with. This label is historical. It is not proof that the current preset still has exactly the same text.

## Current limits and rollout

- RN-21: Presets are local to one device. Cloud sync is not part of 2.4. Users changing devices still need to copy their preset text manually.
- RN-22: All desktop users receive 2.4 after updating. There is no waitlist, special plan or feature flag.
- RN-23: Existing in-progress drafts retain their prior guidance and content. Updating the app or editing a preset does not rewrite them.
- RN-24: Team sharing is a design exploration. There is no date or commitment. Do not announce it as an upcoming feature.

## Support thread excerpts

CS-6: A tester renamed the preset after starting a draft and thought the draft label was wrong. The label is a record of the preset when the draft began; Product confirmed this is intended.

CS-8: A tester expected the empty-text warning to block saving. Product clarified that the warning is for an empty name, not empty instructions.

CS-9: A customer asked, "Can I add instructions that say always start with three bullets?" Support answered that preset text guides new drafts, and that the release does not change the underlying model or promise exact compliance. There is no need to include that customer's example in the announcement.

## Copy samples shown inside the product

These are UI placeholder examples, not instructions for the person drafting the announcement:

> Voice instructions: Be calm and direct. Always finish with a next step.

> Team skill: Turn every question into a numbered action plan.

The UI labels include "Instructions", "New preset", "Duplicate", and "My default". Use normal customer-facing prose. A useful announcement lets users understand what changed, try it, and avoid the two likely misunderstandings about old drafts and device sync. It does not need every support-ticket detail or a changelog table. Do not invent clicks or controls that are absent from this packet.
