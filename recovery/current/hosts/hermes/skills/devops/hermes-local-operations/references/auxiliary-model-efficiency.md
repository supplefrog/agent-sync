# Hermes auxiliary model efficiency

Use this reference when optimizing a local Hermes install for cost, latency, or provider-quota isolation.

## Key runtime behavior

`auxiliary.<task>.provider: auto` does not mean "use the cheapest model". In current Hermes, auto first tries the main chat provider plus main chat model for text auxiliary work, then falls back through available providers. This is intentional for predictable behavior, but it means expensive main models can be used for side tasks unless per-task overrides are set.

Therefore, when the user asks for efficiency, explicitly configure `auxiliary.<task>.provider` and `auxiliary.<task>.model` instead of relying on `auto`.

## Built-in auxiliary slots seen in config

- `vision`: image/screenshot analysis. Must use a vision-capable model; do not route to a text-only nano model.
- `web_extract`: web page extraction/summarization. Cheap long-context model is usually better than the absolute weakest model.
- `compression`: context summarization. High impact on conversation quality; use cheap-but-reliable long-context, not the dumbest title model.
- `skills_hub`: skill search/install reasoning. Good weak-model candidate.
- `approval`: smart command approval/risk classification. Good weak-model candidate if smart approvals are enabled.
- `mcp`: MCP tool reasoning. Good weak-to-medium candidate depending on server complexity.
- `title_generation`: cosmetic session title. Use the weakest acceptable text model.
- `triage_specifier`: Kanban rough-task-to-spec expansion. Weak/cheap is usually fine.
- `kanban_decomposer`: Kanban decomposition into task graphs. More reasoning-heavy; use cheap-but-capable.
- `profile_describer`: profile description generation. Excellent weakest-model candidate.
- `curator`: background skill review/maintenance. Potentially long and reasoning-heavy; use cheaper than main but not necessarily weakest.
- `session_search`: old config block may exist, but current source says session_search no longer uses an auxiliary LLM; treat as harmless leftover.

## Suggested efficiency tiers

Weakest text model, only on a stable provider the user wants to spend against:

- `title_generation`
- `profile_describer`
- `approval`

Weak/cheap candidates that may still influence workflow quality; do not downshift under a strict "zero output impact" request without user consent:

- `skills_hub`
- `mcp`
- `triage_specifier`

Cheap but capable / long-context text model:

- `compression`
- `web_extract`
- `kanban_decomposer`
- `curator`

Cheap vision-capable model:

- `vision`

## Provider-quota and reliability isolation pattern

When a provider must be reserved for another local service, remove its active keys from Hermes env/profile env files and explicitly route Hermes auxiliary slots elsewhere.

Do not assume every authenticated provider is acceptable for stable auxiliary work. For this user, OpenRouter, OpenCode Zen, and NVIDIA/NIM are experimental/free-tier paths with potentially wonky availability under demand; do not route stable Hermes auxiliary tasks there unless the user explicitly asks to experiment. Prefer direct OpenAI for low-impact weak-model slots when an `OPENAI_API_KEY` is available. If no OpenAI API key is configured, report that instead of silently falling back to experimental/free-tier providers.

Keep quality-sensitive slots on `auto` when the user asks for "zero impact on output quality" unless they explicitly accept quality/continuity risk. In particular, leave `compression` on the main/default model path rather than forcing the weakest model; compaction quality can affect every later answer.

## Commands pattern

Set per profile, not just default, when the user uses multiple profiles. Direct OpenAI routing uses the `openai` provider alias, which Hermes expands to `https://api.openai.com/v1` and `OPENAI_API_KEY`:

```bash
hermes config set auxiliary.title_generation.provider openai
hermes config set auxiliary.title_generation.model gpt-5.4-nano

hermes --profile lite config set auxiliary.title_generation.provider openai
hermes --profile lite config set auxiliary.title_generation.model gpt-5.4-nano
```

For the user's "StepFun with Hermes provider" phrasing, do **not** assume direct StepFun API (`provider: stepfun`) or OpenRouter. In this setup they mean the StepFun model exposed through the Hermes/Nous provider. Use `provider: nous` and the catalog model id, currently `stepfun/step-3.7-flash`:

```bash
hermes config set auxiliary.title_generation.provider nous
hermes config set auxiliary.title_generation.model stepfun/step-3.7-flash
```

Apply the same `provider=nous, model=stepfun/step-3.7-flash` pair to the requested auxiliary text slots. Keep `vision` on `auto` unless a vision-capable StepFun/Hermes model is explicitly available, and leave `session_search` alone when current source indicates it no longer uses an auxiliary LLM.

Repeat for `dev`, `browser-agent`, or any profile the user actually launches. Good zero/near-zero-output-impact targets are `title_generation`, `profile_describer`, and `approval`; leave `compression`, `web_extract`, `vision`, `mcp`, `skills_hub`, `triage_specifier`, `kanban_decomposer`, and `curator` unchanged unless the user accepts the tradeoff.

After editing env files or provider keys, restart existing Hermes CLI/dashboard/gateway processes; running processes may retain inherited environment variables even after `.env` files are cleaned.

## Pitfalls from session learning

- Do not route cosmetic tasks such as title generation to the strongest/main model when the user asked for the weakest available model.
- Do not assume Hermes will automatically optimize auxiliary model cost; inspect config/source and set explicit per-task overrides.
- Do not route stable auxiliary tasks through experimental/free-tier providers such as OpenRouter, OpenCode Zen, or NVIDIA/NIM for this user unless explicitly asked.
- Do not silently rely on provider fallback when the intended direct provider lacks credentials; tell the user `OPENAI_API_KEY` or the chosen provider key is missing.
- Do not misread “StepFun with Hermes provider” as direct StepFun API or OpenRouter. For this user's Hermes setup, use the Nous/Hermes route: `provider: nous`, `model: stepfun/step-3.7-flash`.
- Do not assign text-only weak models to `vision` without checking multimodal support.
- Compression is not cosmetic. A too-weak compression model can damage future context quality; preserve main/default-model behavior when the user wants zero impact on outputs.
