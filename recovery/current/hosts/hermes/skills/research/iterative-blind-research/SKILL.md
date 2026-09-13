---
name: iterative-blind-research
description: "Use when doing serious web/GitHub research where first-pass search may miss the best answer: product/tool discovery, alternatives research, proving a target is discoverable from requirements, or acting as the user's search engine. Iteratively improves search queries without waiting for user input, logs evidence, avoids overfitting to known names/vendors, and verifies final claims."
---

# Iterative Blind Research

Use this for research where quality depends on search strategy, not just reading the first result. The goal is to behave like a strong search analyst: generate hypotheses, try diverse queries, inspect misses, mutate the search, and stop only when the answer is supported or further searching is unlikely to change it.

## Modes

### A. Useful search mode — default

Use this when the user wants you to find the best tool/product/source and may not know the answer. The pass condition is practical usefulness: enough independent evidence to make a recommendation, with alternatives compared against the user's real requirements and environment.

### B. Blind benchmark mode — optional

Use this when the user gives or implies a known target and wants to test whether you can rediscover it. The pass condition is explicit: find the target from requirements without querying its known name, author, URL, or overly unique strings unless the user allows them. This is a side evaluation method, not the default research workflow.

## Mode boundary

Only enter broad exploration when the user asked for research/discovery/comparison, the task explicitly needs current facts, or the initial search path is failing. When the active task is a focused fix, style tuning, or eval follow-through, do not resurrect stale research/eval artifacts just because they look related. Stay on the success condition the user actually named.

A good research agent should be broad **when researching** and disciplined **when executing**. The opposite failure mode — shallow research plus wandering execution — is worse than either pure verbosity or pure brevity.

## Workflow

1. **Extract the requirement vector**
   - List the functional requirements, constraints, environment, and deal-breakers.
   - Translate vendor-specific wording into neutral terms unless that vendor is genuinely part of the user's environment.
   - Anchor environment-specific queries on the user's actual tools, or use neutral terms such as “AI coding CLI”, “terminal agent”, “slash commands”, and “agent skills”. Do not substitute an unrelated vendor ecosystem.

2. **Start broad, then mutate deliberately**
   - First query: broad neutral phrase with 4-6 core requirements.
   - Inspect the top results and classify misses: too SaaS, too narrow, too old, wrong market, no install path, no local-first, no source, etc.
   - Mutate one axis at a time:
     - add a discriminating feature (`PDF`, `ATS`, `Greenhouse`, `TUI`, `batch`, `local-first`)
     - subtract likely overfitting or vendor-specific terms and see what survives
     - swap synonyms (`resume`/`CV`, `job search`/`career ops`, `tracker`/`pipeline`)
     - add nearby/random-but-plausible keywords from the domain (`agent`, `skill`, `workflow`, `dashboard`, `scanner`, `pipeline`, `ATS`, `slash command`) to escape one search cluster
     - change surface (`web search`, `site:github.com`, GitHub API, package registry, blog/news)
     - search one site/source at a time when broad search is noisy (`site:github.com`, `site:news.ycombinator.com`, package registries, docs sites, Reddit/forums, curated lists)
     - remove over-constraining terms if results are empty
   - Do not blindly run the full cartesian product of all query variants across all sources. Use a small budgeted matrix: 3-5 query variants × 2-4 high-value surfaces first, then expand only where the result set changes or coverage is known to be weak.
   - Continue until a stable top set emerges or the remaining gaps are clear.

3. **Handle non-indexed or weakly indexed sources**
   - Some high-signal sources are not directly searchable by public web search (Discord, private Slack, gated forums, logged-in communities, newsletters behind JS, some X/Twitter threads).
   - Use indirect discovery first: search invite pages, announcement posts, docs, GitHub issues, release notes, blog posts, mirrors, exported transcripts, and search-engine snippets that quote the hidden source.
   - If access exists through a native tool, API, export, bot, MCP server, or browser session, search that source directly and cite the access path.
   - If access does not exist, label it as a coverage gap instead of pretending the source was searched. Recommend concrete fixes: connect a Discord/Slack/search MCP, export channel archives, use platform-native search manually, or add a small ingestion script that indexes allowed archives into local FTS.

4. **Run independent strategies when useful**
   - Keyword strategy: natural-language descriptions.
   - Repository strategy: GitHub search/API, topics, language filters, stars/activity.
   - Ecosystem strategy: adjacent toolchain terms, slash commands, agent-skill registries, package names, integration names.
   - Alternative-first strategy: find broad competitors, then compare their gaps against the requirements.
   - Technical solutions: choose implementation, practitioner, and academic sources by the decision and the user's requested evidence. Do not require a completed GitHub sweep before relevant literature. Verify implementation claims against canonical source/tests; check primary papers and version/withdrawal status, and distinguish design evidence from production validation. Use `neuroarxiv` for genuinely new project-architecture questions that remain unresolved.

