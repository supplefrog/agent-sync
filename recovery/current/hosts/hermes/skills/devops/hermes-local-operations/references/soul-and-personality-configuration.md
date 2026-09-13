# Hermes SOUL.md and personality configuration

Use after `hermes-self-engineering` identifies identity, voice, communication defaults, or standing cross-context behavior as the target. Current official Hermes docs and installed source are authoritative.

## Supported owners

- `HERMES_HOME/SOUL.md` => primary identity plus durable persona, tone, communication style, default interaction style, broad judgment, and standing behavior that should follow this Hermes instance everywhere.
- Project `.hermes.md` / `HERMES.md` / `AGENTS.override.md` / `AGENTS.md` => repository architecture, conventions, commands, paths, ports, and project workflows; verify precedence from the exact cwd.
- Owning skill => reusable task procedure, decision tree, scripts, failure boundaries, and checks.
- `USER.md` / `MEMORY.md` => stable user preferences or environment facts, never task procedures.
- `/personality <name>` / `agent.personalities` => temporary or named persona overlays.
- `agent.system_prompt` / API override => deployment-specific or experimental instruction text. The CLI resolves it as an ephemeral API-call overlay, and a selected `display.personality` takes precedence; do not use it as the normal owner for baseline persona or communication defaults.
- Provider/config knobs => generation mechanics such as reasoning, output verbosity, platform hints, or structured output.

SOUL may contain stable communication defaults that apply everywhere. It should not contain repo details, commands, file paths, temporary workflow steps, or reusable task procedures.

## Decision contract

- Identity, tone, broad judgment, or standing communication/default interaction => SOUL.
- Project-only working rule => effective project context file.
- Reusable task-class procedure => one owning skill.
- Stable user/environment fact => memory tooling.
- Temporary mode switch => `/personality`.
- Deployment-specific/manual experiment => optional system-prompt override, provided no named personality must supersede it.

If several surfaces contain the same rule, keep the narrowest supported owner and remove stale copies after a fresh-session regression check. Do not infer that `AGENTS.md` is a user-global Hermes file: inside git Hermes loads the git-root-to-cwd chain; outside git it checks only the startup cwd.

## Current baseline shape

```markdown
# Identity

Pragmatic, technically grounded engineer. Optimize for correctness, usefulness, and operational reality.

# Style

Direct, concise, plain-language, and candid. Prefer substance over ceremony. Do not over-explain obvious things.

# Judgment

Check facts when checking matters. Separate evidence from inference. Prefer simple, supported, reversible solutions. Challenge weak assumptions plainly. Ask only when ambiguity changes the action.

# Defaults

Put durable communication defaults that should follow every conversation here.
```

## Verification

1. Confirm the active instance with `hermes config path`.
2. Read `SOUL.md`, `display.personality`, `agent.system_prompt`, and effective project context for the test cwd.
3. Start a fresh session; these surfaces are snapshotted or resolved at session/API-call boundaries.
4. Probe the changed behavior and one near-miss regression.
5. Inspect the raw stored assistant message when a CLI renderer strips Markdown.
6. Recheck ownership after Hermes updates; product docs and source override this reference.
