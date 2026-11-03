# Crawl4AI Cloud

The local Windows fleet connects Codex, Hermes and OMP to the hosted MCP endpoint
`https://api.crawl4ai.com/mcp`. No local browser service is required.

Set `CRAWL4AI_KEY` in the local user environment and restart the agent launcher so
new clients inherit it. Credentials are provisioned per machine and are excluded
from recovery snapshots. Codex uses `bearer_token_env_var`; Hermes and OMP use
their native `${CRAWL4AI_KEY}` header interpolation.

Codex supports secure OS storage for MCP OAuth credentials. That setting does
not automatically store this service's static API key. The environment reference
avoids putting the key in the shared connection configuration.

Tool calls allow 120 seconds. Codex and Hermes expose scraping, search, SERP,
answer, extraction, batch, estimate, balance and job tools. OMP's native HTTP
schema exposes the server catalog without a per-server tool filter; existing
host approval policy remains applicable. Billing, top-ups, subscription changes,
automatic recharge and spending-cap changes require explicit user direction.

The service charges credits per operation and engine. Check balance and estimates
before large work. A setup scrape returned content successfully for 0.25 credits;
this is a single observed cached-page charge, not a general price guarantee.

The connection fragments under `integrations/crawl4ai/` describe each native
client. Merge only the `crawl4ai` entry when recovering the connection; removing
that entry rolls back the setup. Existing running sessions need a reload to
discover newly added tools. The key must be provisioned locally after recovery.

Sources: [Crawl4AI setup](https://crawl4ai.com/llms.txt),
[Codex MCP](https://developers.openai.com/codex/mcp),
[OMP 18.12.6 MCP](https://github.com/can1357/oh-my-pi/blob/v18.12.6/docs/mcp-config.md).
