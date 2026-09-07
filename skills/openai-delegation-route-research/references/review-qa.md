# Bounded source-review questions

Use `scripts/review_qa.py` when a routed task asks exactly three controller questions about a supplied source-review excerpt. `build_prompt` delivers the questions and acceptance contract. `validate_and_repair` enforces fixed IDs, answer/snippet bounds, exact source support, and explicit source-unknown caveats.

The source excerpt must be at most 6,000 characters. Questions must have three unique, nonempty IDs. Parent acceptance requires every part of each controller question to be answered faithfully, source and runtime unknowns to remain explicit, and unsupported claims to be absent. The Python validator checks structure and exact quotation only; it cannot replace parent semantic review.

The only repair allowed is restoring Markdown bold around a paragraph-leading label when the resulting complete snippet is one unique exact source substring. Word, punctuation, whitespace, capitalization, ordering, other formatting changes, absent matches, and ambiguous matches fail.

Qualification is protocol-, route-, verifier-, and parent-review-specific. Preserve raw output and repair traces. Schema success is not semantic review, and unknown subscription quota weight or API cost remains unknown.

The exact machine-readable contract is [review-qa-protocol.json](review-qa-protocol.json), SHA-256 `e20a9bf495942602da6f44104a18e8e774014c21ade56ab256cc30d5ef39309e`. A different protocol hash invalidates this task contract and its qualification evidence.
