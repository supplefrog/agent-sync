# Hermes Desktop repo routing pitfall

Session lesson: Hermes Desktop issues can look like they belong in `fathah/hermes-desktop`, but the user's installed/current Desktop runtime may be the integrated app under `NousResearch/hermes-agent/apps/desktop`.

## What went wrong

An issue about Desktop chat scroll/read-position persistence was first filed in `NousResearch/hermes-agent` based on installed runtime/source evidence. After the user pointed out earlier work targeted `fathah/hermes-desktop`, the issue was moved/refiled there and the original was closed. That was premature because:

- The local runtime command lines and `app.asar` paths pointed at `%LOCALAPPDATA%/hermes/hermes-agent/apps/desktop`.
- The issue in `NousResearch/hermes-agent` had already been triaged/labeled by maintainers.
- `fathah/hermes-desktop` exists and has issues enabled, but may be adjacent/older for this install.

## Correct workflow

1. Verify runtime ownership before filing/moving:
   - Windows process command lines (`Hermes.exe --type=renderer`, `--app-path=...app.asar`).
   - Local source path/version (`%LOCALAPPDATA%/hermes/hermes-agent/apps/desktop/package.json`, git remote/HEAD).
   - Logs (`%LOCALAPPDATA%/hermes/logs/desktop.log`) with bundle paths.
2. If maintainers have already labeled/triaged an issue in a plausible repo, do not close it just because another repo looks plausible.
3. Add a routing comment with the evidence and let maintainers transfer/close if needed.
4. Only close a duplicate after the authoritative tracker is clear.

## Wording pattern

> The installed Desktop runtime/source path on the reporting machine is under `.../hermes-agent/apps/desktop`, so this appears to belong here. If maintainers prefer the standalone Desktop repo, please transfer/close as appropriate.
