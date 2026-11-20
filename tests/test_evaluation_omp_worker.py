"""Check the OMP evaluator's route and credential boundaries without inference."""
import copy
import json
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fixture_workspace import configure

configure()
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import evaluation_omp_worker as omp


def test_report_rejects_omp_route_and_terminal_contradictions():
    requested = {"model": "gpt-6.2-sol", "provider": "openai-codex",
                 "reasoning": "medium", "tool_policy": "none"}
    state = {
        "model": "gpt-6.2-sol", "provider": "openai-codex", "reasoning": "medium",
        "session_id": "test-native-session", "session_persisted": False, "tools": [],
        "message_count": 0, "settled": True, "pending_work": False, "goal": None,
        "system_prompt": [
            "Follow the supplied evaluation task. Return only the requested answer.",
            "<project-context>\n<workstation>\n- OS: win32 10.0.22631\n- Arch: x64\n"
            "- Model: openai-codex/gpt-6.2-sol\n</workstation>\n</project-context>\n\n"
            "<critical>\n- Each response MUST advance the task; completion only stopping condition.\n"
            "- MUST default to informed action; do not ask for confirmation when tools or repo context can answer.\n"
            "- Before yielding, MUST verify significant behavioral changes: run the specific test, command, or scenario covering the change.\n"
            "</critical>",
        ],
    }
    good = {"before": state, "after": {**state, "message_count": 2},
            "events": {"starts": 1, "ends": 1, "tools": 0, "settled": 1},
            "result": {"status": "completed", "agent_invoked": True, "model": requested["model"],
                       "provider": requested["provider"], "stop_reason": "stop", "output": "42"}}
    assert omp.evaluate_evidence(good, requested)["route_attestation"]["ok"]
    for group, key, value in (
        ("before", "system_prompt", state["system_prompt"] + ["personal context"]),
        ("before", "tools", [{"name": "bash"}]),
        ("after", "reasoning", "high"),
        ("after", "session_id", "other"),
        ("after", "session_persisted", True),
        ("events", "tools", 1),
        ("events", "starts", 2),
        ("result", "stop_reason", "error"),
        ("result", "model", "different"),
    ):
        evidence = copy.deepcopy(good)
        evidence[group][key] = value
        assert not omp.evaluate_evidence(evidence, requested)["route_attestation"]["ok"]


def test_native_import_only_receives_selected_access(tmp_path):
    home = tmp_path / "home"
    agent = home / ".omp" / "agent"
    agent.mkdir(parents=True)
    deadline = int((time.time() + 3600) * 1000)
    with closing(sqlite3.connect(agent / "agent.db")) as store, store:
        store.execute("CREATE TABLE auth_credentials (provider, credential_type, disabled_cause, data)")
        store.executemany("INSERT INTO auth_credentials VALUES (?, ?, ?, ?)", [
            ("openai-codex", "oauth", None, json.dumps({
                "access": "fake-live-access", "refresh": "fake-held-refresh", "expires": deadline,
            })),
            ("different-provider", "oauth", None, json.dumps({
                "access": "fake-unrelated-access", "expires": deadline,
            })),
        ])
    with patch.object(omp.subprocess, "run") as launch:
        launch.return_value.returncode = 0
        omp.stage_omp_auth("omp", {"HOME": str(home)}, {}, tmp_path, "openai-codex", 5)
        request = json.loads(launch.call_args.kwargs["input"])
        assert request == {"version": 1, "credentials": [{
            "provider": "openai-codex",
            "credential": {"type": "oauth", "access": "fake-live-access", "refresh": "", "expires": deadline},
        }]}
        launch.reset_mock()
        for selectors in ({"PI_PROFILE": "other"}, {"PI_CONFIG_DIR": "other"}):
            try:
                omp.stage_omp_auth("omp", {"HOME": str(home), **selectors}, {}, tmp_path, "openai-codex", 5)
            except ValueError as exc:
                assert "local credential store" in str(exc)
            else:
                raise AssertionError("an unsupported selector did not block credential projection")
        (agent / ".env").write_text("export PI_CODING_AGENT_DIR=other\n", encoding="utf-8")
        try:
            omp.stage_omp_auth("omp", {"HOME": str(home)}, {}, tmp_path, "openai-codex", 5)
        except ValueError as exc:
            assert "dotenv" in str(exc)
        else:
            raise AssertionError("a dotenv selector did not block credential projection")
        launch.assert_not_called()
