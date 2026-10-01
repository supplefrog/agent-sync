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

Compose for the recipient and channel from the first sentence. Lead with the result, request, correction, or new evidence; include context that changes understanding or action, then stop. Short comments usually need paragraphs, not a report template. Preserve source facts and uncertainty; do not infer causes, owners, quotations, firsthand experience, commitments, or next steps the source does not support.

## Voice

Match a supplied writing sample over these defaults. Use `I` or `we` for genuinely firsthand statements; keep personality proportional to the channel. A maintainer comment can be direct and human, while a personal post can carry more voice. Prefer specific nouns and plain verbs, with natural sentence variety. Use bullets for parallel items or scanning, and omit ritual caveats, apologies, social warm-ups, and generic closers unless the relationship calls for them.

## Engineering surfaces

The domain skill owns facts, required fields, safety, and publication mechanics. This skill owns prose and information order.

- **Issue or maintainer comment:** report the delta. Lead with a correction when correcting an earlier claim. Do not restate the issue, narrate the investigation, turn containment into root cause, or direct maintainers toward a solution the evidence does not establish. First person can distinguish direct reproduction from inference.
- **PR description:** say why the change exists, what changed, and how it was verified. Preserve supplied compatibility or visible-impact notes. Follow the repository template without padding empty sections.
- **Status or incident update:** state current status, impact, and next action. Use a compact lead and short parallel lines when they help scanning. Do not turn “next update after X” into a personal commitment unless the speaker is specified.
- **Technical explanation:** answer first, then give the causal mechanism needed to understand it.

## Final read

Read once as the recipient. Remove repeated summaries, decorative headings, mechanical bold labels, forced groups of three, stock transitions, vague authority, fake emotion, and writer-centered process narration. Make a sentence specific or delete it if it could fit an unrelated report unchanged; remove sections that do not change understanding or action. This checks the artifact rather than requiring a second writing pass.
