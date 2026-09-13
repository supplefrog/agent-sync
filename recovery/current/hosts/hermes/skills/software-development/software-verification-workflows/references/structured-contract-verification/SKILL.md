---
name: structured-contract-verification
description: "Use for structured contracts. Verify fail-closed state."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [verification, contracts, parsers, llm-intake, fail-closed, regression]
    related_skills: [code-change-verification, systematic-debugging, repository-inspection-audits]
---

# Structured Contract Verification

Use this class-level skill when a change validates or persists structured model/API/parser output: JSON intake, LLM-generated task specs, routing decisions, workflow graphs, schemas, durable gates, or other machine-readable contracts.

The goal is to prove the contract at the production seam, not merely to prove that complete fixtures satisfy helper functions.

## When to Use

Use this skill for changes that parse, validate, route, or persist structured output. Trigger it when malformed or incomplete model/API responses could mutate durable state, when a schema introduces an execution gate, or when a graph/dependency contract must hold across sibling producers.

## 1. Establish the contract and failure boundary

1. Read repository guidance and the complete uncommitted diff, including staged, unstaged, and untracked files that are imported by the changed code.
2. Identify the production entry point, parser, validator, persistence mutator, and state transition that the contract controls.
3. Reconstruct the original failure from the pre-change path. In particular, look for fail-open fallbacks that turn malformed or incomplete output into a promotable body.
4. State the invariant in terms of durable state, such as: invalid output leaves the source in triage; accepted output persists the worker-visible gate before execution; graph children cannot execute before evidence.

## 2. Run the adversarial contract matrix

Drive the real entry point with all of these classes:

- malformed syntax or non-object output;
- missing contract metadata;
- invalid enum values, wrong types, and blank reasons;
- each valid alternative mode, including explicitly exempt/reuse modes;
- the smallest otherwise-valid payload: title-only, empty body, empty list, omitted optional fields, and null values where the schema permits them;
- valid complete output preserving the existing behavior;
- graph-specific cases: missing evidence root, parented evidence, disconnected execution, transitive evidence dependency, cycles, and invalid indices.

For every rejection, assert both the returned error/exit status and the unchanged durable state. For every acceptance, assert the persisted artifact—not just the in-memory return value.

## 3. Use a production-seam probe harness, not helper-only fixtures

For CLI or router intake, construct the real parser tree and dispatch namespace (for example, `build_parser` followed by the command dispatcher) and inject only the external response. Use a fresh temporary state store per case so child-count and persistence assertions cannot be polluted by prior cases. For rejected input, query the durable state after the command and assert no promotion, links, children, or partial body writes. For accepted graph output, use the returned child IDs and the schema's actual edge orientation; do not assume the root is the parent row when the lifecycle links the root as a child waiting on its leaves.

Run the negative matrix symmetrically across sibling producers, then run the positive matrix symmetrically too: whitespace-wrapped objects, one complete supported fence, title-only minimal payloads, and each valid exemption/reuse mode. If the probe executes under a delegated context, use the repository's supported test-authority setup rather than weakening or bypassing the production mutation guard.

Inspect every production caller (CLI, gateway watcher, dashboard/plugin) and search for duplicated permissive extraction. A centralized validator is not sufficient if an alternate producer still slices the first and last braces or falls back to promoting raw prose.

## 4. Separate terminal child evidence from broader decision scope

A passing candidate-trial or terminal-child artifact is evidence only for the scope declared by its immutable contract. It cannot satisfy candidate-comparison, architecture-selection, or promotion scope by implication.

For each broader decision scope, assert all three boundaries through externally observable behavior:

1. the immutable contract explicitly declares the broader scope;
2. the decision record contains every required evidence lane, not merely a passing child receipt. For option selection, check at least baseline, defect detection, execution/context cost, maintenance burden, Windows portability, host neutrality, infrastructure cost, and rollback;
3. promotion or authorization remains blocked when either the scope declaration or any required lane is absent, even if the terminal child artifact itself passes.

Use a black-box acceptance check with a legitimate passing child receipt submitted to a broader scope while lanes are omitted. The expected result is narrow-scope recognition without broader acceptance or promotion. Add a falsification matrix that removes one prerequisite at a time; any broader acceptance or promotion in those variants is a load-bearing failure. External-framework claims do not fill local evidence lanes unless the contract explicitly admits and locally verifies superior evidence.

## 4a. Verify scope coverage, receipt roots, and report currency

For evidence-gated verification reports, add a deterministic receipt matrix rather than trusting summary prose:

