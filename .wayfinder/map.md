# Wayfinder Map: Global Agent Adaptive Control Plane

## Destination
Turn Agent Signal into a bounded global learning and retirement controller for the upgraded `gpt-5.6-sol` session at `ultra` reasoning. The system must measure whether generic standing instructions still help, retain only evidence-backed steering, admit the existing governance owners only on current evidence, and accept privacy-safe learning signals from any workflow into a shadow queue that cannot mutate live agent surfaces.

## Scope
- In: session-scoped ultra stack profile/evidence; owner-specific retirement suites; bounded Hermes ultra ablations; current admission evidence for `capability-curator` and `surface-convergence`; one portable global-learning intake owner and deterministic shadow queue; GitHub handoff to that owner; registry/ownership/fleet integration; live discovery verification.
- Out: changing the persisted Hermes default from medium; model weight training; ambient transcript mining; automatic promotion of global behavior; automatic GitHub scheduling; editing other Hermes profiles; unrelated agent cleanup.

## Evidence inspected
- `profiles/gpt-5.6-sol-openai-codex.json`: current global profile records Hermes medium, Codex medium, and OMP high.
- Active Hermes `config.yaml` field search: persisted default remains `gpt-5.6-sol`, `openai-codex`, medium.
- `hermes chat --help`: session override accepts `ultra`.
- `contracts/instruction-units.json`: generic steering is independently selectable and retested on effective-stack changes.
- `skills/capability-curator/references/instruction-retirement.md`: requires bare/full/leave-one-out evidence and forbids release monitors from mutating live surfaces.
- `evals/core-instruction-retirement.json`: current four-case suite is broad smoke coverage, not owner-specific proof.
- `registry.json` and `contracts/ownership.json`: capability-curator and surface-convergence remain staged/unresolved.
- `skills/github-follow-up/SKILL.md`: GitHub retains its admitted cross-project promotion gate because the replacement global intake failed required-host admission.
- Initial working tree: two pre-existing user edits under `skills/conversational-communication/`; local commit `f5f4f8b24d3fc5cea3c1bc6d92d88a4f1b6d8d5a` preserves their exact hunks, and the current control-plane work does not claim or alter them.

## Decisions
| ID | Decision | Rationale | Evidence/owner | Answer-key IDs |
|---|---|---|---|---|
| D-001 | Treat ultra as a session-scoped candidate stack, not a new persisted default. | The live config remains medium; evidence must not misstate it. | Model profile and CLI help | AK-001, AK-002 |
| D-002 | Optimize for the smallest useful delta via owner-specific retirement tests. | A stronger model can make generic steering redundant or harmful. | Capability curator retirement contract | AK-003, AK-004, AK-005 |
| D-003 | Do not remove any instruction without an actual retirement verdict. | Structural intent is not behavioral evidence. | Capability admission policy | AK-005 |
| D-004 | Make global learning event-driven and shadow-only. | Ambient transcript mining is noisy/private; live self-mutation is unsafe. | Outcome-first and admission contracts | AK-006, AK-007, AK-008, AK-009 |
| D-005 | Give general learning promotion one owner; GitHub remains an evidence adapter. | Avoid duplicate policy and make the architecture global. | Ownership and skill-creator rules | AK-010, AK-011 |
| D-006 | Admit curator/convergence only on current bound evidence; otherwise leave staged. | The control plane must pass its own gate. | Registry and stale results | AK-012 |
| D-007 | Preserve pre-existing style edits and generated-session cleanliness. | User work and session list are protected state. | Git diff and evaluator lifecycle | AK-013, AK-014 |
| D-008 | Preserve nondiscriminating confirmation cases and use only bounded, predeclared high-risk expansion under the unchanged candidate and harness. | The upgraded GitHub PR v2.4 approach earned confirmation by adding package-consumer, security-review, and Windows-platform boundaries without deleting the original case or relaxing a failed criterion. | Upgraded PR workflow plus expanded confirmation receipt | AK-003, AK-011, AK-012 |
| D-009 | Keep global-learning-intake staged and remove its GitHub adapter after the final required-host gate rejected the exact v0.1.3 candidate. | Hermes admitted it, but Codex recorded one valid comparative loss; deploying an adapter to an unavailable owner would create a dead route. | Cross-host aggregate, exact host reports, and fleet diff | AK-010, AK-011, AK-015, AK-016 |
| D-010 | Keep capability-curator staged after the current required-host aggregate returned inconclusive. | Both host reports are truthful harness failures, not behavioral rejections, and neither sealed 90-attempt lane has enough budget left for a complete 72-attempt rerun. | Host reports, attempt ledgers, and cross-host aggregate | AK-012, AK-015, AK-016 |
| D-011 | Preserve the narrow Hermes no-response timeout classifier change, but invalidate the surface admission episode that attempted to use it. | The classifier correctly identifies the observed provider timeout, but stopping the pre-amendment launcher did not stop its evaluator child; the child continued while the 71-attempt rerun started, so the amendment's one-discarded-attempt premise was false. | Timeout regression test, sealed amendment, and corrected attempt ledger | AK-012, AK-014, AK-015 |
| D-012 | Keep raw model-evaluation payloads in ignored local evidence and publish only hash-bound compact summaries. | Raw reports contain model outputs, session receipts, and machine-local paths; the repository already defines `evals/results/` as compact evidence and raw runs as ignored. | `tools/summarize_eval.py`, `tools/public_check.py`, README publication boundary | AK-014, AK-015 |
| D-013 | Close surface-convergence admission as an integrity failure without running its Codex lane. | Two Hermes evaluators overlapped, the earlier raw report was overwritten before archival, and the surviving report's candidate/baseline hashes differ from the sealed plan. Their 63 attempts leave only 9 of 72, below the 56-attempt clean minimum. | Surface attempt ledger, compact Hermes report, and cross-host inconclusive summary | AK-012, AK-014, AK-015, AK-016 |
| D-014 | Rebind recovery and profile evidence to Hermes 0.21.0/config v40, while treating the 0.20.6 model-evaluation lanes as historical after the runtime change. | A host version change is a declared staleness trigger; it must not silently inherit behavioral qualification, but it does not rewrite the independently closed negative or inconclusive owner outcomes. | Surface matrix, recovery manifest, and current instruction profile | AK-001, AK-002, AK-005, AK-012, AK-015 |
| D-015 | Keep the admitted 15-skill fleet unchanged and perform no apply after render/diff showed no delta; verify active discovery on Hermes, Codex, and OMP instead. | Distribution is already hash-matched, and applying an unchanged render would add risk without changing state. | Fleet manifest and three-host discovery receipt | AK-015, AK-016 |

