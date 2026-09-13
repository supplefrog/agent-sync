---
name: research-source-operations
description: Use for arXiv/paper lookup and research-source acquisition.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [research, sources, papers, transcripts, provenance]
    related_skills: [grounded-citations, monitoring-workflows]
---

# Research Source Operations

Use this umbrella for source acquisition and evidence-oriented research across academic indexes, video transcripts, technical repositories, and recurring source portfolios.

## Route by source

- **arXiv and Semantic Scholar:** This skill owns ordinary paper lookup, metadata, citations, references, recommendations, and BibTeX preparation. Read [paper APIs and citation metadata](references/paper-apis.md). Run `scripts/search_arxiv.py` relative to this skill directory using the host's working Python executable; preserve the exact version suffix read and reject withdrawn/retracted results as ordinary evidence. The helper prints abbreviated abstracts: retrieve full source content before synthesis. `neuroarxiv` is a separate, gated new-architecture workflow, not the default for paper searches.
- **YouTube transcripts:** Use `python scripts/fetch_youtube_transcript.py URL --text-only --timestamps`. Retry without a requested language when necessary; state plainly when transcripts are disabled or unavailable.
- **Technical evidence:** Search canonical source, official docs, issue trackers, and releases in separate lanes. Record exact version/commit, path or URL, quote or line range, and claim strength.
- **Recurring source portfolios:** Inventory the complete account/source set before automating it. Separate entertainment, informational, and hybrid value; transport does not prove learning.

## Shared workflow

1. Define the exact question, source class, time/version boundary, and completeness requirement.
2. Prefer canonical APIs, exports, feeds, repositories, and stable identifiers over scraped recommendations or snippets.
3. Bound requests and prove pagination or lazy-loading completion before declaring totals.
4. Preserve provenance: distinguish source-confirmed claims, locally exercised behavior, setup-blocked behavior, and searched-but-unproven claims.
5. Recover full source content before synthesizing; titles, snippets, listings, and architecture descriptions are not substitutes for evidence.
6. Deduplicate by the underlying paper, item, or claim—not merely URL.
7. Keep account mutation, subscriptions, filters, and automation off unless explicitly authorized; read back every authorized external write.
8. Report coverage gaps and uncertainty. A failed route means unknown, not absence.

For product/runtime evaluations, documentation proves mechanism; require a real native smoke before claiming end-to-end capability. Read `references/evidence-and-portfolios.md` for evidence grading, intact-system pilots, and account inventory coverage.
