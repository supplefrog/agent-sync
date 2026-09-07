# Current Hermes cache and guidance rebase

Owner: native Hermes runtime. Rebased on 820106d4a52e83a426400659231ae14093585109.
Restores only the previously selected cache/scanner and guidance deltas; preserves current upstream changes. Historical guidance/ cache evidence is not rewritten. Current baseline reproduced six failures in seven synthetic checks; candidate passed seven and fresh native AIAgent assembly. These are mechanism checks, not Astra-medium or Sol quality evidence.

Restore only after exact HEAD and every baseline hash match manifest.json. Validate repair.patch on a copy, install exact candidate bytes, then rerun fresh native loading and cache checks. Roll back using exact bundled baseline bytes only after every installed hash matches. Existing processes keep imported guidance until restarted; no reset or restart performed by this bundle.

Shared instruction core is the default. No model-specific variant or automatic routing is selected here. Original cache limitations remain: metadata freshness is not atomic, scanner checks are bounded, no comprehensive threat detection or provider-general compatibility claim.
