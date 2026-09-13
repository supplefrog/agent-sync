# Shared agent-capability stack

## Canonical layout

```text
repo/
├── skills/                 # portable Agent Skills source of truth
│   └── capability-name/
│       ├── SKILL.md
│       └── references|scripts|templates/
├── surfaces/core.md        # shared durable behavior/style
├── adapters/               # host-specific installation/enforcement only
├── evals/                  # representative and held-out suites
└── registry.json           # provenance, license, tested environment, status
```

Compatible agents should read the same admitted `skills/` sources instead of copied stores. Keep the repository outside every live discovery root while capabilities are staged; cloning directly into `~/.agents` can activate candidates before evaluation and contaminate the baseline.

Installation is a promotion step, not repository layout. Drive it from registry status:

- expose only components marked `admitted`;
- link skills individually so unrelated user skills remain intact;
- never replace an entire shared skill directory merely to install one repository;
- fail closed when a shared instruction surface references a staged or missing skill;
- make `doctor` detect both missing admitted components and staged components accidentally linked live.

A shared source file may feed host-specific global surfaces such as Codex `AGENTS.md` and Hermes `SOUL.md`. Prefer links or an explicit synchronization/doctor step so one file remains authoritative.

## Semantic convergence

Cross-agent parity is behavioral, not textual. Maintain a modality matrix covering at least persistent instructions, skills, tools/MCP, routing/delegation, memory/session context, hooks/security, planning/background automation, and lifecycle updates. Each row records:

- portable behavior contract and acceptance cases;
- canonical owner in each host and tested host/model version;
- adapter required, if any;
- intentional native-only advantage or unsupported gap;
- evidence date and staleness trigger.

Minimize unexplained semantic delta, not implementation delta. Preserve a host-native mechanism when it performs better, but document and test the intentional difference. Refresh official docs/source and rerun affected cases when either host, model, or tool surface changes materially.

Admission and convergence are separate responsibilities: admission decides whether a capability deserves to enter the stack; convergence maps an admitted behavior to each host and owns intentional deltas, unsupported mappings, and host-version drift. Keep a public-safe evidence ledger with `confirmed`, `contradicted`, `unresolved`, and `superseded` findings. Append or supersede contradictory results—never erase them to make the product appear unified.

## Boundary

The portable skill and evidence contract own behavior. Pre-tool hooks, plugin manifests, profile paths, prompt filenames, and install commands are thin adapters. Do not make a Codex-only hook or Hermes-only curator the universal mechanism.

Host-native specialist skills may remain as adapters when they contain real platform procedure. The portable admission workflow should invoke them after a candidate passes rather than duplicate their details.

## Publishing rule

Publish only original content or third-party material with a compatible license and retained provenance. Exclude local/private extensions from the public tree. Commit evaluation suites and compact result summaries; ignore raw runs, credentials, private paths, and transcripts.

Before release, verify:

1. clean clone installation;
2. structural validation of every registered skill;
3. live baseline/candidate evidence on supported hosts;
4. shared-surface drift check;
5. duplicate/legacy owners disabled or clearly scoped;
6. natural triggering after installation;
7. remote URL and published contents read back.
