# Model-qualified instruction profiles

Agent Signal treats the user-owned instruction overlay as a versioned, testable surface rather than pretending to own a provider's hidden system prompt.

## Current profile

[`profiles/gpt-5.6-sol-openai-codex.json`](../profiles/gpt-5.6-sol-openai-codex.json) is the current observed profile for `gpt-5.6-sol` on `openai-codex`:

| Host | Runtime | Reasoning | Standing user-owned bytes | Budget |
|---|---|---:|---:|---:|
| Hermes | Hermes Agent 0.20.5 | medium | 1,211 | 2,048 |
| Codex | codex-cli 0.150.0-alpha.12.2 | medium | 1,475 | 2,048 |
| OMP | omp 17.2.13 | high | 1,475 inherited from Codex | 2,048 |

`current-observed` means the exact user-owned files, current model selectors, runtime versions, hashes, composition, and context budgets were read back and verified. It does **not** claim that Agent Signal can copy provider-hidden or runtime-native system instructions, or that every line is globally optimal forever.

Verify it with:

```bash
python tools/instruction_profile.py
python tools/instruction_retirement.py \
  --host hermes --model gpt-5.6-sol --provider openai-codex \
  --reasoning medium --trigger model-release --max-batches 2
```

The default verifier also reads the installed Hermes/Codex/OMP versions and dry-runs the reviewed recovery snapshot against the live roots, so coordinated edits to the profile, matrix, and snapshot cannot self-certify as current. Use `python tools/instruction_profile.py --artifact-only` only for an offline/clean-clone repository binding check; `bootstrap --apply` always uses the live check.

The second command is used only when a model/provider/runtime/instruction trigger actually reopens retirement evaluation.

## Complete surface inventory

`contracts/instruction-surfaces.json` records all non-skill, non-tool instruction classes:

- provider-native and runtime-native system prompts, identified as externally owned and restored by reinstalling the matching runtime;
- Hermes `SOUL.md`;
- Codex global and project `AGENTS.md` hierarchy;
- OMP's inherited Codex instructions and optional native append/system files;
- dynamic project context such as `AGENTS.md`, `CLAUDE.md`, and `.cursorrules`;
- session-start hooks that can inject context;
- disabled or retired instruction injectors and their replacement;
- the portable `surfaces/core.md` intent reference.

`contracts/instruction-units.json` splits the effective global files into headings or tagged lines so model-sensitive generic steering can be evaluated and retired independently. Skills and tool schemas stay outside this standing-unit inventory because they are selected on demand.

OMP v17.2.13 explicitly discovers `~/.codex/AGENTS.md` through its `codex` discovery provider at user scope. The current OMP native `AGENTS.md` is absent, so the higher-priority native provider does not shadow the Codex file. This inheritance is therefore a verified host mechanism, not an assumed file convention; see the version-pinned OMP `docs/context-files.md` source recorded in the surface contract.

The earlier local Codex `agent-surface-curator` plugin was a host-local pre-edit/inventory gate, not a complete current cross-host evaluator. It is disabled and superseded by the repository's `capability-curator`, machine-readable surface inventory, recovery manifest, and model-profile verifier. The current Codex `AGENTS.md` snapshot still contains the old route because the protected-file update was not approved; the surface inventory records that drift instead of silently changing it. `agent-surface-bridge` remains prior evidence, not a second canonical control plane.

## Writing ownership

The current profile assigns one owner per writing mode:

| Mode | Owner | Loading |
|---|---|---|
| Routine chat and status | `conversational-communication` | on demand |
| Public prose: issues, PRs, releases, email, Slack, posts | `humanizer` | on demand |
| Model-facing instructions and skills | `skill-creator` | on demand |
| Hermes persistence placement | `hermes-self-engineering` | on demand |

The full humanizer is intentionally **not** injected into every response. Routine chat uses the compact standing output defaults plus `conversational-communication` when needed. Public artifacts load `humanizer`. Model-facing instructions remain dense and machine-useful, but `skill-creator` now requires plain human-readable language rather than bureaucratic prompt prose.

## Context and retirement policy

- Recovery config, memory, sessions, skills, and tool schemas are not standing prompt content.
- Effective user-global instruction bytes must stay below the host budget.
- OMP's duplicate `RULES.md` was retired because Codex `AGENTS.md` already supplies the behavior OMP inherits.
- Generic rules are reevaluated after a material model/provider/runtime, prompt assembly, tool schema, context policy, or instruction change.
- Safety, governance, and environment constraints stay protected from automatic model-triggered retirement.
- Profile promotion requires schema validation, exact artifact hashes, live-selector readback, prompt-budget checks, and decision-bound evidence.

The result is one definitive repository owner for the current user-controlled overlay, while host-native and provider-native layers remain honestly identified as external dependencies.
