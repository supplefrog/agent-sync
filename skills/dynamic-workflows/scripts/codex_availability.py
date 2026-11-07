"""Acquire and cache exact native Codex worker availability for V3 dispatch."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROUTE_ID = "codex-workflow-on-demand"
SHELL_TOOLS = {"exec_command", "shell_command", "functions.exec"}
SUPPORTED_TOOLS = SHELL_TOOLS | {"apply_patch"}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}")
THREAD_ID = re.compile(r"[a-f0-9-]{36}")
PROBE_TIMEOUT = 180


def check_request(request):
    required = request["requirements"]
    budget = request["budget"]
    verifier = request["verifier"]
    for field in ("model", "reasoning_effort"):
        if not isinstance(required[field], str) or not IDENTIFIER.fullmatch(required[field]):
            raise ValueError(f"Codex on-demand dispatch needs an exact {field}")
    unsupported = set(required["tools"]) - SUPPORTED_TOOLS
    if unsupported:
        raise ValueError(f"No safe native probe for Codex tools: {', '.join(sorted(unsupported))}")
    if "apply_patch" in required["tools"] and request["effects"] != "reversible":
        raise ValueError("The Codex apply_patch probe requires reversible effects")
    if (request["effects"] not in {"none", "reversible"}
            or (request["effects"] == "reversible" and not required["tools"])
            or request["failure_cost"] != "low"
            or verifier["kind"] != "deterministic" or not verifier["independent"]
            or verifier["coverage"] != "complete"
            or (required["tools"] and verifier["scope"] != "artifact-effects")):
        raise ValueError("Codex on-demand dispatch needs a low-risk task with complete independent deterministic verification")
    if (budget["allow_api_spend"] or budget["attempt_cap"] != 1 or budget["attempts_used"] != 0
            or budget["fallback_route_id"] is not None or budget["fallback_route_sha256"] is not None
            or budget.get("execution_request") or budget.get("evidence_trial")
            or budget["unknown_cost_policy"] != "explicit_preference"
            or budget["preference_order"] != [ROUTE_ID]):
        raise ValueError(f"Codex on-demand dispatch needs one subscription attempt with preference {ROUTE_ID}")
    pool = budget["quotas"].get("codex-main", {})
    if (pool.get("unit") != "percentage-points" or pool.get("remaining") is None
            or pool["remaining"] <= 0 or pool.get("reserve") != 0):
        raise ValueError("Codex on-demand dispatch needs current positive subscription quota and no protected reserve")


def native_cli():
    injected = os.environ.get("CODEX_APP_RUNTIME_CLI_PATH")
    executable = injected if injected and Path(injected).is_file() else shutil.which("codex")
    if executable is None:
        raise ValueError("No native Codex CLI executable was found")
    return str(Path(executable).resolve())


def cli(executable, *args, timeout=30, **kwargs):
    try:
        return subprocess.run([executable, *args], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Codex native availability check timed out") from exc
    except OSError as exc:
        raise ValueError("Could not start the native Codex availability check") from exc


def profile_generation(home):
    # Read file identity only. Neither credentials nor configuration enter the proof.
    markers = {}
    for name in ("config.toml", "auth.json"):
        path = home / name
        if path.is_file():
            stat = path.stat()
            markers[name] = [stat.st_ino, stat.st_size, stat.st_mtime_ns]
    if "auth.json" not in markers:
        # Keyring-backed logins lack a reusable on-disk credential generation.
        markers["session"] = os.environ.get("CODEX_THREAD_ID") or secrets.token_hex(16)
    return {"home": str(home), "markers": markers}


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def payloads(rows, event):
    return [row["payload"] for row in rows if row.get("payload", {}).get("type") == event]


def session_file(home, thread_id):
    if not isinstance(thread_id, str) or not THREAD_ID.fullmatch(thread_id):
        raise ValueError("Codex native session identity is invalid")
    matches = list((home / "sessions").rglob(f"*{thread_id}.jsonl"))
    if len(matches) != 1:
        raise ValueError("Codex native session trace is unavailable")
    return matches[0]


def dispatch_contract():
    scripts = Path(__file__).resolve()
    path = scripts.parents[3] / "surfaces/core.md"
    if not path.is_file():
        fleet = json.loads((scripts.parents[2] / ".agent-signal-fleet.json").read_bytes())
        snapshot = Path(fleet["source_snapshot"])
        if snapshot.parts[-2:] != ("render", "fleet"):
            raise ValueError("Cannot resolve the published Agent Sync dispatch contract")
        path = snapshot.parents[1] / "surfaces/core.md"
    contract = path.read_text(encoding="utf-8")
    return contract.split("# Execution contract", 1)[1].split("# Standing instructions", 1)[0]


def completed_items(rows, item_type):
    items = (event.get("item", {}) for event in payloads(rows, "item_completed"))
    return [item for item in items if item.get("type") == item_type]


def child_activity(rows):
    activity = completed_items(rows, "SubAgentActivity")
    starts = [item for item in activity if item.get("kind") == "started"]
    stops = [item for item in activity if item.get("kind") == "completed"]
    if (len(starts) != 1 or len(stops) != 1
            or starts[0].get("agent_thread_id") != stops[0].get("agent_thread_id")):
        raise ValueError("Codex native controller has no unique completed child")
    return starts[0]


def probe_recipe(scope):
    tools = set(scope["tools"])
    commands = []
    if tools & SHELL_TOOLS:
        commands.append("Get-Content -Raw -LiteralPath challenge.txt" if os.name == "nt" else "cat -- challenge.txt")
        if scope["effects"] == "reversible":
            commands.append("Set-Content -LiteralPath shell.txt -NoNewline -Value shell-ok" if os.name == "nt"
                            else "printf %s shell-ok > shell.txt")
    patch = "*** Begin Patch\n*** Update File: patch.txt\n@@\n-before\n+patch-ok\n*** End Patch"
    wrappers = {
        f"const r = await tools.exec_command({{cmd: {json.dumps(command)}}}); text(r.output);": "exec_command"
        for command in commands
    }
    if "apply_patch" in tools:
        wrappers[f"text(await tools.apply_patch({json.dumps(patch)}));"] = "apply_patch"
    return commands, patch, wrappers


def probe_worker(executable, home, scope, scratch):
    token = secrets.token_hex(16)
    tools = set(scope["tools"])
    shell_tools = sorted(tools & SHELL_TOOLS)
    shell = bool(shell_tools)
    patch = "apply_patch" in tools
    writes = scope["effects"] == "reversible"
    commands, patch_text, wrappers = probe_recipe(scope)
    instructions = []
    if shell:
        (scratch / "challenge.txt").write_text(token, encoding="ascii")
        instructions.append(f"Run these exact shell commands, once each, in the current directory: {commands!r}.")
    else:
        instructions.append(f"Use the text token {token!r}.")
    if patch:
        (scratch / "patch.txt").write_bytes(b"before\n")
        instructions.append(f"Use apply_patch with exactly this patch:\n{patch_text}\n")
    if wrappers:
        instructions.append(
            "For any call made through functions.exec, copy the corresponding code exactly, "
            "one separate call per line, without any extra code:\n" + "\n".join(wrappers) + "\n"
        )
    if "functions.exec" in tools:
        instructions.append("Use functions.exec to invoke the shell tool.")
    if shell_tools:
        instructions.append(f"The required shell tool names are {', '.join(shell_tools)}.")
    instructions.append(
        "Return only the token. Use only the specified tools and files with default sandbox permissions. "
        "Stop if the sandbox denies access. Do not request approval, delegate, or access the network."
    )
    child_prompt = " ".join(instructions)
    model = scope["model"]
    effort = scope["reasoning_effort"]
    prompt = (
        "The user authorizes a single native Codex subagent to verify an exact workflow route. "
        "The invoking parent resolved and read the Agent Sync dispatch contract before selecting this test. "
        "The applicable contract is included below so you can read it directly, without a tool call. "
        "The exact requested tuple below takes precedence over its defaults.\n"
        f"{dispatch_contract()}\n"
        f"Spawn exactly one worker named availability_probe in fresh context with explicit model {model!r} "
        f"and explicit reasoning effort {effort!r}. Pass this worker prompt verbatim:\n{child_prompt}\n"
        "Wait for the child to finish. Return a brief status and exit. Do not perform the worker task, "
        "start other workers, use shell tools yourself, modify settings, or substitute models or effort."
    )
    config_path = home / "config.toml"
    config = tomllib.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    controller = []
    if isinstance(config.get("model"), str):
        controller += ["-m", config["model"]]
    if isinstance(config.get("model_reasoning_effort"), str):
        controller += ["-c", f"model_reasoning_effort={json.dumps(config['model_reasoning_effort'])}"]
    sandbox_mode = config.get("windows", {}).get("sandbox")
    if sandbox_mode in {"unelevated", "elevated"}:
        controller += ["-c", f"windows.sandbox={json.dumps(sandbox_mode)}"]
    result = cli(
        executable, "-a", "never", "exec", "--ignore-user-config", "--disable", "apps",
        "--json", "--skip-git-repo-check", "-C", str(scratch),
        "--sandbox", "workspace-write" if writes else "read-only",
        "-c", 'model_provider="openai"', "-c", 'web_search="disabled"',
        "-c", "project_doc_max_bytes=0", *controller, "-", timeout=PROBE_TIMEOUT, input=prompt,
    )
    if result.returncode:
        raise ValueError("Codex native controller failed; the requested route was not verified")
    events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    starts = [event.get("thread_id") for event in events if event.get("type") == "thread.started"]
    if (len(starts) != 1 or not isinstance(starts[0], str) or not THREAD_ID.fullmatch(starts[0])
            or sum(event.get("type") == "turn.completed" for event in events) != 1
            or any(event.get("type") in {"error", "turn.failed"} for event in events)):
        raise ValueError("Codex native controller did not supply a clean terminal trace")
    started = child_activity(read_rows(session_file(home, starts[0])))
    identity = {"controller": starts[0], "child": started["agent_thread_id"]}
    return identity, native_observation(home, identity, scope, scratch, token)


def native_observation(home, identity, scope, scratch=None, token=None):
    parent_rows = read_rows(session_file(home, identity["controller"]))
    child_rows = read_rows(session_file(home, identity["child"]))
    parent = parent_rows[0]["payload"]
    child = child_rows[0]["payload"]
    source = child.get("source")
    lineage = source.get("subagent", {}).get("thread_spawn", {}) if isinstance(source, dict) else {}
    if (parent.get("id") != identity["controller"] or child.get("id") != identity["child"]
            or lineage.get("parent_thread_id") != identity["controller"]):
        raise ValueError("Codex native child does not belong to the exact controller")
    native_scratch = Path(parent["cwd"])
    if not native_scratch.name.startswith("probe-") or (scratch is not None and native_scratch != scratch):
        raise ValueError("Codex native controller did not run in its scratch workspace")
    turns = [row["payload"] for row in parent_rows if row.get("type") == "turn_context"]
    if len(turns) != 1 or turns[0].get("approval_policy") != "never":
        raise ValueError("Codex probe controller did not use the restricted approval policy")
    terminal = [row["timestamp"] for row in parent_rows if row.get("payload", {}).get("type") == "task_complete"]
    if len(terminal) != 1:
        raise ValueError("Codex probe controller has no unique terminal event")
    completed_at = datetime.fromisoformat(terminal[0]).astimezone(timezone.utc)
    parent_calls = payloads(parent_rows, "function_call") + payloads(parent_rows, "custom_tool_call")
    if any(call.get("name") not in {"spawn_agent", "wait", "wait_agent", "list_agents", "close_agent"}
           for call in parent_calls):
        raise ValueError("Codex probe controller invoked an unexpected tool")
    launches = [call for call in parent_calls if call.get("name") == "spawn_agent"]
    if len(launches) != 1:
        raise ValueError("Codex availability requires one exact native worker launch")
    started = child_activity(parent_rows)
    launch = json.loads(launches[0]["arguments"])
    route = (scope["model"], scope["reasoning_effort"])
    if (started.get("id") != launches[0].get("call_id")
            or started.get("agent_thread_id") != identity["child"]
            or (started.get("model"), started.get("reasoning_effort")) != route
            or (launch.get("model"), launch.get("reasoning_effort")) != route
            or not (launch.get("fork_turns") == "none" or launch.get("fork_context") is False)):
        raise ValueError("Codex availability probe launched with different settings or inherited context")
    windows = verify_child(child_rows, scope, native_scratch, token)
    return completed_at, windows


def verify_child(rows, scope, scratch, token):
    metadata = [row["payload"] for row in rows if row.get("type") == "session_meta"]
    contexts = [row["payload"] for row in rows if row.get("type") == "turn_context"]
    expected = (scope["model"], scope["reasoning_effort"])
    if (len(metadata) != 1 or metadata[0].get("model_provider") != "openai"
            or metadata[0].get("cli_version") != scope["version"] or not contexts
            or any((context.get("model"), context.get("effort")) != expected
                   or context.get("approval_policy") != "never" for context in contexts)):
        raise ValueError("Codex child provider, model, effort, or runtime did not match the request")
    completed = payloads(rows, "task_complete")
    answer = str(completed[0].get("last_agent_message", "")).strip() if len(completed) == 1 else ""
    if not re.fullmatch(r"[a-f0-9]{32}", answer) or (token is not None and answer != token):
        raise ValueError("Codex child did not complete the independent tool fixture")
    windows = [event.get("model_context_window") for event in payloads(rows, "task_started")]
    if not windows or any(type(window) is not int or window <= 0 for window in windows):
        raise ValueError("Codex child did not report its context limit")
    calls = payloads(rows, "function_call") + payloads(rows, "custom_tool_call")
    expected_commands, patch_text, wrappers = probe_recipe(scope)
    shell_names = set()
    patch_count = 0
    used_wrappers = set()
    for call in calls:
        name = call.get("name")
        raw = call.get("input", call.get("arguments", "")).strip()
        if "require_escalated" in raw:
            raise ValueError("Codex probe requested elevated permissions")
        if name == "exec" and raw in wrappers and raw not in used_wrappers:
            used_wrappers.add(raw)
            if wrappers[raw] == "exec_command":
                shell_names.update({"functions.exec", "exec_command"})
            else:
                patch_count += 1
        elif name in {"exec_command", "shell_command"}:
            arguments = json.loads(raw)
            if arguments.get("cmd", arguments.get("command")) not in expected_commands:
                raise ValueError("Codex probe did not run the prescribed shell command")
            shell_names.add(name)
        elif name == "apply_patch" and raw == patch_text:
            patch_count += 1
        else:
            raise ValueError("Codex probe invoked an unexpected tool or code payload")
    commands = completed_items(rows, "CommandExecution")
    tools = set(scope["tools"])
    if not (tools & SHELL_TOOLS).issubset(shell_names):
        raise ValueError("Codex child did not exercise the requested shell tool names")
    if (len(commands) != len(expected_commands)
            or any(item.get("exit_code") != 0 for item in commands)
            or any(not isinstance(item.get("command"), list) or not item["command"]
                   or item["command"][-1].strip() != expected
                   for item, expected in zip(commands, expected_commands))
            or (expected_commands and commands[0].get("aggregated_output", "").strip() != answer)):
        raise ValueError("Codex native shell events did not match the fixture")
    if token is not None and expected_commands and (scratch / "challenge.txt").read_text(encoding="ascii") != token:
        raise ValueError("Codex probe changed the read fixture")
    if token is not None and expected_commands and scope["effects"] == "reversible":
        shell_file = scratch / "shell.txt"
        if not shell_file.is_file() or shell_file.read_bytes() != b"shell-ok":
            raise ValueError("Codex shell tool did not produce the expected reversible edit")
    if patch_count != int("apply_patch" in tools):
        raise ValueError("Codex apply_patch tool did not match the requested scope")
    if patch_count:
        changes = completed_items(rows, "FileChange")
        expected_edit = {"type": "update", "unified_diff": "@@ -1 +1 @@\n-before\n+patch-ok\n", "move_path": None}
        if (len(changes) != 1 or changes[0].get("status") != "completed"
                or {Path(path): edit for path, edit in changes[0].get("changes", {}).items()}
                != {scratch / "patch.txt": expected_edit}
                or (token is not None and (scratch / "patch.txt").read_bytes().splitlines() != [b"patch-ok"])):
            raise ValueError("Codex apply_patch tool did not produce the expected edit")
    if token is not None and any(path.name not in {"challenge.txt", "patch.txt", "shell.txt"} for path in scratch.iterdir()):
        raise ValueError("Codex availability probe produced unexpected scratch files")
    return min(windows)


def availability(request, cache, execution_context, state):
    check_request(request)
    executable = native_cli()
    version = cli(executable, "--version")
    login = cli(executable, "login", "status")
    if version.returncode or login.returncode or "Logged in using ChatGPT" not in (login.stdout + login.stderr):
        raise ValueError("Codex availability requires a verified native ChatGPT subscription login")
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").resolve()
    required = request["requirements"]
    scope = {
        "version": version.stdout.strip().split()[-1],
        "executable": executable,
        "profile": state.receipt_digest(profile_generation(home)),
        "execution_context": state.receipt_digest(execution_context),
        "model": required["model"],
        "reasoning_effort": required["reasoning_effort"],
        "tools": sorted(required["tools"]),
        "effects": request["effects"],
        "probe_contract": state.receipt_digest(Path(__file__).read_text(encoding="utf-8")),
    }
    key = state.receipt_digest(scope)
    entry = cache / f"{key}.json"
    def proof_for(observation):
        observed, context_tokens = observation
        return {
            **{field: scope[field] for field in ("version", "model", "reasoning_effort", "tools", "effects", "probe_contract")},
            "scope_sha256": key, "context_tokens": context_tokens, "observed_at": observed.isoformat(),
            "valid_until": (observed + timedelta(hours=24)).isoformat(),
        }

    with state._exclusive_lock(cache / f"{key}.lock", "Codex availability", timeout=PROBE_TIMEOUT + 45):
        if entry.is_file():
            try:
                record = state.load_json(entry)
                proof = record["proof"]
                if (proof["scope_sha256"] == key
                        and datetime.fromisoformat(proof["observed_at"]) <= datetime.now(timezone.utc)
                        < datetime.fromisoformat(proof["valid_until"])
                        and proof == proof_for(native_observation(home, record["native_session"], scope))):
                    return proof
            except (ValueError, KeyError, TypeError, AttributeError, OSError):
                pass
        # Use inherited workspace permissions. Windows sandbox users cannot read
        # private TemporaryDirectory fixtures, even inside the permitted root.
        scratch = cache / f"probe-{secrets.token_hex(16)}"
        scratch.mkdir()
        identity, observation = probe_worker(executable, home, scope, scratch)
        for name in ("challenge.txt", "shell.txt", "patch.txt"):
            (scratch / name).unlink(missing_ok=True)
        scratch.rmdir()
        proof = proof_for(observation)
        state.atomic_json(entry, {"proof": proof, "native_session": identity})
        return proof
