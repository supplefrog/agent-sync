---
name: archive-t3-codex-threads
description: Archive settled T3 Code threads and their matching Codex Desktop conversations. Use for a requested one-time cleanup of the T3 Settled shelf, across projects or within a specified scope.
license: UNLICENSED
---

T3 Archive and Codex Archive are separate actions. Use the T3 thread tools for T3 and the Codex app-server archive API for the matching native conversations.

1. Page through `t3_thread_list` with `settled: true` in the requested environment and project scope. Use `allProjects: true` when asked to archive all settled threads on that host. Freeze the eligible IDs in a private scratch JSON array. Keep threads with active work or pending user input out of the batch.
2. On the machine hosting both applications, run `python scripts/archive_codex.py <ids.json>` from this skill directory. It reads T3's saved Codex thread references and the local Codex archive state by ID. Confirm the databases belong to the selected T3 environment and Codex home. Use the explicit path options for nondefault databases. Resolve missing or weak links before acting on those Codex conversations.
3. Archive each eligible T3 thread with `t3_thread_organize` and `action: "archive"`. Process sequentially. Check failures by reading the thread before retrying. Archive keeps conversations recoverable.
4. Run the helper with `--apply` on the original IDs. It checks the T3 archive state before calling `thread/archive` for each eligible Codex ID and rereads the saved states. Set `CODEX_HOME` to the matching Codex installation's home. Pass `--codex-executable <path>` if the shell's `codex` is a wrapper that Python cannot launch. Use the official API even if the helper needs adapting to a new database schema.
5. Re-list settled T3 threads in the selected scope and check the helper's readback. Report archived counts, already archived Codex conversations, unresolved matches and failures. A failed or timed-out archive may have succeeded. Reread state before retrying. Use the original ID file to retry the Codex side because already archived T3 threads disappear from the settled list.

The helper supports T3's local v2 SQLite projections and Codex's local `state_5.sqlite`. For unavailable or different hosts, use equivalent native tools or report the missing access. Keep ID files and conversation data local. Restore with T3's Unarchive and Codex's Unarchive for the corresponding IDs.
