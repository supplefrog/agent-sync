# Grounded-verification adversarial probes

Use these probes when a contract adds a typed independent-test-author receipt and artifact binding.

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
