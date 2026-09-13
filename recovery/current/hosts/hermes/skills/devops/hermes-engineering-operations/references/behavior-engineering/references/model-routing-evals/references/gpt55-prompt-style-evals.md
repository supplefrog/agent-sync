# GPT-5.5 prompt/style tuning for Hermes

Session lesson: when Hermes answers become too verbose or over-structured on GPT-5.5, do not keep adding ad hoc style rules blindly. First check the current OpenAI prompt guidance, then run small fresh-session probes.

## Authoritative guidance checked

OpenAI GPT-5.5 prompt guidance highlights:

- Shorter, outcome-first prompts usually work better than process-heavy prompt stacks.
- Re-evaluate `low` and `medium` reasoning effort before escalating.
- GPT-5.5 works best when prompts define the outcome, constraints, available evidence, and final answer shape, while leaving room for the model to choose the path.
- Avoid carrying over every instruction from older prompt stacks; legacy process-heavy prompts can add noise and produce mechanical answers.
- For short outputs, set `text.verbosity` to `low`; API default is `medium`.
- Plain paragraphs should be the default for normal conversation. Use headers, bold text, bullets, and numbered lists sparingly, mainly when the user asks or comparison/ranking needs scanability.

## Hermes-specific diagnosis pattern

1. Inspect the live config and prompt stack before changing it:
   - `agent.system_prompt`
   - `agent.reasoning_effort`
   - `display.show_reasoning`
   - loaded skills whose descriptions may over-trigger formal templates
   - SOUL.md style section
2. Run 2-4 fresh-session probes with realistic prompts:
   - one trivial command/fact prompt,
   - one ordinary tradeoff/advice prompt,
   - optionally one explicit "give me options" prompt to ensure formal skills still trigger only when requested.
3. Compare output shape, not just word count:
   - direct first sentence?
   - unnecessary headers/templates?
   - follow-up offers appended?
   - caveats that change the decision vs filler?
4. Prefer the smallest fix that changes behavior:
   - narrow `agent.system_prompt` overlay for final-answer style,
   - fix only genuinely wrong skill behavior; do not weaken a class-level skill just because its structured output felt verbose in one session,
   - lower reasoning effort if quality is unchanged,
   - verify whether API `text.verbosity: low` is actually supported in the active Hermes API mode before recommending it.

## Hermes system-prompt and API surfaces

Hermes has an additive runtime system-prompt overlay:

- `HERMES_EPHEMERAL_SYSTEM_PROMPT` takes precedence.
- `agent.system_prompt` in the active profile config is the persistent overlay.
- The overlay is appended to the cached base system prompt at API-call time and is intentionally kept out of the cached/stored base system prompt.

For OpenAI/Codex verbosity, distinguish prompt overlay from API support. As of the inspected Hermes path, `request_overrides` can inject request fields, but top-level Responses API `text: {"verbosity": "low"}` is not a clean first-class Hermes knob: the Codex Responses preflight whitelist does not include `text`, while `extra_body` is passed through but needs live backend verification before claiming it works. Do not tell the user this API dial is implemented unless you have inspected the active code path or verified a live request.

## Known effective overlay shape

A concise overlay pattern that tested well, with the important constraint that concision must not suppress steering or class-level skill triggers:

```text
Final answer style: answer simple questions with only the answer. For ordinary advice, give the direct recommendation plus only the caveats that change the decision. Be blunt and critical when useful. Avoid formal proposal scaffolding unless the task genuinely calls for structured decision-making, options analysis, or the relevant skill triggers. Do not append follow-up offers. Concision must not suppress pushback, missing context, or steering the user away from a bad plan.
```

This improved a simple prompt to a one-command answer and kept an ordinary hosted-auth tradeoff answer compact/direct, while preserving automatic trigger behavior for structured-decision skills such as `one-three-one-rule` when their use case applies.

## Pitfalls

- Do not treat mini-SWE-agent's prompt as generally superior. Its advantage is a narrow coding loop and minimal scaffold: inspect, reproduce, edit, verify, submit. That is useful as a coding task mode, not as Hermes' global behavior.
- Do not copy mini-SWE-agent's bash-only assumptions into Hermes. Hermes' value is its broader real-world tool surface.
- Do not patch or narrow `one-three-one-rule` merely to reduce verbosity. The user expects it to trigger automatically for its configured use case; they will not necessarily type "1-3-1" explicitly. If its output is unwanted, first verify the task was outside its class before changing the skill.
- Do not equate concise style with refusing to steer. The user may lack important context; add pushback, caveats, or extra explanation when it materially changes the decision or prevents a bad plan.
- Do not hide or disable visible reasoning as a style fix unless the user explicitly asks. The user's preference is visible reasoning that can be minimized, not removed.
- Do not save transient run paths or per-session outputs as memory; keep reproducible lessons here.
