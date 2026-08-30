# AI LABS workflow-extraction mode

Use this focused mode when the source channel is **AI LABS** and the user wants the workflow, automation, prompt pattern, or paywalled resource reconstructed rather than a general lesson.

## Goal

Recover the smallest operational workflow supported by the public video material. Do not reproduce sales framing, generic AI explanations, sponsor copy, community promotion, or the normal teaching/retention sections unless the user asks.

## Source policy

1. Start with the title, description, chapters, transcript excerpt/full transcript supplied by the user, and every public source linked there.
2. The description is sufficient when it explicitly states the mechanism, artifacts, control flow, and checks. Read transcript sections only to fill missing operational details; do not force full-video coverage for this mode.
3. Inspect linked primary sources such as repositories, original posts, docs, and public skills before reconstructing. Public upstream source beats the channel's paraphrase.
4. Do not bypass or scrape the paid community. Treat claims about a paywalled file as unverified unless its behavior is visible publicly.
5. Separate:
   - **Observed:** directly stated or shown publicly.
   - **Upstream:** verified in the linked original source.
   - **Reconstructed:** the minimal implementation inferred from observed behavior.
   - **Unknown:** paid-only names, exact wording, hidden files, or runtime details.

## Extraction ledger

Capture only workflow-bearing material:

| Stage | Trigger/input | Action/decision | Artifact/state | Feedback/gate | Failure/stop |
|---|---|---|---|---|---|

Also capture prerequisites, actor boundaries, concurrency/dependencies, cost/time claims, and stated weaknesses. Ignore repetition and hype.

## Reconstruction rules

- Reproduce behavior, not proprietary wording.
- Prefer one coherent Hermes-native owner over copying the channel's arbitrary skill count or Claude-only wrappers.
- Replace magic keywords with explicit supported mechanisms.
- Make checks immutable before execution when the video's failure is self-authored verification.
- Keep builders, critics, and parent verification distinct where that distinction is load-bearing.
- Add bounded retries, evidence requirements, and a stop/escalation condition when the video omits them.
- Label these safety/operational additions as reconstruction, not video claims.

## Output

Return only what helps the user run or preserve the workflow:

1. one-paragraph mechanism and candid gap assessment;
2. ordered workflow with inputs, artifacts, gates, and stop conditions;
3. source-vs-reconstruction notes;
4. the requested durable artifact (skill/reference/template) when authorized;
5. concise verification that the artifact loads or executes.

Do not emit the standard Learn From YouTube teaching artifact in this mode unless requested.
