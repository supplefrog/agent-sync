# Catalogue source policy

Use only data the user can verify for each exact GPT model and reasoning-level combination.

1. **Availability and identifiers:** the user's current `openai-codex` model list. Keep model and reasoning identifiers exact.
2. **Intelligence:** Artificial Analysis Intelligence Index for that exact displayed variant.
3. **Task time:** Artificial Analysis Time per Intelligence Index Task for that exact displayed variant. It is weighted decode time per task and excludes first-token and other overhead.
4. **Task cost:** Artificial Analysis Cost per Intelligence Index Task in USD for that exact displayed variant.
5. **Hallucination:** Artificial Analysis AA-Omniscience Hallucination Rate for that exact displayed variant. Treat it as one knowledge-reliability signal, not a universal factuality guarantee.

Record the comparison URL and observation date. Store visible comparison precision: whole Intelligence points, task time and task cost to two decimals, and hallucination rate to two decimal percentage points. Do not transfer a value to another reasoning level unless the source explicitly shows that variant.

Prefer the rendered Artificial Analysis page because the user can inspect it. If extraction is blocked, accept a user-provided table, screenshot, or export, or another attributed page reproducing the same fields. Never invent values or silently substitute per-token throughput/price, fixed-output response time, or local benchmarks.

Do not store credentials or account data. Refresh is manual and creates no monitor.
