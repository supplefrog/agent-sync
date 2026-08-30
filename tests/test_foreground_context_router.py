from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE = Path(__file__).parents[1] / "integrations" / "hermes" / "foreground-context-router" / "dashboard" / "plugin_api.py"


def load_module():
    spec = importlib.util.spec_from_file_location("foreground_context_router_api", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_normalize_decision_accepts_explicit_extended_new_topic():
    api = load_module()
    result = api.normalize_decision(
        {"context_need": "extended", "topic_relation": "new", "confidence": 0.91, "title": "Repository audit"}
    )
    assert result == {
        "context_need": "extended",
        "topic_relation": "new",
        "confidence": 0.91,
        "title": "Repository audit",
        "reason": "",
    }


def test_normalize_decision_fails_closed_on_ambiguous_or_invalid_output():
    api = load_module()
    assert api.normalize_decision({"context_need": "huge"}) == api.SAFE_DECISION
    assert api.parse_model_output("not json") == api.SAFE_DECISION
    assert api.parse_model_output('{"context_need":"extended","topic_relation":"same","confidence":0.4}') == api.SAFE_DECISION


def test_classify_uses_context_routing_auxiliary_task(monkeypatch):
    api = load_module()
    calls = []

    def fake_call_llm(**kwargs):
        calls.append(kwargs)
        return response(
            '```json\n{"context_need":"extended","topic_relation":"same","confidence":0.88,"title":"Broad refactor","reason":"many files"}\n```'
        )

    monkeypatch.setattr(api, "call_llm", fake_call_llm)
    result = api.classify_request(
        text="Refactor the repository-wide authentication layer",
        current_mode="normal",
        recent_messages=[{"role": "user", "content": "We need to replace auth."}],
    )

    assert result["context_need"] == "extended"
    assert result["topic_relation"] == "same"
    assert calls[0]["task"] == "foreground_context_routing"
    assert calls[0]["max_tokens"] <= 300


def test_classify_failure_returns_safe_stay_decision(monkeypatch):
    api = load_module()

    def fail(**_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(api, "call_llm", fail)
    assert api.classify_request("audit everything", "normal", []) == api.SAFE_DECISION


def test_http_route_offloads_blocking_model_call(monkeypatch):
    api = load_module()
    calls = []

    async def fake_to_thread(function, **kwargs):
        calls.append((function, kwargs))
        return {"context_need": "normal", "topic_relation": "same", "confidence": 0.9}

    monkeypatch.setattr(api.asyncio, "to_thread", fake_to_thread)
    result = asyncio.run(api.classify({"text": "hello", "current_mode": "normal", "recent_messages": []}))

    assert result["context_need"] == "normal"
    assert calls[0][0] is api.classify_request
    assert calls[0][1]["text"] == "hello"
