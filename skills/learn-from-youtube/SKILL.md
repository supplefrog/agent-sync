---
name: learn-from-youtube
description: Learn from any video or triage mixed learning sources. Build source-faithful lessons with audiovisual coverage, verified context, and retrieval practice.
license: MIT
compatibility: Source access determines achievable coverage; local media tools are optional and authorization-bound.
metadata:
  author: supplefrog
  version: "1.2.0"
  hermes:
    tags: [youtube, learning, research, transcripts]
    related_skills: [youtube-content]
---

# Learn From Video and Learning Sources

Use for source-based learning from YouTube, other hosted videos, local recordings, lectures with slides, or a mixed learning collection. The existing skill identifier is retained for compatibility; YouTube is not a requirement. Use `youtube-content` for simple transcript extraction, brief summaries, chapters, threads, blogs, or quotes. Do not use for media downloads, simple translation, or general research without a learning goal.

For several sources or a choice of what to study, read [references/source-triage.md](references/source-triage.md) before deep extraction. Triage may be deliberately partial; a finished lesson must account for its selected scope. Do not turn a preview of every source into a claim to have studied the collection.

**AI LABS exception:** when the channel is AI LABS and the user wants a workflow, automation, prompt pattern, or paywalled resource reconstructed from public material, read [references/ai-labs-workflow-extraction.md](references/ai-labs-workflow-extraction.md). That focused mode replaces the normal teaching artifact and full-coverage requirement.

Produce a usable lesson, not an orientation to watching the material. Establish coverage separately for transcript, slides, recording visuals and audio listening; a complete transcript inventory proves none of the other channels.

## Core contract

- Review the selected scope before final synthesis; keep inaccessible or unreviewed portions explicit rather than reconstructing them.
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

Collect the source URL or local locator, title, creator, duration, available date, chapters, languages and companion material. Mark unknown metadata as unknown. Read [references/source-fidelity.md](references/source-fidelity.md) when recordings, ASR, slides, diagrams or embedded clips carry the lesson.

Use an available transcript extractor such as `yt-dlp --skip-download --list-subs`. Prefer creator-provided captions in the original language, then original auto-captions, then translated captions. If captions are absent, use authorized speech-to-text when available or explain the limitation.

For visual meaning, inspect source pages and relevant recording states. Chapter-boundary frames alone can miss demonstrations between them. Surveying transitions identifies review candidates, not watched content. Use selected sequences for meaningful change; a thumbnail, link or still does not prove a clip played or establish its dialogue.

### 2. Acquire and normalize the transcript

Reuse available captions or transcripts before new extraction. For hosted captions, prefer JSON3; VTT is an acceptable fallback. Local media stays read-only; use authorized existing tools and bounded temporary audio if transcription is needed. Do not download models, copy/transcode entire recordings, spend on inference or launch redundant workers without the applicable authorization. Check temporary storage needs, not just final output size.

For VTT captions, run:

```bash
python scripts/clean_vtt.py <captions.vtt> --format markdown
```

Treat extraction failure as a limitation on the affected channel. Check companion evidence before declaring the concept unrecoverable, but never substitute a description, comment or slide for verified speech. Flag repaired timelines and invalid segment bounds; resampling can align a clock but cannot restore missing words.

### 3. Build a coverage ledger

Divide the source by creator chapters. If absent, use coherent topic changes or 2–5 minute windows. For every segment record:

- timestamp range and topic;
- distinct claims, concepts, examples, warnings, and references;
- destination in the final lesson, or an explicit exclusion reason;
- uncertainty or visual evidence still needed.
- evidence channel and locator: source ID, original clock/page, native object or reviewed frame; distinguish requested seek time from exact timing.

Every selected segment needs a destination, explicit exclusion or unresolved-gap entry. Partial delivery is valid when clearly scoped; an unresolved central dependency prevents claiming a standalone replacement.

### 4. Reconstruct the model

Identify:

- the central problem and thesis;
- concepts and precise definitions;
- relationships, causal chain, or workflow;
- alternatives and selection criteria;
- assumptions, tradeoffs, failure modes, and stop conditions;
- examples and what each demonstrates;
- actionable procedures and required feedback signals.

Resolve consequential transcription errors against the original or corroborating evidence; context suggests candidates, not recovered speech. Flag unresolved names, numbers or terms. Reinspect originals when reviews disagree; delegated descriptions and existing ledgers are not independent proof.

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
- source figures are legible at reader size, captions match visible labels, and any new schematic is clearly an addition rather than recovered data;
- if delivering an interface, real navigation, answer controls and source-image loading work; automated consistency checks do not certify comprehension, audiovisual fidelity or taste.

## Long-source token control

Process transcript chunks into the coverage ledger first, then synthesize from that ledger while retaining timestamps. Run a final global pass against the full ledger. Never recursively summarize summaries without checking the source; omissions compound.

Save transcripts or ledgers only when requested or needed as durable artifacts. Otherwise use a temporary directory and leave the project untouched.

Reusable workflow improvements belong in this canonical skill or its existing references, not only in the current project's status file. Preserve source-specific evidence with its project; apply `skill-creator` for checked procedural updates during the work.
