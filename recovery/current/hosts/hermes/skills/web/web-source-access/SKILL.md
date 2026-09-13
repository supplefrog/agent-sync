---
name: web-source-access
description: Use when reading feeds or recovering blocked web pages.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [web, feeds, rss, archives, recovery]
    related_skills: [grounded-citations, monitoring-workflows]
---

# Web Source Access

Use this umbrella for structured feed access and blocked-page recovery before escalating to an expensive browser.

## Feeds

- Use `python scripts/feed.py read URL --limit N [--since DATE]` for RSS, Atom, or JSON Feed and `discover URL` when only a site page is known.
- Prefer feeds for recurring collection because structured incremental entries are cheaper and more stable than scraping a front page.
- Cite each entry’s canonical link rather than the feed URL; fetch the article when the truncated feed summary cannot support the claim.
- Treat missing dates as unknown and prove pagination/checkpoint coverage before declaring a complete interval.

## Blocked pages

- Use `python scripts/recover_page.py URL --json` after 403/429, paywall, WAF, or bot interstitial failures.
- Try Wayback, archive.today domain rotation, keyed Jina rendering, API/feed pivots, then a real browser; do not loop on the same blocked route.
- Validate the body, title, and redirect behavior because interstitials and rate-limit pages often return plausible HTTP success.
- Label archive copies as snapshots and cite the snapshot date; snapshots are context, not current price, availability, or breaking-news evidence.
- Never relay credentials or cookies through generic proxy services because their provenance and confidentiality are untrustworthy.

## Completion

Report the route used, live-versus-snapshot provenance, timestamp when applicable, exact entry/page URL, and coverage gaps. A failed route means unknown, not proof that content or updates do not exist.
