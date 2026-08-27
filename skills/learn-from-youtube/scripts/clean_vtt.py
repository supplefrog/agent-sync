#!/usr/bin/env python3
"""Normalize WebVTT captions into timestamped text without rolling duplicates."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

TIMING_RE = re.compile(r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})[.,](?P<ms>\d{3})\s+-->")
INLINE_TS_RE = re.compile(r"<\d{2}:\d{2}:\d{2}[.,]\d{3}>")
TAG_RE = re.compile(r"<[^>]+>")


def stamp(total_seconds: float) -> str:
    seconds = int(total_seconds)
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def clean(text: str) -> str:
    text = INLINE_TS_RE.sub("", text)
    text = TAG_RE.sub("", text)
    return " ".join(html.unescape(text).replace("\u200b", "").split())


def overlap_trim(previous_words: list[str], words: list[str]) -> list[str]:
    maximum = min(40, len(previous_words), len(words))
    for size in range(maximum, 0, -1):
        if previous_words[-size:] == words[:size]:
            return words[size:]
    return words


def parse_vtt(path: Path) -> list[dict[str, object]]:
    blocks = re.split(r"\r?\n\s*\r?\n", path.read_text(encoding="utf-8-sig"))
    segments: list[dict[str, object]] = []
    emitted_words: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        match = TIMING_RE.search(lines[timing_index])
        if not match:
            continue
        seconds = int(match["h"]) * 3600 + int(match["m"]) * 60 + int(match["s"]) + int(match["ms"]) / 1000
        payload = lines[timing_index + 1 :]
        progressive = [line for line in payload if "<c" in line or INLINE_TS_RE.search(line)]
        candidate = clean(" ".join(progressive or payload))
        if not candidate:
            continue
        new_words = overlap_trim(emitted_words, candidate.split())
        if not new_words:
            continue
        text = " ".join(new_words)
        emitted_words.extend(new_words)
        segments.append({"seconds": seconds, "timestamp": stamp(seconds), "text": text})
    return segments


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("vtt", type=Path)
    parser.add_argument("--format", choices=("markdown", "text", "json"), default="markdown")
    args = parser.parse_args()
    segments = parse_vtt(args.vtt)
    if args.format == "json":
        print(json.dumps(segments, ensure_ascii=False, indent=2))
    elif args.format == "text":
        print(" ".join(str(segment["text"]) for segment in segments))
    else:
        for segment in segments:
            print(f"[{segment['timestamp']}] {segment['text']}")


if __name__ == "__main__":
    main()
