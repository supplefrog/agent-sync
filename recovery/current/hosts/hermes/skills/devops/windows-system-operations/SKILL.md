---
name: windows-system-operations
description: Use for Windows app, shell, and package troubleshooting.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [windows, powershell, completion, appx, msix, troubleshooting]
---

# Windows System Operations

Use this umbrella for Windows application/package diagnosis, privacy-preserving removal, and PowerShell profile or completion engineering.

## Windows apps and packages

1. Split Store/AppX failures into discovery/licensing, DNS/routing, package download, delivery services, deployment/registration, and application identity because a healthy earlier layer does not prove the next one.
2. Capture the exact timestamp, endpoint, HRESULT, product ID, package identity, service state, and whether Store UI and `winget --source msstore` fail alike.
3. Test the exact endpoint and alternate resolver answer without globally changing DNS; apply only the smallest reversible change and restore it in `finally`.
4. Keep elevation-only network changes separate from normal-user Store licensing operations.
5. For removal, identify the installation owner before deleting files: query `winget list`, the HKLM/HKCU uninstall registry entries (`UninstallString` / `QuietUninstallString`), and the relevant package provider; invoke that backend first because it owns registration and shared cleanup.
6. Treat an app-managed portable runtime as directory-owned only after those package checks return no match and its path/metadata identify the owning application. Stop it with its native lifecycle command, remove the isolated runtime root, then verify the path, processes, and listening ports are all absent.
7. Verify package `Status = Ok`, install location, Start registration, and restored configuration—not merely a success string.
8. Separate runtime-crash cause from post-crash package damage; a reinstall can repair the consequence without fixing the trigger.

Read `references/windows-app-lifecycle.md` for GPU crash boundaries and privacy-preserving uninstall.

## Workspace relocation and home-folder cleanup

- Treat user-added projects, automatic chat/output workspaces, application state, and disposable artifacts as separate scopes. For Codex project moves, use registered project roots as the default allowlist; a thread cwd or dated output folder does not establish project ownership.
- Keep the user's home folder tidy without sweeping application state into Projects. When asked for candidates so the user can decide, inventory only; report likely leftovers, active/protected items, and uncertain ownership separately. An uninstalled application does not make its conversation history, projects, worktrees, or credentials disposable.
- Preserve `NTUSER.DAT`, its logs/transaction companions, `ntuser.ini`, and Windows compatibility links during home cleanup; protected profile files are not stray project output. Do not change permissions to inspect or remove them.
- Remove explicitly obsolete setup files and confirmed empty uninstalled-app remnants, not credential stores or cloud resources merely because deployment is complete.
- Do not retain old-name project shortcuts once their dependencies use canonical paths. Before unlinking, check saved thread/project metadata, Git worktree pointers, launchers, and installed skill/plugin mount targets; repair required mounts and verify fresh discovery without the old aliases. Preserve Windows system links.
- Judge checkout disposal by preserved commits and local work, not age alone. Report checkout redundancy, behavior in the retained canonical source, installed behavior, and upstream PR status separately: a newer checkout containing equivalent work supersedes the old copy even when that work is not deployed or merged. Name the repository, retained ref, and commit when saying work is preserved in Git. Keep recovery compact and inside the task workspace; report net reclaimed space after recovery, not just bytes removed.

For existing Codex project moves, read `references/codex-workspace-relocation.md` before mutating thread state; loaded-session settings and paginated-history offsets need separate treatment. For SQLite remnants and repository disposal, use the cleanup procedure in `references/windows-app-lifecycle.md`.

## PowerShell completion and startup

- Separate PSReadLine display behavior from completion sources/ranking because changing Tab’s UI cannot invent arguments.
- Test command position, first subcommand, nested positional arguments, unrelated completers, and path fallback.
- Use the correct `Register-ArgumentCompleter` signature for command/native versus parameter completers; the wrong signature can fail silently.
- Generate a maintainable PowerShell shim when a CLI emits only POSIX completion, rather than hardcoding one shallow case.
- Measure profile startup and lazy-load heavyweight modules because discovery/import work on every shell launch is user-visible latency.

Read `references/powershell-completion.md` for acceptance probes and lazy-loading rules.
