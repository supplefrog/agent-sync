---
name: neuroarxiv
description: Use only for a genuinely new project-architecture decision after comparing enabled skills and native/existing solutions and finding no adequate approach. Ground that new architecture in real arXiv prior art, isolated paper reads, and one cited recommendation. If an existing skill, reference architecture, comparable project, framework, or established approach fits, route to advise-project-approach or the existing owner instead.
license: MIT
---

# NeuroArxiv

Starting a genuinely new project architecture before checking relevant prior art can waste substantial work. This skill is the fallback after existing-solution comparison, not the default architecture adviser. arXiv is one evidence source, not final authority: abstracts are incomplete, results may not transfer to the user's constraints, and broader primary sources may still be required.

## Pre-flight (run before Phase 1)

This skill is expensive: a real arXiv fetch plus roughly one isolated Agent call per paper (typically 10-20), plus scoring, clustering, and convergence. Every invocation must pass both gates below, including an explicit `$neuroarxiv`, `/skill neuroarxiv`, arXiv, prior-art, or state-of-the-art request.

**Gate 1. Existing-solution comparison.**

Inspect enabled skills first. Then check native features, reference architectures, comparable projects, frameworks, libraries, standards, and established approaches relevant to the decision. If an installed skill already owns the task, route to that owner. If an adequate existing approach fits the project constraints, ABORT NeuroArxiv and use `advise-project-approach` to compare or adapt it.

Do not treat "not already installed locally" as "genuinely new." The architecture is genuinely new only when this comparison finds no adequate existing approach.

**Gate 2. New project-architecture decision.**

Ask all three questions. If the answer to any is no, ABORT.

1. **Is this a project-architecture decision?** It must determine a load-bearing system structure, not merely an algorithm, component implementation, variable, CRUD form, SDK integration, or routine stack choice.
2. **Is the architecture genuinely new after Gate 1?** Existing skills and established solutions do not adequately satisfy the project constraints.
3. **Is the user about to commit real effort while leaving the architecture open?** The decision will be expensive to redo, and the user has not already fixed the architecture or asked for direct implementation.

If all three checks pass, proceed to Phase 1. If any check fails, use the owning skill, `advise-project-approach`, or direct implementation. Do not invent novelty merely to trigger this skill.

## The loop

Three phases. Fetching is not divergence — it's find real documents, then
read each in isolation, then converge. Skipping the isolation step turns
this into an LLM guessing about papers it hasn't actually read.

### Phase 0 — Categorize

Map the build problem onto 3-5 arXiv subject categories and 3-6 concrete
search terms (the technical mechanism words — "cache invalidation", not
"caching system"). Pick from the table below, or name another category id
if you're confident of it.

| Category | Covers |
|---|---|
| cs.AI | general AI systems, agents, planning, knowledge representation |
| cs.LG | learning algorithms, training methods, model architectures |
| cs.CL | NLP, language models, text processing |
| cs.CV | image/video understanding, generation, perception |
| cs.IR | search, ranking, recommendation, retrieval-augmented systems |
| cs.DC | distributed systems, consensus, sharding, replication, scheduling |
| cs.DB | storage engines, query processing, indexing, transactions, consistency |
| cs.SE | development practices, testing, program analysis, tooling |
| cs.PL | language design, type systems, compilers, runtimes |
| cs.CR | protocols, authentication, adversarial robustness, privacy |
| cs.NI | routing, congestion control, edge/CDN |
| cs.OS | kernels, schedulers, memory management, virtualization |
| cs.HC | interface design, usability, interaction models |
| cs.MA | coordination, negotiation, emergent behavior among agents |
| cs.RO | control, perception, manipulation, motion planning |
| cs.DS | algorithmic techniques, complexity, data structure design |
| cs.GT | mechanism design, auctions, incentive-compatible systems |
| stat.ML | statistical learning theory, probabilistic models |
| eess.SP / eess.SY | signal processing / control theory |
| math.OC | optimization, scheduling, resource allocation |

If the decision is not genuinely new project architecture, ABORT and use the existing owning skill, `advise-project-approach`, or direct implementation. Do not invent an architecture question merely to force an arXiv search.

### Phase 1 — Fetch (real HTTP, no generation)

For each chosen category, use the host's static URL reader against arXiv's
real export API. In Codex or OMP, call `read` with the URL's `:raw` selector so the
Atom `<entry>` fields are not collapsed; in Hermes, use `web_extract` or a
direct raw API fetch that preserves the full abstract. Do not paraphrase
this step from memory:

    https://export.arxiv.org/api/query?search_query=cat:<CATEGORY>+AND+(all:"<term1>"+OR+all:"<term2>")&start=0&max_results=4&sortBy=relevance&sortOrder=descending

Return, per `<entry>`, the arXiv id, title, full abstract, authors, published
date, and `abs`/`pdf` links from the feed without inventing missing fields.
Treat the feed as source metadata, not proof that a paper's claims are correct.

If a category returns fewer than 2 results, retry that category's query
with the search terms dropped (`cat:<CATEGORY>` alone) — don't pad the
result set with irrelevant hits to hit a target count. If everything
comes back thin, say so in the output rather than manufacturing findings.

**Courtesy:** arXiv asks for one request at a time with a few seconds
between calls. Fetch categories one after another, not concurrently.

### Phase 2 — Diverge (read each paper in isolation)

For every paper collected in Phase 1, launch one **parallel, isolated** worker
in a single batch (`task` in Codex or OMP; `delegate_task` in Hermes). Each worker gets only:

- the build problem
- that ONE paper's title, abstract, authors, year — no other paper
- the instruction below

