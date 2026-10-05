# Native project association

Load only the affected host procedure. The portable owner decides project scope and filesystem ownership; this adapter describes supported host glue. A successful file move never proves native thread association. Record requested, persisted, live-runtime and UI state separately.

## Codex

Prefer app tools that expose project creation or assignment. The current Codex app tools can list projects, create a user-requested new thread in an existing project, and move sidebar sections; they do not expose creating a local project or assigning an existing thread. A custom sidebar section is not a project. Do not create a replacement thread just to simulate a move.

The installed Codex CLI's experimental app-server schema (checked 2026-10-05) exposes:

- `project/list`, `project/read`, `project/create` with `{idempotencyKey, name, roots: [{path: <absolute root>}]}`. Resolve/reuse a matching root before creation; retain one idempotency key through an uncertain result.
- `thread/metadata/update` with `{threadId, projectId}` assigns an existing project without resuming the thread. Read `thread/read` with `includeTurns: false` to verify `projectId`. Do not use `project/move` for this; it changes sidebar order.
- `thread/settings/update` includes `cwd` but is a separate loaded-thread setting. Project membership does not establish cwd, file relocation, runtime reload or changed sandbox permissions. Do not resume another dormant or user-owned live thread merely to change cwd. Use an exposed supported current-thread setting when authorized; otherwise record the canonical project root in the continuation and report the remaining workspace limitation.

Generate the schema from the accessible installed wrapper (`codex app-server generate-json-schema --experimental --out <task-scratch>`), then verify current parameters and read capability before a write. Native app-server RPC requires `initialize` with experimental capability and the normal initialized notification; consume notifications, match response IDs, use bounded timeouts and do not replay an uncertain write before readback. Do not start a replacement app, write SQLite/rollouts or alter authentication/trust. An isolated app-server test establishes native contract support, not that the running Desktop refreshed its sidebar. If the active environment has no suitable native connection, finish project-local work and report association pending with the exact required UI/API step.

The native [Codex project helper](../tools/codex_project.py) implements paginated discovery, root reuse/collision checks, exact stored-thread assignment and metadata readback without resuming a thread or making a model call:

```text
python tools/run.py codex_project --codex-exe <verified-native-exe> --root <canonical-root> --name <project-name> --thread-id <stored-id>
# After reviewing that preview within the user's authorization:
python tools/run.py codex_project --codex-exe <verified-native-exe> --root <canonical-root> --name <project-name> --thread-id <stored-id> --apply --expect-project <prior-id-or-none> --idempotency-key <retained-uuid>
```

Use the current host/profile's existing environment. `--apply` is an execution flag, not authorization. Keep the same creation key through an uncertain result, preview/read back before retrying, and never answer native approvals automatically. A newly started empty thread may have no persisted rollout yet; leave assignment pending rather than inject history into a real thread or start inference to manufacture persistence. A project created before a later assignment failure remains visible for inspection/reuse; it is never automatically deleted. The helper does not change cwd, permissions, files, active selection or histories. Concurrent ownership of the same native thread must be resolved first; the API has no atomic compare-and-set for membership.

## Hermes

Use its native `session-librarian` and `references/desktop-session-api.md` from the active profile. Verify the live tool schema and correct authenticated backend/profile first. On this installed source, `desktop_project` exposes `list`, `create` and `switch`; it does not expose a stored-session `move` action.

For the calling Desktop chat, `desktop_project(action="create", name=..., path=...)` creates/reuses the project and re-anchors that chat, and `switch` selects an existing one. The callback is Desktop-specific; CLI/messaging use can instead alter the profile-global project pointer. Do not use that unscoped path to organize a concurrent Desktop chat.

For a stored session use the existing authenticated `session.workspace.move` with `{session_key: <stored ID>, cwd: <absolute root>, profile: <verified profile>}`. The installed handler replaces stored cwd/git identity and updates a matching live owner. `projects.create` accepts `name`, `folders`, `primary_path`, `profile` and `use: false` to avoid changing a shared active selection. Verify `projects.list`/`projects.project_sessions`, exact membership, title/history preservation and unaffected neighboring sessions. Membership neither moves files nor merges histories. Read back uncertain writes; never automatically resend or bypass an approval/authentication refusal.

No new credentials, remote access or background watcher is needed. Reuse the native authenticated local connection procedure, without printing/persisting its token. Source presence is not proof that an already-running backend loaded it; verify live availability or mark it pending.

## Optional hosts

OMP has no managed standing lifecycle overlay in the currently observed setup. The shared skill can be loaded on demand; automatic triggering and native project association are unverified. Do not claim all-host activation.
