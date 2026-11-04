# Crawl4AI Cloud

The local Windows fleet connects Codex, Hermes and OMP through a small local
stdio adapter to `https://api.crawl4ai.com/mcp`. The adapter adds deterministic
HTML recovery; it does not run a browser or host the Crawl4AI crawler.

Set `CRAWL4AI_KEY` in the local user environment. The adapter reads the process
environment or, on Windows, the same named User environment value. Credentials
are provisioned per machine and excluded from shared source. No website login,
cookies, browser profile or session storage is read.

Codex supports secure OS storage for MCP OAuth credentials. That setting does
not automatically store this service's static API key. The environment reference
avoids putting the key in the shared connection configuration.

Host tool calls allow 150 seconds; upstream calls allow 125 seconds. Codex and Hermes expose scraping, search, SERP,
answer, extraction, batch, estimate, balance and job tools. OMP's native MCP
schema exposes the server catalog without a per-server tool filter; existing
host approval policy remains applicable. Billing, top-ups, subscription changes,
automatic recharge and spending-cap changes require explicit user direction.

The service charges credits per operation and engine. Check balance and estimates
before large work. A setup scrape returned content successfully for 0.25 credits;
this is a single observed cached-page charge, not a general price guarantee.

The connection fragments under `integrations/crawl4ai/` describe each native
client. Their launcher resolves the published source from the existing fleet
manifest. Install the pinned `requirements.txt` into a dedicated Python 3.12
environment at `~/.local/share/crawl4ai-recovery/venv` before applying a fragment.
Merge only the `crawl4ai` entry; existing host tool approvals remain unchanged.
The previous HTTP connection remains the rollback option. Existing sessions need
a reload to start the adapter. The key must be provisioned locally after recovery.

## Missing-content recovery

Single-page `scrape` requests ask the cloud for HTML and Markdown in the same
request. The local parser recovers Reddit comment records from captured comment
trees and Instagram profile fields from recognized page metadata/embedded JSON.
It appends missing readable content and returns structured recovery with source
hashes, selectors and partial/conflict warnings. Original Markdown and upstream
fields remain available; explicit `format=both` or `format=html` retains HTML.
Default/Markdown calls omit bulky HTML from model output after recovery.
Oversized scrape text/HTML returns a bounded error instead of flooding context.

Recovery is a derived view of returned bytes. It performs no extra fetch, login,
script execution, pagination or canonical-store write. It cannot recover a
blocked response or content absent from the captured HTML. It does not establish
a complete thread, profile, follower list or timeline. Ordinary pages and other
upstream tools keep their existing behavior. Batch/job tools remain upstream
operations; this adapter's automatic recovery applies to single-page `scrape`.

Saved test envelopes can be recovered offline without the key or a cloud call:
run `server.py --recover-saved INPUT.json --output NEW_OUTPUT.json` using the
dedicated Python environment. Output files must be absent; raw input is preserved.

Sources: [Crawl4AI setup](https://crawl4ai.com/llms.txt),
[Codex MCP](https://developers.openai.com/codex/mcp),
[OMP 18.12.6 MCP](https://github.com/can1357/oh-my-pi/blob/v18.12.6/docs/mcp-config.md).
