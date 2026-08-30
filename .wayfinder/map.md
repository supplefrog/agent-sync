# Wayfinder Map: context strategy and capability uplift

## Destination

Agent Signal selects, verifies, and deploys one smallest coherent same-thread context strategy for Hermes, retires the failed foreground context router from active deployment, and records a prioritized online capability-uplift scout. Completion means the selected context path survives restart without creating visible test sessions, matched evaluation evidence supports the decision over current compression, 900K, and hermes-lcm, and all repository/public/fleet/publication gates pass.

## Scope

- In: Hermes same-thread context management on the current GPT-only `openai-codex` route; current built-in compressor; in-place compaction; OpenAI Responses native compaction; explicit 900K picker variant; hermes-lcm intact evaluation; public-safe benchmark harness and receipts; live promotion/rollback; capability scouting for all Agent Signal registry outcomes; final repository publication.
- Out: a second composer, automatic prompt routing, visible test chats, live worker fan-out, raw/private transcript commits, new supported hosts, non-GPT providers, replacing Hermes/Codex/OMP as the supported roster, autonomous installation of unrelated capabilities, provider benchmark reproduction, or a generic memory/database rewrite.

## Evidence inspected

- Live Hermes source documentation: Hermes supports default in-place compaction, GPT-5.6 Responses-native compaction, opt-in `-900k` aliases, and pluggable context engines.
- Live Hermes config read 2026-08-30: `context.engine=compressor`, compression enabled at `0.5`, `in_place=false`, Responses-native unset, base model `gpt-5.6-sol`, proactive prune `48000`.
- `evals/results/foreground-context-router-deterministic.json`: deterministic component tests passed but live validation polluted the user session list; this is a live operational failure, not admission evidence.
- Live plugin inventory: `foreground-context-router` disabled, then removed; `routed-delegation` remains enabled.
- `docs/context-integrity-ledger.md` and `tools/context_ledger.py`: existing staged ledger is suitable for payload-free provenance receipts, not context-quality scoring.
- `skills/capability-curator/SKILL.md`: no change wins ties; candidates must be staged outside live stores and evaluated on matched fresh cases.
- Agent Skills specification, OpenAI compaction docs, Prime Agent, Letta context repositories, LangGraph persistence, and `stephenschoettler/hermes-lcm`: candidate mechanisms and comparison leads, not local-fitness evidence.
- Agent Signal base commit `9ff25e3ec3dcedb5b7bf82baf8a28c96937be0b6`; the working tree already contains substantial uncommitted convergence work that must be preserved and verified as one final release.

## Decisions

| ID | Decision | Rationale | Evidence/owner | Answer-key IDs |
|---|---|---|---|---|
| D-001 | Permanently retire the foreground context router from live deployment; retain failed source/evidence until final replacement cleanup. | It solved model selection by creating a second visible conversation and produced unacceptable audit fan-out. | live incident; failed evidence | AK-001, AK-011 |
| D-002 | Compare four configurations: current no-change baseline, base-model in-place/native compaction, 900K in-place/native compaction, and hermes-lcm. | These cover the smallest native path, larger hard window, and recoverable hierarchical context without assuming a winner. | Hermes docs; capability admission | AK-004–AK-010 |
| D-003 | Use synthetic, non-secret, deterministic transcript fixtures and isolated Hermes homes; never use live user sessions as benchmark fixtures. | Preserves privacy and prevents user-visible session pollution. | goal contract | AK-002, AK-003, AK-016 |
| D-004 | Separate runtime proof from model proof. | Deterministic tests can prove session identity, compaction, persistence, restart, and cleanup; GPT runs separately measure semantic recall and latency. | agent-capability-engineering | AK-003, AK-005–AK-009 |
| D-005 | Evaluate user outcomes, not product labels. | A candidate passes only with no critical regression and at least one material gain; ties favor no change. | capability-curator | AK-009, AK-010 |
| D-006 | Promote only through supported Hermes configuration/plugin surfaces with rollback and post-restart readback. | One-off internal mutations are not admissible operational configuration. | Hermes docs; goal contract | AK-011, AK-012 |
| D-007 | Scout all registry outcomes by lane, but evaluate at most three credible finalists for any gap. | Avoids marketplace accumulation and keeps Agent Signal small. | registry; capability admission | AK-013 |
| D-008 | Keep public receipts payload-free. | Raw prompts, transcripts, secrets, private paths, and provider-hidden data cannot enter the public repository. | context-integrity ledger; repository rules | AK-003, AK-016 |

