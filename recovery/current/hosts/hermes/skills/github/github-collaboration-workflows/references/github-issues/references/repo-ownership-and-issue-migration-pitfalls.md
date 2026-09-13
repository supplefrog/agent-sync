# Repo ownership and issue migration pitfalls

Use this when a product has multiple plausible GitHub repos, an older standalone repo, or an integrated app under a monorepo.

## Failure pattern captured

A Desktop GUI report was filed in an older standalone `hermes-desktop` repo because the repo name matched the product. Later inspection showed the running app's source/runtime path was under an integrated `hermes-agent/apps/desktop` tree. Several issues were recreated in the active repo and the old copies were closed too aggressively, even though the older repo maintainer was still addressing reports there.

## Correct workflow

1. **Establish active ownership before filing.** Verify at least two of:
   - installed runtime/source path and its git remote;
   - log stack paths (`app.asar`, source maps, package path);
   - package version/release channel;
   - maintainer triage/labels on existing issues;
   - repo README/archive status/release activity.
2. **If ownership is ambiguous, do not mass-file or mass-close.** State the ambiguity and keep the next operation reversible: comment with evidence or ask maintainers/users which tracker they prefer.
3. **Before recreating an issue in another repo, run a real duplicate/overlap audit in the target repo.** Search exact title, symptom terms, subsystem terms, and broader umbrella issues. Treat broad hits as potential consolidation targets.
4. **Prefer GitHub transfer over recreate+close.** Try `gh issue transfer -R OLD_REPO N NEW_REPO`. If permissions fail, record that and use comments/cross-links; do not imply transfer happened.
5. **Do not close old-repo issues merely because a copy exists elsewhere when that maintainer may still act on them.** Leave them open with a cross-link unless the maintainer requests closure, the repo is archived, or the issue is clearly harmful/duplicate spam.
6. **If you did create a duplicate in the active repo, dedupe there too.** Close exact duplicates; add related-issue comments for partial overlaps instead of inventing new standalone trackers.

## Good closing comment shape

Only when closure is justified:

```md
Closing this as a duplicate of <target issue>. This report was refiled/transferred because <brief ownership evidence>. If maintainers prefer tracking it here, please reopen.
```

## Good non-closing cross-link comment shape

```md
Cross-linking: the active integrated product also tracks this as <issue>. Leaving this open so this repo's maintainer can decide whether to address it here, transfer it, or close it.
```
