---
name: native-mcp
description: Use for MCP server setup and connection troubleshooting.
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
---

# Native MCP setup

Use when adding, removing, authenticating, configuring tool exposure, or diagnosing a persistent MCP server connection. Merely calling an already-connected MCP tool does not require this skill. Browser navigation and browser task execution belong to the browser-specific owner, not MCP setup.

## Discover before changing

1. Load `hermes-agent` for the active host, frontend, home, profile, and installed-version checks. Native Windows is not WSL merely because the terminal uses Bash.
2. Read the current [official MCP guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp) and relevant installed `hermes mcp --help` subcommand help. Current docs and actual help beat legacy recipes. Standard current installs include MCP support; do not reflexively install a second SDK.
3. Inspect configured servers with `hermes mcp list`. Distinguish a missing server, failed connection, filtered tool, deferred schema, and stale frontend discovery before choosing a repair.

## Configure narrowly

- Prefer the supported catalog/add/configure flow over manually duplicating configuration. Inspect a server's publisher, executable or URL, dependencies, authentication, exposed tools, and effects before installation.
- Local stdio servers use a command and arguments; remote servers use an HTTP URL. Resolve executable paths for the actual host. Do not copy Unix paths or WSL networking recipes into native Windows configuration.
- Expose only the needed tools and roots. Keep credentials in the supported secret/auth flow, not literal secrets in chat or copied YAML examples.
- Review server-initiated sampling separately: connecting an MCP server does not authorize paid inference. Disable sampling unless its model, cost, and authority are acceptable for the authorized task.
- Changing server configuration does not authorize invoking a mutating tool. Preserve user and native approval boundaries; do not use hook-acceptance flags as a setup shortcut.

## Verify and stop

Use the installed `hermes mcp test` interface after reading its help; inspect the exact server result, then verify tool discovery in the affected frontend. Reload or restart only when that installed frontend requires it. One harmless read-only tool call verifies usable integration; connection success alone does not prove tool behavior. Report auth, network, or discovery blockers without claiming readiness.

For browser-server setup specifically, read [browser connection boundaries](references/browser-control-mcp.md). For additional config fields, use the [official MCP configuration reference](https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference).
