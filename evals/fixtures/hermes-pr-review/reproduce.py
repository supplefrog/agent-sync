"""Exercise LCM-X unload in a fresh Windows Hermes process."""

from contextlib import closing
import inspect
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4


ROOT = Path(os.environ.get("LCMX_PROOF_ROOT", Path(__file__).resolve().parent)).resolve()
HOST = (ROOT / os.environ.get("LCMX_HERMES_PROOF_SOURCE", "hermes-agent")).resolve()
LCM = ROOT / "lcm-x"
PLUGIN = "hermes-lcm-x"
PROMPT = "Record this synthetic unload test."
REPLY = "Synthetic unload test recorded."


def probe_delete(path):
    try:
        path.unlink()
        return {"deleted": True}
    except OSError as error:
        return {"deleted": False, "winerror": error.winerror, "errno": error.errno}


def block_network(*args, **kwargs):
    raise OSError("Network disabled for the unload reproduction")


def child(home, explicit_shutdown):
    sys.path.insert(0, str(HOST))
    socket.socket.connect = block_network
    socket.socket.connect_ex = block_network
    socket.create_connection = block_network
    socket.getaddrinfo = block_network

    import psutil
    from hermes_cli import plugins
    from hermes_cli.plugins_context import PluginContext
    from hermes_constants import get_hermes_home
    from hermes_state import SessionDB
    from run_agent import AIAgent

    assert Path(plugins.__file__).resolve().is_relative_to(HOST)
    assert Path(get_hermes_home()).resolve() == home
    assert callable(PluginContext.on_unload)
    plugins.discover_plugins()
    prototype = plugins.get_plugin_context_engine()
    assert prototype is not None and prototype.name == "lcm-x"
    assert Path(inspect.getfile(type(prototype))).resolve().is_relative_to(home / "plugins" / PLUGIN)

    state = SessionDB(db_path=home / "state.db")
    with patch("agent.process_bootstrap.OpenAI"):
        agent = AIAgent(
            api_key="unused", base_url="https://openrouter.ai/api/v1",
            model="test/model", quiet_mode=True, session_db=state,
            session_id="unload-probe", skip_context_files=True, skip_memory=True,
            platform="cli", enabled_toolsets=["todo"],
        )
    engine = agent.context_compressor
    assert engine is not prototype and engine.name == "lcm-x"
    agent.client, agent.tool_delay, agent.save_trajectories = MagicMock(), 0, False
    agent._compression_feasibility_checked = True
    engine.update_model("test/model", 64000, provider="openrouter")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=REPLY, tool_calls=None), finish_reason="stop")],
        model="test/model", usage=SimpleNamespace(prompt_tokens=100, completion_tokens=6, total_tokens=106),
    )
    agent.client.chat.completions.create.side_effect = [response]
    with patch("agent.title_generator.call_llm", return_value=response):
        turn = agent.run_conversation(user_message=PROMPT, conversation_history=[], task_id="unload-probe")
    assert turn.get("final_response") == REPLY, str(turn)
    assert agent.client.chat.completions.create.call_count == 1

    db = home / "lcm.db"
    assert db.is_file() and Path(engine._db_path).resolve() == db
    with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as reader:
        rows = reader.execute("SELECT role, content FROM messages ORDER BY store_id").fetchall()
    assert rows == [("user", PROMPT), ("assistant", REPLY)], rows

    def db_handles():
        return sorted({Path(f.path).name for f in psutil.Process().open_files()
                       if Path(f.path).parent == home and Path(f.path).name.startswith("lcm.db")})

    unlocked = home / "delete-control.txt"
    unlocked.touch()
    delete_control = probe_delete(unlocked)
    assert delete_control["deleted"], delete_control
    before = db_handles()
    manager = plugins.get_plugin_manager()
    assert manager.unload(PLUGIN), "Hermes did not unload the plugin"
    assert plugins.get_plugin_context_engine() is None, "LCM-X is still registered"
    assert not manager._hooks.get("post_llm_call"), "Plugin hook still registered"
    after = db_handles()
    immediate = probe_delete(db)
    delayed = None
    if not immediate["deleted"]:
        time.sleep(2)
        delayed = probe_delete(db)

    after_shutdown = None
    if explicit_shutdown and delayed and not delayed["deleted"]:
        # The same host stays alive. Only the retired agent clone is shut down.
        engine.shutdown()
        after_shutdown = {"handles": db_handles(), "delete": probe_delete(db)}
    print("REPRO " + json.dumps({
        "pid": os.getpid(), "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
        "platform": sys.getwindowsversion().build, "stored_roles": [role for role, _ in rows],
        "engine_slot_after_unload": None, "post_llm_hook_after_unload": False,
        "handles_before_unload": before, "handles_after_unload": after,
        "unlocked_file_control": delete_control, "delete_immediately": immediate,
        "delete_after_2s": delayed, "explicit_clone_shutdown": after_shutdown,
    }), flush=True)


def parent():
    assert sys.platform == "win32"
    fixed = "--expect-fixed" in sys.argv[1:]
    source = (ROOT / "pr-proof-final-2230" if "--pr-source" in sys.argv[1:]
              else ROOT / "verified-lcm-x-release" if "--verified-source" in sys.argv[1:]
              else ROOT / "lcm-x-unload" if fixed else LCM)
    source = (ROOT / os.environ.get("LCMX_PROOF_SOURCE", source)).resolve()
    assert source.is_relative_to(ROOT) and (source / "plugin.yaml").is_file(), source
    run = ROOT / f"run-{uuid4().hex[:8]}"
    run.mkdir()
    expect_bug = "--expect-bug" in sys.argv[1:]
    cases = ("normal-unload",) if fixed or expect_bug else ("normal-unload", "explicit-shutdown-control")
    for name in cases:
        home = run / name
        shutil.copytree(source, home / "plugins" / PLUGIN, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        (home / "config.yaml").write_text(
            "plugins:\n  enabled: [hermes-lcm-x]\ncontext:\n  engine: lcm-x\n", encoding="utf-8",
        )
        tmp = home / "tmp"
        tmp.mkdir()
        env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT")
               if key in os.environ}
        env.update({key: str(home) for key in ("HERMES_HOME", "USERPROFILE", "HOME", "APPDATA", "LOCALAPPDATA")})
        env.update(TEMP=str(tmp), TMP=str(tmp), HERMES_DISABLE_LAZY_INSTALLS="1", LCMX_PROOF_ROOT=str(ROOT),
                   OPENROUTER_API_KEY="unused", LCM_EMBEDDINGS_ENABLED="0",
                   LCMX_HERMES_PROOF_SOURCE=str(HOST))
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--child", str(home), name],
            cwd=HOST, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=100,
        )
        (run / (name + ".log")).write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
        if result.returncode != 0:
            raise RuntimeError(result.stdout[-4500:] + "\n" + result.stderr[-5500:])
        report = json.loads(next(line[6:] for line in result.stdout.splitlines() if line.startswith("REPRO ")))
        if (home / "lcm.db").exists():
            report["delete_after_host_exit"] = probe_delete(home / "lcm.db")
        print(json.dumps({"case": name, **report}), flush=True)
        if fixed:
            assert report["handles_after_unload"] == [] and report["delete_immediately"]["deleted"], report
        if expect_bug:
            assert report["delete_immediately"].get("winerror") == 32, report
            assert report["delete_after_2s"].get("winerror") == 32 and report["delete_after_host_exit"]["deleted"], report


if __name__ == "__main__":
    if sys.argv[1:2] == ["--child"]:
        child(Path(sys.argv[2]), sys.argv[3] == "explicit-shutdown-control")
    else:
        parent()
