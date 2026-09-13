# Model-harness optimization research

Use when the question is how to get more capability from a named model and the candidate answers span prompts, provider knobs, context policy, tool interfaces, multi-agent modes, and intact runtimes.

## Evidence lanes

1. Inspect the live model/provider catalog and effective host configuration before relying on API model pages. Record advertised, requested, catalog-capped, and runtime-observed values separately.
2. Separate techniques by owner: prompt/instruction, provider request knob, host transport, tool interface, context/memory layer, fixed workflow, auto-delegating mode, or intact harness.
3. Compare community scaffolds against existing owners before installing them. A prompt kit, state machine, or role ladder that duplicates a mature owner is evidence to borrow narrowly, not a new authority.
4. Treat auto-delegating efforts as intact multi-agent substrates, not ordinary points on a single-agent reasoning-effort frontier, unless child routing, accounting, visibility, and rollback are equivalent and verified.
5. Prefer intact evaluation when the claimed gain comes from coupled persistent state, programmatic computation, recovery, subagent lifecycle, and online refinement. Do not reconstruct a weaker facsimile inside the incumbent first.

## Evaluation contract

- Freeze representative tasks, hidden acceptance checks, wall-clock ceilings, provider/model settings, and root-plus-descendant accounting.
- Optimize for the user's declared objective: verified completion and wall time may outrank token cost.
- Keep vendor benchmark evidence directional. Require a matched local pilot before promotion, especially when results vary sharply by task family.
- Distinguish source-documented, locally exercised, host-blocked, and unproven claims.

## Durable-state safety

A trajectory that can gain reward by exploiting the task or evaluator must not approve its own prompt, memory, skill, or policy update. For durable refinement require least privilege, independent state validation, provenance, held-out checks, versioned rollback, and a clean readback at the real consumer boundary. Disable global skill/memory writes during comparative benchmarks.
