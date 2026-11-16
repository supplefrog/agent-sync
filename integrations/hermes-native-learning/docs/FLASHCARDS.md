# Flashcards

Open **Flashcards** in a supported lesson view. Create a deck and save cards with a question and an answer. **Review due** shows scheduled cards. Use **Show answer**, then choose **Again**, **Hard**, **Good**, or **Easy**. **Extra practice** cycles through a deck without changing due dates.

## Authoring from enrolled sources

The current lesson owner can use the flashcards operation through the existing lesson command boundary:

- {op: 'flashcards', chatId, action: 'decks'} lists deck counts and dates.
- {action: 'create-deck', title} creates or reopens a named deck.
- {action: 'source', kind: 'graph', id} resolves a proposition already available in the lesson's explicitly enrolled graph. Use its statement to write a concise question and answer.
- {action: 'source', kind: 'material', id} fingerprints an attached material. Use the existing bounded notes reader or authorized PDF-reading route for evidence.
- {action: 'add', deckId, front, back, source} saves the cue with the exact source reference returned by source. A changed source requires a fresh read before saving.
- {action: 'cards', deckId, offset?, expectedRevision?} reads bounded deck pages for authoring. Copy the page revision into subsequent page requests.
- {action: 'edit', cardId, expectedVersion, front, back} preserves the card's due date and refuses stale edits or scoring an older version.

Source references prove which recorded generation the card author used. The author remains responsible for grounding the text in that source. Flashcard decks are private to the enrolled lesson and owner. Host bindings that already share an authority can share the same flashcard record when they point to the same physical lesson state. Decks and review schedules live in a separate .flashcards directory under the enrolled private state root.

The learner view receives only the question before reveal. Rating requires a signed review token from a reveal within the current lesson, and an atomic version check prevents duplicated ratings or grading a changed card. Reopening a view reloads deck and schedule state from disk. Flashcard operations leave lesson revisions and graph records untouched.

The scheduler is the LearnHarness v0.6.1 FSRS-6 implementation (Amos Blomqvist and contributors, AGPL-3.0-only), with portions adapted from ts-fsrs 5.2.3 under MIT. See [FSRS-LICENSE.txt](../licenses/FSRS-LICENSE.txt).
