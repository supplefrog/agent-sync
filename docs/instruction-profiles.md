# Model-qualified instruction profiles

The [current defaults profile](../profiles/current-observed-defaults.json) records configured defaults and exact retained standing artifacts. Codex and Hermes default to GPT-6 Sol/medium; OMP retains Astra/xhigh. A selected chat may override its host default. Earlier profiles are superseded evidence, not live identities or quality/parity claims.

| Host | Runtime | Default model / reasoning | Standing-file bytes | Budget |
|---|---|---|---:|---:|
| hermes | 0.21.5+2453.gd0288be.dirty | GPT-6 Sol / medium | 1,945 | 2,048 |
| codex | 0.158.0-alpha.2.1 | GPT-6 Sol / medium | 1,970 | 2,048 |
| omp | 18.2.6 | GPT-6 Astra / xhigh | 0 | 2,048 |

Current evidence is in `evals/results/astra-surface-repair-20260926.json`. Live recovery and profile checks passed after separate ongoing work resolved the earlier recovery conflicts; artifact-only checks alone still do not prove live settings. Active conversations were not restarted.

Run `python tools/instruction_profile.py` to resolve the one `current-observed` profile and check its bindings against installed settings. Missing or multiple current profiles fail rather than silently selecting an obsolete model. `--artifact-only` checks repository bindings without proving live settings.

The standing-unit inventory in `contracts/instruction-units.json` is one part of the effective-surface audit. Skills, tool schemas, hooks, configurable native prompts, routing, and memory injection mechanisms must also be considered. Recovery excludes credentials, personal memory contents and sessions; that exclusion does not exempt their mechanisms from review. Prompt assembly order is distinct from instruction authority.

Fresh Codex prompt inspection, Hermes native skill loading, and OMP RPC discovery are separate checks. OMP's supported discovery providers include Codex inheritance, but exact duplicate precedence must be observed; a flag or identical file is insufficient evidence. Already-running applications may retain previously assembled settings or prompts.

The inline evaluator's current native lane is `inline-text-no-tools-v1`. It tests the supplied instruction-text projection, not packaged scripts or unrestricted tool behavior. Explicit injection does not test natural triggering. Public summaries derive machine decisions from validated evidence and preserve scope; editorial labels cannot manufacture admission. Historical recorded-only summaries remain unvalidated records.

The separate [native instruction diagnostic checkpoint](native-instruction-diagnostic.md) records an assembly-only adapter and its unresolved runtime boundaries. It has no inference command and grants no admission/retirement authority; blocked preflight evidence must not be called a full-stack comparison or an instruction-health result.

For a mechanism fix, replay the failure and relevant valid cases. For a claimed model-quality improvement, compare the affected current runtime and hold out cases from development. Keep missing-host evidence, uncertainty, and rollback explicit. Existing governance and budget choices remain reviewable within the authorized task.
