---
name: hermes-model-routing-evals
description: Evaluate Hermes main, auxiliary, delegation, and provider routes with isolated representative tasks, live account availability checks, repeated calls, externally verified outcomes, token/tool/API usage, latency, and real rate-limit/error behavior before changing defaults.
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, models, routing, evaluation, cost, benchmarks]
    related_skills: [hermes-self-engineering, delegation-workflows, lean-code-repair]
---

# Hermes Model Routing Evaluations

Use this when model/provider/routing choice is the variable. Do not optimize from benchmark reputation, catalog visibility, price, or one successful prompt.

The decision target is task-class reliability and quality under the user’s real harness. A nominally free model that stalls, rate-limits, or breaks tool use is not a usable default.

## 1. Define the route and acceptance bar

Specify:

- task slot: main chat, delegation, compression, extraction, approval/review, title, vision, etc.;
- representative task class and risk;
- baseline route;
- quality/reliability threshold;
- cost, quota, or latency objective;
- constraints such as provider quotas reserved for another service.

Compare like with like. A cheap bounded worker is not a substitute benchmark for parent-level architecture or ambiguous debugging.

## 2. Check live availability

Before runs:

- inspect active Hermes config and auth source without printing secrets;
- query/probe the provider’s live account model surface;
- send a minimal real request because listed models may still be uncallable;
- record rate-limit, quota, account-tier, streaming, and API-mode constraints;
- verify Hermes transport/config accepts the route and request fields.

Do not persist temporary provider rankings as memory. They age quickly.

## 3. Isolate variants

Use disposable task copies and per-run `HERMES_HOME` directories. Keep fixed:

- task inputs and fixture state;
- model-independent prompt/harness;
- tool surface and coding-context mode unless under test;
- reasoning effort unless under test;
- acceptance tests.

Copy only required config/auth material. Never expose credentials in artifacts or summaries.

## 4. Use representative suites

Prefer several small deterministic tasks over toy one-line prompts. Depending on route, include:

- strict concise/structured output;
- domain reasoning or repair task;
- tool use with a real side effect;
- actual `delegate_task` compatibility for delegation routes;
- realistic long-input faithfulness for compression/extraction;
- malformed or boundary inputs;
- repeated calls to expose 429/5xx/latency variance.

For coding/agent tasks, independently run tests and inspect diffs after each invocation. Do not grade the agent’s self-report.

For auxiliary summarizers, grade factual retention, omissions, unsupported conclusions, and format before speed. For cosmetic slots, latency/cost can dominate once minimum quality is met.

## 5. Capture metrics

Record per run:

- pass/fail and failure class;
- externally verified acceptance result;
- input, cached-input, output, and reasoning tokens where available;
- API and tool call count;
- elapsed time;
- provider errors, retries, 429/5xx, malformed output, or empty visible content;
- changed files/artifacts for agent tasks.

Hermes run homes may expose usage in the latest `state.db` session. Keep machine-readable `summary.jsonl`/CSV plus full artifacts when useful.

Aggregate success rate and latency distribution; averages alone hide intermittent stalls. Repeat enough to detect the practical failure mode, not to manufacture false statistical precision from a tiny suite.

## 6. Interpret by slot

- **Main/parent:** prioritize capability, judgment, and reliability.
- **Delegation:** require bounded instruction following, tool compatibility, easy verification, and live concurrency behavior.
- **Compression/extraction:** faithfulness first; a fast model that drops decisions or invents conclusions fails.
- **Approval/review:** false approvals and missed risk matter more than verbosity.
- **Titles/classification:** use the weakest reliable route that meets formatting and latency needs.
- **Vision:** verify actual image support, not text-only model naming.

A cheaper candidate wins only when it preserves the acceptance bar for that slot. Report small-suite limits honestly.

## 7. Apply cautiously

1. Recommend the route and scope before mutation when tradeoffs are meaningful.
2. Change only the task-specific config keys.
3. Read back config and run `hermes config check`.
4. Start a fresh Hermes process/session if routing is snapshotted.
5. Run one post-apply smoke task through the real slot.
6. Keep rollback simple by recording the prior values, not by accumulating permanent backup files.

Do not silently route Hermes through provider quota reserved for another service. Do not change main-model defaults to solve an auxiliary slot.

## Useful existing references

Load only when relevant and revalidate current facts:

- `references/codex-auxiliary-routing.md` — transport/request acceptance probe patterns.
- `references/mini-vs-focus-benchmark.md` — isolated Hermes repair benchmark mechanics.

Dated model names/results in references are examples, not current recommendations.

## Pitfalls

- A configured auxiliary slot name does not prove every same-named feature invokes that model. Trace live call sites first. For example, ordinary URL `web_extract` may be backend-only/model-free while `auxiliary.web_extract` is used only for LLM reduction of oversized browser snapshots; benchmark the model-invoking path, not the label.
- Catalog visibility is not callability.
- One strict-JSON success does not prove tool/delegation compatibility.
- Tight token caps can yield empty visible output from reasoning models.
- Free-tier nominal cost can be dominated by latency, 429s, and capacity errors.
- Changing prompt, tools, model, and reasoning simultaneously makes the comparison uninterpretable.
- Reusing previous results is good only when provider availability and task harness still match.
