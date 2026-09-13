# Persistent surface gate audits

Use this when determining whether edits to agent instructions, skills, config, plugins, hooks, or shared capability roots actually enter a governance process.

## Separate the layers

Inventory each layer independently:

1. **Soft routing:** `AGENTS.md`, `SOUL.md`, system instructions, and skill triggers can tell an agent what process to follow, but cannot observe out-of-band writes or prove enforcement.
2. **Native lifecycle maintenance:** a host curator may track use, consolidate, mark stale, or archive. It is not automatically the portable ownership, admission, or promotion authority.
3. **Hard interception:** pre/post-tool hooks and plugins can allow, deny, or record mutations, but only for the events, tools, and paths their classifier covers.
4. **Canonical control plane:** ownership registry, change-request state, evaluation, promotion, distribution, recovery, and rollback should have one authoritative implementation. Host hooks should be thin adapters to it.

Do not infer coupling from names or co-location. A mutation guard can live beside a curator while deliberately never invoking it; conversely, a hook can mention the new system while still using a legacy private receipt store.

## Audit the effective runtime

1. Read the active profile's live config and standing instruction file, not a recovery snapshot or old backup.
2. Ask the runtime to list loaded hooks and plugins. Config text proves intent, not activation.
3. Follow each hook from registration to the exact executable or script.
4. Record its event, matcher, tool names, timeout, fail-open/fail-closed behavior, and status message.
5. Read the classifier and authorization path. Identify exact protected roots, target normalization, approval state, hash binding, expiry/use limits, and self-modification rules.
6. Verify whether the hook invokes a curator, calls the canonical intake, writes a canonical change request, or only consults host-private state.
7. Check native curator source or tests for external-root behavior before deciding whether it can mutate a managed shared skill tree.

Ignore caches, backups, ambient suggestions, and stale generated copies until the active source and runtime registration are known.

## Build a coverage matrix

Test or statically prove each relevant mutation class separately:

- host-local skills;
- shared external skill roots;
- standing instructions;
- host config;
- local plugin source and generated plugin cache;
- canonical control-plane repository;
- writes made by another host, editor, or process;
- writes while the host is not running.

Report **covered**, **soft-routed**, **detected only by later drift scan**, or **uncovered**. Never summarize partial path coverage as a universal gate.

## Converge without parallel gates

When a legacy host guard and a newer canonical control plane coexist:

1. Preserve any proven deterministic protections while mapping their behavior.
2. Do not add a second independent receipt/approval system.
3. Add a thin host event adapter that emits bounded, privacy-safe metadata into one canonical change-request ledger.
4. Use post-mutation observation plus periodic drift scanning first; keep it non-blocking while coverage and noise are measured.
5. Promote enforcement only for deterministic, reversible maintenance of an existing admitted owner.
6. Keep novel, cross-host, ambiguous, conflicting, safety-sensitive, retirement, and promotion decisions reviewed.
7. Verify fresh runtime loading and representative covered/uncovered paths after migration.

A successful gate audit states both what is protected and what remains outside the process.