# Computer-use end-to-end latency

Use when computer use feels slow, especially when the visible pause occurs before the first tool call. Measure the desktop driver and the complete agent turn separately; do not assume cua-driver is the bottleneck.

## Diagnostic partition

1. Record the active Hermes version, provider/model, profile, frontend, and effective request controls.
2. Run and time `hermes computer-use doctor` several times. This isolates driver startup, MCP reachability, UI Automation, and capture health.
3. Time a fresh model → tool → answer turn with a fixed harmless prompt and fixed toolset. Use `hermes chat --source tool --oneshot -Q ...`; record and later delete every agent-created test session.
4. Run `hermes prompt-size` to attribute payload to system guidance, core tool schemas, skills, and deferred plugin/MCP tools.
5. Inspect SOUL/personality/project instructions for policies that require organization, confirmation, or narration before clear reversible actions.
6. Compare installed source with current official Hermes and provider docs before claiming a native feature is exposed.

If the doctor is fast but the whole turn is slow, the dominant cause is model/request orchestration, prompt payload, or instruction policy—not the desktop driver. One end-to-end run is weak evidence because provider latency is noisy; repeat equivalent variants.

## Supported optimization order

1. **Instruction policy:** let clear reversible requests proceed immediately while preserving clarification for ambiguity that changes the action. Do not weaken safety, scope, or verification.
2. **Reasoning effort:** test `agent.reasoning_effort: low` against the current baseline for ordinary tool-driving requests. Keep higher effort available for genuinely hard analysis.
3. **Priority processing:** when the user values latency over quota/cost and the provider supports it, test `agent.service_tier: fast`. State the tradeoff and verify that the active main and auxiliary transports actually forward it.
4. **Text output:** keep provider-native output verbosity low where supported. This reduces answer generation but does not replace reasoning-effort measurement.
5. **Tool Search:** retain upstream progressive disclosure when it already defers MCP/plugin tools. Core Hermes tools are deliberately non-deferrable; disabling them may lower payload but is not a free optimization when every chat must retain broad capability.
6. **Update path:** if upstream contains relevant transport or liveness fixes, update only with approval and outside active Desktop/TUI work. Never bypass a blocked updater.

Useful commands:

```bash
hermes config set agent.reasoning_effort low
hermes config set agent.service_tier fast
hermes prompt-size
hermes computer-use doctor
hermes update --check
```

Read config back and verify in a fresh process/session because request and prompt surfaces may be snapshotted at startup.

## A/B verification

Keep the prompt, toolset, model, provider, and environment equivalent. Vary one causal setting at a time when practical and record wall-clock time plus functional success.

Minimum probes:

- repeated fixed tool call at baseline and candidate settings;
- a natural-language positive case such as “computer use feels slow; check it now,” which should perform the obvious safe diagnostic without a clarification turn;
- a nearby ambiguous case that should still ask before consequential action;
- fresh-process config readback and restart/reset requirement;
- doctor after changes to prove driver health remains intact.

Report driver time separately from whole-turn time. Do not present noisy single-run percentages as a stable benchmark.

## Provider-native feature audit

Classify each feature as one of:

- supported and exercised by the active Hermes transport;
- supported in source but not exercised;
- documented upstream but not exposed by Hermes;
- not found/unproven.

Do not recommend extra-compute modes such as reasoning `pro` or native multi-agent as general latency improvements. Programmatic tool calling may help bounded bulk workflows, but it is not an ordinary single-tool desktop latency fix.
