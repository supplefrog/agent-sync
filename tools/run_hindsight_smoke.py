from __future__ import annotations

import argparse
import json
import sys
import time

from plugins.memory.hindsight import HindsightMemoryProvider

BANK_ID = "agent-shared-memory-eval"
EXACT = "Synthetic subject Orion's vault code is 4827-Zeta."
SEMANTIC = "Synthetic user preference: status updates should be brief, factual, and lead with the result."
OLD = "Synthetic Project Atlas deployment window is Tuesday at 09:00 UTC."
NEW = "Synthetic Project Atlas deployment window moved to Thursday at 14:00 UTC; Tuesday is obsolete."
SOURCE = "agent-signal-hindsight-eval"


def elapsed(call):
    started = time.perf_counter()
    value = call()
    return value, round((time.perf_counter() - started) * 1000, 1)


def tool_result(response: str) -> tuple[str, int]:
    payload = json.loads(response)
    if "error" in payload:
        raise RuntimeError(f"recall failed: {payload}")
    text = str(payload.get("result", ""))
    if text == "No relevant memories found.":
        return text, 0
    return text, len([line for line in text.splitlines() if line.strip()])


def make_provider() -> HindsightMemoryProvider:
    provider = HindsightMemoryProvider()
    provider.initialize("hindsight-eval", platform="cli", agent_identity="default")
    if provider._mode != "local_embedded":
        raise RuntimeError(f"unexpected Hindsight mode: {provider._mode}")
    provider._bank_id = BANK_ID
    expected = {
        "memory_mode": "tools",
        "auto_recall": False,
        "auto_retain": False,
        "budget": "low",
        "recall_max_tokens": 1024,
        "recall_types": ["observation"],
    }
    actual = {
        "memory_mode": provider._memory_mode,
        "auto_recall": provider._auto_recall,
        "auto_retain": provider._auto_retain,
        "budget": provider._budget,
        "recall_max_tokens": provider._recall_max_tokens,
        "recall_types": provider._recall_types,
    }
    if actual != expected:
        raise RuntimeError(f"unexpected production config: {actual}")
    return provider


def retain(provider: HindsightMemoryProvider, content: str, context: str) -> float:
    response, latency = elapsed(
        lambda: json.loads(
            provider.handle_tool_call(
                "hindsight_retain",
                {"content": content, "context": context, "tags": ["synthetic-eval"]},
            )
        )
    )
    if "error" in response or "successfully" not in str(response.get("result", "")).lower():
        raise RuntimeError(f"retain failed: {response}")
    return latency


def recall(provider: HindsightMemoryProvider, query: str):
    response, latency = elapsed(
        lambda: provider.handle_tool_call("hindsight_recall", {"query": query})
    )
    text, count = tool_result(response)
    return text, count, latency


def delete_bank(provider: HindsightMemoryProvider) -> tuple[bool, float]:
    try:
        _, latency = elapsed(
            lambda: provider._run_hindsight_operation(
                lambda client: client.adelete_bank(BANK_ID)
            )
        )
        return True, latency
    except Exception as exc:
        text = str(exc).lower()
        if "404" in text or "not found" in text:
            return False, 0.0
        raise


def seed() -> dict[str, Any]:
    provider = make_provider()
    try:
        client, startup_ms = elapsed(provider._get_client)
        version, version_ms = elapsed(lambda: provider._run_sync(client.aget_version()))
        delete_bank(provider)
        retain_ms = [
            retain(provider, EXACT, "synthetic exact recall probe"),
            retain(provider, SEMANTIC, "synthetic semantic recall probe"),
            retain(provider, OLD, "synthetic contradiction probe before update"),
            retain(provider, NEW, "synthetic contradiction probe corrected update"),
        ]
        return {
            "phase": "seed",
            "service_started": True,
            "service_url": str(getattr(client, "url", "")),
            "version": str(version),
            "startup_ms": startup_ms,
            "version_ms": version_ms,
            "retain_ms": retain_ms,
            "seeded": 4,
        }
    finally:
        provider.shutdown()


def verify() -> dict[str, Any]:
    provider = make_provider()
    try:
        client, startup_ms = elapsed(provider._get_client)
        exact_text, exact_count, exact_ms = recall(provider, "What is Orion's vault code?")
        semantic_text, semantic_count, semantic_ms = recall(provider, "How should progress updates be written?")
        contradiction_text, contradiction_count, contradiction_ms = recall(provider, "When is Project Atlas deployed now?")
        irrelevant_text, irrelevant_count, irrelevant_ms = recall(provider, "What is the tax filing deadline on Mars?")

        exact_text = exact_text.lower()
        semantic_text = semantic_text.lower()
        contradiction_text = contradiction_text.lower()
        provenance = exact_text

        checks = {
            "exact_recall": "4827-zeta" in exact_text,
            "semantic_recall": "brief" in semantic_text and ("status" in semantic_text or "result" in semantic_text),
            "contradictory_update": (
                "thursday" in contradiction_text
                and "14:00" in contradiction_text
                and "tuesday at 09:00" not in contradiction_text
            ),
            "irrelevant_query_silence": irrelevant_count == 0,
            "provenance": SOURCE in provenance or "synthetic-eval" in provenance,
            "restart_persistence": "4827-zeta" in exact_text,
        }
        return {
            "phase": "verify",
            "service_started": True,
            "service_url": str(getattr(client, "url", "")),
            "startup_ms": startup_ms,
            "latency_ms": {
                "exact": exact_ms,
                "semantic": semantic_ms,
                "contradiction": contradiction_ms,
                "irrelevant": irrelevant_ms,
            },
            "result_counts": {
                "exact": exact_count,
                "semantic": semantic_count,
                "contradiction": contradiction_count,
                "irrelevant": irrelevant_count,
            },
            "obsolete_contradiction_returned": "tuesday at 09:00" in contradiction_text,
            "irrelevant_response_was_empty": irrelevant_count == 0,
            "checks": checks,
            "passed": all(checks.values()),
        }
    finally:
        provider.shutdown()


def cleanup() -> dict[str, Any]:
    provider = make_provider()
    try:
        deleted, delete_ms = delete_bank(provider)
        _, count, recall_ms = recall(provider, "What is Orion's vault code?")
        empty = count == 0
        return {
            "phase": "cleanup",
            "bank_deleted": deleted,
            "delete_ms": delete_ms,
            "post_delete_recall_ms": recall_ms,
            "post_delete_empty": empty,
            "passed": empty,
        }
    finally:
        provider.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("seed", "verify", "cleanup"))
    args = parser.parse_args()
    try:
        result = {"seed": seed, "verify": verify, "cleanup": cleanup}[args.phase]()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("passed", True) else 1
    except Exception as exc:
        print(json.dumps({"phase": args.phase, "passed": False, "error_type": type(exc).__name__, "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())