## Constraints
- No paid API key route or non-subscription inference.
- No delegation or unbounded agent fan-out.
- Every live evaluation uses explicit model/provider/reasoning and a hard run budget.
- Evaluator-created sessions are deleted by exact runtime receipt and verified absent.
- No secrets, raw transcript bodies, private identifiers, or public comment text in learning records.
- Project-only conventions remain project-local; stable facts remain memory candidates.
- The initial conversational-communication hunks remain preserved in local commit `f5f4f8b24d3fc5cea3c1bc6d92d88a4f1b6d8d5a` and untouched by this control-plane work.

## Failure modes and recovery
| Failure | Required behavior | Recovery/rollback |
|---|---|---|
| Ultra inference unavailable or rate-limited | Retry only explicit transient provider errors within the predeclared physical-attempt cap; if exhausted, mark harness failure, aggregate it as inconclusive, and do not use it as behavior evidence. | Preserve reports, clean evaluator sessions, retain current surfaces. |
| A launcher exits `1` after writing a complete `retain`, `reject`, or `inconclusive` report | Treat the exit as the evaluator's negative-verdict signal, not by itself as a harness failure; validate the durable report, hashes, routes, budget, and cleanup. | Preserve the verified report and keep the affected surface unchanged/staged. |
| A launcher is interrupted before it can write a report | The partial run is not behavioral evidence, but every observed model attempt still counts against the original lane cap. | Delete only the exact evaluator sessions, record discarded attempts in a sidecar ledger, and require completed-report attempts plus discarded attempts to remain within the sealed cap. |
| A background launcher stops while its evaluator child survives | Do not infer process-tree termination from the wrapper result, launch a replacement lane, or trust overlapping reports. | Verify exact evaluator argv/process trees, terminate the child tree with approval, clean exact evaluator sessions, bind surviving raw evidence, record any overwritten evidence, and close the episode if a clean rerun no longer fits. |
| A nominal no-tools run passes an empty toolset | Hermes treats the empty value as absent and falls back to configured coding tools. | Deliver the prompt inline, pass an explicit `none` toolset, attest exact route plus zero tool calls from the redacted session record, and fail closed on mismatch. |
| Retirement result is tie/noisy/inconclusive | No live removal. | Keep current unit and requeue only on a new signal. |
| Admission misses a host or artifact hash | Leave owner staged. | Retain compact evidence and rerun only missing/stale lanes. |
| Learning input contains secret-like or raw transcript content | Reject before durable candidate write. | Emit a local rejection receipt without sensitive payload. |
| Duplicate event arrives | Remain idempotent. | Reuse fingerprint and avoid duplicate pending state. |
| A launcher writes a raw report into `evals/results/` | Do not publish the raw payload or discard verified evidence. | Move it unchanged to ignored `.evals/reports/raw/`, publish a compact summary bound to the raw SHA-256, and reduce session lifecycle to counts. |
| Fleet collision or stale live host | Stop promotion and report exact delta. | Do not force; restore from canonical render/recovery manifest. |

