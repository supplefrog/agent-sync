# Flashcards, coding, drawing, and notation

Use the existing LearnHarness workbench in the conversation that owns the lesson.

If you need clarification during a teaching question, ask in the same conversation. The reply can explain a concept while the lesson stays on the pending question and keeps its solution hidden. In the Codex or T3 lesson card, choose **Save unfinished answer** before closing the card to keep your edits. Reopen the lesson in the same conversation to pick up that question and draft.

- Open **Flashcards** to create a deck, write cards, or review due cards. Reveal the answer and choose Again, Hard, Good, or Easy to set the next review date. Extra practice leaves the schedule intact. The tutor can draft cards from an enrolled graph proposition or lesson material. Decks are stored with the enrolled lesson.
- For a JavaScript coding question, edit the starter code and choose **Run tests** to see the individual results. **Submit code** sends the code and any thinking or drawing to the tutor. A submitted test receipt is valid for that code and question revision only. Practice accepts further attempts until the tutor concludes the problem and reveals the committed solution.
- Open **Draw** below the response. The pen supports mouse, touch, and stylus pressure. Eraser removes a stroke, Undo restores the previous state, and Clear empties the pad. Saving the draft preserves the strokes for that question. Submitting the ordinary response attaches the drawing.
- A complete fenced `smiles`, `abc`, or `tikz` block displays a static molecule, score, or diagram. ABC expects one tune with X, M, L and K headers. TikZ supplies its own document class and uses the locally bundled packages. An invalid block displays readable source.
- Long practice histories show the latest responses first. **Load earlier responses** opens the next page from the same saved problem. If the lesson advances during a read, refresh before continuing.

The connected MCP App provides the JavaScript test button, flashcard review controls, and notation renderer. The inline fallback renders coding and drawing inputs through its existing transport. Host-specific operation beyond the connected workbench requires separate verification.

The local notation worker needs the dependencies recorded in `notation-runtime/package-lock.json`. Prepare them from that directory with `npm ci --ignore-scripts`. The app loads the prepared modules locally. The JavaScript test runner is bundled separately and executes guest code in QuickJS WebAssembly.
