# Windows OpenSSH remote access

Use for SSH/mobile clients, mesh-VPN hosts and pairing tools on native Windows. Check the client's current entitlement before changing host configuration; host repairs cannot unlock a paid feature.

## Diagnose one boundary at a time

1. Verify peers and the exact advertised host/IP and port. If a mesh IP works but private DNS fails, diagnose DNS separately.
2. Identify SSH, Mosh or Auto. Select SSH explicitly when the reached environment has no actual Mosh server; a warning is not proof of a usable automatic transport.
3. Inspect the server's effective authorized-key path for the intended account before changing keys.
4. After real SSH login, test the intended daemon, persistent multiplexer, hooks and agent discovery. A setup CLI and daemon can share an executable but have distinct roles. Verify live pairing/bridge state and restart only the affected authorized daemon if it started unpaired.

Do not delete a working mobile connection to refresh hooks: it can discard the client's private key and require new authorization.

## Administrator key routing

Inspect the intended account's group membership and effective `sshd_config`, including any `Match Group administrators` rule. If the matching rule selects `__PROGRAMDATA__/ssh/administrators_authorized_keys`, the ordinary account key file is not the configured path.

Explain privileged-account access and consider a dedicated non-administrator account when appropriate; do not create or switch accounts without task authorization. If the selected authorized account is administrative, install only the exact generated public key in the configured key store. Preserve existing authorized keys. Use an elevated operation to apply and read back the Windows OpenSSH ACL requirements: inheritance disabled and access limited to SYSTEM and BUILTIN\Administrators. Inspect existing explicit ACEs; adding grants alone does not remove unrelated access. Do not broaden ACLs for normal-user verification. Verify current official Windows OpenSSH guidance and localized identity resolution before applying ACL commands.

For multi-step elevated work, prefer a temporary PowerShell script and minimal readback receipt. When invoking PowerShell through Bash, prevent Bash from expanding PowerShell variables. Verify exact protected targets and clean up task-owned helpers/receipts.

## Verify safely

Compare public-key fingerprints without printing key material. Check the running sshd service's actual binary path and recent OpenSSH Operational events around the attempt. The decisive check uses the actual remote client, intended username, host/IP, port, key and transport, followed by intended session discovery. Report host readiness separately until that passes. For VPN-only access, inspect relevant firewall/router exposure; a mesh IP does not prove absence of public forwarding.
