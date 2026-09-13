# Evaluation contract

## Required identity

Record:

- capability name and exact tested claim;
- canonical source URL, version/commit, and license;
- agent host, model, tool policy, OS, and date;
- baseline surface and staged candidate path.

## Suite

Use realistic tasks rather than instruction-compliance trivia. Include:

- representative success cases;
- hard failure cases;
- near-miss/non-trigger prompts when activation matters;
- at least one held-out case not used during adaptation.

Run fresh baseline and candidate sessions. Keep tool policy equal unless the capability's claim specifically changes tools. Blind or randomize output labels before semantic judgment.

Deterministic assertions are appropriate for files, exit codes, schema validity, forbidden destructive actions, and exact protocol requirements. Do not make wording such as `20k` versus `20,000` a hard failure when meaning is the criterion.

## Pass rule

Pass requires all:

1. every hard requirement is satisfied;
2. no critical case regresses;
3. the candidate wins at least one meaningful case and is not worse overall;
4. security and license review pass;
5. overlap resolves by replacement, extension, or rejection;
6. a fresh held-out run passes after final adaptation.

Popularity and upstream benchmarks can rank candidates but cannot satisfy this rule. Ties favor the baseline.

## Harness reliability

Validate the evaluator itself before trusting results:

- confirm multiline prompts reach each runner intact; stdin is often safer than a shell argument on Windows;
- capture only the final answer, not terminal reasoning decoration or event logs;
- record subprocess exit code, timeout, stderr, runner version, model, and judge host;
- treat judge parse errors and timeouts as harness failures, not candidate failures;
- keep generated transcripts local when they contain private data; commit only suites and compact summaries.

### Candidate bundle integrity

Evaluate the capability that would actually be installed, not only its top-level `SKILL.md`:

- resolve required local Markdown/text references inside the candidate directory and include them in the candidate fixture;
- compute one deterministic candidate hash over relative paths plus file bytes, and also hash the suite and harness;
- reject compact summaries when any evaluated artifact hash differs from the current artifact;
- treat a response that claims a required linked file is missing as a harness defect when that file exists in the candidate package;
- preserve the invalidated result as historical or contradictory evidence, but never use it to authorize promotion.

### Baseline isolation

A candidate is staged only when the baseline cannot discover it:

- keep the repository and candidate package outside live discovery roots such as `~/.agents/skills`, host skill stores, configured external directories, and enabled plugin trees;
- use separate empty working directories and fresh session state for baseline, candidate, and judge runs;
- expose candidate instructions and bundled resources only to the candidate run;
- when authentication is required, construct a temporary runner home containing only the minimum credential material, not user config, plugins, skills, or session state, and remove it after the run;
- before an expensive suite, run a sentinel probe that asks for a unique candidate description or resource available only through discovery; the baseline must not reproduce it.

Do not rely on a temporary `HOME` override alone when a host resolves its user skill root through the operating system profile. Moving the staged repository outside the live discovery tree is the reliable fix.

### Judge scope

Apply case criteria to that case's `hard_pass`. Suite-wide claims are coverage requirements across the suite, not extra requirements that every individual answer must mention. Otherwise a correct focused answer can hard-fail for omitting unrelated architecture or workflow details.

Declare the judge host/model in the evidence. A second judge may investigate a material ambiguous loss, but do not select judges after seeing outcomes or discard an unfavorable judgment without recording the disagreement.

## Promotion record

Record adaptations, installed paths, superseded owners, rollback command, natural-trigger smoke test, and the condition that should trigger re-evaluation.
