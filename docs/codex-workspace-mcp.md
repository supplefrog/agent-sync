# Codex workspace MCP

Codex-only native adapter for the creation gaps in `codex-app-tools`, and private
cloud media/file handoff. The source owner is `tools/codex_workspace_mcp.py`, with
the existing `tools/codex_project.py` native RPC helper. No portable skill or
shared standing-instruction change is needed.

Tools: durable cloud-configuration listing/creation/publication, safe config and
publication operation readback, ChatGPT/local project creation,
durable Codex task creation from a saved configuration, stored task-environment
readback, and cloud-file export. Existing app tools continue to own messaging,
waiting, archiving, and supported project assignment. Durable Codex tasks cannot
be assigned to ChatGPT projects by this adapter; it does not bypass the installed
app's local-only membership restriction.

## Contracts and evidence

Observed in installed Codex 26.1007.2314.0 on 2026-10-11:

- Native `getAuthStatus` with `includeToken=true` supplies the current signed-in
  token in memory. No auth files, tokens or account claims enter source, receipts
  or tool results. A native app-server subprocess closes after each tool call.
- Durable configurations use `/v1/environment-configs` on the cloud backend.
  List user and workspace scopes independently. The older WHAM catalog is a
  different backend and cannot supply durable saved-configuration IDs.
  Creation passes explicit repository IDs/refs, network policy and sharing, with
  `start_onboarding=false`. Secret setup stays in the native UI. Creation alone
  establishes neither publication readiness nor a task launch.
- Publication uses the native draft `/approve/begin` operation with an exact
  expected revision and idempotency key, `/v1/environment-operations/{id}`
  readback, and `/approve/complete`. Completion requires a succeeded operation
  bound to this account/configuration/draft by the private begin receipt. Use a
  fresh UUID for completion, while retaining both receipts across uncertainty.
  These explicit publication tools do not answer agent approval requests.
- ChatGPT project creation uses `POST /projects` with `creation_request_id`;
  local project creation uses `project/create` with `idempotencyKey`.
- The native durable transport uses the authenticated
  `codex-cloud-backend.chatgpt.com` WebSocket. Saved-configuration startup uses
  `thread/start`, `environments[{environmentConfigId,cwd}]` and
  `deferredEnvironment=true`, matching the installed transport adapter.
- Native file download uses `fs/readFile({environmentId,path})`, not a writable
  `/codex` deliverable directory. The returned bytes can be saved privately on
  the PC and displayed by normal local media previews.

These are private, version-sensitive endpoints, not a public OpenAI API support
guarantee. Runtime probes established native authentication, HTTP 200 for the
durable configuration/model lists, durable initialization, and an environment-registry
404 for a deliberately nonexistent file-read environment. No product chat was
resumed or modified. Creating remote objects and exporting real product media
remain action-specific verification; those operations are not claimed completed
merely because negotiation and boundary probes passed.

## Installation and recovery

Use Agent Sync's dependency-ready Python, and install the single extra pinned
dependency into a stable user-local runtime from
`requirements-codex-workspace.txt`. Register `codex-workspace` with `codex mcp add`
using the published script and its `--codex-exe`, `--deps`, `--state-root` and
`--export-root` arguments. Config, operation receipts, dependency installs and
exported files remain private native state; they are not committed or captured
into the shared repository. Verify `codex mcp get codex-workspace` and fresh MCP
initialize/tools-list negotiation. Already-running chats may need a tool refresh
or a new chat. Never restart or disturb another running task to expose the tools.

The native CLI executable and Python path are resolved on the receiving host;
do not copy machine-specific paths or credentials into shared source. This
adapter is installed for Codex only. Rollback is `codex mcp remove
codex-workspace`; preserve exported files and uncertain-operation receipts.

Each creation reserves a caller-supplied UUID before sending its write. Restart
and duplicate calls return a confirmed result or stop on uncertain state; they
never blindly replay an ambiguous creation. A partially initialized cloud task
retains its thread identity before optional naming/first-turn submission.
Creating a task does not authorize a later batch, spending escalation, publishing,
or replying to approvals. No approvals/server requests are automatically answered.

Exports stay under the selected local export root, verify an optional source
SHA256, enforce a byte ceiling up to 256 MiB, and refuse conflicting destinations.
The MCP result contains a local path/size/hash instead of large base64 payloads.
The cloud remains unchanged and no public upload is involved.

The retirement condition is full native-tool coverage of these creation and
private-export contracts with equivalent uncertainty/identity handling. Remove
this adapter when that occurs rather than maintaining duplicate write paths.
