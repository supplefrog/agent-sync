# Current native repair

This existing bundle now targets Hermes revision `ead7e91dabf1e963796ec834b196984a2fa44ff4`. It restores the previously selected skill-cache/guidance or summary-adapter behavior; the current upstream memory-write availability gate, steering rows, and runtime markers are preserved.

Before installation require the exact native revision and every target before-hash in manifest.json. Test candidate bytes in a disposable worktree. Install only those candidate files; roll back using bundled baseline bytes only when all installed after-hashes still match. The patch is a review aid; on Windows use the exact bundled bytes to avoid line-ending ambiguity. Do not apply this bundle to a different revision without another checked rebase. Restart Hermes to load changed Python modules; no running session is restarted automatically.
