# Optional authoring review

Use this when a persistent skill or instruction edit risks later ownership, overlap, model-evidence, or catalog rework. It is an optional preview, not a hook, mandatory intake, evaluator, or permission to publish. Small known-owner repairs can proceed directly.

From the Agent Sync source checkout, before editing:

```text
python tools/reconcile.py review --target skills/NAME/SKILL.md --candidate STAGED/NAME/SKILL.md --host codex --host hermes
```

The target selects the canonical source owner. Candidate/baseline files are read without execution. Preserve the full staged skill package and linked references when comparing package behavior; a renamed standalone Markdown candidate is a text projection.

After editing, reuse the same review alongside the ordinary reconciliation plan:

```text
python tools/reconcile.py plan --target skills/NAME/SKILL.md --baseline SAVED/NAME/SKILL.md --host codex --host hermes
```

Both entrypoints call the same function. The review uses the existing intake classifier, registry and instruction-surface ownership. It reports description/body size and a token-based overlap shortlist. The shortlist is not proof of semantic overlap; compare each owner's unique procedures and native strengths before consolidation or retirement. No length threshold alone establishes poor quality.

## Publication necessity record

Managed instruction publication uses the existing `evals/results` change evidence, not a new review service. In one selected receipt, add `instruction_changes`: records with `owner`, `basis` (`user-correction`, `observed-deviation` or `mechanical-maintenance`), `deviation`, `evidence`, `baseline_sufficient`, `why_instruction`, `alternative`, and `artifacts`. Each artifact maps its canonical path to exact `before_sha256` and `after_sha256`; absent files use `absent`.

The deviation comes from the author's required outcome. Assess the current model and system before assuming prose is needed; include no change and the existing tool/runtime as alternatives. If the baseline is sufficient, add no rule. A checked pure deletion may use `change_kind: remove` with that assessment; the tool rejects added or rewritten content disguised as removal. Other records default to `add-or-change`. A mechanical repair can use directly verified evidence; no model comparison is required by this record. Correct source ownership, complete reasoning and exact bindings are checked before publication. The tool does not judge taste, authenticate human approval or turn a filled record into quality evidence.

Generated standing overlays inherit their selected core/adapter correction and still pass the renderer/profile checks. Source instructions need their own bound record; naming a file in `--include` does not supply it. Necessary operational protocols and explicit author corrections remain supported. Optional drafting review and inference remain optional.

## Existing/native procedure references

Use repeated `--reference-skill PATH` to inspect an existing/native skill alongside the proposal. See [useful-behavior review](useful-behaviors.md). The same source inventory and judgment questions are available before editing and with `plan --target`; source names or website links alone do not establish preservation of the source workflow.

## Official guidance and exact models

For OpenAI model-specific prompt edits, use OpenAI Docs when available, otherwise retrieve current official guidance for the exact requested model. Keep source URLs and observation date with the comparison. The bundled guide is a fallback; an official link alone is not proof that it was read. Do not replace shared guidance with Astra-only policy without checking affected Sol/Luna workloads.

The review suggests cells from the declared current model profile. Narrow native-only changes with `--host`. Add a session-selected model with `--model`; additional models inherit that host's provider/reasoning and are requested comparison cells, not verified supported routes. The command does not refresh live runtime observations.

## Measurement already available

- `tools/eval.py`: exact-model, fresh baseline/candidate comparisons of injected text, tool-free. Suitable for instruction decision boundaries; not natural triggering, scripts, or a complete live prompt stack.
- Artifact pilot: a bounded injected-instruction/artifact study with an independently executed oracle. It excludes full workflow equivalence and natural discovery.
- Native diagnostic: assembly-only and currently blocked before behavioral inference. Full-stack claims remain unsupported until its named fidelity and lifecycle checks pass.

Keep one existing `eval_gate` per exact model stack. The review indexes separate cells; it does not pool models or relax gate equality. Supply actual reports and independently sourced suites with repeated `--evidence REPORT --suite SUITE`. The index matches host, exact model/provider/reasoning, candidate/baseline identities and suite hashes, then uses the existing recorded-evidence validator. Omit `--evidence`/`--suite` to scan top-level public result/suite files; skipped/unreadable/non-comparative records remain counted.

`recorded-text-comparison` means a consistent comparison record exists for the requested cell; rejected, tied or inconclusive outcomes still count as comparisons. `positive_decision_sufficient_in_record` is the existing validator's result, not execution authentication, SME review or general quality. Structural/profile checks and tool callability never fill this cell.

Do not launch inference just to make a checklist green. Choose cases that can distinguish the change, verify the oracle and lane, name the budget/stop condition, and preserve authorization. Record narrower successes and unsupported claims explicitly. This tool itself performs no inference, mutation, admission, deployment, or publication.
