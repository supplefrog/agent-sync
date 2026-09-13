# Legacy rebuild and run-lease probes

Use these probes when a change adds run-scoped durable fields or workspace leases.

## Legacy table-rebuild probe

A migration can add a column and then silently lose it if a later drift-repair rebuild uses an old canonical `CREATE TABLE`. Test the full production open path, not only the additive `ALTER TABLE` helper:

1. Create a fresh database with the current schema.
2. Replace the target table with a legacy-shaped version (for example, a `TEXT PRIMARY KEY` `task_runs` table that predates `route_receipt`).
3. Clear any in-process initialized-path cache and reconnect through the public `connect()`/migration entry point.
4. Inspect `PRAGMA table_info(target)` and perform the first write that depends on the new field.

The canonical rebuild spec must include the new column. Shared-column copy logic should omit it only when it did not exist in the legacy table, allowing the nullable/defaulted field to be populated safely.

## Workspace-lease probe

Exercise both ordinary and recovery claims:

- claim two tasks with equivalent paths (`root` and `root/.`) and confirm the second claim defers;
- complete/end the first run and confirm the second can claim;
- force a `ready` task with a stale `current_run_id`, then claim it and confirm the old run's workspace lease is released before the replacement insert;
- expire a claim while its worker is still considered alive and confirm the lease is extended or remains protected, rather than being deleted by a generic expired-row purge;
- reclaim a dead/stale run and confirm its lease is removed in the same transaction.

The invariant is: at most one live run owns a normalized writable workspace key, and every path that ends or recovers a run releases exactly that run's lease.
