# Native project association

Load only the affected host procedure. The portable owner decides project scope and filesystem ownership; this adapter describes supported host glue. A successful file move never proves native thread association. Record requested, persisted, live-runtime and UI state separately.

## Codex

Use supported app tools to discover saved projects and assign existing threads within their host/access limits. Local Desktop project creation/adoption is not exposed by the current callable tools. A custom sidebar section is not a project. Do not create a replacement thread just to simulate a move.

For a user-requested new local chat in an existing saved project, discover the project with `codex_app.list_projects`, verify its exact ID and local execution support, then use `codex_app.create_thread` with `target: {type: "project", projectId: <verified-existing-ID>, environment: {type: "local"}}`. Preserve the user's prompt and any explicitly selected model. This is a new-chat route, not an existing-chat move or local-project creation route.

After creation, independently read the returned thread through the active app's thread listing/read tools and verify its actual `hostId` and exact `projectId` against the requested placement. Pending setup or a `clientThreadId` is not completed placement. A wrong host, null project, mismatched project, or unavailable readback leaves placement unverified; report the returned identity and discrepancy, inspect it before any retry, and do not silently create a second chat. Filesystem cwd and an environment selection do not establish saved-project membership. Parent `cloud_threads.create` with environmentId/projectId/cwd previously created a durable-host chat with no project; do not use it as this local-chat route. Cloud execution helpers remain available when the requested outcome is durable cloud execution without a local placement requirement.

The existing helper can check JSON obtained from that independent active-app readback without connecting or writing: `python tools/run.py codex_project --verify-app-readback <readback.json> --thread-id <returned-thread-ID> --project-id <requested-project-ID> --host-id local`. Supply the actual observed `id`/`threadId`, `hostId` and `projectId`; do not fill missing fields with expected values. This checks the readback fields, not its authenticity or UI refresh.

The installed Codex CLI's experimental app-server schema (checked 2026-10-05) exposes:

- `project/list`, `project/read`, `project/create` with `{idempotencyKey, name, roots: [{path: <absolute root>}]}`. Resolve/reuse a matching root before creation; retain one idempotency key through an uncertain result.
- `thread/metadata/update` with `{threadId, projectId}` assigns an existing project without resuming the thread. Read `thread/read` with `includeTurns: false` to verify `projectId`. Do not use `project/move` for this; it changes sidebar order.
- `thread/settings/update` includes `cwd` but is a separate loaded-thread setting. Project membership does not establish cwd, file relocation, runtime reload or changed sandbox permissions. Do not resume another dormant or user-owned live thread merely to change cwd. Use an exposed supported current-thread setting when authorized; otherwise record the canonical project root in the continuation and report the remaining workspace limitation.

Generate the schema from the accessible installed wrapper (`codex app-server generate-json-schema --experimental --out <task-scratch>`), then verify current parameters and read capability before a write. Native app-server RPC requires `initialize` with experimental capability and the normal initialized notification; consume notifications, match response IDs, use bounded timeouts and do not replay an uncertain write before readback. Do not start a replacement app, write SQLite/rollouts or alter authentication/trust. An isolated app-server test establishes native contract support, not that the running Desktop refreshed its sidebar. If the active environment has no suitable native connection, finish project-local work and report association pending with the exact required UI/API step.

These APIs and the native [Codex project helper](../tools/codex_project.py) operate on the local app-server registry, not the saved Desktop sidebar catalog. The helper retains paginated discovery, root reuse/collision checks, stored local-thread metadata assignment and readback without resuming a thread or making a model call. Use it only for explicitly requested native registry work; it cannot fulfill Desktop project setup or durable-host placement. A registry-only result is not migration completion.

For that narrow registry scope, supply the actual thread host (only `local` is supported):

```text
python tools/run.py codex_project --codex-exe <verified-native-exe> --root <canonical-root> --name <project-name> --thread-id <stored-id> --host-id local
# After reviewing that preview within the user's authorization:
python tools/run.py codex_project --codex-exe <verified-native-exe> --root <canonical-root> --name <project-name> --thread-id <stored-id> --host-id local --apply --expect-project <prior-id-or-none> --idempotency-key <retained-uuid>
```

Use the current host/profile's existing environment. `--apply` is an execution flag, not authorization. Keep the same creation key through an uncertain result, preview/read back before retrying, and never answer native approvals automatically. A newly started empty thread may have no persisted rollout yet; leave assignment pending rather than inject history into a real thread or start inference to manufacture persistence. A project created before a later assignment failure remains visible for inspection/reuse; it is never automatically deleted. The helper does not change cwd, permissions, files, active selection or histories. Concurrent ownership of the same native thread must be resolved first; the API has no atomic compare-and-set for membership.

Helper outcomes distinguish verified native registry/thread metadata from unsupported Desktop sidebar adoption; the existing `ui_refresh_verified: false` remains. An explicit non-local host fails before connecting. An unloaded local thread requires checking actual host/persistence, not resuming or recreating it. Do not infer host membership from a null projectId alone.

The installed `codex-workspace.create_project(kind="local")` Desktop workflow was retired in 0.1.1; ChatGPT project creation and cloud controls remain. For a Desktop project, use supported manual setup and read back its exact saved ID/root. Preserve any existing native registry record until a supported adoption/reconciliation operation is available; do not replay creation or edit internal state to make it appear in the sidebar.

## Hermes

Use its native `session-librarian` and `references/desktop-session-api.md` from the active profile. Verify the live tool schema and correct authenticated backend/profile first. On this installed source, `desktop_project` exposes `list`, `create` and `switch`; it does not expose a stored-session `move` action.

For the calling Desktop chat, `desktop_project(action="create", name=..., path=...)` creates/reuses the project and re-anchors that chat, and `switch` selects an existing one. The callback is Desktop-specific; CLI/messaging use can instead alter the profile-global project pointer. Do not use that unscoped path to organize a concurrent Desktop chat.

For a stored session use the existing authenticated `session.workspace.move` with `{session_key: <stored ID>, cwd: <absolute root>, profile: <verified profile>}`. The installed handler replaces stored cwd/git identity and updates a matching live owner. `projects.create` accepts `name`, `folders`, `primary_path`, `profile` and `use: false` to avoid changing a shared active selection. Verify `projects.list`/`projects.project_sessions`, exact membership, title/history preservation and unaffected neighboring sessions. Membership neither moves files nor merges histories. Read back uncertain writes; never automatically resend or bypass an approval/authentication refusal.

No new credentials, remote access or background watcher is needed. Reuse the native authenticated local connection procedure, without printing/persisting its token. Source presence is not proof that an already-running backend loaded it; verify live availability or mark it pending.

## Optional hosts

OMP has no managed standing lifecycle overlay in the currently observed setup. The shared skill can be loaded on demand; automatic triggering and native project association are unverified. Do not claim all-host activation.
