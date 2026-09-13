# Implicit skill-routing evaluation

Use when an agent should infer the right workflow from an ordinary outcome request, or when implicit skill/plugin activation seems inconsistent. Optimize correct workflow use, not activation count.

## Resolve the real surface

Measure these layers separately:

1. **Source inventory** — skill/plugin folders present on disk.
2. **Configured state** — enabled/disabled skill and plugin entries.
3. **Runtime resolution** — active marketplaces, precedence, duplicate names, plugin gates, and current host/version.
4. **Model-visible index** — the exact names/descriptions exposed to a fresh model turn.
5. **Selected workflow** — evidence that the full workflow was actually loaded and used.

Do not infer availability or breakage from cache contents alone. A cached plugin may be disabled or stale; an enabled plugin may expose capabilities through a plugin gate rather than the static skill index. Conversely, a skill folder can exist while its description is omitted from the model-visible budget.

For Codex, use primary runtime readbacks:

```text
codex --version
codex plugin list --json
codex debug prompt-input
```

Parse the `### Available skills` section from `debug prompt-input`; count entries, description characters, duplicate owner names, relevant expected skills, and truncation/omission warnings. Inspect `agents/openai.yaml` for `policy.allow_implicit_invocation: false`. Re-run in a fresh thread after any staged configuration or plugin change.

## Candidate designs

Compare coherent alternatives rather than accumulating instructions:

- **Native implicit matching:** host selects a workflow from concise skill descriptions.
- **Deterministic routing:** explicit inventory, admission, overlap resolution, and verification rules select the owner.
- **Hybrid:** native matching proposes likely workflows; deterministic rules govern material/novel selection, existing-solution research, conflicts, safety, and verification.

The hybrid is a candidate, not a presumption. A native implementation may outperform custom steering; an established deterministic owner may outperform nondeterministic matching. Select from evidence.

## Probe contract

Use isolated equivalent homes and repeated fresh sessions. Keep model/provider snapshot, reasoning, prompt assembly, enabled tools/plugins, context budget, and evaluator identity fixed or fingerprinted.

Include:

- representative prompts that should activate one workflow;
- paraphrased outcome-only prompts with no skill name;
- near misses that should not activate it;
- ambiguous prompts with two plausible owners;
- adversarial prompts that encourage broad/random activation;
- held-out tasks testing end-to-end outcome quality;
- plugin-gated and disabled-skill controls.

Record actual workflow-load/tool traces, not agent self-report. Evaluate correct owner selection, false activation, task success, preserved safety/research/evaluation gates, latency, and total retry cost. Exact wording is not a behavioral invariant.

## Decision and promotion

1. Identify the exact failure mechanism: description mismatch, model-visible omission, duplicate/overlap, explicit policy disablement, plugin gate, instruction conflict, or model variance.
2. Prefer fixing the narrow owner/description/configuration over adding global steering.
3. Promote only a candidate that materially improves held-out behavior without weakening protected gates.
4. Stage persistent changes outside live stores; retain stack hashes, paired observations, rollback, and required approval.
5. Verify fresh-runtime discovery and one real outcome task after promotion.

## Pitfalls

- Treating every installed or cached skill as model-visible.
- Declaring implicit routing broken because one run missed a skill.
- Requiring users to name skills, defeating outcome-driven discovery.
- Forcing a global “always search every skill” rule that increases random activation and prompt cost.
- Unioning native and custom routing instructions instead of selecting one coherent responsibility split.
- Enabling or installing another plugin before measuring the baseline, contaminating attribution.