1. Count acceptance criteria and flatten every criterion-to-scope mapping. Require every criterion to appear exactly once; reject unknown, omitted, and duplicate IDs.
2. For each declared scope, require one typed evidence artifact whose `scope_id`, decision type, contract binding, and declared lane set match the immutable scope. Verify every lane's path exists, digest matches the bytes on disk, and both the lane and artifact result are `pass`.
3. Exercise representative mutations for omitted required lanes, missing required verdict gates, duplicate evidence records/lanes, wrong-scope artifacts, stale hashes, unknown scopes, and stale or substituted trust-root receipts. Assert rejection at the CLI boundary, not only from a helper.
4. Run the valid CLI with every verifier-supplied external trust root. Run it again with roots omitted and with a stale root; all must reject. A provisional label is a reporting state, not a technical blocker, but it must not be silently treated as final approval.
5. Recompute every artifact hash claimed by each current report independently. Compare the reports' counts, scope coverage, runtimes, and verdict fields to live execution output. Record any optional live-environment drift separately from the contract verdict.

For a pilot/world-state gate, derive blockers from the evidence fixture and compare the derived blocker set, non-regression set, and route-change flag to the persisted report. Never certify a claimed pilot count from report prose alone.

## 5. Check persistence on minimal accepted payloads

A common defect is conditional contract injection: the implementation prepends a gate only when an optional body is nonempty, while separately allowing a title-only response to promote. If the contract promises a durable worker-visible instruction, either render the gate with an empty body or reject that payload. Add a regression through the production entry point for every path that can promote the item, including sibling/single-item fallbacks.

Use the existing persistence/lifecycle APIs rather than reproducing their SQL in the test. Verify the full transition sequence: source status before, promotion/decomposition result, stored body/metadata, child links/statuses, and reload from a fresh connection when relevant.

## 6. Verify sibling paths and lifecycle boundaries

Trace all producers of the contract and all consumers of the persisted result. A fix in a specifier must be checked against a decomposer or alternate CLI/gateway path that can create the same invalid state. Verify:

- parent and transitive dependency enforcement;
- atomicity: rejected graphs create no children and do not promote the root;
- accepted repetitive/mechanical exemptions retain explicit reasons;
- retry/reload/claim behavior remains unchanged when the contract module has no schema role;
- prompt-cache safety: auxiliary prompt changes do not mutate a long-lived main conversation context or rebuild its system prompt.

## 6a. Verify callable provenance contracts at the execution seam

When a structured receipt authorizes an imported callable, plugin, executor, or other implementation by provenance, treat the attestation as a durable contract and test both rejection and normal execution:

1. Bind the expected distribution/version, module, qualname, callable bytecode identity, and immutable source-file identity at import time.
2. Patch the real import seam with a forged callable whose module and qualname are mutable to the expected values and whose source path is readable. Assert the attestation rejects it before factory invocation, the fake's invocation counter remains zero, and durable state enters the documented fail-closed state (for example, `needs_review`).
3. Verify the genuine callable still executes and its receipt includes the complete attestation.
4. Recompute the same structured identity in an independent fresh process/container and compare every field—not merely module or version strings—to each applicable receipt.
5. Separately verify immutable image/artifact digest, pinned source revisions, sandbox constraints, and cleanup. In-process provenance checks alone do not establish deployment identity.

A fake with matching metadata but unreadable source only exercises an early error path; include a readable-source forge so the bytecode/source identity boundary is genuinely tested.

## 7. Test and report honestly

Run focused tests first, then nearby lifecycle tests with the repository's required interpreter and cleared repository addopts when appropriate. Run a real CLI/production-entry-point probe in addition to mocked unit tests. Record actual counts and command output; do not trust prior claimed counts.

Separate:

- **Blockers:** accepted state violates the durable contract, fail-open behavior remains, or a sibling path bypasses validation.
- **Improvements:** missing adversarial coverage, unclear error text, or unverified unrelated worktree changes.
- **Scope caveats:** unrelated staged/unstaged changes, untracked imported files, or test fixtures that cannot be attributed to the contract patch.

End with a strict verdict (`pass` or `rework`) and give file:line evidence, concrete reproductions, and the smallest complete fix for each blocker.

## Pitfalls

- Complete happy-path fixtures do not test fail-closed behavior.
- Rejecting malformed syntax is not enough if valid-but-minimal output can omit the durable gate.
- Checking only return values misses promotion and persistence bugs.
- Source-string assertions do not prove production routing, DB transitions, or graph dependencies.
- A green combined suite can still hide a minimal-payload hole; add the smallest accepted payload explicitly.
- Treat unrelated worktree changes and untracked dependencies as attribution caveats, not as proof that the focused patch is correct or incorrect.

## References

- `references/fail-closed-probe-matrix.md` — compact adversarial matrix and evidence checklist for structured intake patches.
