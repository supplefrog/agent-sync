"""Availability and launch receipts for the T3 and Paseo worker dispatchers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


SURFACES = {"t3-workflow": "t3", "paseo-workflow": "paseo"}
WINDOW = timedelta(days=1)
CONTEXT_LIMIT = 2048
EFFORTS = {"minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
TARGET_FIELDS = {"dispatcher", "scope", "instance", "model", "effort", "option", "mode"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def stamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("Dispatcher evidence timestamps must include a timezone")
    return result


def route_id(dispatcher):
    return f"{dispatcher}-dispatch"


def target(value):
    if not isinstance(value, dict) or set(value) != TARGET_FIELDS:
        raise ValueError("Dispatcher target fields must match the exact live selection")
    if value["dispatcher"] not in SURFACES.values() or value["effort"] not in EFFORTS:
        raise ValueError("Unsupported dispatcher or reasoning effort")
    if not all(isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9_.:/@-]{1,200}", item)
               for item in value.values()):
        raise ValueError("Dispatcher targets must be single-line native identifiers")
    if value["dispatcher"] == "t3":
        if len(value["scope"].split(":", 2)) != 3:
            raise ValueError("T3 scope must identify environment, project and parent thread")
        if value["option"] not in {"reasoningEffort", "thinking", "effort"} or value["mode"] != "inherit":
            raise ValueError("T3 must advertise the exact reasoning option and inherit approvals")
        if not (value["model"].startswith(("openai-codex/", "openai-codex:"))
                or value["instance"] == "codex" and value["model"].startswith("gpt-")):
            raise ValueError("Only an exact OpenAI Codex subscription model is supported")
    else:
        if not re.fullmatch(r"srv_[A-Za-z0-9_-]+:wks_[A-Za-z0-9_-]+", value["scope"]):
            raise ValueError("Paseo scope must identify the daemon and workspace")
        expected = {"codex": "auto", "hermes": "default", "omp": "ask"}
        model_prefix = {"codex": "gpt-", "hermes": "openai-codex:gpt-", "omp": "openai-codex/gpt-"}
        if (value["instance"] not in expected or value["mode"] != expected[value["instance"]]
                or value["option"] != "thinkingOptionId"
                or not value["model"].startswith(model_prefix[value["instance"]])):
            raise ValueError("Paseo requires an exact configured subscription worker and its approval mode")
    return value


def launch(selected, assignment, attempt):
    if selected["dispatcher"] == "t3":
        return {"tool": "delegate_task", "arguments": {
            "task": assignment, "clientRequestId": f"dynamic-workflow-{attempt}", "mode": "async",
            "target": {"providerInstanceId": selected["instance"], "model": selected["model"],
                       "options": {selected["option"]: selected["effort"]}},
        }}
    server, workspace = selected["scope"].split(":")
    return {"server": server, "argv": [
        "run", "--workspace", workspace, "--provider", selected["instance"], "--model", selected["model"],
        "--thinking", selected["effort"], "--mode", selected["mode"], "--title", f"Dynamic workflow {attempt}",
        "--no-wait", "--json", "--", assignment,
    ]}


def t3_payload(value):
    if value and "structuredContent" in value:
        if value.get("isError") is not False:
            raise ValueError("T3 returned a tool error")
        return value["structuredContent"]
    return value


def validate_t3_capabilities(selected, capabilities):
    capabilities = t3_payload(capabilities)
    if not capabilities or capabilities["parentThreadId"] != selected["scope"].split(":", 2)[2]:
        raise ValueError("Read live T3 capabilities from the pinned parent thread")
    inherited_instance = capabilities["inheritedProviderInstanceId"]
    cross_provider = inherited_instance != selected["instance"]
    provider = next((item for item in capabilities["providers"]
                     if item["providerInstanceId"] == selected["instance"]), None)
    support = "canRunCrossProviderChildTask" if cross_provider else "canRunChildTask"
    if not provider or not provider[support]:
        raise ValueError("The pinned provider is unavailable for this T3 child")
    model = next((item for item in provider["models"] if item["id"] == selected["model"]), None)
    if not model or not any(option["id"] == selected["option"] and selected["effort"] in option["values"]
                            for option in model["options"]):
        raise ValueError("T3 does not advertise the pinned model and reasoning option")
    inherited_options = {option["id"] for option in (capabilities["inheritedOptions"] or [])}
    if (not cross_provider and capabilities["inheritedModel"] == selected["model"]
            and inherited_options - {selected["option"]}):
        raise ValueError("The same-model T3 child would inherit options outside the pinned route")


def verify_result(selected, result, assignment, handle=None):
    """Check the saved app readbacks. The controller is responsible for collecting them."""
    if selected["dispatcher"] == "t3":
        identifier, output = t3_result(selected, result, assignment)
    else:
        identifier, output = paseo_result(selected, result, assignment)
    if not identifier or (handle is not None and identifier != handle) or not output.strip():
        raise ValueError("Dispatcher result does not match the exact handle or has no answer")
    return output


def t3_result(selected, result, assignment):
    environment, project, parent = selected["scope"].split(":", 2)
    status, read = (t3_payload(result[key]) for key in ("status", "activity"))
    thread = read["thread"]
    run_id, thread_id = status["childRunId"], status["childThreadId"]
    if (result["environment"] != environment or not run_id or not thread_id
            or status["status"] != "completed" or status["workState"] != "result_available"
            or status["latestTerminalRunId"] != run_id or status["latestTerminalStatus"] != "completed"
            or status["hasPendingChildRuns"] or status["hasPendingQuestion"] or status["pendingApproval"] is not None
            or thread["threadId"] != thread_id or thread["projectId"] != project or thread["parentThreadId"] != parent
            or thread["activeRunId"] is not None or thread["runCount"] != 1 or thread["pendingRequestCount"]
            or read["hasMore"] or read.get("earlierPosition") is not None):
        raise ValueError("T3 child must be completely settled in the pinned project and parent")
    if len(read["recentRuns"]) != 1:
        raise ValueError("T3 requires the original child run")
    run = read["recentRuns"][0]
    if (run["runId"] != run_id or run["status"] != "completed"
            or status.get("options") != [{"id": selected["option"], "value": selected["effort"]}]
            or any(row["providerInstanceId"] != selected["instance"] or row["model"] != selected["model"]
                   or row.get("executedModel") not in (None, selected["model"]) for row in (status, thread, run))):
        raise ValueError("T3 did not report the pinned instance, model, effort and original run")
    items = [item for item in read["items"] if item["visibility"] == "local"]
    if any(item["sourceThreadId"] != thread_id or item["runId"] != run_id or item["textTruncated"]
           or (item["type"] not in {"user_message", "assistant_message", "reasoning"}
               and not (item["type"] == "checkpoint" and item["text"] == "[]")) for item in items):
        raise ValueError("T3 child activity contains tools, other work or incomplete data")
    if [item["text"] for item in items if item["type"] == "user_message"] != [assignment]:
        raise ValueError("T3 child assignment does not match this attempt")
    return status["taskId"], "\n".join(item["text"] for item in items if item["type"] == "assistant_message")


def paseo_result(selected, result, assignment):
    server, workspace = selected["scope"].split(":")
    agent = result["inspect"]
    location = result["workspace"]
    effective_mode = {"default", "ask"} if selected["instance"] == "hermes" else {selected["mode"]}
    no_activity = "No activity to display."
    if (result["daemon"]["serverId"] != server or result["daemon"]["connectedDaemon"] != "reachable"
            or location["workspaceId"] != workspace or location["cwd"] != agent["Cwd"]
            or agent["Provider"] != selected["instance"] or agent["Model"] != selected["model"]
            or agent["Thinking"] != selected["effort"] or agent["Mode"] not in effective_mode
            or agent["Status"] != "closed" or not agent["Archived"] or agent["PendingPermissions"] != []
            or result["tools"].strip() != no_activity or result["errors"].strip() != no_activity
            or result["permissions"].strip() != no_activity):
        raise ValueError("Paseo worker must match the pinned workspace and route and be archived after settling")
    transcript = result["logs"].strip()
    prefix = f"[User] {assignment.strip()}\n"
    if not transcript.startswith(prefix):
        raise ValueError("Paseo logs do not contain the original assignment")
    output = transcript.removeprefix(prefix)
    if re.search(r"(?m)^\[", output):
        raise ValueError("Paseo logs contain another event after the initial assignment")
    return agent["Id"], output


def verify_observation(observation, selected, when):
    if not isinstance(observation, dict) or set(observation) != {"target", "observed_at", "valid_until", "attempt", "result"}:
        raise ValueError("Missing exact dispatcher observation")
    if observation["target"] != selected or not re.fullmatch(r"[a-f0-9]{32}", observation["attempt"]):
        raise ValueError("Dispatcher observation belongs to a different target or attempt")
    observed = stamp(observation["observed_at"])
    until = stamp(observation["valid_until"])
    attempt = observation["attempt"]
    output = verify_result(selected, observation["result"], probe_assignment(attempt))
    if (observed != result_observed_at(selected, observation["result"])
            or until - observed != WINDOW or not observed <= when <= until or output.strip() != f"READY-{attempt}"):
        raise ValueError("Dispatcher observation is expired or did not return its challenge")


def result_observed_at(selected, result):
    if selected["dispatcher"] == "t3":
        return stamp(t3_payload(result["activity"])["recentRuns"][0]["completedAt"])
    # The worker may have been archived well after completing its task. Use its creation time.
    return stamp(result["inspect"]["CreatedAt"])


def probe_assignment(attempt):
    return f"Reply with only READY-{attempt}. Use no tools and make no changes."


def prepare(root, selected, when, state, capabilities=None):
    target(selected)
    if selected["dispatcher"] == "t3":
        validate_t3_capabilities(selected, capabilities)
    root.mkdir(parents=True, exist_ok=True)
    path = root / (digest(selected) + ".json")
    with state.state_lock(root):
        try:
            existing = state.load_json(path) if path.is_file() else {}
            observation = existing.get("observation")
            if observation is not None:
                verify_observation(observation, selected, when)
                return {"kind": "current", "observation": observation}
            pending = existing.get("pending")
            if pending:
                return {"kind": "pending", "attempt": pending["attempt"], "cache": str(path.resolve())}
        except (OSError, ValueError, AttributeError, TypeError, KeyError):
            # An unusable cache entry does not establish availability.
            pass
        attempt = secrets.token_hex(16)
        state.atomic_json(path, {"target": selected, "pending": {"attempt": attempt, "created": when.isoformat()}})
        return {"kind": "probe", "cache": str(path.resolve()), "attempt": attempt,
                **launch(selected, probe_assignment(attempt), attempt)}


def complete(path, attempt, result, when, state):
    with state.state_lock(path.parent):
        stored = state.load_json(path)
        selected = target(stored["target"])
        if path.name != digest(selected) + ".json":
            raise ValueError("Dispatcher cache path does not match the target")
        pending = stored.get("pending")
        observed = result_observed_at(selected, result)
        if not pending or pending["attempt"] != attempt or not stamp(pending["created"]) <= observed <= when:
            raise ValueError("Dispatcher challenge belongs to another attempt")
        observation = {"target": selected, "observed_at": observed.isoformat(),
                       "valid_until": (observed + WINDOW).isoformat(), "attempt": attempt, "result": result}
        verify_observation(observation, selected, when)
        state.atomic_json(path, {"target": selected, "observation": observation})
        return {"kind": "current", "observation": observation}


def fail_probe(path, attempt, reason, state):
    with state.state_lock(path.parent):
        stored = state.load_json(path)
        selected = target(stored["target"])
        if (path.name != digest(selected) + ".json" or not reason.strip()
                or stored.get("pending", {}).get("attempt") != attempt):
            raise ValueError("A failed probe needs the exact pending attempt and reason")
        state.atomic_json(path, {"target": selected, "failed": {"attempt": attempt, "reason": reason.strip()}})
        return {"kind": "failed", "attempt": attempt}


def overlay(catalog, task, surface, descriptor, as_of):
    context = descriptor.get("execution_context")
    if surface not in SURFACES:
        return catalog
    if not isinstance(context, dict):
        raise ValueError("Dispatcher runs require an explicit controller context")
    dispatcher = SURFACES[surface]
    active_t3 = context.get("active_t3")
    if type(active_t3) is not bool or active_t3 != (dispatcher == "t3"):
        raise ValueError("Use the native dispatcher inside T3 and Paseo for standalone fallback")
    observation = context.get("dispatcher_observation")
    if observation is None:
        raise ValueError("Refresh dispatcher availability before freezing this task")
    selected = target(observation["target"])
    if selected["dispatcher"] != dispatcher or selected["scope"] != context.get("dispatcher_scope"):
        raise ValueError("Dispatcher evidence belongs to another native context")
    verify_observation(observation, selected, stamp(as_of))
    request = task["route_request"]
    requirements = request["requirements"]
    route_name = route_id(dispatcher)
    if (task["risk"] != "read" or task["ownership"] or task["workdir"] != "."
            or request["effects"] != "none" or requirements["tools"]
            or len(descriptor["prompt"].encode("utf-8")) > CONTEXT_LIMIT
            or request["budget"]["preference_order"] != [route_name]):
        raise ValueError("Dispatcher workers require a small text task, no effects and an explicit route preference")
    route = {"host": dispatcher, "transport": surface, "provider": "openai-codex",
             "model": selected["model"], "reasoning_effort": selected["effort"],
             "runtime": dispatcher + "-native-dispatch", "contract_sha256": digest(selected)}
    evidence_id = digest(observation)
    parts = {"generation": None, "verification": None, "fallback": None}
    candidate = {"id": route_name, "route": route, "quality": [], "benchmark_priors": [],
                 "availability": {
                     "status": "verified", "observed_at": observation["observed_at"],
                     "valid_until": observation["valid_until"], "route_sha256": digest(route),
                     "context_tokens": CONTEXT_LIMIT, "tools_verified": [], "allowed_effects": ["none"],
                     "evidence": {"locator": f"inline:{dispatcher}-dispatch/{evidence_id}", "sha256": evidence_id},
                 },
                 "cost": {"billing": "subscription", "basis": "unknown", "task_contract_sha256": None,
                          "verifier_sha256": None, "route_sha256": None, "api_usd": parts, "evidence": None,
                          "quota": {"bucket": "codex-main", "unit": "percentage-points", "parts": parts}}}
    if any(row["id"] == route_name for row in catalog["candidates"]):
        raise ValueError("The dispatcher route is reserved for fresh native observations")
    return {**catalog, "candidates": [*catalog["candidates"], candidate]}


def current_observation(root, selected, when, state):
    path = root / (digest(selected) + ".json")
    observation = state.load_json(path)["observation"]
    verify_observation(observation, selected, when)
    return observation


def task_assignment(prompt, token):
    attempt = digest(token)[:32]
    return f"{prompt}\n\nWorkflow attempt {attempt}. Return the requested text without tools or side effects."


def paseo_call(home, *args):
    env = os.environ.copy()
    for name in ("PASEO_AGENT_ID", "PASEO_WORKSPACE_ID", "PASEO_HOST"):
        env.pop(name, None)
    executable = shutil.which("paseo")
    if os.name == "nt" and (not executable or Path(executable).suffix.lower() == ".cmd"):
        app = Path(env["LOCALAPPDATA"]) / "Programs" / "Paseo"
        resources = app / "resources"
        command = [str(app / "Paseo.exe"), "--disable-warning=DEP0040",
                   str(resources / "app.asar.unpacked/dist/daemon/node-entrypoint-runner.js"), "node-script",
                   str(resources / "app.asar/node_modules/@getpaseo/cli/dist/index.js")]
        env.update(ELECTRON_RUN_AS_NODE="1", PASEO_NODE_ENV="production")
    else:
        if not executable:
            raise ValueError("No installed Paseo CLI was found")
        command = [executable]
    result = subprocess.run([*command, "--home", str(home.resolve()), *args], env=env,
                            check=False, capture_output=True, encoding="utf-8", timeout=45)
    if result.returncode:
        raise ValueError(f"Paseo {args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def paseo_daemon(home, server, *, start=False):
    if not (home / "config.json").is_file():
        raise ValueError("Select the already configured local Paseo dispatcher home")
    status = json.loads(paseo_call(home, "status", "--json"))
    if not str(status.get("configuredListen", "")).startswith(("127.0.0.1:", "[::1]:")):
        raise ValueError("Shared workflow dispatch requires the configured local Paseo listener")
    if status.get("serverId") not in (server, None):
        raise ValueError("Paseo home belongs to a different daemon")
    if start and status.get("localDaemon") == "stopped":
        paseo_call(home, "start")
        status = json.loads(paseo_call(home, "status", "--json"))
    if status.get("connectedDaemon") != "reachable" or status.get("serverId") != server:
        raise ValueError("The pinned Paseo daemon is unavailable")
    return status


@contextmanager
def paseo_send_slot(document, request, request_path, state):
    if document.get("kind") == "probe":
        cache = Path(document["cache"]).resolve()
        attempt = document["attempt"]
        with state.state_lock(cache.parent):
            stored = state.load_json(cache)
            selected = target(stored["target"])
            if (cache.name != digest(selected) + ".json" or stored.get("pending", {}).get("attempt") != attempt
                    or launch(selected, probe_assignment(attempt), attempt) != request):
                raise ValueError("Paseo probe does not match its active cache claim")
            yield cache.with_name(f"{cache.stem}.{attempt}.paseo-sent")
    else:
        path = request_path.resolve()
        run = path.parent.parent.parent
        task = path.parent.name
        if path != state.task_artifact_path(run, task, "dispatcher-launch.json"):
            raise ValueError("Launch Paseo from the canonical workflow intent")
        with state.state_lock(run):
            _plan, saved, _manifest = state.load_run_snapshot(run)
            current = saved["tasks"][task]
            token = current["launch_token"]
            claim_path = state.launch_claim_path(run, task)
            if (saved["target_surface"] != "paseo-workflow" or saved["stop_requested"]
                    or current["status"] != "launching" or not token or not claim_path.is_file()
                    or claim_path.read_text(encoding="ascii").strip() != token
                    or document.get("claim_sha256") != digest(token) or state.load_json(path) != document):
                raise ValueError("Paseo task has no active launch claim")
            selected = current["dispatch"]["input"]["execution_context"]["dispatcher_observation"]["target"]
            state._current_worker_observation(run, selected)
            if launch(selected, task_assignment(current["dispatch"]["input"]["prompt"], token),
                      digest(token)[:32]) != request:
                raise ValueError("Paseo launch request drifted from the pinned workflow decision")
            yield path.with_name(path.name + ".paseo-sent")


def paseo_launch(home, document, request_path, state):
    request = ({key: document[key] for key in ("server", "argv")} if document.get("kind") == "probe"
               else document["request"])
    argv = request["argv"]
    if (len(argv) != 17 or argv[0:2] != ["run", "--workspace"]
            or argv[3:13:2] != ["--provider", "--model", "--thinking", "--mode", "--title"]
            or argv[13:16] != ["--no-wait", "--json", "--"]
            or not re.fullmatch(r"Dynamic workflow [a-f0-9]{32}", argv[12])):
        raise ValueError("Expected the workflow's issued Paseo worker arguments")
    paseo_daemon(home, request["server"], start=True)
    with paseo_send_slot(document, request, request_path, state) as marker:
        try:
            with marker.open("x", encoding="ascii") as file:
                file.write(digest(request))
        except FileExistsError as exc:
            raise ValueError("This Paseo launch was already issued. Recover the original worker by exact title") from exc
        return json.loads(paseo_call(home, *argv))


def paseo_readback(home, selected, handle, request, request_path, state):
    server, workspace_id = selected["scope"].split(":")
    daemon = paseo_daemon(home, server)
    workspaces = json.loads(paseo_call(home, "workspace", "ls", "--json"))
    workspace = next((item for item in workspaces if item["workspaceId"] == workspace_id), None)
    agent = json.loads(paseo_call(home, "inspect", handle, "--json"))
    expected = launch(selected, request["argv"][-1], request["argv"][12].removeprefix("Dynamic workflow "))
    if (any(request.get(key) != value for key, value in expected.items()) or agent["Name"] != request["argv"][12]
            or agent["Id"] != handle or workspace is None or workspace["cwd"] != agent["Cwd"]
            or agent["Status"] not in {"idle", "closed"} or agent["PendingPermissions"]):
        raise ValueError("The exact Paseo worker is still active or belongs to another workspace")
    before_close = request_path.with_name(request_path.name + ".paseo-activity.json")
    if agent["Archived"]:
        activity = state.load_json(before_close)
        if activity["agentId"] != handle:
            raise ValueError("Saved Paseo activity belongs to another worker")
    else:
        activity = {"agentId": handle, "logs": paseo_call(home, "logs", handle)}
        for kind in ("tools", "errors", "permissions"):
            activity[kind] = paseo_call(home, "logs", handle, "--filter", kind)
        # Archive adds an activity event. Save the actual worker timeline first.
        state.atomic_json(before_close, activity)
        paseo_call(home, "archive", handle)
        agent = json.loads(paseo_call(home, "inspect", handle, "--json"))
    return {**activity, "daemon": daemon, "workspace": workspace, "inspect": agent}


def main():
    import workflow_state as state

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("target", type=Path)
    prep.add_argument("--root", type=Path, required=True)
    prep.add_argument("--capabilities", type=Path)
    done = commands.add_parser("complete")
    done.add_argument("cache", type=Path)
    done.add_argument("attempt")
    done.add_argument("result", type=Path)
    failed = commands.add_parser("probe-failed")
    failed.add_argument("cache", type=Path)
    failed.add_argument("attempt")
    failed.add_argument("--reason", required=True)
    send = commands.add_parser("paseo-launch")
    send.add_argument("request", type=Path)
    send.add_argument("--home", type=Path, required=True)
    read = commands.add_parser("paseo-read")
    read.add_argument("target", type=Path)
    read.add_argument("handle")
    read.add_argument("request", type=Path)
    read.add_argument("--home", type=Path, required=True)
    args = parser.parse_args()
    when = datetime.now(timezone.utc)
    try:
        if args.operation == "prepare":
            capabilities = state.load_json(args.capabilities) if args.capabilities else None
            result = prepare(args.root, state.load_json(args.target), when, state, capabilities)
        elif args.operation == "complete":
            result = complete(args.cache, args.attempt, state.load_json(args.result), when, state)
        elif args.operation == "probe-failed":
            result = fail_probe(args.cache, args.attempt, args.reason, state)
        elif args.operation == "paseo-launch":
            result = paseo_launch(args.home, state.load_json(args.request), args.request, state)
        else:
            selected = target(state.load_json(args.target))
            if selected["dispatcher"] != "paseo":
                raise ValueError("Paseo readback requires a Paseo target")
            request = state.load_json(args.request)
            result = paseo_readback(args.home, selected, args.handle, request.get("request", request),
                                     args.request, state)
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
