from __future__ import annotations

import os

from .caretaker import (
    ensure_task_for_id,
    load_settings,
    pending_ambiguity_context,
    pending_resolution_context,
)


def _on_kanban_task_blocked(task_id: str, board: str = "", **_kwargs):
    """Create one idempotent caretaker card after an actionable block."""
    settings = load_settings()
    if board in settings.boards:
        ensure_task_for_id(settings, board, task_id)


def _on_pre_llm_call(**_kwargs):
    """Surface one unresolved caretaker question on the next user-driven turn."""
    delegated_child = bool(os.environ.get("HERMES_DELEGATED_CHILD_CONTEXT"))
    try:
        from agent.delegation_context import is_delegated_child_process_context

        delegated_child = delegated_child or is_delegated_child_process_context()
    except ImportError:
        pass
    if os.environ.get("HERMES_KANBAN_TASK") or delegated_child:
        return None
    settings = load_settings()
    context = pending_ambiguity_context(settings) or pending_resolution_context(settings)
    return {"context": context} if context else None


def register(ctx):
    ctx.register_hook("kanban_task_blocked", _on_kanban_task_blocked)
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
