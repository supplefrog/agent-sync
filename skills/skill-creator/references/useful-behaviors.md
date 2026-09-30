# Review useful behavior before choosing an implementation

Use this when a proposal borrows from, replaces, or routes around an existing/native skill, or may duplicate a capability. The early review is optional; the same useful-behavior lens is available during reconciliation.

Supply the source explicitly rather than relying on shared catalog descriptions:

```text
python tools/reconcile.py review --target TARGET --candidate STAGED_FILE --reference-skill EXISTING_OR_NATIVE_SKILL
python tools/reconcile.py plan --target TARGET --baseline SAVED_FILE --reference-skill EXISTING_OR_NATIVE_SKILL
```

The tool provides hashed source identities, addressable procedure clues, relationship hints, alternatives and open questions. It does not pronounce semantic overlap, missing behavior, or a winner from keywords. A candidate that references a source may preserve its workflow without copying its text; a website link may preserve facts without preserving that workflow.

Inspect complete relevant procedures and helpers, not just headings. Enumerate outcomes/triggers, decision rules, inputs/outputs, scripts/templates, failures/recovery, verification, host-native strengths and update relationships. Then explain each applicable behavior as reused by reference, adapted, retained natively, ported, deliberately deferred, or missing. Source clues are partial; follow their addresses and conditional references only where the decision needs them.

Give the user visible judgment: what is missing or changed, your recommendation, why it fits, the strongest meaningful alternative and tradeoff, and unresolved limitations. Prefer an existing supported source or owner when it meets the outcome. Do not union instructions, remove a native variant before preserving its unique behavior, or create an adapter merely because two formats differ. Missing behavior is a finding to investigate, not automatic permission to copy, install, retire, or publish.

Verify claimed update behavior. Distinguish reading installed source afresh, native provenance-backed check/update, and a maintained mirror with a reviewed merge relationship. Do not promise upstream propagation from a file path or hash alone. Keep licensing/provenance and source availability visible; Codex-specific procedures remain about Codex when reused by Hermes. Actual behavioral comparison and natural discovery still require the appropriate existing evidence lane.
