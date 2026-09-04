"""Automatic exact-route delegation without shared config mutation."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import os
import threading
import contextvars
import time
import tempfile
from pathlib import Path
from typing import Any

_PLUGIN_VERSION = "0.4.0"
_SURFACE = "hermes-delegate"
_WORKFLOW_SURFACE = "hermes-workflow"
_ALLOWED_PROVIDERS = {"openai-codex"}
_TIERS = {"routine", "standard", "strong", "demanding", "maximum"}
_FAILURE_COSTS = {"low", "medium", "high"}
_ROLES = {"leaf", "orchestrator"}
_MAX_ITERATIONS = 250
_PIN_LOCK = threading.RLock()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(value: Any) -> str:
    payload = value if isinstance(value, bytes) else _canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home()).expanduser().resolve()
    except ImportError:
        pass
    override = os.environ.get("HERMES_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return (Path(os.environ["LOCALAPPDATA"]) / "hermes").resolve()
    return (Path.home() / ".hermes").resolve()


def _route_skill() -> Path:
    override = os.environ.get("HERMES_ROUTED_DELEGATION_SKILL")
    candidates = [Path(override).expanduser()] if override else []
    candidates.extend(
        [
            Path(__file__).resolve().parents[3]
            / "skills"
            / "openai-delegation-route-research",
            Path.home() / ".agents" / "skills" / "openai-delegation-route-research",
            _hermes_home() / "skills" / "openai-delegation-route-research",
        ]
    )
    skills_root = _hermes_home() / "skills"
    if skills_root.is_dir():
        candidates.extend(
            path
            for path in skills_root.rglob("openai-delegation-route-research")
            if path.is_dir()
        )
    for candidate in candidates:
        if (
            (candidate / "scripts" / "route_selector.py").is_file()
            and (candidate / "references" / "current-gpt-catalog.json").is_file()
        ):
            return candidate.resolve()
    raise RuntimeError("openai-delegation-route-research skill is unavailable")


def _selector_and_catalog() -> tuple[Any, dict[str, Any], Path]:
    skill = _route_skill()
    selector_path = skill / "scripts" / "route_selector.py"
    catalog_path = skill / "references" / "current-gpt-catalog.json"
    spec = importlib.util.spec_from_file_location("routed_delegation_selector", selector_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load route selector: {selector_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    module.validate_catalog(catalog)
    return module, catalog, catalog_path


def _workflow_skill() -> Path:
    override = os.environ.get("HERMES_DYNAMIC_WORKFLOWS_SKILL")
    candidates = [Path(override).expanduser()] if override else []
    candidates.extend(
        [
            Path(__file__).resolve().parents[3] / "skills" / "dynamic-workflows",
            Path.home() / ".agents" / "skills" / "dynamic-workflows",
            _hermes_home() / "skills" / "dynamic-workflows",
        ]
    )
    skills_root = _hermes_home() / "skills"
    if skills_root.is_dir():
        candidates.extend(
            path for path in skills_root.rglob("dynamic-workflows") if path.is_dir()
        )
    for candidate in candidates:
        if (candidate / "scripts" / "workflow_state.py").is_file():
            return candidate.resolve()
    raise RuntimeError("dynamic-workflows skill is unavailable")


def _workflow_state_module() -> Any:
    path = _workflow_skill() / "scripts" / "workflow_state.py"
    spec = importlib.util.spec_from_file_location("routed_delegation_workflow_state", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load workflow state owner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_hermes_workflow_plan(plan: dict[str, Any]) -> None:
    legacy = [task["id"] for task in plan["tasks"] if "intelligence_tier" not in task]
    if legacy:
        raise ValueError(
            "Hermes workflows require router-selected intelligence_tier tasks; "
            f"legacy difficulty tasks are unsupported: {legacy}"
        )
    unsupported_workdirs = [
        task["id"] for task in plan["tasks"] if task.get("workdir", ".") != "."
    ]
    if unsupported_workdirs:
        raise ValueError(
            "Hermes delegates do not support per-node working directories; "
            f"use workdir='.' and state paths in the prompt: {unsupported_workdirs}"
        )


def _workflow_run_key(run_dir: Path) -> tuple[str, str]:
    canonical = os.path.normcase(str(run_dir.resolve()))
    return canonical, _sha(canonical.encode("utf-8"))


def _workflow_binding_path(run_dir: Path) -> Path:
    _canonical_run, key = _workflow_run_key(run_dir)
    return (
        _hermes_home()
        / "cache"
        / "routed-delegation"
        / "workflow-bindings"
        / f"{key}.json"
    )


def _workflow_binding(workflow: Any, run_dir: Path) -> dict[str, Any]:
    _plan, _state, manifest = workflow.load_run_snapshot(run_dir)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 2:
        raise RuntimeError("Hermes workflow run lacks a version 2 integrity manifest")
    canonical, _key = _workflow_run_key(run_dir)
    return {
        "schema_version": 1,
        "owner": "routed-delegation",
        "run_dir": canonical,
        "target_surface": _WORKFLOW_SURFACE,
        "manifest_sha256": _sha(manifest),
    }


def _register_workflow_binding(workflow: Any, run_dir: Path) -> None:
    _atomic_text(
        _workflow_binding_path(run_dir),
        json.dumps(
            _workflow_binding(workflow, run_dir),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
    )


def _verify_workflow_binding(workflow: Any, run_dir: Path) -> str:
    path = _workflow_binding_path(run_dir)
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Hermes workflow run is not registered in the trusted adapter binding store"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read trusted Hermes workflow binding: {path}") from exc
    if actual != _workflow_binding(workflow, run_dir):
        raise RuntimeError("Hermes workflow trusted binding does not match its run manifest")
    return actual["manifest_sha256"]


def _initialize_workflow(
    plan_path: Path, run_root: Path, variables: dict[str, str]
) -> Path:
    workflow = _workflow_state_module()
    plan = workflow.read_plan(Path(plan_path))
    _validate_hermes_workflow_plan(plan)
    if not isinstance(variables, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in variables.items()
    ):
        raise ValueError("workflow variables must be a string-to-string object")
    run_dir = workflow.init_run(
        Path(plan_path),
        Path(run_root),
        variables,
        target_surface=_WORKFLOW_SURFACE,
    )
    _register_workflow_binding(workflow, run_dir)
    return run_dir


def _normalize_task(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("each task must be an object")
    task_id = str(raw.get("id") or "").strip()
    goal = str(raw.get("goal") or "").strip()
    tier = str(raw.get("intelligence_tier") or "").strip()
    latency = raw.get("latency_sensitive")
    failure_cost = str(raw.get("failure_cost") or "medium").strip()
    role = str(raw.get("role") or "leaf").strip()
    if not task_id or len(task_id) > 128:
        raise ValueError("task id must contain 1-128 characters")
    if not goal or len(goal) > 16000:
        raise ValueError(f"task {task_id!r} goal must contain 1-16000 characters")
    if tier not in _TIERS:
        raise ValueError(f"task {task_id!r} has invalid intelligence_tier")
    if not isinstance(latency, bool):
        raise ValueError(f"task {task_id!r} latency_sensitive must be true or false")
    if failure_cost not in _FAILURE_COSTS:
        raise ValueError(f"task {task_id!r} has invalid failure_cost")
    if role not in _ROLES:
        raise ValueError(f"task {task_id!r} role must be leaf or orchestrator")
    context = raw.get("context")
    if context is not None and (not isinstance(context, str) or len(context) > 32000):
        raise ValueError(f"task {task_id!r} context must be a string up to 32000 characters")
    toolsets = raw.get("toolsets")
    if toolsets is not None and (
        not isinstance(toolsets, list)
        or not all(isinstance(value, str) and value.strip() for value in toolsets)
    ):
        raise ValueError(f"task {task_id!r} toolsets must be a list of names")
    verifier_plan = raw.get("verifier_plan", {"kind": "none"})
    if not isinstance(verifier_plan, dict):
        raise ValueError(f"task {task_id!r} verifier_plan must be an object")
    return {
        "id": task_id,
        "goal": goal,
        "context": context,
        "intelligence_tier": tier,
        "latency_sensitive": latency,
        "failure_cost": failure_cost,
        "task_class": str(raw.get("task_class") or "delegated-agent-task").strip(),
        "verifier_plan": verifier_plan,
        "toolsets": toolsets,
        "role": role,
    }


def _pin_path(parent_session_id: str) -> Path:
    root = _hermes_home() / "cache" / "routed-delegation" / "pins"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{_sha(parent_session_id.encode('utf-8'))}.json"


def _read_pins(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "plugin_version": _PLUGIN_VERSION, "tasks": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("tasks"), dict):
        raise RuntimeError(f"invalid routed-delegation pin store: {path}")
    return value


def _write_pins(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _request(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_surface": _SURFACE,
        "intelligence_tier": task["intelligence_tier"],
        "latency_sensitive": task["latency_sensitive"],
        "task_id": task["id"],
        "task_class": task["task_class"],
        "failure_cost": task["failure_cost"],
        "attempt_number": 1,
        "verifier_plan": task["verifier_plan"],
    }


def _validate_receipt_against_catalog(
    receipt: Any, catalog: dict[str, Any], request: dict[str, Any]
) -> None:
    if not isinstance(receipt, dict) or receipt.get("outcome") != "selected":
        raise RuntimeError("route pin has no selected receipt")
    route = receipt.get("route")
    constraints = receipt.get("constraints_applied")
    if not isinstance(route, dict) or not isinstance(constraints, dict):
        raise RuntimeError("route pin has invalid route evidence")
    expected_constraints = {
        "target_surface": request["target_surface"],
        "task_id": request["task_id"],
        "task_class": request["task_class"],
        "failure_cost": request["failure_cost"],
        "intelligence_tier": request["intelligence_tier"],
        "latency_sensitive": request["latency_sensitive"],
    }
    if any(constraints.get(key) != value for key, value in expected_constraints.items()):
        raise RuntimeError("route pin constraints do not match the task")
    if receipt.get("requirement_sha256") != _sha(constraints):
        raise RuntimeError("route pin requirement hash is invalid")
    decision = {
        "policy_sha256": receipt.get("policy_sha256"),
        "requirement_sha256": receipt.get("requirement_sha256"),
        "outcome": "selected",
        "route": route,
    }
    if receipt.get("decision_id") != _sha(decision):
        raise RuntimeError("route pin decision hash is invalid")
    allowed = {
        (
            candidate.get("id"),
            catalog.get("provider"),
            candidate.get("model"),
            candidate.get("reasoning_effort"),
        )
        for candidate in catalog.get("delegation_candidates", [])
        if isinstance(candidate, dict)
    }
    selected = (
        route.get("id"),
        route.get("provider"),
        route.get("model"),
        route.get("reasoning_effort"),
    )
    if selected not in allowed:
        raise RuntimeError("route pin selects a route outside the active catalog")


def _select_or_reuse(
    parent_session_id: str, task: dict[str, Any], max_iterations: int
) -> dict[str, Any]:
    request = _request(task)
    binding = {
        "goal_sha256": _sha(task["goal"].encode("utf-8")),
        "context_sha256": _sha((task.get("context") or "").encode("utf-8")),
        "execution": {
            "role": task["role"],
            "toolsets": task["toolsets"],
            "max_iterations": max_iterations,
        },
        "request": request,
    }
    path = _pin_path(parent_session_id)
    with _PIN_LOCK:
        store = _read_pins(path)
        existing = store["tasks"].get(task["id"])
        if existing is not None:
            envelope = {key: existing.get(key) for key in ("binding", "receipt")}
            if existing.get("pin_sha256") != _sha(envelope):
                raise RuntimeError(f"task {task['id']!r} route pin failed integrity validation")
            if existing.get("binding") != binding:
                raise RuntimeError(f"task {task['id']!r} already pins a different task or requirement")
            _, catalog, _ = _selector_and_catalog()
            _validate_receipt_against_catalog(existing["receipt"], catalog, request)
            return existing["receipt"]
        selector, catalog, catalog_path = _selector_and_catalog()
        receipt = selector.select_route(catalog, request, catalog_locator=str(catalog_path))
        _validate_receipt_against_catalog(receipt, catalog, request)
        route = receipt.get("route") or {}
        if route.get("provider") not in _ALLOWED_PROVIDERS:
            raise RuntimeError(f"selector returned unsupported provider: {route.get('provider')}")
        envelope = {"binding": binding, "receipt": receipt}
        store["tasks"][task["id"]] = {**envelope, "pin_sha256": _sha(envelope)}
        _write_pins(path, store)
        return receipt


def _private_runtime() -> dict[str, Any]:
    from tools import delegate_tool
    from agent.chat_completion_helpers import (
        _build_api_kwargs_for_mode,
        _reasoning_config_for_wire,
    )
    from agent.transports.codex import ResponsesApiTransport

    build = getattr(delegate_tool, "_build_child_preserving_parent_tools", None)
    run = getattr(delegate_tool, "_run_single_child", None)
    finalize = getattr(delegate_tool, "_finalize_child_results", None)
    get_max_children = getattr(delegate_tool, "_get_max_concurrent_children", None)
    get_max_depth = getattr(delegate_tool, "_get_max_spawn_depth", None)
    is_paused = getattr(delegate_tool, "is_spawn_paused", None)
    load_config = getattr(delegate_tool, "_load_config", None)
    capture_owner = getattr(delegate_tool, "_capture_gateway_steer_authority", None)
    interrupt = getattr(delegate_tool, "interrupt_subagent", None)
    list_active = getattr(delegate_tool, "list_active_subagents", None)
    default_iterations = getattr(delegate_tool, "DEFAULT_MAX_ITERATIONS", None)
    required_callables = (
        build,
        run,
        finalize,
        get_max_children,
        get_max_depth,
        is_paused,
        load_config,
        capture_owner,
        interrupt,
        list_active,
    )
    if not all(callable(value) for value in required_callables) or not isinstance(
        default_iterations, int
    ):
        raise RuntimeError("installed Hermes delegation seam is incompatible")
    required = {"task_index", "goal", "context", "toolsets", "model", "parent_agent", "role"}
    if not required.issubset(inspect.signature(build).parameters) and not any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in inspect.signature(build).parameters.values()
    ):
        raise RuntimeError("installed Hermes child builder contract changed")
    reasoning_helper_source = inspect.getsource(_reasoning_config_for_wire)
    mode_builder_source = inspect.getsource(_build_api_kwargs_for_mode)
    transport_source = inspect.getsource(ResponsesApiTransport.build_kwargs)
    if not _reasoning_source_contract(
        reasoning_helper_source, mode_builder_source, transport_source
    ):
        raise RuntimeError("installed Hermes exact-reasoning request seam changed")
    return {
        "build": build,
        "run": run,
        "finalize": finalize,
        "get_max_children": get_max_children,
        "get_max_depth": get_max_depth,
        "is_paused": is_paused,
        "load_config": load_config,
        "capture_owner": capture_owner,
        "interrupt": interrupt,
        "list_active": list_active,
        "default_iterations": default_iterations,
    }


def _reasoning_source_contract(
    reasoning_helper_source: str,
    mode_builder_source: str,
    transport_source: str,
) -> bool:
    return (
        "cfg = agent.reasoning_config" in reasoning_helper_source
        and "_wire_reasoning_config = _reasoning_config_for_wire(agent)"
        in mode_builder_source
        and "reasoning_config=_wire_reasoning_config" in mode_builder_source
        and 'reasoning_config = params.get("reasoning_config")' in transport_source
        and 'reasoning_effort = reasoning_config["effort"]' in transport_source
    )


def _prepare_child(
    parent: Any,
    task: dict[str, Any],
    receipt: dict[str, Any],
    index: int,
    count: int,
    max_iterations: int,
    *,
    build: Any = None,
) -> Any:
    from hermes_constants import parse_reasoning_effort

    route = receipt["route"]
    parent_provider = str(getattr(parent, "provider", "") or "")
    if route["provider"] != parent_provider:
        raise RuntimeError(
            f"route provider {route['provider']!r} does not match active parent provider {parent_provider!r}"
        )
    reasoning = parse_reasoning_effort(route["reasoning_effort"])
    if reasoning is None:
        raise RuntimeError(f"unsupported reasoning effort: {route['reasoning_effort']}")
    if build is None:
        build = _private_runtime()["build"]
    child = build(
        task_index=index,
        goal=task["goal"],
        context=task["context"],
        toolsets=task["toolsets"],
        model=route["model"],
        max_iterations=max_iterations,
        task_count=count,
        parent_agent=parent,
        role=task["role"],
    )
    child.reasoning_config = dict(reasoning)
    session_config = getattr(child, "_session_init_model_config", None)
    if not isinstance(session_config, dict):
        close = getattr(child, "close", None)
        if callable(close):
            close()
        raise RuntimeError("child session model-config persistence seam changed")
    session_config["reasoning_config"] = dict(reasoning)
    primary_runtime = getattr(child, "_primary_runtime", None)
    if isinstance(primary_runtime, dict):
        primary_runtime["reasoning_config"] = dict(reasoning)
    child._fallback_chain = []
    child.fallback_model = None
    child._fallback_index = 0
    child._fallback_activated = False
    try:
        _assert_exact_child_route(child, route)
    except Exception:
        close = getattr(child, "close", None)
        if callable(close):
            close()
        raise
    return child


def _assert_exact_child_route(child: Any, route: dict[str, Any]) -> None:
    from hermes_constants import parse_reasoning_effort

    expected_reasoning = parse_reasoning_effort(route["reasoning_effort"])
    child_provider = str(getattr(child, "provider", "") or "")
    child_model = str(getattr(child, "model", "") or "")
    if child_provider != route["provider"] or child_model != route["model"]:
        raise RuntimeError(
            f"child route mismatch: expected {route['provider']}/{route['model']}, got {child_provider}/{child_model}"
        )
    if getattr(child, "reasoning_config", None) != expected_reasoning:
        raise RuntimeError("child live reasoning config does not match the pinned receipt")
    session_config = getattr(child, "_session_init_model_config", None)
    if not isinstance(session_config, dict) or session_config.get("reasoning_config") != expected_reasoning:
        raise RuntimeError("child persisted reasoning config does not match the pinned receipt")
    primary_runtime = getattr(child, "_primary_runtime", None)
    if isinstance(primary_runtime, dict) and primary_runtime.get("reasoning_config") != expected_reasoning:
        raise RuntimeError("child retry reasoning config does not match the pinned receipt")
    if getattr(child, "_fallback_chain", None) not in (None, []):
        raise RuntimeError("child route fallback is not disabled")


def _run_exact_child(
    run: Any,
    index: int,
    task: dict[str, Any],
    receipt: dict[str, Any],
    child: Any,
    parent: Any,
    owner_kwargs: dict[str, Any],
) -> Any:
    _assert_exact_child_route(child, receipt["route"])
    return run(
        task_index=index,
        goal=task["goal"],
        child=child,
        parent_agent=parent,
        **owner_kwargs,
    )


def _execute_children(
    prepared: list[tuple[int, dict[str, Any], dict[str, Any], Any]],
    parent: Any,
    run: Any,
    finalize: Any,
    *,
    max_children: int,
    owner_kwargs: dict[str, Any],
) -> list[dict[str, Any]]:
    from concurrent.futures import FIRST_COMPLETED, wait
    from tools.daemon_pool import DaemonThreadPoolExecutor

    results: list[dict[str, Any]] = []
    if len(prepared) == 1:
        index, task, receipt, child = prepared[0]
        results.append(
            _run_exact_child(
                run, index, task, receipt, child, parent, owner_kwargs
            )
        )
    else:
        child_by_index = {index: child for index, _task, _receipt, child in prepared}
        with DaemonThreadPoolExecutor(
            max_workers=max_children, thread_name_prefix="routed-delegate"
        ) as pool:
            futures = {}
            for index, task, receipt, child in prepared:
                child_context = contextvars.copy_context()
                future = pool.submit(
                    child_context.run,
                    _run_exact_child,
                    run,
                    index,
                    task,
                    receipt,
                    child,
                    parent,
                    owner_kwargs,
                )
                futures[future] = index
            pending = set(futures)
            while pending:
                if getattr(parent, "_interrupt_requested", False) is True:
                    for future in pending:
                        index = futures[future]
                        if future.done():
                            try:
                                entry = future.result()
                            except Exception as exc:
                                entry = {
                                    "task_index": index,
                                    "status": "error",
                                    "summary": None,
                                    "error": str(exc),
                                    "api_calls": 0,
                                    "duration_seconds": 0,
                                    "_child_role": getattr(
                                        child_by_index[index], "_delegate_role", None
                                    ),
                                }
                        else:
                            entry = {
                                "task_index": index,
                                "status": "interrupted",
                                "summary": None,
                                "error": "Parent agent interrupted — child did not finish in time",
                                "api_calls": 0,
                                "duration_seconds": 0,
                                "_child_role": getattr(
                                    child_by_index[index], "_delegate_role", None
                                ),
                            }
                        results.append(entry)
                    break
                done, pending = wait(
                    pending, timeout=0.5, return_when=FIRST_COMPLETED
                )
                for future in done:
                    index = futures[future]
                    try:
                        results.append(future.result())
                    except Exception as exc:
                        results.append(
                            {
                                "task_index": index,
                                "status": "error",
                                "summary": None,
                                "error": str(exc),
                                "api_calls": 0,
                                "duration_seconds": 0,
                                "_child_role": getattr(
                                    child_by_index[index], "_delegate_role", None
                                ),
                            }
                        )
    results.sort(key=lambda entry: entry["task_index"])
    task_list = [task for _index, task, _receipt, _child in prepared]
    native_children = [
        (index, task, child) for index, task, _receipt, child in prepared
    ]
    finalize(results, task_list, native_children, parent)
    return results


def _workflow_owner_kwargs(runtime: dict[str, Any]) -> dict[str, Any]:
    try:
        from gateway.session_context import get_session_env

        owner_session_id = get_session_env("HERMES_UI_SESSION_ID", "")
    except Exception:
        owner_session_id = ""
    owner_transport, owner_record = runtime["capture_owner"](owner_session_id)
    return {
        "owner_session_id": owner_session_id or None,
        "owner_transport": owner_transport,
        "owner_session_record": owner_record,
    }


def _workflow_snapshot(
    workflow: Any,
    run_dir: Path,
    trusted_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    _plan, state = workflow.load_run(run_dir, trusted_manifest_sha256)
    tasks = {}
    for task_id, current in state["tasks"].items():
        receipt = current.get("decision_receipt")
        route = receipt.get("route") if isinstance(receipt, dict) else None
        tasks[task_id] = {
            "status": current["status"],
            "attempts": current["attempts"],
            "handle": current.get("handle", ""),
            "handle_closed_at": current.get("handle_closed_at", ""),
            "output_path": current.get("output_path", ""),
            "error": current.get("error", ""),
            "decision_id": receipt.get("decision_id") if isinstance(receipt, dict) else None,
            "route": route,
        }
    return {
        "run_dir": str(run_dir.resolve()),
        "status": state["status"],
        "stop_requested": state["stop_requested"],
        "tasks": tasks,
    }


def _validate_hermes_workflow_run(
    workflow: Any, run_dir: Path
) -> tuple[dict[str, Any], dict[str, Any], str]:
    trusted_manifest_sha256 = _verify_workflow_binding(workflow, run_dir)
    plan, state = workflow.load_run(run_dir, trusted_manifest_sha256)
    if state.get("target_surface") != _WORKFLOW_SURFACE:
        raise RuntimeError(
            f"workflow target surface must be {_WORKFLOW_SURFACE!r}, got {state.get('target_surface')!r}"
        )
    _validate_hermes_workflow_plan(plan)
    for task in plan["tasks"]:
        workflow.task_model(run_dir, task["id"], trusted_manifest_sha256)
    return plan, state, trusted_manifest_sha256


def _workflow_task_envelope(
    workflow: Any,
    run_dir: Path,
    task: dict[str, Any],
    trusted_manifest_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    selected, receipt = workflow.task_route_receipt(
        run_dir, task["id"], trusted_manifest_sha256
    )
    prompt_path, goal = workflow.render_prompt_with_text(
        run_dir, task["id"], trusted_manifest_sha256
    )
    if selected.get("decision_id") != receipt.get("decision_id"):
        raise RuntimeError(f"workflow route receipt changed for task {task['id']!r}")
    return {
        "id": task["id"],
        "goal": goal,
        "context": None,
        "intelligence_tier": task["intelligence_tier"],
        "latency_sensitive": task["latency_sensitive"],
        "failure_cost": task["failure_cost"],
        "task_class": task["task_class"],
        "verifier_plan": {"kind": "none"},
        "toolsets": None,
        "role": "leaf",
    }, receipt


def _prepare_workflow_child(
    parent: Any,
    task: dict[str, Any],
    receipt: dict[str, Any],
    index: int,
    count: int,
    max_iterations: int,
    build: Any,
) -> Any:
    child = _prepare_child(
        parent,
        task,
        receipt,
        index,
        count,
        max_iterations,
        build=build,
    )
    if getattr(child, "_delegate_role", None) != "leaf":
        close = getattr(child, "close", None)
        if callable(close):
            close()
        raise RuntimeError(
            "Hermes workflow nodes must be native leaf children with delegation disabled"
        )
    handle = getattr(child, "_subagent_id", None)
    if not isinstance(handle, str) or not handle:
        close = getattr(child, "close", None)
        if callable(close):
            close()
        raise RuntimeError("Hermes failed to assign a native workflow child handle")
    child._workflow_task_id = task["id"]
    return child


def _safe_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _close_witness_path(run_dir: Path, task_id: str) -> Path:
    task_dir = run_dir.resolve() / "tasks" / task_id
    if (
        os.path.normcase(str(task_dir.resolve())) != os.path.normcase(str(task_dir))
        or not task_dir.is_dir()
    ):
        raise RuntimeError(f"workflow task directory escapes its run: {task_dir}")
    return task_dir / "native-close.json"


def _trusted_close_witness_path(
    run_dir: Path, task_id: str, handle: str, launch_token: str
) -> Path:
    canonical_run, run_key = _workflow_run_key(run_dir)
    witness_key = _sha({
        "run_dir": canonical_run,
        "task_id": task_id,
        "handle": handle,
        "launch_token": launch_token,
    })
    return (
        _hermes_home()
        / "cache"
        / "routed-delegation"
        / "workflow-close-witnesses"
        / run_key
        / f"{witness_key}.json"
    )


def _install_close_witness(
    child: Any,
    run_dir: Path,
    task_id: str,
    handle: str,
    launch_token: str,
) -> None:
    original_close = getattr(child, "close", None)
    if not callable(original_close):
        raise RuntimeError("Hermes workflow child has no close method")
    close_lock = threading.Lock()
    close_result: list[Any] = []

    def close_with_witness() -> Any:
        with close_lock:
            if close_result:
                return close_result[0]
            result = original_close()
            canonical_run, _run_key = _workflow_run_key(run_dir)
            payload = {
                "schema_version": 1,
                "run_dir": canonical_run,
                "task_id": task_id,
                "handle": handle,
                "launch_token": launch_token,
                "closed_at_unix": time.time(),
            }
            text = json.dumps(
                payload,
                sort_keys=True,
                ensure_ascii=False,
            ) + "\n"
            _atomic_text(
                _trusted_close_witness_path(
                    run_dir, task_id, handle, launch_token
                ),
                text,
            )
            _atomic_text(_close_witness_path(run_dir, task_id), text)
            close_result.append(result)
            return result

    child.close = close_with_witness


def _native_handle_is_closed(
    runtime: dict[str, Any],
    run_dir: Path,
    task_id: str,
    handle: str,
    launch_token: str,
) -> bool:
    list_active = runtime.get("list_active")
    if callable(list_active) and handle in {
        entry.get("subagent_id")
        for entry in list_active()
        if isinstance(entry, dict)
    }:
        return False
    witness_path = _trusted_close_witness_path(
        run_dir, task_id, handle, launch_token
    )
    try:
        witness = json.loads(witness_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return witness == {
        "schema_version": 1,
        "run_dir": _workflow_run_key(run_dir)[0],
        "task_id": task_id,
        "handle": handle,
        "launch_token": launch_token,
        "closed_at_unix": witness.get("closed_at_unix"),
    } and isinstance(witness.get("closed_at_unix"), (int, float)) and not isinstance(
        witness.get("closed_at_unix"), bool
    )


def _native_result_status(result: dict[str, Any], route: dict[str, Any]) -> tuple[str, str]:
    reported_model = result.get("model")
    if isinstance(reported_model, str) and reported_model and reported_model != route.get("model"):
        return "failed", (
            f"native child route mismatch: expected {route.get('model')!r}, "
            f"got {reported_model!r}"
        )
    if (
        result.get("status") == "completed"
        and result.get("exit_reason") == "completed"
        and (reported_model is None or reported_model == "" or reported_model == route.get("model"))
        and isinstance(result.get("summary"), str)
        and result["summary"].strip()
    ):
        return "succeeded", ""
    if result.get("status") == "interrupted" or result.get("exit_reason") == "interrupted":
        return "stopped", str(result.get("error") or "Hermes child was interrupted")
    return "failed", str(
        result.get("error")
        or f"Hermes child ended with status={result.get('status')!r}, exit_reason={result.get('exit_reason')!r}"
    )


def _run_workflow_wave(
    workflow: Any,
    run_dir: Path,
    plan: dict[str, Any],
    trusted_manifest_sha256: str,
    ready: list[str],
    parent: Any,
    runtime: dict[str, Any],
    max_iterations: int,
    owner_kwargs: dict[str, Any],
) -> dict[str, Any]:
    from concurrent.futures import FIRST_COMPLETED, wait
    from tools.daemon_pool import DaemonThreadPoolExecutor

    by_id = {task["id"]: task for task in plan["tasks"]}
    prepared: list[tuple[int, dict[str, Any], dict[str, Any], Any, str]] = []
    launch_errors: list[dict[str, Any]] = []
    pool = DaemonThreadPoolExecutor(
        max_workers=max(1, len(ready)), thread_name_prefix="routed-workflow"
    )
    futures: dict[Any, tuple[int, dict[str, Any], dict[str, Any], Any, str]] = {}
    try:
        for index, task_id in enumerate(ready):
            task = by_id[task_id]
            child = None
            token = ""
            try:
                token = workflow.claim_task(
                    run_dir, task_id, trusted_manifest_sha256
                )
                envelope, receipt = _workflow_task_envelope(
                    workflow,
                    run_dir,
                    task,
                    trusted_manifest_sha256,
                )
                child = _prepare_workflow_child(
                    parent,
                    envelope,
                    receipt,
                    index,
                    len(ready),
                    max_iterations,
                    runtime["build"],
                )
                handle = child._subagent_id
                _install_close_witness(
                    child, run_dir, task_id, handle, token
                )
                workflow.start_task(
                    run_dir,
                    task_id,
                    handle,
                    token,
                    trusted_manifest_sha256,
                )
                prepared.append((index, envelope, receipt, child, token))
                future = pool.submit(
                    _run_exact_child,
                    runtime["run"],
                    index,
                    envelope,
                    receipt,
                    child,
                    parent,
                    owner_kwargs,
                )
                futures[future] = prepared[-1]
            except Exception as exc:
                error_text = str(exc)
                if child is not None:
                    close = getattr(child, "close", None)
                    if callable(close):
                        try:
                            close()
                        except Exception as close_exc:
                            error_text += f"; child close failed: {close_exc}"
                try:
                    if not token:
                        raise RuntimeError("task claim was not acquired")
                    _plan, current_state = workflow.load_run(
                        run_dir, trusted_manifest_sha256
                    )
                    current = current_state["tasks"][task_id]
                    if current["status"] == "launching":
                        workflow.abort_launch(
                            run_dir,
                            task_id,
                            error_text,
                            token,
                            trusted_manifest_sha256,
                        )
                    elif current["status"] == "running":
                        handle = current["handle"]
                        if not _native_handle_is_closed(
                            runtime,
                            run_dir,
                            task_id,
                            handle,
                            token,
                        ):
                            raise RuntimeError(
                                "native child did not produce an exact close witness"
                            )
                        workflow.finish_task(
                            run_dir,
                            task_id,
                            "failed",
                            "",
                            "",
                            error_text,
                            True,
                            handle,
                            token,
                            trusted_manifest_sha256,
                        )
                except Exception as state_exc:
                    launch_errors.append({
                        "task_id": task_id,
                        "error": error_text,
                        "state_error": str(state_exc),
                    })
                else:
                    launch_errors.append({"task_id": task_id, "error": error_text})

        pending = set(futures)
        done_results: list[
            tuple[dict[str, Any], tuple[int, dict[str, Any], dict[str, Any], Any, str]]
        ] = []
        interrupt_sent = False
        while pending:
            if getattr(parent, "_interrupt_requested", False) is True and not interrupt_sent:
                workflow.request_stop(run_dir, trusted_manifest_sha256)
                interrupt = runtime.get("interrupt")
                if callable(interrupt):
                    for future in pending:
                        interrupt(futures[future][3]._subagent_id)
                interrupt_sent = True
            done, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
            for future in done:
                metadata = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "task_index": metadata[0],
                        "status": "failed",
                        "exit_reason": "error",
                        "summary": None,
                        "error": str(exc),
                        "model": metadata[2]["route"]["model"],
                    }
                done_results.append((result, metadata))

        completion_records = []
        for result, metadata in done_results:
            index, envelope, receipt, child, token = metadata
            task_id = envelope["id"]
            handle = child._subagent_id
            result_path = workflow.task_artifact_path(
                run_dir, task_id, "result.json"
            )
            workflow.atomic_json(
                result_path,
                _safe_json({
                    "task_id": task_id,
                    "route_receipt": receipt,
                    "native_result": result,
                }),
            )
            status, error = _native_result_status(result, receipt["route"])
            output_path = workflow.task_artifact_path(
                run_dir, task_id, "output.md"
            )
            if status == "succeeded":
                _atomic_text(output_path, result["summary"])
            completion_records.append({
                "index": index,
                "task": envelope,
                "receipt": receipt,
                "child": child,
                "token": token,
                "handle": handle,
                "result": result,
                "status": status,
                "error": error,
                "output": str(output_path) if status == "succeeded" else "",
            })

        if completion_records:
            ordered = sorted(completion_records, key=lambda item: item["index"])
            native_results = [item["result"] for item in ordered]
            task_list = [{"goal": ""} for _ in ready]
            for item in ordered:
                task_list[item["index"]] = item["task"]
            runtime["finalize"](
                native_results,
                task_list,
                [(item["index"], item["task"], item["child"]) for item in ordered],
                parent,
            )
            for item in ordered:
                if not _native_handle_is_closed(
                    runtime,
                    run_dir,
                    item["task"]["id"],
                    item["handle"],
                    item["token"],
                ):
                    launch_errors.append({
                        "task_id": item["task"]["id"],
                        "error": "native handle lacks an exact close witness after child completion",
                    })
                    continue
                workflow.finish_task(
                    run_dir,
                    item["task"]["id"],
                    item["status"],
                    item["output"],
                    str(item["result"].get("summary") or ""),
                    item["error"],
                    True,
                    item["handle"],
                    item["token"],
                    trusted_manifest_sha256,
                )
        return {
            "completed": len(completion_records),
            "launch_errors": launch_errors,
            "abandoned_after_interrupt": False,
        }
    finally:
        pool.shutdown(wait=True, cancel_futures=False)


def _run_workflow(
    run_dir: Path,
    parent: Any,
    runtime: dict[str, Any],
    *,
    owner_kwargs: dict[str, Any],
) -> dict[str, Any]:
    workflow = _workflow_state_module()
    run_dir = workflow.resolve_run(str(run_dir))
    plan, _state, trusted_manifest_sha256 = _validate_hermes_workflow_run(
        workflow, run_dir
    )
    if int(getattr(parent, "_delegate_depth", 0) or 0) != 0:
        raise RuntimeError("routed_workflow may run only from a top-level Hermes parent")
    config = runtime["load_config"]()
    max_iterations = config.get("max_iterations", runtime.get("default_iterations", _MAX_ITERATIONS))
    if not isinstance(max_iterations, int) or isinstance(max_iterations, bool) or max_iterations < 1:
        raise RuntimeError("delegation.max_iterations must be a positive integer")
    native_limit = runtime["get_max_children"]()
    limit = min(plan["max_workers"], native_limit)
    if limit < 1:
        raise RuntimeError("Hermes max_concurrent_children must be positive")

    waves = []
    while True:
        ready = workflow.ready_tasks(run_dir, trusted_manifest_sha256)
        if getattr(parent, "_interrupt_requested", False) is True:
            workflow.request_stop(run_dir, trusted_manifest_sha256)
            break
        if not ready:
            break
        wave = _run_workflow_wave(
            workflow,
            run_dir,
            plan,
            trusted_manifest_sha256,
            ready[:limit],
            parent,
            runtime,
            max_iterations,
            owner_kwargs,
        )
        waves.append(wave)
        if wave["abandoned_after_interrupt"]:
            break
    snapshot = _workflow_snapshot(
        workflow, run_dir, trusted_manifest_sha256
    )
    snapshot["success"] = snapshot["status"] == "succeeded"
    snapshot["waves"] = waves
    return snapshot


def _handle(params: dict[str, Any], **_kwargs: Any) -> str:
    try:
        from agent.subagent_lifecycle import get_active_subagent_parent

        parent = get_active_subagent_parent()
        if parent is None:
            raise RuntimeError("No active Hermes parent session is available")
        parent_session_id = str(getattr(parent, "session_id", "") or "")
        if not parent_session_id:
            raise RuntimeError("active Hermes parent has no session id")
        runtime = _private_runtime()
        if runtime["is_paused"]():
            raise RuntimeError("Delegation spawning is paused")
        depth = int(getattr(parent, "_delegate_depth", 0) or 0)
        max_depth = runtime["get_max_depth"]()
        if depth >= max_depth:
            raise RuntimeError(
                f"Delegation depth limit reached (depth={depth}, max_spawn_depth={max_depth})"
            )
        raw_tasks = params.get("tasks")
        if not isinstance(raw_tasks, list) or not 1 <= len(raw_tasks) <= 4:
            raise ValueError("tasks must contain 1-4 entries")
        tasks = [_normalize_task(raw) for raw in raw_tasks]
        if len({task["id"] for task in tasks}) != len(tasks):
            raise ValueError("task ids must be unique")
        max_children = runtime["get_max_children"]()
        if len(tasks) > max_children:
            raise ValueError(
                f"Too many tasks: {len(tasks)} provided, but max_concurrent_children is {max_children}"
            )
        config = runtime["load_config"]()
        max_iterations = config.get(
            "max_iterations", runtime["default_iterations"]
        )
        if not isinstance(max_iterations, int) or isinstance(max_iterations, bool) or max_iterations < 1:
            raise RuntimeError("delegation.max_iterations must be a positive integer")
        try:
            from gateway.session_context import get_session_env

            owner_session_id = get_session_env("HERMES_UI_SESSION_ID", "")
        except Exception:
            owner_session_id = ""
        owner_transport, owner_record = runtime["capture_owner"](owner_session_id)
        owner_kwargs = {
            "owner_session_id": owner_session_id or None,
            "owner_transport": owner_transport,
            "owner_session_record": owner_record,
        }
        prepared = []
        try:
            for index, task in enumerate(tasks):
                receipt = _select_or_reuse(
                    parent_session_id, task, max_iterations
                )
                child = _prepare_child(
                    parent,
                    task,
                    receipt,
                    index,
                    len(tasks),
                    max_iterations,
                    build=runtime["build"],
                )
                prepared.append((index, task, receipt, child))
        except Exception:
            for _index, _task, _receipt, child in prepared:
                close = getattr(child, "close", None)
                if callable(close):
                    close()
            raise
        results = _execute_children(
            prepared,
            parent,
            runtime["run"],
            runtime["finalize"],
            max_children=max_children,
            owner_kwargs=owner_kwargs,
        )
        wrapped = []
        by_index = {index: (task, receipt) for index, task, receipt, _child in prepared}
        for result in results:
            task, receipt = by_index[result["task_index"]]
            wrapped.append(
                {
                    "task_id": task["id"],
                    "route": receipt["route"],
                    "route_receipt": receipt,
                    "result": result,
                }
            )
        success = all(item["result"].get("status") == "completed" for item in wrapped)
        return json.dumps({"success": success, "results": wrapped}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


def _workflow_handle(params: dict[str, Any], **_kwargs: Any) -> str:
    try:
        action = str(params.get("action") or "").strip()
        if action not in {"init", "run", "status", "resume"}:
            raise ValueError("action must be init, run, status, or resume")
        workflow = _workflow_state_module()
        if action == "init":
            plan_value = str(params.get("plan_path") or "").strip()
            if not plan_value:
                raise ValueError("action=init requires plan_path")
            if params.get("run_dir"):
                raise ValueError("action=init does not accept run_dir")
            root_value = str(params.get("run_root") or "").strip()
            run_root = (
                Path(root_value)
                if root_value
                else _hermes_home() / "workflows" / "runs"
            )
            variables = params.get("variables", {})
            run_dir = _initialize_workflow(Path(plan_value), run_root, variables)
            trusted_manifest_sha256 = _verify_workflow_binding(workflow, run_dir)
            snapshot = _workflow_snapshot(
                workflow, run_dir, trusted_manifest_sha256
            )
            snapshot["success"] = True
            return json.dumps(snapshot, ensure_ascii=False)

        run_value = str(params.get("run_dir") or "").strip()
        if not run_value:
            raise ValueError(f"action={action} requires run_dir")
        if params.get("plan_path") or params.get("run_root") or params.get("variables"):
            raise ValueError(f"action={action} does not accept init-only fields")
        run_dir = workflow.resolve_run(run_value)
        if action == "status":
            _plan, _state, trusted_manifest_sha256 = (
                _validate_hermes_workflow_run(workflow, run_dir)
            )
            snapshot = _workflow_snapshot(
                workflow, run_dir, trusted_manifest_sha256
            )
            snapshot["success"] = True
            return json.dumps(snapshot, ensure_ascii=False)
        if action == "resume":
            retry_failed = params.get("retry_failed", False)
            retry_interrupted = params.get("retry_interrupted", False)
            if not isinstance(retry_failed, bool) or not isinstance(retry_interrupted, bool):
                raise ValueError("retry flags must be true or false")
            with workflow.execution_lock(run_dir):
                _plan, _state, trusted_manifest_sha256 = (
                    _validate_hermes_workflow_run(workflow, run_dir)
                )
                if retry_interrupted:
                    runtime = _private_runtime()
                    active = {
                        entry.get("subagent_id")
                        for entry in runtime["list_active"]()
                        if isinstance(entry, dict)
                    }
                    _plan, state = workflow.load_run(
                        run_dir, trusted_manifest_sha256
                    )
                    unsafe_retries = []
                    for task_id, current in state["tasks"].items():
                        handle = current.get("handle", "")
                        if current["status"] not in {"running", "stopped"} or not handle:
                            continue
                        token = current.get("launch_token", "")
                        if handle in active or not _native_handle_is_closed(
                            runtime,
                            run_dir,
                            task_id,
                            handle,
                            token,
                        ):
                            unsafe_retries.append(handle)
                    if unsafe_retries:
                        raise RuntimeError(
                            "cannot retry interrupted workflow tasks without exact native close witnesses: "
                            + ", ".join(sorted(unsafe_retries))
                        )
                workflow.resume_run(
                    run_dir,
                    retry_failed,
                    retry_interrupted,
                    trusted_manifest_sha256,
                )
                snapshot = _workflow_snapshot(
                    workflow, run_dir, trusted_manifest_sha256
                )
                snapshot["success"] = True
                return json.dumps(snapshot, ensure_ascii=False)

        from agent.subagent_lifecycle import get_active_subagent_parent

        parent = get_active_subagent_parent()
        if parent is None:
            raise RuntimeError("No active Hermes parent session is available")
        runtime = _private_runtime()
        if runtime["is_paused"]():
            raise RuntimeError("Delegation spawning is paused")
        with workflow.execution_lock(run_dir):
            result = _run_workflow(
                run_dir,
                parent,
                runtime,
                owner_kwargs=_workflow_owner_kwargs(runtime),
            )
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


def register(ctx: Any) -> None:
    schema = {
        "name": "routed_delegate_task",
        "description": (
            "Delegate 1-4 independent tasks. Classify requirements only; the tool deterministically "
            "selects and pins each exact provider/model/reasoning route. Reuse a task id only for an "
            "identical task retry."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["tasks"],
            "properties": {
                "tasks": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "goal", "intelligence_tier", "latency_sensitive"],
                        "properties": {
                            "id": {"type": "string", "minLength": 1, "maxLength": 128},
                            "goal": {"type": "string", "minLength": 1, "maxLength": 16000},
                            "context": {"type": "string", "maxLength": 32000},
                            "intelligence_tier": {"enum": sorted(_TIERS)},
                            "latency_sensitive": {"type": "boolean"},
                            "failure_cost": {"enum": sorted(_FAILURE_COSTS)},
                            "task_class": {"type": "string", "minLength": 1},
                            "verifier_plan": {"type": "object"},
                            "toolsets": {"type": "array", "items": {"type": "string", "minLength": 1}},
                            "role": {"enum": sorted(_ROLES)},
                        },
                    },
                },

            },
        },
    }
    ctx.register_tool(
        name="routed_delegate_task",
        toolset="routed_delegation",
        schema=schema,
        handler=_handle,
        description=schema["description"],
        emoji="🧭",
    )
    workflow_schema = {
        "name": "routed_workflow",
        "description": (
            "Initialize, run, inspect, or explicitly resume a persisted dependency-aware workflow. "
            "The shared dynamic-workflows state owner validates the DAG and pins every child through "
            "the deterministic router; Hermes only supplies bounded native leaf workers. Use init once, "
            "then run with the returned run_dir."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["action"],
            "properties": {
                "action": {"enum": ["init", "run", "status", "resume"]},
                "plan_path": {"type": "string", "minLength": 1},
                "run_root": {"type": "string", "minLength": 1},
                "run_dir": {"type": "string", "minLength": 1},
                "variables": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
                "retry_failed": {"type": "boolean"},
                "retry_interrupted": {"type": "boolean"},
            },
        },
    }
    ctx.register_tool(
        name="routed_workflow",
        toolset="routed_delegation",
        schema=workflow_schema,
        handler=_workflow_handle,
        description=workflow_schema["description"],
        emoji="🕸️",
    )
