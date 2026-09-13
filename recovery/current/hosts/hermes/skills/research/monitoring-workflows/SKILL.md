---
name: monitoring-workflows
description: Use for recurring feed, competitor, or price monitoring.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [monitoring, feeds, competitors, prices, cron, alerts]
---

# Monitoring Workflows

Use this umbrella to configure or run recurring watches that collect incremental changes, maintain durable state, deduplicate events, and deliver alerts or digests.

## Routing

- RSS/Atom feeds, site feed discovery, and unread article state: `references/blogwatcher/SKILL.md`.
- Material competitor news, product changes, filings, and strategic events: `references/competitor-news-monitor/SKILL.md`.
- Product price, stock, threshold, and availability watches: `references/product-price-monitor/SKILL.md`.

## Shared contract

1. Freeze targets, canonical identifiers, cadence, event categories, thresholds, destination, and silence policy.
2. Establish authoritative sources and record coverage gaps; a failed source means unknown, not no change.
3. Persist the last successful checkpoint and enough evidence to replay deduplication and alert decisions.
4. Collect with overlap for late publication, but advance checkpoints only after successful coverage.
5. Deduplicate by underlying event or product observation, not merely URL.
6. Separate measured facts from interpretation and cite primary evidence when claims matter.
7. Deliver only according to the declared threshold and silence policy.
8. Verify the scheduled job, state path, and one bounded test tick before claiming the watch is live.

Each branch remains a complete package under `references/<branch>/`; follow the selected nested `SKILL.md` for provider-specific commands and schemas.