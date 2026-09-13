# WSL provider-stall triage for Hermes

Use this when Hermes in WSL reports frequent provider no-response / stale-call timeouts, but the same provider appears healthy from Windows-native tools.

## Key lesson

Do not assume WSL networking is broken just because Hermes provider calls hang. Isolate raw network reachability from Hermes/provider/SDK behavior.

In a representative session, Hermes logs repeatedly showed:

- `Non-streaming API call stale for 300s`
- `provider=openai-codex`
- `base_url=https://chatgpt.com/backend-api/codex`
- retry after `APIConnectionError`

But raw WSL IPv4 HTTPS timing to `chatgpt.com` and `api.openai.com` was sub-second, and Windows PowerShell timing to the same endpoints was also healthy. The likely issue class was provider/backend/SDK/concurrency rather than broken WSL NAT/DNS.

## Read-only probe pattern

Run from WSL first:

```bash
printf '== Time / OS ==\n'; date -Is; uname -a
printf '\n== WSL info ==\n'; cat /proc/version; printf '\nWSL_INTEROP=%s\n' "$WSL_INTEROP"
printf '\n== DNS config ==\n'; sed -n '1,120p' /etc/resolv.conf
printf '\n== Routes ==\n'; ip route
printf '\n== Proxy env ==\n'; env | grep -Ei '^(http|https|all|no)_proxy=' || true
printf '\n== Name resolution ==\n'; getent ahosts chatgpt.com; getent ahosts api.openai.com

for host in chatgpt.com api.openai.com; do
  echo "== curl IPv4 $host =="
  for i in 1 2 3; do
    curl -4 -sS -o /dev/null \
      -w "try=$i code=%{http_code} dns=%{time_namelookup} connect=%{time_connect} tls=%{time_appconnect} start=%{time_starttransfer} total=%{time_total} ip=%{remote_ip}\n" \
      --max-time 20 "https://$host/" 2>&1
  done
done
```

If Windows comparison is needed from WSL, invoke PowerShell with the absolute path because `powershell.exe` may not be on WSL PATH:

```bash
'/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe' -NoProfile -ExecutionPolicy Bypass -Command '
$urls = @("https://chatgpt.com/backend-api/codex/", "https://api.openai.com/v1/models")
foreach ($u in $urls) {
  Write-Host "URL=$u"
  for ($i=1; $i -le 3; $i++) {
    $sw=[System.Diagnostics.Stopwatch]::StartNew()
    try {
      $r=Invoke-WebRequest -Uri $u -Method Get -TimeoutSec 20 -UseBasicParsing -ErrorAction Stop
      $sw.Stop(); Write-Host ("try={0} code={1} total={2:N3}s" -f $i, [int]$r.StatusCode, $sw.Elapsed.TotalSeconds)
    } catch {
      $sw.Stop(); $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { "ERR" }
      Write-Host ("try={0} code={1} total={2:N3}s err={3}" -f $i, $code, $sw.Elapsed.TotalSeconds, $_.Exception.GetType().Name)
    }
  }
}'
```

Then inspect Hermes-specific state:

```bash
python3 - <<'PY'
from pathlib import Path
p=Path('/root/.hermes/logs/agent.log')
if p.exists():
    lines=p.read_text(errors='replace').splitlines()
    hits=[l for l in lines if 'stale for 300s' in l or 'APIConnectionError' in l or 'Connection error' in l]
    print('\n'.join(hits[-40:]))
PY

ps -eo pid,ppid,etime,cmd | grep -Ei 'hermes|codex|openai|python.*run_agent' | grep -v grep
ss -tanp 2>/dev/null | awk 'NR==1 || /:443/ {print}' | sed -n '1,120p'
```

## Interpretation guide

- Fast WSL curl + fast Windows PowerShell + Hermes 300s stale calls: suspect provider backend/SDK behavior, OAuth/Codex runtime quirks, large prompts, or concurrent Hermes processes before blaming WSL networking.
- Multiple long-lived Hermes processes, dashboard, curator, or subagents can create concurrent provider calls; ask/confirm before killing, but recommend closing unneeded sessions with `/exit`.
- `CLOSE-WAIT` sockets attached to Hermes are evidence of stale connection lifecycle issues, not by themselves proof that WSL NAT is broken.
- If WSL has no global IPv6 route but DNS returns AAAA records, note it as a possible contributor; verify IPv4 explicitly with `curl -4` before proposing IPv6/system-wide networking changes.
- Auxiliary warnings such as Gemini `RESOURCE_EXHAUSTED` / HTTP 429 for `title_generation` are quota/routing issues, not WSL networking. Route that auxiliary task to a provider with quota or disable/ignore title generation.

## Safe next steps

1. Use a lighter Hermes profile (`hermes --profile lite`) to reduce context/tool overhead while debugging.
2. Close extra Hermes sessions/dashboard/curator jobs that are not needed.
3. Route noisy auxiliary tasks away from exhausted providers, e.g. title generation away from Gemini when `GOOGLE_API_KEY` quota is exhausted.
4. Compare the same WSL profile with a different provider. If other providers work reliably while openai-codex stalls, keep the root cause scoped to Codex/Hermes SDK/provider behavior rather than WSL networking.
