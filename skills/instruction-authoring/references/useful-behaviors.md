# Review useful behavior before choosing an implementation

Use this when a proposal borrows from, replaces, or routes around an existing/native skill, or may duplicate a capability. The early review is optional; the same useful-behavior lens is available during reconciliation.

Supply the source explicitly rather than relying on shared catalog descriptions:

```text
python tools/reconcile.py review --target TARGET --candidate STAGED_FILE --reference-skill EXISTING_OR_NATIVE_SKILL
python tools/reconcile.py plan --target TARGET --baseline SAVED_FILE --reference-skill EXISTING_OR_NATIVE_SKILL
```

The tool provides hashed source identities, addressable procedure clues, relationship hints, alternatives and open questions. It does not pronounce semantic overlap, missing behavior, or a winner from keywords. A candidate that references a source may preserve its workflow without copying its text; a website link may preserve facts without preserving that workflow.

Start with the recorded objective, added value and retirement test in the existing ownership record. Consider accomplishing that objective without the whole skill before preserving individual rules. Model improvement can eliminate a need for prose while scripts, user-specific policy or native integration still require an owner; do not infer either continued need or redundancy from a model label.

Inspect complete relevant procedures and helpers, not just headings. Enumerate outcomes/triggers, decision rules, inputs/outputs, scripts/templates, failures/recovery, verification, host-native strengths and update relationships. Then explain each applicable behavior as reused by reference, adapted, retained natively, ported, deliberately deferred, or missing. Source clues are partial; follow their addresses and conditional references only where the decision needs them.

For a skill fold, trim or retirement, keep a compact behavior preservation map in the existing change record. Bind it to the baseline revision or source hash. Map each distinct removed or moved mechanism to its remaining owner and address, or state the intentional omission, reason and capability loss. Group truly repeated advice; do not hide a unique exception in a broad "already covered" row. Include conditional dependencies and how the destination becomes available before use. Check the resulting source and load path against the map before publication; a matching topic or metadata relation does not establish preservation. Keep the map with the bounded change evidence, rather than creating a separate permanent registry.

Give the user visible judgment: what is missing or changed, your recommendation, why it fits, the strongest meaningful alternative and tradeoff, and unresolved limitations. Prefer an existing supported source or owner when it meets the outcome. Do not union instructions, remove a native variant before preserving its unique behavior, or create an adapter merely because two formats differ. Missing behavior is a finding to investigate, not automatic permission to copy, install, retire, or publish.

Verify claimed update behavior. Distinguish reading installed source afresh, native provenance-backed check/update, and a maintained mirror with a reviewed merge relationship. Do not promise upstream propagation from a file path or hash alone. Keep licensing/provenance and source availability visible; Codex-specific procedures remain about Codex when reused by Hermes. Actual behavioral comparison and natural discovery still require the appropriate existing evidence lane.
