---
name: hermes-provider-stall-triage
description: Diagnose Hermes provider no-response/stale-call issues, especially when WSL and Windows-native clients differ.
---

# Hermes provider stall triage

Use this skill when Hermes reports provider no-response, stale API calls, repeated `APIConnectionError`, or long hangs before a model response, especially when the user suspects WSL networking but another client on Windows works.

## Core rule

Do not jump straight to WSL network repair. First separate:

1. raw WSL DNS/TCP/TLS reachability,
2. Windows-native reachability to the same endpoints,
3. Hermes-specific provider logs and process concurrency,
4. auxiliary-model quota/routing failures.

Only propose network fixes after the raw network probes show a real WSL-specific failure.

## Investigation sequence

1. Check WSL network basics:
   - `/etc/resolv.conf`
   - `ip route`
   - proxy env vars
   - `getent ahosts` for the provider host
   - `curl -4` timings for the provider endpoint

2. Compare Windows-native timing from WSL using the absolute PowerShell path:

   `/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe`

   Do not assume `powershell.exe` is on PATH inside WSL.

3. Inspect Hermes logs for provider-specific stale calls:
   - `Non-streaming API call stale for 300s`
   - `APIConnectionError`
   - provider name, model, base_url

4. Inspect concurrent Hermes processes and open sockets:
   - multiple interactive Hermes sessions
   - dashboard
   - curator
   - subagents
   - `CLOSE-WAIT` sockets attached to Hermes

5. Separate auxiliary failures from main provider failures. Gemini `RESOURCE_EXHAUSTED` / HTTP 429 on title generation is a quota/routing issue, not WSL networking.

## Interpretation

- Fast WSL curl plus fast Windows PowerShell plus Hermes 300s stale calls usually points to provider/backend/SDK/OAuth/concurrency behavior, not broken WSL NAT/DNS.
- Multiple Hermes processes can amplify provider stalls and quota issues. Ask/confirm before killing processes; prefer closing unneeded interactive sessions with `/exit`.
- If WSL lacks global IPv6 but DNS returns AAAA records, verify with `curl -4` and note IPv6 as a possible contributor rather than the assumed root cause.
- Large default-profile prompts/toolsets can make provider stalls feel worse. Use a lighter profile during diagnosis.

## Safe mitigations

- Use `hermes --profile lite` while debugging.
- Close extra Hermes/dashboard/curator sessions if they are not needed.
- Route noisy auxiliary tasks away from exhausted providers, e.g. title generation away from Gemini when `GOOGLE_API_KEY` quota is exhausted.
- Test the same WSL profile with a different provider. If other providers work reliably while one provider stalls, keep the root cause scoped to that provider path.

## References

- `hermes-provider-stall-triage/wsl-provider-stall-triage.md` — concrete probe commands and interpretation notes from a WSL vs Windows provider-stall investigation.

## Related / overlap note

This overlaps with the broader `hermes-wsl-operations` class skill when that skill is available in the active profile. Prefer consolidating this material there during skill curation.
