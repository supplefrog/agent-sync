# Grounded-verification adversarial probes

Use these probes for machine-readable verification gates with freeze receipts, role isolation, pilot manifests and result reports. The typed test-author matrix below applies when that contract is present.

## Contract and report audit

1. Verify the corrected positive fixture and current pilot evidence, but treat every claimed hash, test count, verdict, and report as a claim to re-execute.
2. Run the real focused suite, the valid/negative CLI paths, the pilot evaluator, and the repository-wide suite when practical. Record actual counts instead of repeating embedded result claims.
3. Add adversarial probes that mutate criteria and the pilot manifest, recompute the current hash, delete decision events, mutate the freeze receipt and its digest, rewrite the source reference, rewrite hash-chain fields, and hide each held-out blocker independently.
4. Distinguish a hash mismatch from a trust-anchor failure. A receipt digest stored inside the same mutable contract is not an immutable anchor: mutate the receipt, update its contract digest, set its original hash to the altered current hash, and confirm the gate still rejects. If it passes, report a blocking self-authorized-freeze finding.
5. Bind the source identifier to the authoritative task/card, not merely to criterion fields that all agree with the same attacker-controlled reference. Test a coordinated rewrite to the previously used or adjacent task ID.
6. Derive or independently attest metrics such as false positives and false negatives. Schema minimums are not metric integrity; mutate each reported metric and verify rejection or provenance validation.
7. Inventory **all** related grounded fixtures, result reports, verdicts, and docs—not only the newest pilot report—and check each for generation drift. A corrected contract with stale reports (wrong source ID, blocker count, event count, test count, validation count, trust root, or artifact hash) is an evidence-integrity blocker unless the file is explicitly marked historical/superseded. Do not let a current pilot report's clean hashes hide an older checked-in verdict that still claims authority.
8. Re-execute reported test suites and record actual counts/timings separately from embedded claims. Treat changed counts, roots, or hashes as report drift requiring regeneration or explicit archival marking; do not silently normalize them in the audit.
9. For held-out state, mutate one condition at a time and require the validator to reject an unchanged reported manifest when deterministic evidence no longer derives that blocker.

For typed independent-test-author receipts, also apply the positive checks and substitution matrix below.

## Required positive checks

Confirm the receipt is typed and binds, by exact value, to:

- contract ID;
- test-author principal and context;
- the externally supplied original freeze hash;
- the current/final decision-chain hash;
- the exact freeze timestamp;
- artifact path and digest;
- frozen-intent/specification input scope;
- independent-test-author output type; and
- denied implementation access.

Also verify the artifact's frozen-input metadata agrees with the trusted freeze chain and that the role boundary denies implementation access.

## Negative matrix

1. Rewrite the criteria freeze receipt and coordinate source, criteria, declared digest, and receipt fields. The verifier-supplied freeze root must still reject it.
2. Substitute an artifact with a stale freeze timestamp, then update the mutable contract path/digest and receipt path/digest. The timestamp mismatch must reject it.
3. Substitute artifact *content* while preserving all checked metadata, recompute the artifact digest, update the receipt's artifact path/digest, and update the contract's mutable receipt/path/digest fields. This must reject. If it passes, the contract has only self-consistent mutable hashes, not artifact provenance/integrity; report a blocking finding.
4. Mutate receipt metadata (principal/context, original/final hashes, timestamp, scope, output type, or implementation access) and recompute only the mutable declared receipt digest. The validator must reject unless the mutation is independently authorized and anchored.

Do not confuse a stale-timestamp regression with full artifact-integrity coverage. A digest stored in the same mutable contract or in a receipt whose digest is also mutable is not an immutable trust anchor.

## Evidence reporting

Record exact CLI/test counts, current artifact-hash comparisons, blocker/non-regression derivation, and the precise mutated field set. Keep temporary adversarial fixtures outside the repository and confirm `git status` is unchanged afterward.
