---
name: github-auth
description: "Use when GitHub or git authentication is missing or broken: gh login, account verification, HTTPS credential setup, SSH keys, Windows/WSL host fallback, or permission diagnosis."
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [github, authentication, git, gh-cli, ssh, setup]
    related_skills: [github-collaboration-workflows, github-follow-up]
---

# GitHub Authentication

Establish the smallest supported authentication path without exposing or scraping credentials. This skill owns login and credential diagnosis; `github-collaboration-workflows` owns repository, issue, PR, review, CI, release, and settings operations.

## Workflow

1. **Identify the runtime.** Confirm whether the shell is native Windows, WSL, Linux, or macOS. Do not infer the credential store from the repository path.
2. **Check existing tools and identity.** Run:

   ```bash
   git --version
   gh --version
   gh auth status
   gh api user --jq .login
   ```

   If `gh` is missing or unauthenticated in WSL, load `references/wsl-windows-gh.md` before requesting credentials; the authenticated Windows-host CLI may already be usable.
3. **Reuse a valid login.** If `gh auth status` succeeds for the intended account and host, run `gh auth setup-git` when Git HTTPS operations still prompt. Do not reauthenticate merely because a repository command failed; inspect repository permission and remote ownership first.
4. **Login only when needed.** Prefer the supported browser/device flow:

   ```bash
   gh auth login --hostname github.com --git-protocol https --web
   gh auth setup-git
   ```

   Let `gh` generate and poll its own device flow. Show the user the verification URL/code when interaction is required, then verify after they complete it. Do not implement GitHub's OAuth protocol manually or ask the user to paste a token into chat.
5. **Use SSH only when requested or already established.** Inspect existing public keys and GitHub connectivity first. Creating a key, changing global URL rewrites, or editing `~/.ssh/config` requires explicit scope because it changes host-wide behavior.
6. **Use a personal access token only as a bounded fallback.** Prefer a fine-grained, expiring token limited to the required repositories and permissions. Supply it through `gh auth login --with-token` or a supported credential manager without printing it.
7. **Verify the exact seam.** Check all that apply:

   ```bash
   gh auth status
   gh api user --jq .login
   gh repo view OWNER/REPO --json nameWithOwner,viewerPermission
   git ls-remote ORIGIN_URL
   ```

   A valid login does not prove write, Actions, organization, or private-repository permission.

## Security boundaries

- Never read tokens from `.env`, `.git-credentials`, remote URLs, shell history, logs, or unrelated process environments.
- Never embed a token in a Git remote URL or command argument.
- Never select plaintext `credential.helper store` as the default. Prefer `gh auth setup-git`, Git Credential Manager, an OS keyring, or SSH.
- Never hand-write `hosts.yml`, copy browser cookies, or bypass organization SSO.
- Do not delete credentials, switch accounts, regenerate tokens, or rewrite global Git configuration without confirming the affected host/account scope.
- Redact secrets from output; report identity, host, scopes/permissions, and the failing operation instead.

## Diagnosis

- **`gh auth status` fails:** login is absent, expired, or stored in an unavailable keyring.
- **`gh` works but `git push` prompts:** run `gh auth setup-git`, then inspect the remote protocol and credential helper.
- **Repository permission denied:** verify the live viewer, repository owner, collaborator role, token scopes, and organization SSO before reauthenticating.
- **SSH port 22 blocked:** diagnose first; use GitHub SSH over port 443 only with user approval for the SSH configuration change.
- **Multiple accounts:** use supported `gh auth status`, `gh auth switch`, and explicit `-R OWNER/REPO`; do not guess which identity should mutate the target.

Done means the intended live identity and exact required read/write operation are verified without exposing credentials or altering unrelated accounts.
