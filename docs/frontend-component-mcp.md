# Component MCP setup

Checked 3 October 2026. Codex and Hermes have **shadcn 4.21.1** and **GodUI MCP 0.1.0** configured and enabled. Node 24.12.0 and the pinned packages are installed in a stable user-local runtime, independent of WhichAI's product dependencies. Existing settings and servers were preserved. The running clients must reload their MCP configuration; an already running chat does not acquire tools merely because its config changed.

| Server | Setup | Actual verification |
|---|---|---|
| shadcn | Both hosts use the same pinned Node entrypoint; six discovery/source/command-text tools allowed | Native Hermes negotiation through the installed SDK succeeded. Tools list, item metadata and TSX examples succeeded. `view_items_in_registries` returned metadata; `get_item_examples_from_registries` returned source. Codex's native `mcp get` readback confirms its declaration and filter. |
| GodUI | Both hosts use the same pinned Node entrypoint; list/search/get tools allowed | Same native negotiation succeeded; search and `get_component` returned actual TSX, dependencies and install instructions. Codex's native readback confirms its declaration and filter. |
| 21st (`twentyfirst`) | Full official HTTP endpoint configured in both hosts for OAuth, with discovery/source-only tool filters; disabled pending authentication | Account sign-in is separate from GitHub. Native authorization has been started. Successful sign-in, server discovery and enablement are not yet established. |

The free-server probes used isolated project fixtures and Hermes's native negotiation/discovery methods with its installed MCP SDK transport. They avoided the full stdio supervisor's unscoped orphan-process reaper. This is protocol/source-retrieval evidence, not a full launcher test, visual-quality result, current-chat tool exposure or cross-host behavioral parity.

Shadcn reads a project's `components.json` to discover third-party registries. Its MCP does not require initializing a real product merely to configure the server. Add the selected registry to the actual project when needed, after the parts preview; inspect its files/dependencies before installation. Fancy, Animate UI and Magic UI can use this source-delivery mechanism where compatible, without separate global servers or wholesale component installation. GodUI's returned installation instructions merge global theme tokens/styles; review that CSS diff rather than accepting its demo's theme as the product's identity.

The 21st full endpoint advertises OAuth discovery; its read-only endpoint does not. Only `search`, `get_inspiration`, `get_component` and `search_logo` are allowed in this declaration. Hosted generation, publishing and account mutation are not exposed. Authentication does not authorize spending or establish source-copy entitlement; check the current account allowance before a metered operation. OAuth credentials remain in each host's native private store. The new server declarations are owned by the native configs; the existing narrow Agent Sync settings snapshot does not capture these new servers. This document records the reinstall procedure without expanding capture to unrelated settings.

## Reproduce the dependencies

Use an installed Node version satisfying the packages' requirements (shadcn >=20.18.1, GodUI >=20.19.0). This setup uses Node 24.12.0. Install the pinned packages under the user's local runtime:

```powershell
$componentRuntime = Join-Path $env:USERPROFILE '.local/share/frontend-component-mcp'
npm install --prefix $componentRuntime --save-exact shadcn@4.21.1 @godui/mcp@0.1.0
```

Launch the installed `shadcn/dist/index.js` with argument `mcp`, and `@godui/mcp/dist/index.js` without extra arguments, using the durable Node executable. Avoid an ephemeral `fnm_multishells` path or PowerShell shim as a stdio command. `package-lock.json` records the installed dependency tree locally. Reinstall dependencies and resolve the executable path on a recovered host; use this recipe to add the server declarations again. Credentials and full private configs are not published.

Native sign-in commands:

```text
codex mcp login twentyfirst
hermes mcp login twentyfirst
```

Enable each host's server only after its authentication and a read-only tool check succeed. Reload the applicable client, then verify tool availability in a fresh context. No real product component was installed or changed by this setup.

Primary references: [shadcn MCP](https://ui.shadcn.com/docs/mcp), [GodUI MCP](https://godui.design/docs/mcp), [Codex MCP](https://developers.openai.com/codex/mcp), [Hermes MCP config](https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference), [21st authentication](https://21st.dev/auth.md), [21st tools](https://21st.dev/mcp.md).
