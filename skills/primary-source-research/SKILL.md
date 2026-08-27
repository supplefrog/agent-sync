---
name: primary-source-research
description: Trace claims to canonical sources before synthesis
license: MIT
compatibility: Requires web or repository access.
metadata:
  author: supplefrog
  version: "1.0.0"
---

# Primary-Source Research

Use when a decision depends on current external facts, implementations, or competing technical approaches. Optimize precision before coverage.

## Research contract

Define the decision, claim set, freshness requirement, and stopping condition. Separate facts that need evidence from judgment criteria supplied by the user.

## Source order

Prefer the closest authoritative artifact for each claim:

1. source code, specification, standard, API schema, dataset, or paper;
2. owner documentation, release notes, issue tracker, benchmark method, or maintainer statement;
3. direct practitioner evidence with reproducible artifacts;
4. secondary analysis;
5. catalogs, search snippets, social posts, and videos.

Lower tiers are useful for discovery. Trace their factual claims and cited mechanisms upstream before relying on them. A video can reveal terminology, demos, or sources; it is not privileged over the artifacts it discusses.

## Iterative loop

### 1. Map the question

Break the decision into answerable claim buckets. Identify likely source owners, canonical repositories, exact product names, and synonyms.

### 2. Search in bounded passes

Run a small first pass across independent source families. Keep a ledger of query, URL, source tier, relevant claim, date/version, and unresolved gap.

For each promising secondary result, follow references upstream. Search repository history, releases, tests, and issues when documentation omits behavior or failure modes.

Do not repeat equivalent queries. Stop broadening once new searches produce no decision-changing evidence.

### 3. Verify claims

For material claims, capture the exact supporting passage, code path, test, or observed result. Check version and date. Distinguish:

- **documented:** owner or specification states it;
- **implemented:** current source contains the mechanism;
- **verified:** a live or reproducible check observed it;
- **inferred:** conclusion from the evidence.

Prefer two independent sources for high-impact claims when no single canonical artifact is decisive.

### 4. Compare mechanisms

Normalize candidates against the user's outcome rather than their marketing categories. Compare mechanism, compatibility, operating cost, security surface, maintenance, reversibility, and evidence quality.

Use popularity only as a lead or maintenance signal. Do not treat stars, subscribers, downloads, or search rank as proof of correctness or fit.

### 5. Synthesize for action

Lead with the decision and the evidence that could change it. Cite canonical URLs beside claims. State uncertainty, missing evidence, and what would falsify the recommendation. Exclude interesting facts that do not affect the decision.

## Stopping rules

Stop when:

- the decision criteria are covered by current primary evidence;
- credible alternatives have been checked;
- contradictions are resolved or explicitly bounded;
- another search is unlikely to change the action.

Do not stop merely because the first credible result agrees with the hypothesis.

## Failure modes

- citing a search result or summary when the source is reachable;
- counting many derivative articles as independent evidence;
- confusing documentation with implemented or live behavior;
- using an old benchmark against a changed model or runtime;
- collecting sources without updating the decision;
- presenting breadth as confidence.