5. **Interrogate a canonical GitHub shortlist when useful**
   - Stage repository acquisition by decision maturity: during discovery and broad shortlisting, default to direct GitHub APIs/raw source plus deterministic cross-repository code search (for example Sourcegraph public search). Once a candidate becomes a finalist, pilot, integration target, or deployment choice, clone the canonical repository at an exact revision, run its real build/tests and relevant execution probes, and optionally add a local index when repeated architectural queries justify the setup cost. Keep evaluation clones isolated and clean them up when no longer needed.
   - DeepWiki is an optional orientation shortcut after discovery and canonicalization, not a required comparison stage. Use it only when several repositories must be understood along the same implementation axis and its generated explanation is likely to save targeted reads.
   - For a narrow, fixed-schema DeepWiki scan, one call may use up to the tool's 10-repository limit. Ask one capability question per pass with explicit repo labels; use smaller groups or individual queries when the comparison requires architectural depth.
   - Treat multi-repo output as partial until checked. Parse returned repo identities programmatically against the requested set and preserve input order during normalization. A missing repository is an omission, never `NOT_FOUND`; retry omissions individually once, then fall back to direct source inspection if the call fails or remains incomplete. Reduce scope when output becomes bloated, malformed, or loses provenance.
   - Use generated explanations only to identify likely implementation paths, architectural differences, and which claims deserve inspection. Do not repeat full repository inspection for every candidate by default; inspect decision-critical evidence for the leading 2-3 plus any candidate whose elimination depends on an absence claim.
   - Treat DeepWiki output as orientation, not authority. Verify claims of absence, security or lifecycle behavior, current-version behavior, and every winner-determining distinction against canonical source, tests, issues, releases, and commit state. An answer without an index commit or timestamp is not freshness evidence.

6. **Keep a query log**
   - Record exact queries and why each was tried.
   - Record top hits and why they passed/failed.
   - Failed queries are useful evidence; they teach which wording does not expose the answer.

7. **Verify outside the search snippet**
   - Open/extract the repo or official page.
   - For GitHub, verify canonical repo, stars/forks, license, recent activity, install path, README claims, and whether forks/mirrors are involved.
   - Prefer official metadata/API over blog summaries when deciding canonicality.
   - Parent must verify important subagent claims before reporting them as fact.

8. **Decide and report**
   - Do not declare “best” from popularity alone.
   - Compare against the requirement vector.
   - Separate “best full match” from “best specialist alternative”.
   - State confidence and remaining uncertainty.

## Blind benchmark rules

Use these only when the task is explicitly a test of discoverability.

- Forbidden strings include known target name, author, URL, exact repo slug, and exact tagline if the user says the test must be stricter.
- If a query uses a unique tagline from the known project, label it as a weak pass or overfit.
- Stronger pass: neutral/environment-accurate queries find the target, and at least one independent query path also points to it.
- Canonicalize forks/mirrors via GitHub API sorted by stars or package metadata.

## GitHub API checks

Use the existing `github-collaboration-workflows` owner for authenticated GitHub access rather than embedding a second HTTP client here. For repository search, use an explicit GET request, for example:

```bash
gh api --method GET search/repositories -f q='local-first dashboard' -f sort=stars -f order=desc -F per_page=10
```

Preserve the command's exit status and error output. HTTP/auth/rate-limit failures, malformed JSON, and missing or invalid `total_count`, `items`, or `incomplete_results` fields are failed acquisition, not an empty search. A successful response with `total_count: 0` and `items: []` is a valid empty result only when `incomplete_results` is false. Otherwise retain the coverage gap. Returned items are one bounded page, not the declared total; paginate when the claim requires complete coverage. Do not mask a failed producer with a succeeding formatting command.

## Reporting format

Use a compact structure:

```markdown
## Search strategy
| Query | Why this mutation | Top useful hits | Failure/miss notes |

## Shortlist
| Candidate | Evidence | Fit vs requirements | Gaps | Verdict |

## Recommendation
- Best full match: ...
- Best specialist alternative: ...
- Not recommended: ...
- Confidence / uncertainty: ...
```

For blind benchmark mode, add:

```markdown
## Pass condition
## Proof query/proof path
## Canonical verification
```

## Pitfalls

- Do not anchor on a vendor/tool the user is not using; search the verified environment or neutral terms.
- Do not let a subagent violate forbidden-query rules unnoticed; audit its query log.
- Do not stop after finding a known-looking result if the query was overfit. Try a neutral paraphrase too.
- Search snippets can be stale or SEO-contaminated; verify official sources.
- Forks and mirrors may outrank or obscure canonical repos; canonicalize before recommending install.
- If broad queries surface a different strong match, investigate it rather than forcing the expected target.