> You are in DIVERGENT READ mode. You have exactly one paper's title and
> abstract, and one build problem. You do not know what other papers
> exist — do not assume, invent, or gesture at a broader survey.
> Read this abstract as if scouting prior art for someone about to build
> the stated thing from scratch. Never quote the abstract verbatim beyond
> a few consecutive words — paraphrase in your own words.
> Extract: approach (1-2 sentences, the core mechanism), borrow (1
> sentence, the single most concrete implementable takeaway — imperative:
> "Use X to do Y"; if too tangential, say so plainly), limitation (1
> sentence, the load-bearing weakness or breaking condition), relevanceNote
> (1 short clause on fit to the stated problem).
> Output JSON only: `{"approach":"...","borrow":"...","limitation":"...","relevanceNote":"..."}`

**Critical invariant.** These calls must be batched, parallel, and isolated.
Do not expose one paper's worker to any other abstract. If the host cannot
provide isolated workers, stop and disclose that this workflow cannot preserve
its core evidence boundary; do not simulate isolation in one shared context.

### Phase 3 — Converge (one path, not a shortlist)

After all reads return:

1. **Score.** Rate each reading 0-10 on: relevance (fit to the stated
   problem), practicality (buildable by a small team without exotic
   infra), rigor (does the abstract itself show real evidence — benchmarks,
   proofs, a shipped system — vs pure concept). Flag a "trap" when a
   paper's own stated limitation implies a failure mode a builder would
   otherwise rediscover the hard way. Always pair it with a "strength" —
   the one concrete thing that paper's approach gets right.
2. **Cluster.** Group readings into 3-6 clusters by underlying
   architectural angle (not by paper, not by keyword): "cache-invalidation
   plays", "consensus-free plays", "learned-index plays".
3. **Pick ONE.** Choose the cluster with the strongest relevance +
   practicality combination — not the most novel, not the most cited, the
   one an engineer should actually build. This is the point of departure
   from wide-open brainstorming: NeuroArxiv commits to a single
   recommendation, because "here are 4 papers, you decide" is exactly the
   time-wasting the skill exists to prevent.
4. **Synthesize.** For the chosen cluster, produce: a 4-8 sentence
   implementation sketch (actionable, not a lit-review summary), citations
   (paper id + title + url + role — "primary mechanism" / "supporting
   evidence" / "failure mode to avoid" — grounded only in fetched data),
   the first concrete step, the load-bearing risk, and an "avoid" list
   pulled from every paper's limitation (not just the winner's — a pitfall
   named by a paper in a rejected cluster is still worth avoiding).
5. **Name the runner-ups.** One honest sentence per non-chosen cluster on
   the real trade-off that lost it the pick. Not a dismissal — the
   builder should be able to switch paths later knowing why.
6. **One open thread.** A question the read papers raise but don't
   answer — worth a design-review checkpoint before shipping.

When this workflow follows `advise-project-approach`, the existing-solution comparison has already failed to find an adequate architecture. Return the cited convergence result to the parent workflow. NeuroArxiv recommends the genuinely new project architecture; the parent may still supply broader constraint, cost, vendor, and delivery analysis.

## Output shape

1. **Searched.** Categories, search terms, paper count.
2. **Papers read.** Grouped by cluster. Each paper: id, title, one-line
   approach, score chips `[rel8 prac6 rig7]`.
3. **Prior-art pitfalls.** Papers whose limitation flags a real trap —
   listed separately as watch-outs, not verdicts.
4. **THE PATH.** The one chosen cluster: sketch, citations, first step,
   load-bearing risk, avoid-list. This is the deliverable — make it bold
   and unmissable, not buried under the paper list.
5. **Alternates considered, not chosen.** One line each.
6. **Open thread.** The unanswered question.

## Anti-patterns

- **Cross-contaminated reads.** If a paper's read mentions "compared to
  the other papers here" or "collectively these show", isolation broke —
  discard and re-run that read alone.
- **Hallucinated citations.** Never state a paper detail (a number, a
  claim, a result) that wasn't actually in the fetched abstract. If
  unsure, re-fetch rather than infer from the title.
- **Shortlist-as-cop-out.** Ending Phase 3 with "here are 3 good options"
  instead of one recommendation defeats the purpose. Commit.
- **Padding a thin result set.** Zero or few relevant papers is a valid,
  useful finding — it means the mechanism is either genuinely novel or the
  search terms were wrong. Say so. Don't stretch tangential papers to look
  like coverage.
- **Treating a paper's abstract as the whole paper.** The abstract is a
  pointer, not ground truth about implementation details it doesn't state.
  The "borrow" and "avoid" items should stay at the level of what the
  abstract actually supports.

## Calibration

- **How many papers?** Default 4 per category × 3-5 categories ≈ 12-20
  papers. Scale down for narrow/well-known mechanisms (2 per category is
  enough when the space is small), up for genuinely unclear territory.
- **When to stop widening?** If a category-only retry (terms dropped)
  still returns nothing usable, say so and move on — don't cascade into
  unrelated categories chasing a result count.

## Cost

1 categorize + N isolated reads (typically 12-20) + 1 score + 1 cluster + 1 converge is roughly N+4 worker-shaped calls, plus real arXiv HTTP fetches (~3s courtesy delay between categories). Not for ordinary design decisions—only genuinely new project architecture after existing-solution comparison fails.

## Installation boundary

This installation includes only the portable skill instructions. It does not
install or execute the repository's companion Node/TypeScript CLI, Claude Agent
SDK dependency, package scripts, hooks, or plugins. Use the host's existing URL
reader and isolated-worker tools described above.
