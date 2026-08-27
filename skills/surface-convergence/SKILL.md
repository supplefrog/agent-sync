---
name: surface-convergence
description: Map desired agent behavior across hosts and close semantic surface deltas
license: MIT
compatibility: Requires access to each target agent and fresh evaluation sessions.
metadata:
  author: supplefrog
  version: "0.1.0"
---

# Surface Convergence

Use when the user asks for a persistent behavior across agents, when adding a supported host, or when host updates may have changed an existing mapping. This skill owns cross-agent parity, adapter boundaries, evidence drift, and explicit host-native exceptions. Use `capability-curator` to decide whether a new or changed capability deserves admission.

## Contract

Minimize **semantic delta**, not file or mechanism differences. A portable contract defines the outcome; each host should use its best reliable native mechanism. Preserve host-native advantages when emulation would add fragility, cost, or a false parity claim.

## Procedure

### 1. Compile the behavior request

Translate “I want X behavior” into:

- observable outcomes and trigger conditions;
- hard failures and regression boundaries;
- target agents and active versions;
- affected modalities from `contracts/surface-matrix.json`;
- acceptable intentional deltas and rollback.

Do not choose a host mechanism before the behavior contract is clear.

### 2. Inventory before designing

Inspect the current portable artifacts, registry status, evidence summaries, host instructions, skills, tools, configuration, plugins, hooks, memory, routing, and native lifecycle features relevant to the request.

Mark existing evidence stale when a host version, active model/tool policy, artifact hash, upstream dependency, or observed behavior changed materially.

### 3. Research current implementations

Use primary owner documentation and source at versioned revisions. Compare each host's native mechanism, the current baseline, and credible alternatives. Reject marketplace popularity, copied conventions, and old model benchmarks as proof.

For each finding, distinguish:

- portable behavior contract;
- host-native implementation;
- adapter required;
- unsupported behavior;
- intentional host advantage.

Record useful negative results and contradictions in `evidence/findings.json`; do not flatten disagreement into a false consensus.

### 4. Assign one owner per concern

Choose the narrowest reliable owner:

- Agent Skills for portable procedures;
- the shared instruction surface for portable judgment and communication intent;
- MCP for shared external tools when practical;
- a thin host adapter for discovery, policy, or lifecycle integration;
- the host itself for native memory, sandbox, scheduling, model routing, and other mechanisms that should not be copied.

Do not duplicate policy across skills, prompts, hooks, and plugins. Do not create a universal adapter for a mechanism only one host exposes.

### 5. Stage the smallest coherent change

Keep candidates outside live discovery paths. Preserve provenance and licensing. Modify the portable contract first when semantics change, then update only the adapters required to realize it.

When one host cannot implement the contract reliably, record `partial`, `unsupported`, or `intentional-delta`; do not lower the other host or claim parity.

### 6. Evaluate behavior, triggering, and regressions

Run `tools/eval.py` on every target host, then `tools/eval_gate.py` across the required-host set. Broad persistent mutation is blocked until the aggregate gate admits it.

- Normalize model, provider, reasoning, prompt/tool/context assembly, and effective-stack equivalence before comparison; record irreducible differences.
- Use representative, adversarial, near-miss/non-trigger, and fresh held-out cases.
- Judge task success before mechanism similarity.
- Use deterministic hard checks, matched repeated trials, order-swapped blind judging, and a predeclared bounded sequential confidence rule.
- Test natural triggering and explicit invocation where applicable.
- Exercise deterministic adapters directly.
- Measure material latency, token, tool, and maintenance overhead.
- Reject any critical regression; ties favor the current surface.

A host passes only with a meaningful gain or necessary parity restoration and no critical loss. Harness failures are inconclusive. Cross-host convergence is confirmed only when every required host passes with matching artifacts and compatible effective-stack fingerprints; partial success stays staged and explicit.

### 7. Preserve evidence and promote

Update the surface matrix, compact public evidence summaries, and contradiction ledger. Keep raw transcripts, credentials, private paths, user memory, and third-party content out of the repository.

Promote only admitted artifacts. Install by linking or registering the canonical repository artifacts rather than copying them. Verify a real task on each host after installation and record rollback and reevaluation triggers.

## Adding another agent

Map its native surfaces into the existing modality contracts before writing an adapter. Reuse portable artifacts where behavior matches, retain valuable native differences, and add a new cross-host evaluation row. The target is a portable product with honest adapters—not a lowest-common-denominator prompt.

## Failure modes

- **Zero-delta theater:** forcing identical files or mechanisms while behavior differs.
- **Lowest-common-denominator design:** deleting a host advantage because another host lacks it.
- **False parity:** calling an unsupported or untested adapter equivalent.
- **Evidence amnesia:** losing failed searches, contradictions, or why a mechanism was rejected.
- **Stale proof:** reusing results after relevant host, model, tool, or artifact changes.
- **Live staging:** exposing a candidate through an auto-discovery path before admission.
- **Surface duplication:** assigning the same concern to several persistent instruction owners.
