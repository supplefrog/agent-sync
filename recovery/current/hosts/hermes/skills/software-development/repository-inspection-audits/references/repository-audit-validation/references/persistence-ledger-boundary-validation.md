# Persistence-ledger boundary validation

Use this reference when reviewing a metadata-only ledger, provenance index, ingestion cursor store, or similar persistent audit artifact.

## Boundary matrix

Test every public write seam, not only the primary importer:

- direct record APIs;
- configured field extraction;
- replay/version-derivation paths;
- schema and startup migrations;
- diagnostic/database handles;
- CLI entry points.

A schema without `payload` or `content` columns does not prove payload exclusion. Metadata-shaped columns can still retain arbitrary bodies unless values are semantically constrained before SQL writes.

## High-value adversarial probes

- Feed a transcript body through every configurable metadata field.
- Require configured extraction to receive the expected record shape and a present, valid field; do not silently omit malformed values.
- Accept timestamps only in the documented representation. For an offset-aware datetime contract, reject numeric epochs, naive datetimes, dates, booleans, and arbitrary scalars.
- Validate decoded URI paths, then require canonical reserialization. Reject encoded control characters, invalid percent escapes, backslashes/UNC forms, authorities, queries when forbidden, dot-segments, and reversed ranges.
- Close and reopen the database before searching the main DB, WAL, and SHM for forbidden payload bytes.
- Expose diagnostics through bounded query methods. SQLite `mode=ro` protects only the main database: an unrestricted handle may still `ATTACH` a writable external database. If SQL access must remain, combine a narrow statement whitelist with a deny-by-default SQLite authorizer that blocks `ATTACH`/`DETACH`, write/schema/transaction opcodes, write-capable pragmas, and extension loading.
- Probe the full external-write sequence in a fresh process: `ATTACH` → schema creation → insert → commit, plus writable pragmas and `load_extension`; verify every step is rejected and no external file is created.

## Migration state matrix

Exercise startup from each plausible intermediate state:

1. old table only;
2. legacy-renamed table only;
3. current table plus legacy table after partial copy;
4. old table plus legacy table after interrupted normalization;
5. duplicate identical rows;
6. duplicate conflicting rows.

Migrations should be transactional and restartable. Identical rows may converge idempotently. Conflicting cursor evidence must fail closed while preserving recovery tables; `INSERT OR IGNORE` must not silently discard contradictory state.

## Evidence discipline

- Add regressions at the public production seam before changing validators.
- Run focused tests, the full repository suite, syntax checks, and the real audit/public-safety commands.
- Bind independent review to exact hashes and test counts.
- When asynchronous reviews arrive late, compare their hashes and test count with the current artifact before acting; preserve obsolete FAIL findings in history, but do not reapply already-corrected fixes.
- Do not promote until the current exact-hash review passes. A green suite does not override a material independent finding.
