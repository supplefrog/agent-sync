# Model-qualified instruction profiles

The [current Astra profile](../profiles/gpt-6-astra-openai-codex.json) records foreground defaults and exact retained standing artifacts. It is an observation, not a claim of universal prompt quality or cross-host behavioral parity. The earlier Sol profile is preserved as superseded evidence.

| Host | Runtime | Reasoning | Selected standing bytes | Budget |
|---|---|---|---:|---:|
| hermes | Hermes Agent 0.21.0 | low | 1,869 | 2,048 |
| codex | codex-cli 0.153.4 | xhigh | 2,018 | 2,048 |
| omp | omp 18.1.10 | xhigh | 2,018 | 2,048 |

Run `python tools/instruction_profile.py` to resolve the one `current-observed` profile and check its bindings against installed settings. Missing or multiple current profiles fail rather than silently selecting an obsolete model. `--artifact-only` checks repository bindings without proving live settings.

The standing-unit inventory in `contracts/instruction-units.json` is one part of the effective-surface audit. Skills, tool schemas, hooks, configurable native prompts, routing, and memory injection mechanisms must also be considered. Recovery excludes credentials, personal memory contents and sessions; that exclusion does not exempt their mechanisms from review. Prompt assembly order is distinct from instruction authority.

Fresh Codex prompt inspection, Hermes native skill loading, and OMP RPC discovery are separate checks. OMP's supported discovery providers include Codex inheritance, but exact duplicate precedence must be observed; a flag or identical file is insufficient evidence. Already-running applications may retain previously assembled settings or prompts.

The inline evaluator's current native lane is `inline-text-no-tools-v1`. It tests the supplied instruction-text projection, not packaged scripts or unrestricted tool behavior. Explicit injection does not test natural triggering. Public summaries derive machine decisions from validated evidence and preserve scope; editorial labels cannot manufacture admission. Historical recorded-only summaries remain unvalidated records.

For a mechanism fix, replay the failure and relevant valid cases. For a claimed model-quality improvement, compare the affected current runtime and hold out cases from development. Keep missing-host evidence, uncertainty, and rollback explicit. Existing governance and budget choices remain reviewable within the authorized task.
