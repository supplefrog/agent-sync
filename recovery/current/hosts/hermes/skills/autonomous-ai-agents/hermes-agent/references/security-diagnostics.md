# Security Diagnostics

Load this reference for approval prompts, secret/PII redaction, tool/network restrictions, pairing/authorization, sandboxing, or a suspected security-control interaction. Current authority: <https://hermes-agent.nousresearch.com/docs/user-guide/security> and the installed version's configuration help.

## Boundary

Security controls are not convenience flags. A user request to diagnose behavior does not authorize weakening approvals, redaction, authorization, isolation, network restrictions, or credential handling. Never disable a safeguard merely to make a task easier or to reveal a real credential to the model.

Use a security switch only when all are true:

1. The symptom plausibly comes from that specific control.
2. Current docs/source confirm the switch exists and its restart scope.
3. The user has authorized that configuration change and understands the exposure.
4. The test uses the least sensitive data and narrowest scope/duration available.
5. A restoration and read-back check are part of the same diagnostic.

If those conditions are not met, keep the control enabled and diagnose through logs, mock values, isolated reproduction, or metadata/status that does not reveal secrets.

## Diagnostic order

1. Capture the exact symptom and affected surface/profile.
2. Determine whether it is command approval, secret redaction, PII redaction, tool availability, network/website policy, pairing/DM authorization, or sandbox policy. These controls are independent.
3. Inspect effective configuration and current docs without printing secret values.
4. Prefer a mock-token or non-sensitive reproduction.
5. If an authorized toggle is necessary, record prior state, set it through the supported interface, restart only the owning component if required, run one bounded test, restore prior state, and verify restoration.

## Specific cautions

- **Secret redaction:** real secrets should remain unavailable to the model. A mock token can test false-positive redaction. Historical recipes for globally disabling redaction are intentionally not repeated here; verify the current supported diagnostic route and startup behavior in docs/source if escalation is genuinely required.
- **Approval prompts:** smart/off/YOLO-style modes, when supported, alter command-approval behavior but do not expand user authorization. Do not use them to bypass a denied or unapproved action. Prefer per-command approval and retain destructive-command scrutiny.
- **PII redaction:** gateway message privacy is separate from tool-output secret redaction. Diagnose on the gateway path and avoid using real PII as a test fixture.
- **Tool/network restriction:** disabled tools or blocked sites may be deliberate policy. Confirm authorization before enabling them; a new session may be needed if tool schemas are startup-bound.
- **MCP:** treat servers as code/data trust boundaries. Minimize forwarded environment variables, review requested scopes, disable server-initiated capabilities not needed, and follow the [official MCP security guidance](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp).
- **Webhooks/gateway:** preserve HMAC/signature verification, pairing, allowlists, rate limits, and network exposure controls. Never expose a listener publicly as a debugging shortcut.

A completed diagnostic reports the observed control, evidence, any temporary change, proof of restoration, and unresolved risk. It does not describe a safety bypass as permission.