## Constraints

- Supported hosts remain exactly Hermes, Codex, and OMP.
- Agent Signal remains canonical; host files are deployments or thin adapters.
- No live test chats, generated worker threads, or duplicate sessions.
- Preserve the current `Skill Sync` session and all non-test user sessions.
- Stage external candidates outside live discovery/config roots.
- Do not request, copy, print, or persist credentials.
- Do not overwrite unrelated dirty-worktree changes.
- No candidate is promoted from documentation, stars, synthetic component tests, or vendor benchmarks alone.
- A context strategy must preserve same-thread identity across compaction and restart.
- Promotion must be reversible without restoring the failed router.
- Publication occurs only after full local verification and local/remote synchronization.

## Failure modes and recovery

| Failure | Required behavior | Recovery/rollback |
|---|---|---|
| Candidate creates visible sessions or workers | Immediate hard fail; stop the run | terminate isolated runtime, delete disposable state, record failure |
| Candidate needs live credentials outside existing supported route | Stop and ask | retain isolated component evidence only |
| Native compaction is rejected or stalls | Record route/model boundary; verify local fallback | remove candidate override; restore isolated baseline |
| Recall improves but exact identifiers/corrections regress | Critical fail | prefer baseline or a different candidate |
| LCM installation or runtime touches live stores | Reject contaminated run | remove staging tree; rebuild in fresh isolated home |
| Restart changes or loses session identity/state | Critical fail | restore prior config and recovery snapshot |
| Harness cannot distinguish candidates | Do not promote | improve held-out cases or retain no-change baseline |
| Repository gates expose unrelated pre-existing failures | Separate baseline/change-caused failures | fix only in-scope caused failures; preserve unrelated work and report blockers |
| Publication fails | Do not claim completion | repair, rerun gates, and verify remote state |

## Dependencies and sequencing

1. Retire live router and capture clean baseline.
2. Freeze this map and answer key.
3. Build deterministic fixtures and isolated runner.
4. Exercise current baseline and native in-place/Responses compaction.
5. Exercise matched 900K configuration.
6. Stage and exercise hermes-lcm intact.
7. Compare, challenge, and select no-change or one winner.
8. Promote with supported controls, restart, readback, and rollback proof.
9. Scout capability lanes and record disposition/evidence.
10. Run full gates, update recovery/fleet state, commit, push, and verify synchronization.

## Design direction

The benchmark will be repository-owned and provider-neutral at the fixture/score layer. It will generate synthetic conversations containing stable canaries, later corrections, contradictory stale facts, exact paths/identifiers, large irrelevant tool-output noise, and recent instructions. A deterministic seam will verify session identity, compaction markers, persistence, restart, and cleanup without a model. Optional isolated GPT runs will replay the same hashed cases through each eligible configuration and score exact answer fields rather than prose style. Metrics include critical recall, stale-fact rejection, exact identifier recovery, session count/identity, active/compacted row behavior, restart persistence, latency, token usage, cache-impact evidence, and cleanup. Only aggregate metrics and hashes enter the repository.

The capability scout will normalize the 18 registry entries into user-visible outcome lanes, inventory native capabilities and current evidence, search primary sources, retain at most three credible candidates per unresolved gap, and emit `retain`, `adapt`, `replace`, `remove`, or `defer` dispositions. It will not install candidates during discovery.

## Blockers

- None. Existing Codex OAuth is already the supported active route; no new credential is needed for eligible isolated GPT-5.6 probes. If isolation cannot reuse it without copying secret material, provider-model probes become blocked and component evidence cannot promote a winner.
