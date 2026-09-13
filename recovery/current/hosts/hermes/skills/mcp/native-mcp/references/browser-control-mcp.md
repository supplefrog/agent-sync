# Browser connection boundaries

Use only when a browser-control MCP server must be configured or repaired; ordinary browsing belongs to `agent-browser-middlepath`, and live Desktop DOM inspection to `inspecting-hermes-desktop-dom`.

- Check the existing native browser and Chrome DevTools tools first. A working direct control path does not need another MCP installation or coding-agent intermediary.
- Match the required surface: Chrome DevTools for console/network/performance debugging; the existing native browser for ordinary DOM navigation and user-session work. Do not rank tools by presumed token savings without task evidence.
- For a CDP connection, verify the intended browser/profile and a reachable endpoint before configuring the server. Do not silently switch a user-account task to an empty profile.
- Remote debugging is privileged browser access. Keep endpoints local/private, preserve profile safety, and do not expose a debugging port publicly.
- Read the installed server's help and official documentation for current connection flags. Verify host-specific executable resolution; WSL-to-Windows connectivity matters only when a real WSL process owns the client.
- Scope exposed tools, authentication, and telemetry deliberately. Test a harmless operation in the intended profile; a successful server spawn alone is not verification.
