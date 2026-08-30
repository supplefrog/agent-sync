---
name: learn-from-youtube
description: Turn a YouTube source into faithful, verified teaching notes
license: MIT
compatibility: Requires transcript access; visual material may require frame inspection.
metadata:
  author: supplefrog
  version: "1.1.0"
  hermes:
    tags: [youtube, learning, research, transcripts]
    related_skills: [youtube-content]
---

# Learn From YouTube

Use when the user wants to learn from a YouTube source without watching the full video: comprehensive knowledge extraction, timestamped study notes, concept teaching, claim checking, prerequisites, or an information-dense lesson. Use `youtube-content` for simple transcript extraction, brief summaries, chapters, threads, blogs, or quotes. Do not use for media downloads or simple translation.

**AI LABS exception:** when the channel is AI LABS and the user wants a workflow, automation, prompt pattern, or paywalled resource reconstructed from public material, read [references/ai-labs-workflow-extraction.md](references/ai-labs-workflow-extraction.md). That focused mode replaces the normal teaching artifact and full-coverage requirement.

Produce a faithful teaching artifact, not a lossy recap. Prove transcript coverage before compressing.

## Core contract

- Read the complete available source before synthesizing.
- Separate **what the video says**, **externally verified context**, and **inference**.
- Preserve every load-bearing concept, distinction, condition, example, warning, number, and named reference.
- Remove repetition, filler, sponsor copy, and verbal scaffolding only when they add no learning value.
- Use timestamps as navigation aids; never invent them.
- Teach missing prerequisites when necessary to understand or apply the material.
- Use `primary-source-research` for external verification when available.
- Paraphrase rather than reproducing the transcript; quote only short essential excerpts.
- Keep source-bounded tasks source-bounded. Add general best practice only when it materially helps, and label each addition as **Inference** at the point of use. Never describe the whole artifact as a source paraphrase if it contains added guidance.

## Workflow

### 1. Inspect the source

Collect the canonical URL, title, channel, duration, description, upload date, chapters, caption languages, and whether the lesson depends on visuals.

Use an available transcript extractor such as `yt-dlp --skip-download --list-subs`. Prefer creator-provided captions in the original language, then original auto-captions, then translated captions. If captions are absent, use authorized speech-to-text when available or explain the limitation.

For a visual tutorial, demo, chart, or slide deck, inspect relevant frames at chapter boundaries and whenever meaning exists only on screen. A transcript alone is insufficient for visual evidence.

### 2. Acquire and normalize the transcript

Download captions to a temporary directory unless the user requests a saved artifact. Prefer JSON3; VTT is an acceptable fallback.

For VTT captions, run:

```bash
python scripts/clean_vtt.py <captions.vtt> --format markdown
```

Treat extraction failure as a blocker to faithful coverage. Do not substitute the description or comments for the video.

### 3. Build a coverage ledger

Divide the source by creator chapters. If absent, use coherent topic changes or 2–5 minute windows. For every segment record:

- timestamp range and topic;
- distinct claims, concepts, examples, warnings, and references;
- destination in the final lesson, or an explicit exclusion reason;
- uncertainty or visual evidence still needed.

Do not write the final lesson until every segment is accounted for.

### 4. Reconstruct the model

Identify:

- the central problem and thesis;
- concepts and precise definitions;
- relationships, causal chain, or workflow;
- alternatives and selection criteria;
- assumptions, tradeoffs, failure modes, and stop conditions;
- examples and what each demonstrates;
- actionable procedures and required feedback signals.

Resolve transcription errors from context. Flag unresolved names, numbers, or terms instead of guessing.

### 5. Research only where it improves understanding

Verify current facts, named methods, tools, papers, and prerequisites against upstream sources. External research may correct, qualify, or extend the video, but must remain visibly distinct from the creator's claims.

Apply provenance labels to the specific statement they qualify; a global disclaimer does not repair mixed source and inferred claims.

Do not inflate the lesson with generic background. Add context only when it closes a real comprehension or application gap.

### 6. Synthesize and validate

Read [references/output-contract.md](references/output-contract.md). Adapt headings to the subject while preserving coverage, provenance, pedagogy, and density.

Before delivery, verify:

- every ledger segment is represented or deliberately excluded;
- the thesis, distinctions, examples, caveats, and procedures survived compression;
- timestamps point to the relevant source moment;
- externally checked claims have upstream citations;
- source claims, research, and inference cannot be confused;
- each paragraph adds distinct understanding;
- the learner can explain, choose, and apply the ideas afterward.

## Long-source token control

Process transcript chunks into the coverage ledger first, then synthesize from that ledger while retaining timestamps. Run a final global pass against the full ledger. Never recursively summarize summaries without checking the source; omissions compound.

Save transcripts or ledgers only when requested or needed as durable artifacts. Otherwise use a temporary directory and leave the project untouched.
