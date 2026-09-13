# Reasoning-effort economics

Use when comparing reasoning levels of the same model or deciding whether retry escalation is economically justified.

## Interpret the request before executing

A question such as “how much better is effort A than effort B for how much cost?” normally asks for analysis of the named benchmark or reviewed catalogue. It is **not** authorization to launch a live evaluation. Compute from existing evidence first. Run a live benchmark only when the user explicitly asks to run, measure, benchmark, or validate one.

If execution starts from a mistaken interpretation, stop it immediately when corrected, clean processes/sessions/temp artifacts, and exclude partial results.

## Comparison contract

For adjacent efforts on one model, report:

- absolute and relative intelligence/quality change;
- absolute and relative task-cost change;
- absolute and relative task-time change;
- hallucination or reliability change, preserving the benchmark’s directionality;
- incremental cost per intelligence/quality point when meaningful.

Use deterministic arithmetic from the reviewed values. Name the evidence boundary: broad benchmark scores are not proof of proportional improvement on the user’s task.

## Escalation economics

Do not recommend `medium -> high -> xhigh -> max` retries merely because each level scores slightly higher. Sequential escalation pays the full cost, latency, and context consumption of every failed attempt; the user does not receive only the marginal upgrade.

Before recommending escalation, compare:

1. marginal quality gain from the next effort;
2. marginal cost and latency of selecting it initially;
3. cumulative cost and token/context consumption after prior failed attempts;
4. whether the failure is likely caused by insufficient inference effort rather than missing facts, ambiguous requirements, poor decomposition, unverifiable assumptions, or a model-family capability ceiling.

When adjacent efforts offer small benchmark gains for large cost/time increases, prefer the lowest effort that clears the task requirement. After failure, first consider better evidence, clearer specification, different decomposition, human judgment, or a genuinely stronger model generation. Higher effort is justified only when task-specific evidence shows the marginal gain is decision-relevant and the failure/rework cost exceeds the premium.

## Reporting style

Lead with the trade-off in one sentence. Use a compact table, then give a direct recommendation. Do not overstate tiny benchmark deltas as “solving harder tasks”; describe them as measured aggregate gains with uncertain task-level impact.

## Session evidence pattern

In the reviewed 2026-08 Sol catalogue, successive effort increases showed strong diminishing returns: Medium→High added about 1.8% Intelligence Index for about 49% more task cost and 60% more time; High→xhigh added about 3.5% for about 47% more cost and 50% more time; xhigh→Max added about 3.4% for about 52% more cost and 40% more time. Treat these numbers as catalogue-specific evidence, not permanent constants. Refresh them from the current reviewed catalogue before reuse.
