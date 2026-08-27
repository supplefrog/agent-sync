# Admission evidence contract

A capability is admitted only when the evidence answers each item.

## Identity

- Capability name and tested claim
- Canonical source URL
- Exact version or commit
- License
- Active agent, model, tool policy, OS, and date

## Comparison

- Current baseline behavior
- Finalist selection rationale
- Representative and held-out cases
- Baseline and candidate raw outputs or durable references to them
- Blind judgment or deterministic assertions
- Matched seeds/trials, predeclared practical margin, confidence/stopping rule, and bounded run budget
- Exact model/provider/reasoning/prompt/tool/context stack and artifact hashes
- Order-swapped judge agreement, separated variance signals, and child-session cleanup readback
- Failures, ties, regressions, latency, and material token/tool overhead

## Decision

Pass requires all of the following:

1. every hard requirement is satisfied;
2. no critical case regresses;
3. the candidate wins at least one meaningful case and is not worse overall;
4. security and license review pass;
5. overlap is resolved by replacement, extension, or rejection;
6. a fresh held-out run passes after final adaptation;
7. every required host passes the cross-host no-regression aggregate gate; missing or mismatched hosts are inconclusive.

Popularity and upstream benchmarks can rank discovery candidates but cannot satisfy these conditions.

## Promotion record

Record adaptations, installed paths, superseded surfaces, rollback command, and next re-evaluation trigger. Generated transcripts may remain local; commit the suite and compact result summary without secrets or private data.
