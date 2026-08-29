---
name: humanizer
description: Write or revise public-facing prose so it sounds like an experienced person rather than a generated template. Use for GitHub issues and comments, PR descriptions, release notes, engineering updates, technical explanations, email, Slack, posts, and explicit humanize or voice-matching requests. Do not use for code, private reasoning, strict-schema output, or creative work owned by a more specific skill.
version: 3.0.0
author: Hermes Agent; derived from Siqi Chen's Humanizer
license: MIT
metadata:
  hermes:
    tags: [writing, engineering-comms, voice, editing]
    related_skills: [github-issues, github-pr-workflow]
---

# Natural public writing

Write the final artifact in a natural voice from the first sentence. Do not generate a formal template and then try to disguise it with a cleanup pass.

## Compose from the reader's perspective

1. Identify who will read it and what they need to understand, decide, or do.
2. Open directly with the result, request, correction, or genuinely new evidence. Skip thanks and social warm-ups unless the relationship actually calls for them.
3. Include only context that changes the reader's interpretation or next action.
4. Do not infer a cause, assign an owner, promise an update, or recommend a next step unless the source supports it.
5. Use the structure native to the channel. Short comments usually need paragraphs, not a miniature report.
6. Stop when the reader has what they need.

## Voice

- Write like a competent person with a point of view. Use `I` or `we` when the statement is genuinely firsthand.
- Prefer plain verbs and specific nouns. Mix short and long sentences naturally.
- Use paragraphs by default. Use bullets when the items are truly parallel or the reader needs to scan them.
- State uncertainty precisely; do not add ritual caveats, apologies, or claims of confidence.
- Match a provided writing sample over these defaults.
- Keep personality proportional to the channel. A maintainer comment should feel human without becoming chatty; a personal post can carry more voice.

## Engineering surfaces

The domain skill owns facts, required fields, safety, and publication mechanics. This skill owns prose and information order.

- **Issue or maintainer comment:** report the delta. Lead with a correction when correcting an earlier claim. Do not restate the issue, narrate the investigation, turn containment into root cause, or direct maintainers toward a solution the evidence does not establish. First person is often the cleanest way to distinguish direct reproduction from inference.
- **PR description:** say why the change exists, what changed, and how it was verified. Preserve supplied compatibility or visible-impact notes. Follow the repository template without padding empty sections.
- **Status or incident update:** state current status, impact, and next action. A compact lead followed by short parallel lines is often easier to scan than one dense paragraph. Do not turn “next update after X” into a personal commitment unless the speaker is specified.
- **Technical explanation:** answer first, then give the shortest causal mechanism that makes the answer understandable.

## Avoid generated-template tells

Rewrite or remove:

- headings and numbered lists used only to make a short note look complete;
- repeated summary, evidence, and conclusion sections saying the same thing;
- stock transitions such as “Additionally,” “This highlights,” or “It is important to note”;
- mechanical bold labels, forced groups of three, and identical sentence rhythms;
- vague authority, invented quotations, fake emotion, or details not present in the source;
- process narration that matters to the writer but not the reader;
- unsupported implications, ownership, commitments, or solutioneering;
- generic closers and offers to provide more information.

## Final read

Read once as the recipient. If a sentence could be pasted into an unrelated report unchanged, make it specific or delete it. If removing a section would not change the reader's understanding or action, remove it. This is verification, not a second writing pass.
