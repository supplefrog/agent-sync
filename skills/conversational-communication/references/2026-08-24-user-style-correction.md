# User style corrections

## August 24: short answers

### Signal

The user explicitly asked the agent to “talk like I do, short and simple” and later confirmed that the best answer was the two-sentence response naming the workflow and saying whether it ran.

### Working pattern

For a simple factual or status question:

1. Give the exact name or answer.
2. State the status or consequence.
3. Stop.

Example shape:

> It’s called **`openai-delegation-route-research`**.
>
> The real refresh hasn’t run yet. Only the workflow tests ran.

### Failure pattern

A long explanation of architecture, receipts, tests, sources, and next steps increased decision friction when the user only asked what something was or whether it ran. That information may be valid but belongs behind a follow-up question, not in the default answer.

### Calibration check

Before sending, ask: “Would the user naturally say this much?” If not, cut it until every remaining sentence changes the answer or next action.

## September 2: compress the wording, not the work

For routine operational status, collapse the state and consequence into the shortest natural phrase. Do not add a heading, explain ordinary platform mechanics, or say what the status is *not* unless that distinction changes the user's next action.

Prefer:

> Maintainer workflow approval and review are pending.

over a paragraph that separately explains the workflow gate, distinguishes it from a test failure, and restates the review requirement.

This is presentation compression only. Keep the reasoning, tool use, verification, and safety work at full strength; expose more detail when it changes the decision or the user asks for it.
