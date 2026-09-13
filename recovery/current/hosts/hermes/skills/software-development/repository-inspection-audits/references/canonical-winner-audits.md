# Canonical winner audits

Use this when a repository is supposed to select the best implementation from experiments, threads, worktrees, or compatibility copies.

## Winner selection

1. Inventory every candidate and classify it as portable owner, host adapter, experiment, historical evidence, or retired artifact.
2. Compare implementation quality, deterministic tests, live runtime compatibility, portability, and failure evidence. Do not treat the current path, most integrated copy, or first green artifact as canonical by default.
3. Require one explicit owner record per capability. An admitted owner needs a decision reason and evidence semantically bound to that capability; an arbitrary existing result file is not selection evidence. Unresolved candidates remain staged.
4. Keep host adapters thin. A compatibility integration must not publish a competing skill entrypoint or own portable state merely because it is already wired into one host.
5. After selection, remove current entrypoints and route surfaces for rejected variants, record retirement/replacement, and mark preserved results historical or superseded. Audit all capability families for the same inversion, not only the reported example.

## Executable guard

Validate the ownership document against its schema. Require registry/owner parity and supported-host parity. Reject duplicate owners, unregistered skills, integration-owned skill entrypoints, unsupported adapters, missing or unrelated selection evidence, and reappearing retired paths.

Add negative controls for malformed ownership records, unrelated-but-existing evidence, duplicate owners, stale adapters, and retired-path resurrection. A validator that passes while its schema rejects the same record is a blocking audit defect.
