# Cross-Agent Runtime Discovery

Use this when minimizing capability drift across agent hosts.

## Inventory dimensions

For each host, inspect:

- built-in and optional tools;
- effective global/project instructions and precedence;
- native and externally discovered skills, including collision order;
- config, model roles, provider routing, and approval/sandbox policy;
- rules, commands, hooks, extensions, plugins, and MCP;
- subagents, task/goal state, sessions/import/export, and memory;
- host-specific UI or runtime capabilities that should remain local.

A directory listing is only source inventory. It does not establish effective runtime capability.

## Verification contract

1. Resolve the exact host profile, cwd, and config overlays.
2. Inspect supported discovery precedence and filters.
3. Probe capability visibility from a fresh real session using the host's normal runtime path.
4. Distinguish resource commands that initialize no session catalog from actual session discovery.
5. Preserve the existing lower-precedence/shared owner when it resolves successfully.
6. Install a host-native copy only when the live probe proves a missing capability and the copy passes admission.
7. Record irreducible host-specific differences instead of forcing file-tree symmetry.

## Routing

- Native capability or existing owning skill fits: retain it.
- Established alternatives need comparison/adaptation: `advise-project-approach`.
- No adequate approach exists and the remaining decision is genuinely new project architecture: `neuroarxiv`.
- Persistent installation or behavioral change: return to `capability-admission` for staging and evaluation.

## Pitfalls

- Treating installed skill counts as a capability map.
- Copying a skill into a higher-precedence native directory when a shared owner already resolves.
- Declaring a skill missing because a standalone `read` command lacks session initialization.
- Equating cross-host convergence with identical files rather than equivalent verified outcomes.
