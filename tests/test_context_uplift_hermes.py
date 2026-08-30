"""Production-seam checks for the installed Hermes context machinery.

These tests stay isolated from the user's live Hermes home and create no Hermes
sessions visible to Desktop. They skip on hosts without a source checkout.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def _hermes_source() -> Path | None:
    override = os.getenv("HERMES_SOURCE")
    if override:
        candidate = Path(override)
    elif os.name == "nt" and os.getenv("LOCALAPPDATA"):
        candidate = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "hermes-agent"
    else:
        candidate = Path.home() / ".hermes" / "hermes-agent"
    return candidate if (candidate / "run_agent.py").is_file() else None


SOURCE = _hermes_source()
pytestmark = pytest.mark.skipif(SOURCE is None, reason="installed Hermes source checkout not found")
if SOURCE is not None and str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))


def _seed(db, session_id: str) -> None:
    db.create_session(session_id, "eval", model="test/model")
    db.set_session_title(session_id, "context-uplift-isolated")
    for index in range(8):
        db.append_message(
            session_id=session_id,
            role="user" if index % 2 == 0 else "assistant",
            content=f"synthetic-canary-{index}",
        )


def _make_agent(db, session_id: str):
    from run_agent import AIAgent

    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "synthetic-test-key"}):
        agent = AIAgent(
            "https://openrouter.ai/api/v1",
            "synthetic-test-key",
            model="test/model",
            quiet_mode=True,
            session_db=db,
            session_id=session_id,
            skip_context_files=True,
            skip_memory=True,
        )
    agent.compression_in_place = True

    def deterministic_compress(messages, current_tokens=None, focus_topic=None, force=False):
        return [
            {"role": "user", "content": "[CONTEXT COMPACTION] synthetic summary"},
            {"role": "assistant", "content": "synthetic recent reply"},
        ]

    agent.context_compressor.compress = deterministic_compress
    agent.context_compressor._last_compress_aborted = False
    agent.context_compressor._last_summary_error = None
    agent.context_compressor.compression_count = 1
    return agent


def test_in_place_compaction_keeps_identity_and_survives_reopen(tmp_path, monkeypatch):
    isolated_home = tmp_path / "hermes-home"
    isolated_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(isolated_home))

    from agent.conversation_compression import compress_context
    from hermes_state import SessionDB

    db_path = isolated_home / "state.db"
    session_id = "eval-context-uplift"
    db = SessionDB(db_path=db_path)
    try:
        _seed(db, session_id)
        agent = _make_agent(db, session_id)
        compressed, _ = compress_context(
            agent,
            [{"role": "user", "content": f"synthetic message {i}"} for i in range(8)],
            approx_tokens=100_000,
            system_message="synthetic system",
        )

        assert agent.session_id == session_id
        assert agent._last_compaction_in_place is True
        assert [message["content"] for message in compressed] == [
            "[CONTEXT COMPACTION] synthetic summary",
            "synthetic recent reply",
        ]
        assert db._conn.execute(
            "SELECT count(*) FROM sessions WHERE parent_session_id = ?", (session_id,)
        ).fetchone()[0] == 0
        assert len(db.get_messages(session_id, include_inactive=True)) == 10
        assert len([m for m in db.get_messages(session_id, include_inactive=True) if not m.get("active", 1)]) == 8
    finally:
        db.close()

    reopened = SessionDB(db_path=db_path)
    try:
        row = reopened.get_session(session_id)
        assert row["title"] == "context-uplift-isolated"
        assert row["end_reason"] is None
        assert [message["content"] for message in reopened.get_messages_as_conversation(session_id)] == [
            "[CONTEXT COMPACTION] synthetic summary",
            "synthetic recent reply",
        ]
        hit = reopened._conn.execute(
            "SELECT 1 FROM messages_fts f JOIN messages m ON m.id = f.rowid "
            "WHERE m.session_id = ? AND messages_fts MATCH 'synthetic' "
            "AND m.active = 0 LIMIT 1",
            (session_id,),
        ).fetchone()
        assert hit is not None
    finally:
        reopened.close()


def test_gpt_56_native_compaction_and_900k_alias_are_supported():
    from types import SimpleNamespace

    from agent.model_metadata import get_model_context_length, is_codex_context_variant
    from agent.native_compaction import (
        is_direct_openai_route,
        is_native_compaction_model,
        native_compaction_context_management,
    )

    assert is_native_compaction_model("gpt-5.6-sol")
    assert is_native_compaction_model("gpt-5.6-sol-900k")
    assert is_direct_openai_route(
        "https://chatgpt.com/backend-api/codex", is_codex_backend=True
    )
    assert is_codex_context_variant("gpt-5.6-sol-900k")

    agent = SimpleNamespace(
        codex_responses_native_compaction=True,
        compression_enabled=True,
        compression_checkpoint_required=False,
        model="gpt-5.6-sol-900k",
        base_url="https://chatgpt.com/backend-api/codex",
        codex_responses_compact_threshold=4_000,
        context_compressor=SimpleNamespace(threshold_tokens=8_000),
    )
    assert native_compaction_context_management(agent, is_codex_backend=True) == [
        {"type": "compaction", "compact_threshold": 4_000}
    ]
    assert get_model_context_length("gpt-5.6-sol-900k", provider="openai-codex") > get_model_context_length(
        "gpt-5.6-sol", provider="openai-codex"
    )
