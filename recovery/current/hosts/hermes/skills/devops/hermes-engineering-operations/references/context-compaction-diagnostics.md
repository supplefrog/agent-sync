# Context-compaction diagnostics

Use when Hermes compacts unexpectedly, compaction blocks the foreground, native compaction appears enabled but no provider checkpoint is emitted, or threshold numbers disagree.

## Diagnose the mechanism before tuning numbers

1. Read only the safe model/provider and compression sections of the active profile config.
2. Find the exact event in the live agent log by timestamp and session. Record:
   - last provider-reported input tokens;
   - next assembled-request estimate;
   - logged preflight/pre-API threshold and context window;
   - selected compression model/provider;
   - start/end timestamps and elapsed time;
   - messages/tokens before and after;
   - whether a provider `compaction` item was emitted and replayed.
3. Trace the runtime resolver. For the built-in compressor, the important shape is:

   ```text
   effective_input_window = context_window - reserved_output_tokens
   ratio_trigger = effective_input_window × effective_threshold_ratio
   final_local_trigger = floors/caps/overrides(ratio_trigger)
   ```

   Do not report `context_window × configured_ratio` as the live trigger when output reservation, model autoraise, a small-window floor, or an absolute cap applies.
4. Trace native eligibility and request construction separately. Confirm the request actually reached the provider above `compact_threshold`; config presence alone proves nothing.
5. Classify the event as provider-native checkpointing, Hermes local summarization, external-engine compaction, tool-output pruning, or provider overflow recovery.

## Native-versus-local preemption race

A recurring boundary is:

1. the last provider request is below the native threshold;
2. one tool-heavy turn makes the next assembled request exceed both native and local thresholds;
3. Hermes' pre-API guard runs local summarization before sending that request;
4. the provider never gets the chance to emit the requested native checkpoint.

This is arbitration failure, not evidence that provider-native compaction itself failed. Reproduce it with one bounded tool-output jump and assert the actual emitted mechanism. A source fix should let an eligible request attempt native compaction while it still safely fits the provider input budget, then retain local summarization as the rejection/overflow fallback. Preserve hard overflow and output-headroom guards.

## Extended-context aliases and provider limits

1. Read the authenticated provider catalog when available and record each distinct field separately: default input window, maximum input window, effective-window percentage, output reserve, and native compaction threshold. Do not collapse them into one “context limit.”
2. Trace what the client-side opt-in changes. A synthetic large-context suffix that is stripped before transport usually raises the client’s admitted-input budget for the same wire model; it does not by itself prove a conditional backend mode switch.
3. Compare the admitted budget with the provider’s live maximum. Do not let a static alias exceed a newer catalog maximum; cap or derive it from live metadata and retain a documented fallback only for catalog failure.
4. Inspect the actual request builder for any extended-context field, header, or endpoint change. If none exists, describe the feature as client-side permission to send a larger prompt, not as a backend flag.
5. Verify pricing independently from capacity. Separate uncached input, cached input, output, service-tier, and any documented long-context rates; never infer a cost multiplier merely because a larger request is accepted.
6. Treat a large accepted request as capacity evidence only. Evaluate quality with task-specific evidence position, relevance, and distractor density before changing retention policy.

For an unexpected early-compaction report, reproduce the boundary with one bounded tool-output jump. Record the previous provider input, next assembled estimate, effective local threshold, selected summary route, elapsed time, before/after message counts, and emitted compaction mechanism. Preserve these as fixture inputs rather than a dated incident narrative.

## Recoverability boundaries

- OpenAI native compaction returns an opaque provider checkpoint. It is useful for lower-payload same-thread continuity, but the checkpoint is not an inspectable archive of what survived.
- Keep exact facts in reviewed artifacts, retained raw transcripts, or an external retrieval store. If the checkpoint omitted a detail, native compaction alone cannot explain or recover it.
- Hermes LCM's primary store is SQLite raw messages plus a summary/DAG structure. Semantic/vector retrieval is optional rather than the canonical store. Treat LCM as a separate persistence authority and test restart, cleanup, sidecar integrity, and security before promotion.

## Windows LCM evidence boundary

The isolated LCM run produced 219 failed tests, but zero `ENOSPC`/“No space left” signatures. Permission failures dominated, including directory-open/fsync behavior and a symlink-privilege error. Preserve that as a Windows portability diagnosis, not a validated patch. Before upstreaming, add a minimal Windows reproduction and tests for atomic file replacement, file flush, directory-durability semantics, and privilege-free test behavior; do not silently weaken durability guarantees.

## Working-set policy

Prefer dynamic working-set construction over silent context-window escalation:

- keep one user-visible thread;
- at meaningful phase boundaries, reconstruct a compact task capsule containing the goal, constraints, decisions, required source artifacts, relevant files, and acceptance tests;
- keep small edits in the existing working set;
- use a larger raw window only when the next operation genuinely needs simultaneous source residency beyond the normal admitted window;
- do not create a fresh visible thread for every code edit.

This is an operating hypothesis until evaluated at the real request-assembly seam. Verify quality, cache effects, latency, exact-detail recovery, and session-list behavior before making it a hard global rule.