## Dependencies and sequencing
1. Freeze ultra candidate stack and deterministic baseline.
2. Improve deterministic contracts/tests before model calls.
3. Run bounded retirement evaluations; apply only proven removals.
4. Run current admission lanes and update registry only for complete passes.
5. Build/test shadow learning intake and GitHub adapter handoff.
6. Render/diff/apply admitted fleet artifacts and verify fresh discovery.
7. Run full repository verification and preserve compact evidence.

## Design direction
Keep intelligence in the target model and put only non-inferable continuity around it. The adaptive controller has immutable admission/privacy boundaries, small model-sensitive global steering, on-demand procedures, and an append-only shadow evidence queue. Candidate generators may propose; deterministic validation and owner-specific evaluation decide; promotion remains a separate reviewed action.

## Blockers
- No external runtime blocker. Ultra is available as an explicit session override; the persisted medium default remains intentionally unchanged.
- `global-learning-intake` failed its final required-host admission cycle and remains staged. This is a bounded negative result, not a reason to weaken the suite or add another adaptation cycle.
- `capability-curator` remains staged because both current host lanes ended in verified harness failures and their sealed retry budgets are exhausted for a complete rerun. The aggregate is inconclusive, not behavioral rejection.
- `surface-convergence` remains staged because overlapping Hermes evaluators invalidated the lane, the earlier raw report was overwritten, and the surviving report is artifact-mismatched. Its remaining nine attempts cannot contain a clean rerun; the Codex lane was not started.

## 2026-09-03 continuation: capability librarian

### Clarified destination

Agent Signal should behave as one hybrid capability librarian. An ordinary request or detected live change enters one intake path that inventories existing native and portable owners, extends an existing owner when possible, researches and stages a genuinely new capability, assigns portable versus host-specific placement, and releases only checked changes. This extends the control plane above; it does not replace its curator, research, convergence, recovery, or fleet owners.

### Continuation scope

- In: a deterministic read-only live-drift intake scan; explicit classification and routing; the user-selected low-risk auto-apply boundary; preservation and correct ownership of the current Hermes and frontend edits; a future thin Hermes hook boundary.
- Out for this slice: a filesystem-watcher daemon; ambient transcript mining; automatic promotion of novel, cross-host, safety-sensitive, or ambiguous changes; exposing staged skills through live discovery; resuming an exhausted evaluation episode; bypassing approval for a live managed-skill replacement.

### Continuation decisions

| ID | Decision | Rationale | Evidence/owner | Answer-key IDs |
|---|---|---|---|---|
| D-016 | Keep the existing owner topology; the librarian is a composition, not a new competing skill. | `capability-curator`, `primary-source-research`, `skill-creator`, `surface-convergence`, recovery, and fleet sync already divide the intended responsibilities cleanly. | `docs/architecture.md`, `contracts/ownership.json`, owner skills | AK-017 |
| D-017 | Add a deterministic, read-only intake scanner before native enforcement. | Manual edits currently surface only as recovery drift or fleet conflict. A bounded scanner can classify those facts without copying content, guessing intent, or mutating live state. | `tools/recovery.py`, `tools/fleet.py` | AK-018, AK-019 |
| D-018 | Auto-apply only deterministic, reversible changes to an existing owner after checks; stage novel, cross-host, safety-sensitive, or ambiguous changes for review. | This is the user's selected autonomy boundary and prevents blind self-mutation while removing ceremony for routine verified maintenance. | User decision at 2026-09-03T05:31:12+05:30 | AK-020 |
| D-019 | Classify the current SOUL/settings edits as Hermes-specific recovery state and the accessibility correction as a portable patch to the existing frontend owner. | The Desktop directory-link workaround and disabled-skill list are host state; the invalid `npx axe-core` command lives in an admitted portable reference and npm metadata confirms `axe-core` has no CLI binary while `pa11y` does. | Live drift, npm package metadata, `skills/frontend-ui-engineering` | AK-021, AK-024 |
| D-020 | Keep the live soft gates on admitted fallback owners until `capability-curator` is admitted; do not point ordinary sessions at a staged owner. | `surfaces/core.md` already contains the complete curator gate, but it is a reference rather than an effective prompt because the owner failed admission. | Instruction-surface contract and current Hermes/Codex global files | AK-022 |
| D-021 | Treat Hermes `pre_tool_call`/`on_session_start` support as a future thin adapter, not a second librarian. | Hermes can block or approve tool calls and run session-start hooks, but activation before scanner and admission proof would add a brittle global failure point. | Current official Hermes hooks documentation | AK-022 |
| D-022 | Any renewed owner evaluation uses a fresh sealed plan and unique lifecycle accounting. | Prior curator and convergence episodes are exhausted or invalidated and cannot be resumed honestly. | D-010 through D-013 | AK-023 |

### Continuation sequencing

1. Preserve and classify current live changes.
2. Implement the read-only scanner and production-seam tests.
3. Verify repository safety, recovery, and fleet behavior.
4. Reopen curator/intake/convergence only under new sealed admission plans.
5. Activate thin native gates only after the routed owners and scanner pass their checks.
