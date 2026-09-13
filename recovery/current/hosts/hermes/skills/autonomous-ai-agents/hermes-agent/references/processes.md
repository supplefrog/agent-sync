# Additional Hermes processes

Use only when an independent process is more appropriate than supported native delegation (for example, a durable mission or required interactive CLI). Confirm host, active home/profile, CLI help, authorization, output ownership and bounded stop/cleanup conditions first. Native Windows should use its supported noninteractive or PTY path; tmux requires a confirmed Linux/WSL process and installed tmux. Do not impose a new approval hop on already authorized, reversible worker execution.

Agent-created one-shots must use `--source tool` so they are distinguishable from user sessions. Record the exact created session ID. After preserving the required output/receipt and integrating the result, delete that session with `hermes sessions delete --yes <session-id>` and verify it is absent; process exit, stop, and archive are not deletion. Never delete user-created, shared, active, or referenced sessions.

```
terminal(command="hermes chat --source tool -q 'Research GRPO papers and write summary to ~/research/grpo.md'", timeout=300)

# Background for long tasks:
terminal(command="hermes chat --source tool -q 'Set up CI/CD for ~/myapp'", background=true)
```

Use the current host's process/status tools to observe completion rather than fixed startup sleeps. Keep approvals enabled. Never delete user-created, shared, active or still-referenced sessions; if the host cannot delete a created session, report the retained handle rather than describing process exit as deletion.
