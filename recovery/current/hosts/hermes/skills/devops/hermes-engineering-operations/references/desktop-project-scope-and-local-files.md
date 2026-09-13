# Desktop Project scope and local files

Use when Desktop groups unrelated chats under one Project, a new chat inherits the last Project unexpectedly, the Files pane opens an irrelevant directory, or a local result is presented as a downloadable artifact.

## State model

Keep these user concepts and storage layers distinct:

- Explicit Projects are per-profile rows in `$HERMES_HOME/projects.db`; their roots are in `project_folders`.
- Session ownership is derived from `state.db.sessions.cwd` by longest matching Project-folder prefix. Archiving a Project does not delete its sessions or filesystem folder.
- The durable backend selection is `projects.db.project_meta.active_id`.
- Desktop also persists a renderer view scope in `hermes.desktop.projectScope`. Clearing `active_id` alone may not neutralize the next chat because the renderer scope can still point at a Project.
- `Home` / `__no_project__` is the intentional detached scope. `All projects` / `__all_projects__` is an overview, not the same state.
- The Files pane is rooted at the selected session's cwd. Artifacts is a cross-session history index, not the task's working folder.

## Cleanup procedure

1. Establish the live profile and runtime. Inspect supported state before changing it:

   ```text
   hermes --version
   hermes config path
   hermes project list --all
   hermes project show <slug>
   ```

2. For each Project, check folder existence and count sessions whose cwd falls under its roots. Do not treat zero sessions as proof that the filesystem folder is empty or disposable. Classify the metadata and folder separately:
   - keep: valid root with active or relevant work;
   - archive metadata: missing root, duplicate/wrong root, or empty one-off wrapper;
   - investigate folder: valid root with ambiguous historical ownership, repository content, or uncommitted files.

   If the user asks to clean up "empty projects," establish whether they mean empty Hermes records, empty directories, or disposable worktrees. Inspect directory entries before changing metadata so deleting the Project row does not erase the only path needed for later folder review.

3. Prefer reversible metadata cleanup:

   ```text
   hermes project archive <slug>
   hermes project use
   ```

   Archive stale Projects and clear the durable active pointer when a neutral default was requested. Do not delete task folders or rewrite session cwd merely to make the sidebar prettier. Roll back with `hermes project restore <slug>`.

   Hard-delete Project metadata only when requested or when archived zero-session records are clearly being purged. Before hard deletion, retain or report the Project-to-folder mapping. A metadata purge does not authorize filesystem deletion.

4. Before deleting an associated folder, establish whether it is disposable:
   - inspect directory contents, repository remotes, current branch, worktree status, latest commit/reflog, and latest non-`.git` modification;
   - for PR/issue worktrees, read the live GitHub PR, linked issue, discussion, checks, and remote head—not just the folder name or local branch;
   - distinguish **superseded**, **rejected on design grounds**, **closed but still the best technical basis**, and **open/current work**;
   - compare local HEAD with the live PR head because an apparently stale local checkout may have newer work on the remote or in another worktree;
   - preserve untracked or uncommitted files even when unrelated to the named PR, and ask for explicit approval before deleting a non-empty repository.

   A missing folder needs no filesystem cleanup. A clean, closed, inactive worktree may be removable; an open PR, live issue, remote-only updates, or unique local content means keep or recover first.

5. Neutralize Desktop's separate scope through the product UI:
   - select one profile rather than All profiles;
   - set session grouping to Project;
   - enter Home.

   The generic project API may manage only explicit Projects and reject the synthetic Home id, so backend cleanup alone is not sufficient.

6. Verify both layers:
   - `hermes project list` shows only keepers;
   - `hermes project list --all` marks archived records or confirms explicitly purged rows are absent;
   - `project_meta` has no `active_id` when neutral was requested;
   - live Desktop accessibility/UI state says `HOME` and exposes `All projects` as the back action;
   - session counts are unchanged;
   - every folder classified for deletion, preservation, or already-missing state matches the reported outcome.

When live Home state plus the installed resolver contract proves that New Session resolves detached, avoid creating a disposable chat solely for testing. If restart persistence is uncertain, inspect the persisted renderer key read-only or create one bounded probe and delete that probe session after verification.

## Minimized or off-screen Desktop control

A minimized Electron window can be absent from ordinary window lists while its process and accessibility tree still exist. A verified control path is:

1. identify the exact Desktop PID and native window id without touching unrelated Chromium windows;
2. capture that exact target;
3. when input is refused because the window is minimized, follow the tool verdict and use the foreground rung once;
4. re-capture after every menu or state transition and use only fresh element refs;
5. verify the final semantic label such as `HOME`, not merely successful input delivery.

This is a recovery technique, not a durable claim that background input is broken.

## Local-file handoff

For a file already present on the user's machine:

- lead with what is ready and which task/Project owns it;
- provide one useful project root, launcher, or entry point instead of a wall of leaf-file links;
- focus the task-scoped Files pane or open a preview when that shortens navigation;
- do not use `MEDIA:` or attachment/download cards unless the user asked to transfer or download the file;
- never treat the global Artifacts history as the primary task workspace.

An isolated preview is not navigable context. Prefer an explicit Project root plus a clear entry point.

## Upstream routing

Search existing broad Desktop UX reports and read their comments before creating another issue. When the complaint is the same product-principle gap, add the current source-backed reproduction to the owning umbrella instead of filing a duplicate.

A useful report states:

- the visible creation workflow and exact environment/version;
- the separate backend and renderer state layers;
- the expected choices at New Session: No project, existing/recent Project, choose folder, or create Project;
- that the exact destination/cwd should be visible before first send;
- that Project view scope and actual session cwd must move together or be shown as distinct states.

Omit private project names and content from public reports.