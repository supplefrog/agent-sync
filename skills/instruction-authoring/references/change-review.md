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

The R02 release categories are separate from necessity reasoning. Behavioral instruction adoption still requires the existing measured-evidence gate. `basis: mechanical-maintenance` alone never exempts prose: only content-identical CRLF/LF repairs qualify mechanically. A substantive explicit user correction limited to this owner's Evaluation discipline or this Publication necessity record uses `change_kind: contract-correction`, `basis: user-correction` and the existing necessity evidence plus one changed-intent reconciliation record binding the instruction, requirements and status. This is contract policy, not a claim of model improvement; it cannot mix behavioral-measurement/claim fields. Existing ownership, dependency, loading and framework reviews still apply. Record validation cannot authenticate the declared authority or semantic scope; the responsible owner must inspect those before publication. Other prose, trigger, workflow and model-quality changes retain measured adoption. Registry retirement follows its existing normal lifecycle review independently.

For the explicitly approved unchanged LearnHarness reader at commit `6cba9c8c5afe8a63f47ea4ebae6e91d8a205cebb`, use `change_kind: requested-reader`, `basis: user-correction` and source-bound `reader_acceptance`: exact six-file package/pin, correct synthetic session/graph reads, no data changes or credential/network/app access, explicit fork data-directory selection, and required native catalogue/body plus repeat-sync checks. This is requested capability installation, with no comparative model-benefit claim. The checker rejects other packages, changed bytes, missing acceptance or behavioral claims; source bindings/records do not authenticate approval or execution. Other instruction adoption and diagnostic evidence retain their existing rules.

Generated standing overlays inherit their selected core/adapter correction and still pass the renderer/profile checks. Source instructions need their own bound record; naming a file in `--include` does not supply it. Necessary operational protocols and explicit author corrections remain supported. Optional drafting review and inference remain optional.

For the one explicitly approved public-audience R2 correction, use `change_kind: public-audience-correction`, `basis: user-correction` and the exact source/recovery freezes and decision in `public_audience_acceptance`. The consumer pins both core/Humanizer before/after byte pairs and requires both selected sources plus bound changed requirements/status. This exception implements only user decision `public-audience-r2-20261026`; it is not measured behavioral improvement or a general prose waiver. Retain independent source/recovery review, normal necessity/dependency/loading checks, actual guarded local readback and rollback. Other changed instructions retain their existing categories and measured adoption. Receipt fields do not authenticate human approval.

## Loading review for growth and restructuring

Use the same necessity record for a substantial workflow restructuring. Set `restructured: true` when moving or materially condensing procedures even if the link set and size stay unchanged. The publication guard also requests `loading_review` when a changed entrypoint has at least 3,000 body words or more than 500 body lines, grows by at least 500 body words and 25 percent, changes local links in a changed Markdown source, or removes a Markdown source. These are review signals, not quality verdicts or hard size ceilings. Validation and advisory review expose body words, bytes and lines; unchanged legacy packages do not need retrospective receipts. Keep one loading map per changed skill owner, covering all selected changed Markdown sources even when necessity reasoning is split across records.

Add `loading_review` to the existing owner record with:

- `entrypoint_reason`: why the remaining common content is needed across the skill's tasks; explain retained substantial compulsory procedures.
- `obligations`: a compact before/after map. Each row has `obligation`, `applies_when`, `required` (boolean), `before` and `after` (lists of canonical source addresses), `disposition` (`preserved`, `changed`, `added`, `removed`), `load_when`, and `reason`. Use `path#Literal heading text` for a precise receipt address, or a file path for a whole-file mechanism. Empty `before` is allowed for an addition; empty `after` for an intentional removal. Group repeated advice, but preserve unique exceptions and conditional dependencies. Cover every changed Markdown source in the owner's record. Explain an intentional omission or policy change and its authority; restructuring itself supplies none.
- `checks`: the actual preservation/loading checks and their limits. Inspect common and conditional routes against representative tasks and a nearby non-applicable case. Verify required reads remain mandatory at the same decision point and under the same conditions. Use native routing/reference-loading probes when uncertainty could change acceptance; no compulsory inference benchmark, image generation or reviewer fan-out.

The existing before/after hashes bind this assessment to the changed sources. Publication checks the record's shape, addresses in the proper baseline/candidate, changed-file coverage, and reachability from `SKILL.md` through local links, including nested routers. It does not infer every obligation from prose, authenticate a declared check, prove semantic preservation, or establish natural triggering. A linked file can still have a wrong or optional trigger: inspect that wording before promotion. Keep unresolved behavior explicit rather than filling the record with unsupported pass claims.

A short entrypoint is not automatically economical. Loading every linked file unconditionally, splitting common rules across many reads, or losing a necessary procedure can raise total cost. A substantial universally needed protocol can remain inline with a justified review. Revisit signals only when observed workload evidence shows unnecessary review or a missed failure class.

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

## Tool and intent dependencies

For changes under `tools/`, `integrations/`, or skill `scripts/`, use the same selected `evals/results` receipt with `change_reconciliation`. Each record contains `artifacts` (exact before/after SHA256 bindings), `obligations` (one row per affected guidance/contract path with `path`, `disposition`: `updated`, `unchanged` or `removed`, and `reason`), `requirement_change` (boolean), `requirement_reason`, `authority`, `checks`, and `outcome_review` (`expected`, `observed`, `evidence`, `limitations`). Compare expected contract outcomes to actual workflow outcomes with suitable acceptance evidence; textual symmetry and structural equality are not the goal. Bind every changed executable source, reverse-linked skill/doc/adapter, and `docs/system-requirements.md` plus `docs/requirement-status.md`. Updated/removed dependencies must be selected in the same change. Unchanged guidance needs source binding and a concrete reason; touching a file is not reconciliation.

The publication check follows exact repository path references and local Markdown links in the baseline and candidate, transitively through guidance. Inspect callers and unlinked/runtime consumers too; static discovery cannot establish exhaustive dependency knowledge. User-requested new intent requires a selected change to the existing requirements and status map, with the user's authority recorded. Other managed instruction changes also assess this contract. These checks enforce coverage and source freshness, not the truth of reasoning, semantic correctness, approval or model benefit. Run the actual affected and nearby regression cases before completion. No extra judge or inference is required merely to fill a receipt.

For a framework change, the same reconciliation record includes one `framework_review` with `affected` (canonical skill/contract/doc paths), `selection_reason`, `unaffected_reason`, and `checks`. Inspect the changed framework obligations and identify their consumers; bind and reconcile affected sources without restructuring unrelated skills. Contract or skill changes also follow reverse guidance links; changed contract sources include their explicitly referenced skills and guidance. For progressive disclosure, keep required loading conditions before governed decisions and preserve the existing loading-review map; file size or reachability alone cannot establish that the routing is correct.
