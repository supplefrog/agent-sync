"""Foreground context routing classifier for Hermes Desktop."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

try:
    from fastapi import APIRouter
except Exception:  # pragma: no cover - only for isolated source tests
    class APIRouter:  # type: ignore[no-redef]
        def post(self, *_args, **_kwargs):
            return lambda fn: fn

from agent.auxiliary_client import call_llm

router = APIRouter()
logger = logging.getLogger(__name__)

TASK_KEY = "foreground_context_routing"
MIN_CONFIDENCE = 0.75
SAFE_DECISION = {
    "context_need": "normal",
    "topic_relation": "same",
    "confidence": 0.0,
    "title": "",
    "reason": "",
}

_CLASSIFIER_PROMPT = """You route a user message between fixed-context Hermes conversations.
Return exactly one JSON object with:
- context_need: "normal" or "extended"
- topic_relation: "same" or "new"
- confidence: number from 0 to 1
- title: concise destination title, at most 60 characters
- reason: at most 120 characters

Use EXTENDED only when the work will likely need a very large amount of evidence or state to remain simultaneously available: broad repository audits/refactors, many documents, prolonged debugging across many files, or similarly context-heavy work. Difficulty alone is not enough. Proofs, advice, ordinary chat, focused fixes, bounded research, and routine coding are NORMAL.

Topic relation is SAME for follow-ups, expansions, corrections, or ambiguous continuity. Use NEW only when the message is clearly unrelated to the recent conversation. If uncertain, lower confidence; do not force a switch.

Current conversation mode: {current_mode}
Recent conversation (bounded, newest last):
{recent}

New user message:
{text}
"""


def normalize_decision(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return dict(SAFE_DECISION)
    need = value.get("context_need")
    relation = value.get("topic_relation")
    try:
        confidence = float(value.get("confidence", 0.0))
    except (TypeError, ValueError):
        return dict(SAFE_DECISION)
    if need not in {"normal", "extended"} or relation not in {"same", "new"}:
        return dict(SAFE_DECISION)
    if not 0.0 <= confidence <= 1.0 or confidence < MIN_CONFIDENCE:
        return dict(SAFE_DECISION)
    return {
        "context_need": need,
        "topic_relation": relation,
        "confidence": confidence,
        "title": str(value.get("title") or "").strip()[:60],
        "reason": str(value.get("reason") or "").strip()[:120],
    }


def parse_model_output(text: str) -> dict[str, Any]:
    if not isinstance(text, str):
        return dict(SAFE_DECISION)
    body = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", body, re.S | re.I)
    if fenced:
        body = fenced.group(1)
    else:
        start, end = body.find("{"), body.rfind("}")
        if start < 0 or end < start:
            return dict(SAFE_DECISION)
        body = body[start : end + 1]
    try:
        return normalize_decision(json.loads(body))
    except (json.JSONDecodeError, TypeError, ValueError):
        return dict(SAFE_DECISION)


def _recent_text(messages: Any, max_chars: int = 12000) -> str:
    if not isinstance(messages, list):
        return "(none)"
    lines: list[str] = []
    used = 0
    for message in reversed(messages[-12:]):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip().lower()
        content = message.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        content = content.strip()[:4000]
        if not content:
            continue
        line = f"{role}: {content}"
        if used + len(line) > max_chars:
            break
        lines.append(line)
        used += len(line)
    return "\n".join(reversed(lines)) or "(none)"


def classify_request(text: str, current_mode: str, recent_messages: Any) -> dict[str, Any]:
    prompt = _CLASSIFIER_PROMPT.format(
        current_mode="extended" if current_mode == "extended" else "normal",
        recent=_recent_text(recent_messages),
        text=str(text or "").strip()[:16000],
    )
    try:
        response = call_llm(
            messages=[{"role": "user", "content": prompt}],
            task=TASK_KEY,
            max_tokens=240,
            timeout=30,
        )
        content = response.choices[0].message.content if hasattr(response, "choices") else str(response)
        return parse_model_output(content or "")
    except Exception as exc:
        logger.warning("foreground context classification failed: %s", exc)
        return dict(SAFE_DECISION)


@router.post("/classify")
async def classify(body: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(
        classify_request,
        text=str(body.get("text") or ""),
        current_mode=str(body.get("current_mode") or "normal"),
        recent_messages=body.get("recent_messages") or [],
    )
