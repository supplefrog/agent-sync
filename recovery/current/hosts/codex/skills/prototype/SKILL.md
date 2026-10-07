---
name: prototype
description: Build a throwaway prototype to answer a logic or state-model question. For visual UI exploration, route to frontend-ui-engineering's comparison guidance.
license: MIT
author: Emil Kowalski; Agent Sync routing adaptation
---

# Prototype

A prototype answers a concrete design question. Choose from the request and surrounding code; if the question is materially ambiguous, resolve it before building.

- Logic, state transitions or data shape => read [LOGIC.md](LOGIC.md). Build a small interactive terminal shell around an isolated logic module, exposing the relevant state and actions.
- UI appearance or interaction alternatives => read [UI.md](UI.md), which routes to the frontend owner. Its fidelity, comparison, preview and production checks apply to UI work.

## Logic prototype boundaries

Keep the experiment clearly marked and near its intended module. Use the project's existing runtime and one run command. Prefer in-memory state; use a clearly disposable store only when persistence is the question. Expose relevant state after each action and keep the shell small enough to answer the question.

Record the question, answer and useful primary-source experiment in the existing project context. Preserve it recoverably before cleanup; a throwaway branch can hold the TUI shell when appropriate. Use `breadcrumb-records` for substantial closeout when no equivalent record exists. Keep only the validated logic in production, with the production checks its behavior requires.
