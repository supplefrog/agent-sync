# August 24, 2026 style correction

## Signal

The user explicitly asked the agent to “talk like I do, short and simple” and later confirmed that the best answer was the two-sentence response naming the workflow and saying whether it ran.

## Working pattern

For a simple factual or status question:

1. Give the exact name or answer.
2. State the status or consequence.
3. Stop.

Example shape:

> It’s called **`openai-delegation-route-research`**.
>
> The real refresh hasn’t run yet. Only the workflow tests ran.

## Failure pattern

A long explanation of architecture, receipts, tests, sources, and next steps increased decision friction when the user only asked what something was or whether it ran. That information may be valid but belongs behind a follow-up question, not in the default answer.

## Calibration check

Before sending, ask: “Would the user naturally say this much?” If not, cut it until every remaining sentence changes the answer or next action.
