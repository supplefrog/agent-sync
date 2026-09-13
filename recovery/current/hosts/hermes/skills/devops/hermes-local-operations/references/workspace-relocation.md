# Relocating Desktop workspaces

Use when project directories move and existing threads must follow without rewriting conversation history.

1. Inventory exact source/destination mappings, root filesystem identities, file counts, Git HEAD/status/worktrees, explicit Projects and session cwd/lineage. Keep system state and unrelated files outside the mapping. Reject collisions.
2. Discover the live Desktop backend; use its authenticated JSON-RPC API. `session.workspace.move` accepts `{session_key: stored_session_id, cwd: destination, profile: "default"}` and updates stored metadata plus a matching live runtime. Direct SQLite updates leave live sessions stale. Do not restart the user's app just to gain access.
3. Move folders on the same filesystem with rename. Preserve legacy absolute dependencies with junctions if appropriate. Hide only the aliases, verify the destination remains visible, and exclude aliases from repository discovery. Preflight file symlinks separately: Windows may permit junctions while rejecting file symlinks with WinError 1314. Do not elevate or change Developer Mode just for compatibility.
4. Use `git worktree repair` for moved main repositories and linked worktrees; verify Git HEAD and full porcelain status against the inventory.
5. For explicit projects, add the destination with `projects.add_folder` (preserve primary status), then remove the source with `projects.remove_folder`. Move every matching stored session/continuation cwd by prefix. Bind previously unanchored threads only from direct ownership evidence; a search/audit mention is not ownership.
6. Preserve and rebase discovered repository cache entries with `projects.record_repos` and the current `discovery_policy`. Snapshot unrelated entries before changing scan policy because policy changes invalidate the cache. Verify `projects.tree` has no duplicate legacy roots.
7. Read back exact session rows, live `session.status`, project folders, and tree paths. Verify identity/counts and loose-file hashes, unchanged unrelated cwd and lineage. Keep one migration receipt and journal in a dedicated project folder. Do not claim that historical absolute file links survive when file aliases could not be created.

Current runtime source owners: `tui_gateway/methods_session.py` (`session.workspace.move`), `methods_projects.py` (folder APIs), `methods_config.py` (discovery/tree APIs), and `agent/conversation_loop.py` (stored prompt cwd mismatch rebuild). Check installed source before reusing these contracts.
