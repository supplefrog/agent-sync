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
_INTERRUPT_GRACE_SECONDS = 2.0
_ACCOUNTING_POLL_SECONDS = 0.05


def _epoch(parent):
    return (getattr(parent, "session_id", None), getattr(parent, "_current_turn_id", None))


def _own_child(child, parent):
    """Take ownership immediately after the native constructor returns."""
    child._routed_home = _hermes_home()
    child._routed_context = contextvars.copy_context()
    try:
        from hermes_constants import set_hermes_home_override
    except ImportError:
        pass  # injected historical test seam; current native resolver requires it
    else:
        child._routed_context.run(set_hermes_home_override, child._routed_home)
    child._routed_epoch = _epoch(parent)
    child._routed_started = False
    child._routed_closed = False
    child._routed_accounting = {"status": "pending"}
    child._routed_accounting_lock = threading.Lock()
    child._routed_accounting_done = threading.Event()
    original = getattr(child, "close", None)
    if callable(original):
        def close():
            result = original()
            child._routed_closed = True
            return result
        child.close = close


def _dispose_unentered(child, parent, detach=None):
    """Independent cleanup obligations; never close an ambiguous native turn."""
    errors = []
    if getattr(child, "_routed_started", False):
        return [{"phase": "close", "error_type": "ExecutionUnknown"}]
    try:
        child.close()
    except BaseException as exc:
        errors.append({"phase": "close", "error_type": type(exc).__name__})
    try:
        if detach is not None:
            detach(parent, child)
        elif hasattr(parent, "_active_children"):
            # Synthetic/older injected seams only; current native resolves detach.
            lock = getattr(parent, "_active_children_lock", _PIN_LOCK)
            with lock:
                if child in parent._active_children:
                    parent._active_children.remove(child)
    except BaseException as exc:
        errors.append({"phase": "detach", "error_type": type(exc).__name__})
    child._routed_cleanup_errors = errors
    return errors


def _definitive_result(result):
    return (isinstance(result, dict) and result.get("status") in {"completed", "failed", "interrupted"}
            and result.get("exit_reason") not in {None, "timeout"}
            and result.get("execution_outcome") != "unknown"
            and result.get("closure_confirmed") is not False)


class _Admission:
    """submit may enqueue before throwing. The callable needs separate consent."""
    def __init__(self):
        self.event = threading.Event()
        self.allowed = False

    def resolve(self, allowed):
        self.allowed = allowed
        self.event.set()

    def run(self, fn, *args):
        self.event.wait()
        if not self.allowed:
            return None  # revoked queue entries never enter native execution
        return fn(*args)


def _submit_owned(pool, fn, *args):
    gate = _Admission()
    try:
        future = pool.submit(gate.run, fn, *args)
    except BaseException:
        gate.resolve(False)
        raise
    gate.resolve(True)
    return future


def _background(context, fn):
    # add_done_callback can call inline: its only job is starting this daemon.
    thread = threading.Thread(target=context.copy().run, args=(fn,), daemon=True,
                              name="routed-accounting")
    thread.start()
    return thread


class _AccountingParent:
    """Keep launch identity stable and reject writes after an observed epoch change.

    Native session resets do not share a generation lock with finalization. This
    guards observed changes, not an atomic reset/accounting transaction.
    """
    def __init__(self, parent, epoch):
        object.__setattr__(self, "_parent", parent)
        object.__setattr__(self, "_epoch", epoch)
        object.__setattr__(self, "_memory_manager", getattr(parent, "_memory_manager", None))

    def __getattr__(self, key):
        if key in {"session_id", "_current_turn_id"}:
            return self._epoch[0 if key == "session_id" else 1]
        return getattr(self._parent, key)

    def __setattr__(self, key, value):
        if _epoch(self._parent) != self._epoch:
            raise RuntimeError("launch accounting epoch changed")
        setattr(self._parent, key, value)


def _schedule_finalization(finalize, parent, item, result, persist=None):
    index, task, _receipt, child = item[:4]
    status = child._routed_accounting
    with child._routed_accounting_lock:
        if getattr(child, "_routed_finalization_scheduled", False):
            return status
        child._routed_finalization_scheduled = True

    def save():
        if persist is not None:
            try:
                persist(dict(status))
            except BaseException as exc:
                status["persistence_error_type"] = type(exc).__name__

    try:
        displayed = _display_result(child, parent, result)
    except BaseException as exc:
        # Projection failure cannot discard independent native accounting.
        displayed = _safe_json(result)
        displayed["summary"] = None
        status["display_error_type"] = type(exc).__name__

    def account():
        try:
            if child._routed_started and not _definitive_result(result):
                status.update(status="pending-execution", error_type="ExecutionUnknown")
                return
            if _epoch(parent) != child._routed_epoch:
                status.update(status="pending-epoch", error_type="AccountingEpochChanged")
                return
            tasks = [{"goal": ""} for _ in range(index)] + [task]
            # Native finalization mutates result entries; keep raw evidence intact.
            entries = [_safe_json(displayed)]
            options = {"summary_budget_applied": True} if callable(getattr(child, "_routed_budget_summary", None)) else {}
            finalize(entries, tasks, [(index, task, child)],
                     _AccountingParent(parent, child._routed_epoch), **options)
            child._routed_finalized_result = entries[0]
            status["status"] = ("failed" if status.get("display_error_type") else
                                "returned" if _epoch(parent) == child._routed_epoch else "pending-epoch")
        except BaseException as exc:
            status.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        finally:
            save()
            child._routed_accounting_done.set()
    save()
    try:
        _background(child._routed_context, account)
    except BaseException as exc:
        status.update(status="failed", error_type=type(exc).__name__)
        save()
        child._routed_accounting_done.set()
    return status


def _poll_accounting(children):
    deadline = time.monotonic() + _ACCOUNTING_POLL_SECONDS
    for child in children:
        child._routed_accounting_done.wait(max(0, deadline - time.monotonic()))


def _display_result(child, parent, result):
    """Keep full execution evidence; budget only the derived native summary."""
    identity = _sha(_safe_json(result))
    cached = getattr(child, "_routed_display_result", None)
    if cached is not None:
        if child._routed_display_input_sha256 != identity:
            raise RuntimeError("display projection input changed for the owned attempt")
        return _safe_json(cached)
    displayed = _safe_json(result)
    budget = getattr(child, "_routed_budget_summary", None)
    if callable(budget):
        child._routed_context.copy().run(budget, [displayed], parent, summary_count=child._routed_summary_count)
    child._routed_display_input_sha256 = identity
    child._routed_display_result = _safe_json(displayed)
    return displayed


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


def _load_selector(selector_path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("routed_delegation_selector", selector_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load route selector: {selector_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _selector_and_catalog(version: int = 2) -> tuple[Any, dict[str, Any], Path]:
    if version not in {2, 3}:
        raise ValueError("route selector version must be 2 or 3")
    skill = _route_skill()
    selector_path = skill / "scripts" / "route_selector.py"
    catalog_path = skill / "references" / (
        "current-gpt-catalog.json"
        if version == 2
        else "current-task-route-catalog.json"
    )
    module = _load_selector(selector_path)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    module.validate_catalog(catalog)
    return module, catalog, catalog_path


def _task_request_module() -> Any:
    path = _route_skill() / "scripts" / "task_request.py"
    spec = importlib.util.spec_from_file_location("routed_delegation_task_request", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load task request materializer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "materialize", None)):
        raise RuntimeError("task request owner has no materialize function")
    return module


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
    legacy = [task["id"] for task in plan["tasks"] if not ({"intelligence_tier", "route_request"} & task.keys())]
    if legacy:
        raise ValueError(
            "Hermes workflows require router-selected intelligence_tier tasks or V3 route_request; "
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
    if not isinstance(manifest, dict) or manifest.get("schema_version") not in {2, 3}:
        raise RuntimeError("Hermes workflow run lacks a supported version 2/3 integrity manifest")
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
    allowed = {
        "id", "goal", "context", "toolsets", "role", "intelligence_tier",
        "latency_sensitive", "failure_cost", "task_class", "verifier_plan",
        "route_request",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"task has unknown fields: {', '.join(sorted(unknown))}")
    task_id = str(raw.get("id") or "").strip()
    goal = str(raw.get("goal") or "").strip()
    role = str(raw.get("role") or "leaf").strip()
    if not task_id or len(task_id) > 128:
        raise ValueError("task id must contain 1-128 characters")
    if not goal or len(goal) > 16000:
        raise ValueError(f"task {task_id!r} goal must contain 1-16000 characters")
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
    has_route_request = "route_request" in raw
    route_request = raw.get("route_request")
    legacy_fields = {
        "intelligence_tier", "latency_sensitive", "failure_cost", "task_class",
        "verifier_plan",
    }
    if has_route_request and legacy_fields.intersection(raw):
        raise ValueError(f"task {task_id!r} conflicts between v2 tier fields and route_request")
    normalized = {
        "id": task_id,
        "goal": goal,
        "context": context,
        "toolsets": toolsets,
        "role": role,
    }
    if has_route_request:
        required = {
            "schema_version", "task_class", "requirements", "verifier", "effects",
            "failure_cost", "deterministic", "budget",
        }
        if not isinstance(route_request, dict) or set(route_request) != required:
            raise ValueError(f"task {task_id!r} route_request must contain exactly the v3 template fields")
        if route_request.get("schema_version") != 3:
            raise ValueError(f"task {task_id!r} route_request schema_version must be 3")
        deterministic = route_request.get("deterministic")
        if isinstance(deterministic, dict) and "input_sha256" in deterministic:
            raise ValueError(f"task {task_id!r} deterministic input_sha256 is controller-owned")
        try:
            _task_request_module().input_digest(route_request)
            normalized["route_request"] = json.loads(
                json.dumps(route_request, ensure_ascii=False, allow_nan=False)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"task {task_id!r} route_request must be finite JSON") from exc
        return normalized

    tier = str(raw.get("intelligence_tier") or "").strip()
    latency = raw.get("latency_sensitive")
    failure_cost = str(raw.get("failure_cost") or "medium").strip()
    verifier_plan = raw.get("verifier_plan", {"kind": "none"})
    if tier not in _TIERS:
        raise ValueError(f"task {task_id!r} has invalid intelligence_tier")
    if not isinstance(latency, bool):
        raise ValueError(f"task {task_id!r} latency_sensitive must be true or false")
    if failure_cost not in _FAILURE_COSTS:
        raise ValueError(f"task {task_id!r} has invalid failure_cost")
    if not isinstance(verifier_plan, dict):
        raise ValueError(f"task {task_id!r} verifier_plan must be an object")
    normalized.update({
        "intelligence_tier": tier,
        "latency_sensitive": latency,
        "failure_cost": failure_cost,
        "task_class": str(raw.get("task_class") or "delegated-agent-task").strip(),
        "verifier_plan": verifier_plan,
    })
    return normalized


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
            if existing.get("route_version") == 3:
                raise RuntimeError(f"task {task['id']!r} already has a v3 route pin")
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


def _v3_input_descriptor(task: dict[str, Any], max_iterations: int) -> dict[str, Any]:
    descriptor = {
        "task_id": task["id"],
        "goal": task["goal"],
        "context": task.get("context"),
        "toolsets": task.get("toolsets"),
        "role": task["role"],
        "max_iterations": max_iterations,
    }
    if "_native_envelope" in task:
        descriptor["native_envelope"] = task["_native_envelope"]
    return descriptor


def _v3_native_contract() -> dict[str, Any]:
    """Disk-source identity for the supported native seam, not server attestation."""
    import run_agent
    root = Path(run_agent.__file__).resolve().parent
    files = (
        "run_agent.py", "tools/delegate_tool.py", "tools/delegate_tool_config.py",
        "tools/delegate_tool_toolsets.py", "tools/delegate_tool_progress.py",
        "tools/delegate_tool_child_run.py", "tools/delegate_tool_results.py",
        "agent/agent_init.py", "agent/system_prompt.py", "agent/prompt_builder.py",
        "agent/chat_completion_helpers.py", "agent/transports/codex.py",
    )
    return {"runtime": "hermes-delegate/native-source-v1",
            "sources": {name: _sha((root / name).read_bytes()) for name in files}}


def _v3_profile_files(home: Path) -> dict[str, Any]:
    return {name: _sha((home / name).read_bytes()) if (home / name).is_file() else None
            for name in ("SOUL.md", "config.yaml")}


def _v3_native_envelope(parent: Any, task: dict[str, Any]) -> dict[str, Any]:
    """Hash inherited context; retain no extra prompt or prefill body in pins."""
    from tools.delegate_tool_config import _get_max_spawn_depth, _get_orchestrator_enabled
    from tools.delegate_tool_toolsets import _resolve_child_toolsets
    from tools.delegate_tool_progress import _build_child_system_prompt, _resolve_workspace_hint
    depth = int(getattr(parent, "_delegate_depth", 0) or 0) + 1
    maximum = _get_max_spawn_depth()
    role = "orchestrator" if _get_orchestrator_enabled() and depth < maximum else "leaf"
    enabled, disabled = _resolve_child_toolsets(parent, task["toolsets"], role)
    prompt = _build_child_system_prompt(task["goal"], task.get("context"),
        workspace_path=_resolve_workspace_hint(parent), role=role,
        max_spawn_depth=maximum, child_depth=depth)
    return {"effective_role": role, "depth": depth,
            "enabled_toolsets": enabled, "disabled_toolsets": disabled,
            "child_prompt_sha256": _sha(prompt),
            "prefill_sha256": _sha(getattr(parent, "prefill_messages", None) or []),
            "home": str(_hermes_home().resolve()),
            "profile_files": _v3_profile_files(_hermes_home())}


def _validate_v3_child(child: Any, task: dict[str, Any], pin: dict[str, Any]) -> None:
    expected = task["_native_envelope"]
    actual = {"effective_role": getattr(child, "_delegate_role", None),
              "depth": getattr(child, "_delegate_depth", None),
              "enabled_toolsets": getattr(child, "enabled_toolsets", None),
              "disabled_toolsets": getattr(child, "disabled_toolsets", None),
              "child_prompt_sha256": _sha(getattr(child, "ephemeral_system_prompt", None)),
              "prefill_sha256": _sha(getattr(child, "prefill_messages", None) or []),
              "home": str(child._routed_home.resolve()),
              "profile_files": _v3_profile_files(child._routed_home)}
    if actual != expected:
        raise RuntimeError("native child context/tools/role differ from the pinned execution input")
    required = pin["request"]["requirements"]
    names = getattr(child, "valid_tool_names", None)
    if names is None or set(names) != set(required["tools"]):
        raise RuntimeError("actual native tools differ from the v3 declared tools")
    capacity = getattr(getattr(child, "context_compressor", None), "context_length", None)
    if not isinstance(capacity, int) or capacity < required["context_tokens"]:
        raise RuntimeError("native context capacity does not meet the pinned requirement")


def _guard_v3_child(child: Any, task: dict[str, Any], pin: dict[str, Any]) -> None:
    _validate_v3_child(child, task, pin)
    original = child._build_api_kwargs
    # Freeze the controller's expected envelope; later task mutation cannot move it.
    frozen_task, frozen_pin = _safe_json(task), _safe_json(pin)
    def checked(*args: Any, **kwargs: Any) -> Any:
        _validate_v3_child(child, frozen_task, frozen_pin)
        return original(*args, **kwargs)
    child._build_api_kwargs = checked


def _selector_identity(selector_path: Path) -> dict[str, str]:
    return {
        "locator": str(selector_path.resolve()),
        "sha256": _sha(selector_path.read_bytes()),
    }


def _validate_v3_dispatch(
    dispatch: Any, decision: dict[str, Any], request: dict[str, Any], *, surface: str = _SURFACE
) -> None:
    if not isinstance(dispatch, dict) or dispatch.get("decision_id") != decision.get("decision_id"):
        raise RuntimeError("v3 dispatch does not preserve the selected decision identity")
    kind = dispatch.get("kind")
    if kind not in {"model", "deterministic", "parent", "defer"}:
        raise RuntimeError("v3 selector returned an unsupported dispatch kind")
    if kind != "model":
        if decision.get("route") is not None or dispatch.get("route") is not None:
            raise RuntimeError("non-model v3 dispatch unexpectedly contains a model route")
        return
    route = dispatch.get("route")
    if not isinstance(route, dict) or route != decision.get("route"):
        raise RuntimeError("v3 model dispatch changed the selected route")
    required = request["requirements"]
    actual = (
        route.get("host"),
        route.get("transport"),
        route.get("provider"),
        route.get("model"),
        route.get("reasoning_effort"),
    )
    if (
        actual[0] != "hermes"
        or surface not in {_SURFACE, _WORKFLOW_SURFACE}
        or actual[1] != surface
        or actual[2] not in _ALLOWED_PROVIDERS
        or not all(isinstance(value, str) and value for value in actual[3:])
    ):
        raise RuntimeError("v3 route has an unsupported host/transport/provider tuple")
    if required.get("host") != actual[0] or required.get("transport") != actual[1]:
        raise RuntimeError("v3 route does not match the materialized host/transport requirement")
    for field in ("model", "reasoning_effort"):
        if required.get(field) is not None and required[field] != route.get(field):
            raise RuntimeError(f"v3 route does not match required {field}")
    contract = _v3_native_contract()
    if route.get("runtime") != contract["runtime"] or route.get("contract_sha256") != _sha(contract):
        raise RuntimeError("v3 route native runtime/source contract differs from installed Hermes")


def _select_or_reuse_v3(
    parent_session_id: str, task: dict[str, Any], max_iterations: int
) -> dict[str, Any]:
    descriptor = _v3_input_descriptor(task, max_iterations)
    template = task["route_request"]
    path = _pin_path(parent_session_id)
    with _PIN_LOCK:
        store = _read_pins(path)
        existing = store["tasks"].get(task["id"])
        selector_path = _route_skill() / "scripts" / "route_selector.py"
        identity = _selector_identity(selector_path)
        identity["consumer_sha256"] = _sha(Path(__file__).read_bytes())
        identity["materializer_sha256"] = _sha((_route_skill() / "scripts/task_request.py").read_bytes())
        materializer = _task_request_module()
        if existing is not None:
            selector = _load_selector(selector_path)
            if existing.get("route_version") != 3:
                raise RuntimeError(f"task {task['id']!r} already has a v2 route pin")
            payload = {key: value for key, value in existing.items() if key != "pin_sha256"}
            if existing.get("pin_sha256") != _sha(payload):
                raise RuntimeError(f"task {task['id']!r} v3 route pin failed integrity validation")
            if existing.get("selector_identity") != identity:
                raise RuntimeError("v3 pinned selector identity is no longer admitted")
            request = materializer.materialize(
                template,
                task_id=task["id"],
                host="hermes",
                transport=_SURFACE,
                input_descriptor=descriptor,
                as_of=existing["request"]["as_of"],
            )
            binding = {"input_descriptor": descriptor, "template": template}
            if existing.get("binding") != binding or existing.get("request") != request:
                raise RuntimeError(f"task {task['id']!r} already pins a different task or requirement")
            dispatch = selector.dispatch_decision(
                existing["decision"], existing["catalog"], existing["request"]
            )
            if dispatch != existing.get("dispatch"):
                raise RuntimeError("v3 pinned dispatch decision changed on replay")
            _validate_v3_dispatch(dispatch, existing["decision"], existing["request"])
            return existing

        selector, current_catalog, catalog_path = _selector_and_catalog(version=3)
        request = materializer.materialize(
            template,
            task_id=task["id"],
            host="hermes",
            transport=_SURFACE,
            input_descriptor=descriptor,
        )
        decision = selector.decide_route(
            current_catalog, request, catalog_locator=str(catalog_path.resolve())
        )
        dispatch = selector.dispatch_decision(decision, current_catalog, request)
        _validate_v3_dispatch(dispatch, decision, request)
        payload = {
            "route_version": 3,
            "binding": {"input_descriptor": descriptor, "template": template},
            "request": request,
            "catalog": current_catalog,
            "selector_identity": identity,
            "decision": decision,
            "dispatch": dispatch,
        }
        entry = {**payload, "pin_sha256": _sha(payload)}
        store["tasks"][task["id"]] = entry
        _write_pins(path, store)
        return entry


def _private_runtime() -> dict[str, Any]:
    from tools import delegate_tool
    from tools.delegate_tool_child_run import _detach_child
    from hermes_constants import set_hermes_home_override
    from agent.chat_completion_helpers import (
        _build_api_kwargs_for_mode,
        _reasoning_config_for_wire,
    )
    from agent.transports.codex import ResponsesApiTransport
    from tools import delegate_tool_results

    build = getattr(delegate_tool, "_build_child_preserving_parent_tools", None)
    run = getattr(delegate_tool, "_run_single_child", None)
    finalize, budget_summary = _summary_runtime_adapter(
        _native_finalizer(delegate_tool), delegate_tool_results
    )
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
        _detach_child,
        set_hermes_home_override,
    )
    if not all(callable(value) for value in required_callables) or not isinstance(
        default_iterations, int
    ):
        raise RuntimeError("installed Hermes delegation seam is incompatible")
    required = {"task_index", "goal", "context", "toolsets", "model", "parent_agent", "role", "max_iterations", "task_count"}
    if not required.issubset(inspect.signature(build).parameters) and not any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in inspect.signature(build).parameters.values()
    ):
        raise RuntimeError("installed Hermes child builder contract changed")
    for fn, parameters in (
        (_reasoning_config_for_wire, {"agent"}),
        (_build_api_kwargs_for_mode, {"agent", "api_messages", "tools_for_api"}),
        (ResponsesApiTransport.build_kwargs, {"self", "model", "messages", "tools"}),
    ):
        if not callable(fn) or not parameters.issubset(inspect.signature(fn).parameters):
            raise RuntimeError("installed Hermes native request-construction interface is unsupported")
    return {
        "build": build,
        "run": run,
        "finalize": finalize,
        "budget_summary": budget_summary,
        "get_max_children": get_max_children,
        "get_max_depth": get_max_depth,
        "is_paused": is_paused,
        "load_config": load_config,
        "capture_owner": capture_owner,
        "interrupt": interrupt,
        "list_active": list_active,
        "default_iterations": default_iterations,
        "validate_request": _install_exact_request_guard,
        "detach": _detach_child,
    }


def _summary_runtime_adapter(finalize: Any, native: Any) -> tuple[Any, Any]:
    """Adapt the known split-native API without changing process-global functions.

    Newer hosts can budget each completion using the launch batch count and skip
    a second trim during accounting. The current split host exposes the same
    native operations, but not those options. Compose its accounting primitives
    only when the *whole* finalizer body matches the known orchestration: an
    added native obligation must fail closed rather than disappear in this shim.
    Native helpers still own headroom, spill/footer, memory, hooks, cost and lock.
    """
    import ast
    import textwrap

    from tools.delegate_tool import _load_config

    budget = native._apply_summary_budget
    try:
        finalize_parameters = inspect.signature(finalize).parameters
        budget_parameters = inspect.signature(budget).parameters
        if ({"summary_count", "summary_budget_applied"}.issubset(finalize_parameters)
                and "summary_count" in budget_parameters):
            return finalize, budget
        if (set(finalize_parameters) != {"results", "task_list", "children", "parent_agent"}
                or set(budget_parameters) != {"results", "parent_agent"}):
            raise ValueError("unknown summary interface")
        for name, args in (
            ("_parent_summary_char_budget", (None, 1)),
            ("_trim_summary_with_footer", ("", 1, 0)),
            ("_parent_finalization_lock", (None,)),
            ("_notify_memory_manager", ([], [], {}, None)),
            ("_fire_subagent_stop_hooks", ([], {}, None)),
            ("_rollup_children_cost", (None, 0)),
        ):
            inspect.signature(getattr(native, name)).bind(*args)
        if not isinstance(native.DEFAULT_MAX_SUMMARY_CHARS, int):
            raise TypeError("unknown summary ceiling")
        body = ast.parse(textwrap.dedent(inspect.getsource(finalize))).body[0].body
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            body = body[1:]
        known = ast.parse(textwrap.dedent('''\
            with _parent_finalization_lock(parent_agent):
                _apply_summary_budget(results, parent_agent)
                child_by_index = {index: child for index, _task, child in children}
                _notify_memory_manager(results, task_list, child_by_index, parent_agent)
                _rollup_children_cost(parent_agent, _fire_subagent_stop_hooks(results, child_by_index, parent_agent))
        ''')).body
        if ([ast.dump(node) for node in body] != [ast.dump(node) for node in known]
                or any(finalize.__globals__.get(name) is not getattr(native, name)
                       for name in ("_parent_finalization_lock", "_apply_summary_budget",
                                    "_notify_memory_manager", "_fire_subagent_stop_hooks",
                                    "_rollup_children_cost"))):
            raise ValueError("unknown native finalization obligations")
    except (AttributeError, TypeError, ValueError, OSError, SyntaxError) as exc:
        raise RuntimeError("installed Hermes summary/finalization interface is unsupported") from exc

    def shared_budget(results, parent_agent, *, summary_count=None):
        summaries = [entry for entry in results if isinstance(entry, dict)
                     and isinstance(entry.get("summary"), str) and entry["summary"]]
        if not summaries:
            return
        count = len(summaries) if summary_count is None else summary_count
        if isinstance(count, bool) or not isinstance(count, int) or count < len(summaries):
            raise ValueError("summary_count must cover all presented summaries")
        # Same static policy as native _apply_summary_budget; only the divisor
        # differs, reserving a slice even for unfinished/failed launch siblings.
        try:
            ceiling = int(_load_config().get("max_summary_chars", native.DEFAULT_MAX_SUMMARY_CHARS))
        except (TypeError, ValueError):
            ceiling = native.DEFAULT_MAX_SUMMARY_CHARS
        candidates = [cap for cap in (ceiling, native._parent_summary_char_budget(parent_agent, count))
                      if cap and cap > 0]
        if not candidates:
            return
        cap = min(candidates)
        for entry in summaries:
            if len(entry["summary"]) <= cap:
                continue
            entry["summary"], path = native._trim_summary_with_footer(
                entry["summary"], cap, entry.get("task_index", -1)
            )
            entry["summary_truncated"] = True
            if path:
                entry["summary_full_path"] = path

    def shared_finalize(results, task_list, children, parent_agent, *,
                        summary_count=None, summary_budget_applied=False):
        with native._parent_finalization_lock(parent_agent):
            if not summary_budget_applied:
                shared_budget(results, parent_agent, summary_count=summary_count)
            child_by_index = {index: child for index, _task, child in children}
            native._notify_memory_manager(results, task_list, child_by_index, parent_agent)
            native._rollup_children_cost(
                parent_agent, native._fire_subagent_stop_hooks(results, child_by_index, parent_agent)
            )

    return shared_finalize, shared_budget


def _native_finalizer(delegate_tool: Any) -> Any:
    """Keep the old exported seam; Hermes 0.21 split its implementation owner."""
    finalize = getattr(delegate_tool, "_finalize_child_results", None)
    if callable(finalize):
        return finalize
    from tools.delegate_tool_results import _finalize_child_results

    return _finalize_child_results


def _assert_native_request_kwargs(child: Any, route: dict[str, Any], kwargs: Any) -> None:
    """Check locally constructed request arguments; this is not provider attestation."""
    if (route.get("provider") != "openai-codex" or child.provider != route["provider"]
            or getattr(child, "api_mode", None) != "codex_responses"
            or str(getattr(child, "base_url", "")).rstrip("/") != "https://chatgpt.com/backend-api/codex"):
        raise RuntimeError("unsupported exact-route native provider/transport")
    if (not isinstance(kwargs, dict) or kwargs.get("model") != route["model"]
            or not isinstance(kwargs.get("reasoning"), dict)
            or kwargs["reasoning"].get("effort") != route["reasoning_effort"]):
        raise RuntimeError("native request arguments do not preserve the pinned model and reasoning effort")
    extra = kwargs.get("extra_body") or {}
    if not isinstance(extra, dict) or any(key in extra and extra[key] != kwargs.get(key) for key in ("model", "reasoning")):
        raise RuntimeError("native request overrides conflict with the pinned route")


def _install_exact_request_guard(child: Any, route: dict[str, Any]) -> None:
    original = getattr(child, "_build_api_kwargs", None)
    if not callable(original):
        raise RuntimeError("installed Hermes child request builder is unsupported")
    # Exercise the actual native request-construction path without a transport
    # call. No task content or personal prompt enters this capability probe.
    try:
        kwargs = original([{"role": "user", "content": "Synthetic route compatibility probe."}], [])
        _assert_native_request_kwargs(child, route, kwargs)
    except Exception as exc:
        raise RuntimeError("native request construction cannot preserve this exact route") from exc
    pinned = dict(route)

    def checked_builder(*args: Any, **kwargs: Any) -> Any:
        _assert_exact_child_route(child, pinned)
        request = original(*args, **kwargs)
        _assert_native_request_kwargs(child, pinned, request)
        return request

    child._build_api_kwargs = checked_builder
    child._routed_request_contract = {
        "source": "native-request-construction", "provider_resolved_identity_verified": False,
        "provider": route["provider"], "model": route["model"], "reasoning_effort": route["reasoning_effort"],
    }


def _prepare_child(
    parent: Any,
    task: dict[str, Any],
    receipt: dict[str, Any],
    index: int,
    count: int,
    max_iterations: int,
    *,
    build: Any = None,
    validate_request: Any = None,
    on_built: Any = None,
    budget_summary: Any = None,
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
        runtime = _private_runtime()
        build = runtime["build"]
        validate_request = runtime["validate_request"]
        budget_summary = runtime["budget_summary"]
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
    if on_built is not None:
        on_built(child)
    _own_child(child, parent)
    child._routed_summary_count = count
    child._routed_budget_summary = budget_summary
    child.reasoning_config = dict(reasoning)
    session_config = getattr(child, "_session_init_model_config", None)
    if not isinstance(session_config, dict):
        if on_built is None:
            _dispose_unentered(child, parent)
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
        if validate_request is not None:
            validate_request(child, route)
    except Exception:
        if on_built is None:
            _dispose_unentered(child, parent)
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
    try:
        _assert_exact_child_route(child, receipt["route"])
    except BaseException:
        _dispose_unentered(child, parent)
        raise
    child._routed_started = True
    return run(
            task_index=index,
            goal=task["goal"],
            child=child,
            parent_agent=parent,
            **owner_kwargs,
        )


def _child_error(index: int, child: Any, error: BaseException, status: str = "error") -> dict[str, Any]:
    return {"task_index": index, "status": status, "exit_reason": "error",
            "summary": None, "error": str(error), "api_calls": 0,
            "duration_seconds": 0, "_child_role": getattr(child, "_delegate_role", None),
            "error_type": type(error).__name__,
            "execution_outcome": "unknown" if getattr(child, "_routed_started", False) else "not-started"}


def _interrupt_child(child: Any, interrupt: Any) -> None:
    """Request cooperative stopping; neither acceptance nor return proves closure."""
    try:
        accepted = callable(interrupt) and interrupt(getattr(child, "_subagent_id", ""))
        if not accepted and callable(getattr(child, "interrupt", None)):
            child.interrupt()
    except Exception:
        pass


def _execute_children(
    prepared, parent, run, finalize, *, max_children, owner_kwargs,
    interrupt=None, detach=None,
):
    from concurrent.futures import FIRST_COMPLETED, wait
    from tools.daemon_pool import DaemonThreadPoolExecutor
    results, futures, settled = [], {}, []
    pool, deadline = None, None

    def consume(future, item):
        try:
            result = future.result()
            if not isinstance(result, dict):
                raise RuntimeError("native child returned no result object")
            return result
        except BaseException as exc:
            return _child_error(item[0], item[3], exc)

    def account(item, result):
        _schedule_finalization(finalize, parent, item, result)
        settled.append((item, result))

    try:
        try:
            pool = DaemonThreadPoolExecutor(max_workers=max_children, thread_name_prefix="routed-delegate")
            for item in prepared:
                index, task, receipt, child = item
                future = _submit_owned(pool, _run_exact_child, run, index, task, receipt, child, parent, owner_kwargs)
                futures[future] = item
        except BaseException as exc:
            submitted = {item[0] for item in futures.values()}
            for item in prepared:
                if item[0] in submitted:
                    continue
                cleanup = _dispose_unentered(item[3], parent, detach)
                result = _child_error(item[0], item[3], exc)
                result["cleanup_errors"] = cleanup
                results.append(result)
                account(item, result)
            deadline = time.monotonic() + _INTERRUPT_GRACE_SECONDS

        pending = set(futures)
        signalled = set()
        while pending:
            if deadline is None and getattr(parent, "_interrupt_requested", False) is True:
                deadline = time.monotonic() + _INTERRUPT_GRACE_SECONDS
            if deadline is not None:
                for future in pending - signalled:
                    item = futures[future]
                    if future.cancel():
                        _background(item[3]._routed_context, lambda owned=item: _dispose_unentered(owned[3], parent, detach))
                    else:
                        _background(item[3]._routed_context, lambda owned=item: _interrupt_child(owned[3], interrupt))
                    signalled.add(future)
            try:
                done, pending = wait(pending, timeout=0.05, return_when=FIRST_COMPLETED)
            except BaseException:
                deadline = deadline or (time.monotonic() + _INTERRUPT_GRACE_SECONDS)
                if time.monotonic() >= deadline:
                    break
                continue
            for future in done:
                item = futures[future]
                result = consume(future, item)
                results.append(result)
                account(item, result)
            if deadline is not None and time.monotonic() >= deadline:
                break
        for future in pending:
            item = futures[future]
            entry = _child_error(item[0], item[3], RuntimeError("cooperative stop requested; completion and closure unconfirmed"), "interrupted")
            entry["closure_confirmed"] = False
            entry["finalization_status"] = "pending-execution"
            results.append(entry)
            def late(completed, owned=item):
                _background(owned[3]._routed_context, lambda: _schedule_finalization(finalize, parent, owned, consume(completed, owned)))
            future.add_done_callback(late)
        _poll_accounting([item[3] for item, _result in settled])
        for item, result in settled:
            status = dict(item[3]._routed_accounting)
            item[3]._routed_raw_result = _safe_json(result)
            displayed = getattr(item[3], "_routed_display_result", None)
            if displayed is not None:
                result.clear()
                result.update(_safe_json(displayed))
            elif callable(getattr(item[3], "_routed_budget_summary", None)):
                result["summary"] = None  # projection failure cannot expose the unbounded raw summary
            if status["status"] == "returned":
                result.clear()
                result.update(item[3]._routed_finalized_result)
            result["finalization_status"] = status["status"]
            if status["status"] != "returned":
                result["finalization_error"] = status.get("error") or status.get("error_type") or status["status"]
        return sorted(results, key=lambda entry: entry["task_index"])
    finally:
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)


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
    finalization_pending = []
    parent_actions = []
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
        dispatch = current.get("dispatch")
        if isinstance(dispatch, dict):
            tasks[task_id]["dispatch_kind"] = dispatch.get("kind")
            tasks[task_id]["acceptance_handoff"] = dispatch.get("acceptance_handoff")
            if dispatch.get("kind") != "model" and current["status"] == "pending":
                parent_actions.append({"task_id": task_id,
                    **{key: dispatch.get(key) for key in ("kind", "decision_id", "executor", "prompt_path", "route_task_path", "route_receipt_path", "acceptance_handoff")}})
        handle, token = current.get("handle", ""), current.get("launch_token", "")
        if handle and token:
            recorded = _trusted_attempt(run_dir, task_id, handle, token, "intent.json")
            if recorded.is_file():
                accounting = _trusted_attempt(run_dir, task_id, handle, token, "finalization.json")
                data = json.loads(accounting.read_text(encoding="utf-8")) if accounting.is_file() else {}
                tasks[task_id]["finalization_status"] = data.get("status", "unconfirmed")
                if data.get("status") != "returned" or data.get("persistence_error_type"):
                    finalization_pending.append(task_id)
    return {
        "run_dir": str(run_dir.resolve()),
        "status": state["status"],
        "stop_requested": state["stop_requested"],
        "tasks": tasks,
        "finalization_pending": finalization_pending,
        "parent_actions": parent_actions,
        "accounting_assurance": "native-finalizer-return-only; internally suppressed outcomes are unverified",
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
        if "route_request" not in task:
            workflow.task_model(run_dir, task["id"], trusted_manifest_sha256)
    if any("route_request" in task for task in plan["tasks"]):
        workflow.load_v3_router_snapshot(run_dir, state)
    return plan, state, trusted_manifest_sha256


def _complete_workflow_parent_action(
    workflow: Any,
    run_dir: Path,
    task_id: str,
    output_path: Path,
    summary: str,
    trusted_manifest_sha256: str,
) -> None:
    output_path = output_path.resolve()
    if not output_path.is_file():
        raise ValueError(f"parent action output does not exist: {output_path}")
    token = workflow.claim_parent_task(run_dir, task_id, trusted_manifest_sha256)
    handle = f"parent-sequential:{task_id}"
    try:
        workflow.start_task(run_dir, task_id, handle, token, trusted_manifest_sha256)
        workflow.finish_task(
            run_dir, task_id, "succeeded", str(output_path), summary, "",
            False, handle, token, trusted_manifest_sha256,
        )
    except Exception as exc:
        _plan, state = workflow.load_run(run_dir, trusted_manifest_sha256)
        current = state["tasks"].get(task_id, {})
        if current.get("status") == "launching":
            workflow.abort_launch(
                run_dir, task_id, str(exc) or type(exc).__name__, token,
                trusted_manifest_sha256,
            )
        raise


def _dispatch_workflow_v3(workflow, run_dir, task, trusted_manifest_sha256, parent, max_iterations):
    # Resolve the native envelope before the portable owner freezes its input.
    goal, _dependencies = workflow.render_prompt_data(run_dir, task["id"], trusted_manifest_sha256)
    tools = task["route_request"]["requirements"]["tools"]
    envelope = {"id": task["id"], "goal": goal, "context": None,
                "toolsets": ["none"] if not tools else None, "role": "leaf"}
    envelope["_native_envelope"] = _v3_native_envelope(parent, envelope)
    context = {"max_iterations": max_iterations, "native_envelope": envelope["_native_envelope"],
               "toolsets": envelope["toolsets"], "role": "leaf",
               "adapter_sha256": _sha(Path(__file__).read_bytes()),
               "workflow_sha256": _sha(Path(workflow.__file__).read_bytes())}
    dispatch = workflow.task_dispatch(run_dir, task["id"], context, trusted_manifest_sha256)
    request = json.loads(Path(dispatch["route_task_path"]).read_bytes())
    receipt = json.loads(Path(dispatch["route_receipt_path"]).read_bytes())
    selected_dispatch = {key: dispatch[key] for key in ("kind", "decision_id", "route", "executor") if key in dispatch}
    _validate_v3_dispatch(selected_dispatch, receipt, request, surface=_WORKFLOW_SURFACE)
    envelope["_v3_request"] = request
    return envelope, receipt, dispatch


def _workflow_task_envelope(
    workflow: Any,
    run_dir: Path,
    task: dict[str, Any],
    trusted_manifest_sha256: str,
    parent: Any = None,
    max_iterations: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if "route_request" in task:
        if parent is None or max_iterations is None:
            raise RuntimeError("V3 workflow preparation needs its actual native parent and iteration limit")
        envelope, receipt, dispatch = _dispatch_workflow_v3(
            workflow, run_dir, task, trusted_manifest_sha256, parent, max_iterations)
        if dispatch["kind"] != "model":
            raise RuntimeError("Non-model V3 workflow action cannot prepare a native child")
        return envelope, receipt
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
    validate_request: Any = None,
    on_built: Any = None,
    budget_summary: Any = None,
) -> Any:
    child = _prepare_child(
        parent,
        task,
        receipt,
        index,
        count,
        max_iterations,
        build=build,
        validate_request=validate_request,
        on_built=on_built,
        budget_summary=budget_summary,
    )
    if getattr(child, "_delegate_role", None) != "leaf":
        if on_built is None:
            _dispose_unentered(child, parent)
        raise RuntimeError(
            "Hermes workflow nodes must be native leaf children with delegation disabled"
        )
    if "_v3_request" in task:
        try:
            _guard_v3_child(child, task, {"request": task["_v3_request"]})
        except Exception:
            if on_built is None:
                _dispose_unentered(child, parent)
            raise
    handle = getattr(child, "_subagent_id", None)
    if not isinstance(handle, str) or not handle:
        if on_built is None:
            _dispose_unentered(child, parent)
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
    trusted_path = _trusted_close_witness_path(run_dir, task_id, handle, launch_token)

    def close_with_witness() -> Any:
        with close_lock:
            if close_result:
                return close_result[0]
            result = original_close()
            close_result.append(result)
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
                trusted_path,
                text,
            )
            _atomic_text(_close_witness_path(run_dir, task_id), text)
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
    return isinstance(witness, dict) and witness == {
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


def _attempt_artifact(workflow, run_dir, task_id, handle, token, suffix):
    key = _sha({"handle": handle, "launch_token": token})
    return workflow.task_artifact_path(run_dir, task_id, f"attempt-{key}.{suffix}")


def _trusted_attempt(run_dir, task_id, handle, token, suffix, home=None):
    canonical_run, run_key = _workflow_run_key(run_dir)
    key = _sha({"run_dir": canonical_run, "task_id": task_id, "handle": handle, "launch_token": token})
    return (home or _hermes_home()) / "cache/routed-delegation/workflow-attempts" / run_key / f"{key}.{suffix}"


def _execution_intent(run_dir, manifest_sha, metadata):
    _index, envelope, receipt, child, token = metadata
    path = _trusted_attempt(run_dir, envelope["id"], child._subagent_id, token, "intent.json", child._routed_home)
    _atomic_text(path, json.dumps({"manifest_sha256": manifest_sha, "receipt_sha256": _sha(receipt),
                                  "execution_outcome": "unknown", "replay_allowed": False}))


def _record_workflow_result(workflow, run_dir, manifest_sha, metadata, result, parent=None):
    index, envelope, receipt, child, token = metadata
    task_id, handle = envelope["id"], child._subagent_id
    record = _safe_json({"schema_version": 2, "task_id": task_id, "handle": handle,
                        "launch_token": token, "manifest_sha256": manifest_sha,
                        "route_receipt": receipt, "native_result": result})
    try:
        record["display_result"] = _display_result(child, parent, result)
        record["summary_count"] = child._routed_summary_count
    except BaseException as exc:
        # Full raw outcome still persists if deriving its context view fails.
        record["display_error_type"] = type(exc).__name__
    trusted = _trusted_attempt(run_dir, task_id, handle, token, "result.json", child._routed_home)
    if trusted.exists() and json.loads(trusted.read_text(encoding="utf-8")) != record:
        raise RuntimeError("trusted attempt result already exists with different evidence")
    _atomic_text(trusted, json.dumps(record, ensure_ascii=False))
    path = _attempt_artifact(workflow, run_dir, task_id, handle, token, "result.json")
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != record:
            raise RuntimeError("attempt result already exists with different evidence")
    else:
        workflow.atomic_json(path, record)
    workflow.atomic_json(workflow.task_artifact_path(run_dir, task_id, "result.json"), record)
    return record


def _finish_recorded_workflow_result(workflow, run_dir, manifest_sha, runtime, record):
    task_id, handle, token = record["task_id"], record["handle"], record["launch_token"]
    result = record["native_result"]
    if record.get("display_error_type"):
        return False
    displayed = record.get("display_result", result)  # historical records retain their original semantics
    if not _definitive_result(result):
        return False
    if not _native_handle_is_closed(runtime, run_dir, task_id, handle, token):
        return False
    status, error = _native_result_status(result, record["route_receipt"]["route"])
    output = ""
    if status == "succeeded":
        output_path = _attempt_artifact(workflow, run_dir, task_id, handle, token, "output.md")
        _atomic_text(output_path, displayed["summary"])
        _atomic_text(workflow.task_artifact_path(run_dir, task_id, "output.md"), displayed["summary"])
        output = str(output_path)
    workflow.finish_task(run_dir, task_id, status, output, str(displayed.get("summary") or ""),
                         error, True, handle, token, manifest_sha)
    return True


def _settle_workflow_result(workflow, run_dir, manifest_sha, runtime, parent, metadata, result, *, finish_state=True):
    index, envelope, receipt, child, token = metadata
    def persist(status):
        _atomic_text(_trusted_attempt(run_dir, envelope["id"], child._subagent_id, token, "finalization.json", child._routed_home),
                     json.dumps(status, ensure_ascii=False))
        workflow.atomic_json(_attempt_artifact(workflow, run_dir, envelope["id"], child._subagent_id, token, "finalization.json"), status)
    try:
        record = _record_workflow_result(workflow, run_dir, manifest_sha, metadata, result, parent)
        finished = finish_state and _finish_recorded_workflow_result(workflow, run_dir, manifest_sha, runtime, record)
        return {"finished": bool(finished)}
    finally:
        # Accounting ownership survives persistence or canonical state failures.
        _schedule_finalization(runtime["finalize"], parent, metadata, result, persist)


def _reconcile_workflow_results(workflow, run_dir, manifest_sha, runtime):
    _plan, state = workflow.load_run(run_dir, manifest_sha)
    reconciled = []
    for task_id, current in state["tasks"].items():
        if current["status"] != "running":
            continue
        handle, token = current.get("handle", ""), current.get("launch_token", "")
        path = _attempt_artifact(workflow, run_dir, task_id, handle, token, "result.json")
        trusted = _trusted_attempt(run_dir, task_id, handle, token, "result.json")
        if not trusted.is_file():
            raise RuntimeError("execution completion is unknown or unbound; manual reconciliation required before replay")
        record = json.loads(trusted.read_text(encoding="utf-8"))
        if path.is_file() and json.loads(path.read_text(encoding="utf-8")) != record:
            raise RuntimeError("stored execution result does not match trusted active attempt evidence")
        if not isinstance(record, dict) or any(record.get(key) != value for key, value in {
            "schema_version": 2, "task_id": task_id, "handle": handle, "launch_token": token,
            "manifest_sha256": manifest_sha, "route_receipt": current.get("decision_receipt"),
        }.items()) or not isinstance(record.get("native_result"), dict):
            raise RuntimeError("stored execution result does not match the active attempt")
        if not _finish_recorded_workflow_result(workflow, run_dir, manifest_sha, runtime, record):
            raise RuntimeError("completed execution cannot be reconciled without exact native close witnesses; replay excluded")
        reconciled.append(task_id)
    return reconciled


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
            constructed = []
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
                    **({"parent": parent, "max_iterations": max_iterations} if "route_request" in task else {}),
                )
                child = _prepare_workflow_child(
                    parent,
                    envelope,
                    receipt,
                    index,
                    len(ready),
                    max_iterations,
                    runtime["build"],
                    runtime.get("validate_request"),
                    constructed.append,
                    budget_summary=runtime.get("budget_summary"),
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
                _execution_intent(run_dir, trusted_manifest_sha256, prepared[-1])
                future = _submit_owned(pool,
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
                child = child or (constructed[0] if constructed else None)
                error_text = str(exc) or type(exc).__name__
                if child is not None:
                    cleanup = _dispose_unentered(child, parent, runtime.get("detach"))
                    if cleanup:
                        error_text += f"; cleanup incomplete: {cleanup}"
                    _schedule_finalization(runtime["finalize"], parent,
                                           (index, envelope, receipt, child),
                                           _child_error(index, child, exc))
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
        completed = 0
        finalization_errors = []
        interrupt_deadline = None
        signalled = set()
        while pending:
            if getattr(parent, "_interrupt_requested", False) is True and interrupt_deadline is None:
                workflow.request_stop(run_dir, trusted_manifest_sha256)
                interrupt_deadline = time.monotonic() + _INTERRUPT_GRACE_SECONDS
                for future in pending:
                    metadata = futures[future]
                    if future.cancel():
                        _background(metadata[3]._routed_context, lambda owned=metadata: _dispose_unentered(owned[3], parent, runtime.get("detach")))
                    else:
                        _background(metadata[3]._routed_context, lambda owned=metadata: _interrupt_child(owned[3], runtime.get("interrupt")))
                    signalled.add(future)
            try:
                done, pending = wait(pending, timeout=0.05, return_when=FIRST_COMPLETED)
            except BaseException:
                workflow.request_stop(run_dir, trusted_manifest_sha256)
                interrupt_deadline = interrupt_deadline or (time.monotonic() + _INTERRUPT_GRACE_SECONDS)
                for future in pending - signalled:
                    owned = futures[future]
                    _background(owned[3]._routed_context, lambda owned=owned: _interrupt_child(owned[3], runtime.get("interrupt")))
                    signalled.add(future)
                if time.monotonic() >= interrupt_deadline:
                    break
                continue
            for future in done:
                metadata = futures[future]
                try:
                    result = future.result()
                except BaseException as exc:
                    result = _child_error(metadata[0], metadata[3], exc)
                try:
                    outcome = _settle_workflow_result(workflow, run_dir, trusted_manifest_sha256,
                                                     runtime, parent, metadata, result)
                    completed += 1
                    if not outcome["finished"]:
                        launch_errors.append({"task_id": metadata[1]["id"], "error": "native execution outcome or exact close witness unconfirmed; replay excluded"})
                except Exception as exc:
                    launch_errors.append({"task_id": metadata[1]["id"], "error": str(exc)})
            if interrupt_deadline is not None and time.monotonic() >= interrupt_deadline:
                break
        for future in pending:
            metadata = futures[future]
            index, envelope, receipt, child, token = metadata
            workflow.atomic_json(_attempt_artifact(workflow, run_dir, envelope["id"], child._subagent_id, token, "abandoned.json"),
                                 {"status": "closure-unconfirmed", "replay_allowed": False})
            def record_late(finished, owned=metadata):
                try:
                    try:
                        result = finished.result()
                    except BaseException as exc:
                        result = _child_error(owned[0], owned[3], exc)
                    # Best-effort evidence/accounting only. Canonical task state
                    # is reconciled later under the workflow execution lock.
                    _settle_workflow_result(workflow, run_dir, trusted_manifest_sha256,
                                            runtime, parent, owned, result, finish_state=False)
                except Exception:
                    # The durable abandonment marker continues excluding replay.
                    pass
            future.add_done_callback(lambda finished, owned=metadata, callback=record_late:
                                     _background(owned[3]._routed_context, lambda: callback(finished)))
        _poll_accounting([owned[3] for future, owned in futures.items() if future not in pending])
        for future, owned in futures.items():
            status = owned[3]._routed_accounting
            if future not in pending and (status["status"] != "returned" or status.get("persistence_error_type")):
                finalization_errors.append({"task_id": owned[1]["id"], **status})
        return {"completed": completed, "launch_errors": launch_errors,
                "finalization_errors": finalization_errors,
                "abandoned_after_interrupt": bool(pending),
                "closure_unconfirmed": [futures[f][1]["id"] for f in pending],
                "stop_reason": "closure-unconfirmed" if pending else "no-progress" if completed == 0 else ""}
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


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
    by_id = {task["id"]: task for task in plan["tasks"]}
    while True:
        ready = workflow.ready_tasks(run_dir, trusted_manifest_sha256)
        if getattr(parent, "_interrupt_requested", False) is True:
            workflow.request_stop(run_dir, trusted_manifest_sha256)
            break
        if not ready:
            break
        v3_ready = [task_id for task_id in ready if "route_request" in by_id[task_id]]
        if v3_ready:
            for task_id in v3_ready:
                _dispatch_workflow_v3(workflow, run_dir, by_id[task_id], trusted_manifest_sha256, parent, max_iterations)
            # Non-model choices remain actions in the snapshot, outside the wave.
            ready = workflow.ready_tasks(run_dir, trusted_manifest_sha256)
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
        if wave["abandoned_after_interrupt"] or wave.get("stop_reason") == "no-progress":
            break
    snapshot = _workflow_snapshot(
        workflow, run_dir, trusted_manifest_sha256
    )
    snapshot["operational_ok"] = not snapshot["finalization_pending"] and not any(w.get("finalization_errors") or w.get("launch_errors") or w.get("abandoned_after_interrupt") for w in waves)
    snapshot["success"] = snapshot["status"] == "succeeded" and snapshot["operational_ok"]
    snapshot["waves"] = waves
    return snapshot


def _handle(params: dict[str, Any], **_kwargs: Any) -> str:
    preparation_cleanup = []
    try:
        from agent.subagent_lifecycle import get_active_subagent_parent

        parent = get_active_subagent_parent()
        if parent is None:
            raise RuntimeError("No active Hermes parent session is available")
        parent_session_id = str(getattr(parent, "session_id", "") or "")
        if not parent_session_id:
            raise RuntimeError("active Hermes parent has no session id")
        runtime = _private_runtime()
        raw_tasks = params.get("tasks")
        if not isinstance(raw_tasks, list) or not 1 <= len(raw_tasks) <= 4:
            raise ValueError("tasks must contain 1-4 entries")
        tasks = [_normalize_task(raw) for raw in raw_tasks]
        if len({task["id"] for task in tasks}) != len(tasks):
            raise ValueError("task ids must be unique")
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
        reservations = {}
        selected = []
        try:
            for index, task in enumerate(tasks):
                if "route_request" in task:
                    task["_native_envelope"] = _v3_native_envelope(parent, task)
                    pin = _select_or_reuse_v3(parent_session_id, task, max_iterations)
                    receipt = pin["decision"]
                    dispatch = pin["dispatch"]
                else:
                    pin = None
                    receipt = _select_or_reuse(parent_session_id, task, max_iterations)
                    dispatch = {
                        "kind": "model",
                        "route": receipt["route"],
                        "decision_id": receipt["decision_id"],
                    }
                selected.append((index, task, receipt, dispatch, pin))
            model_selected = [item for item in selected if item[3]["kind"] == "model"]
            max_children = runtime["get_max_children"]()
            if len(model_selected) > max_children:
                raise ValueError(
                    f"Too many model tasks: {len(model_selected)} selected, but max_concurrent_children is {max_children}"
                )
            if model_selected and runtime["is_paused"]():
                raise RuntimeError("Delegation spawning is paused")
            depth = int(getattr(parent, "_delegate_depth", 0) or 0)
            max_depth = runtime["get_max_depth"]()
            if model_selected and depth >= max_depth:
                raise RuntimeError(
                    f"Delegation depth limit reached (depth={depth}, max_spawn_depth={max_depth})"
                )
            for index, task, receipt, _dispatch, pin in selected:
                # Own each attempt after admission checks, before any construction.
                reservation = _hermes_home() / "cache/routed-delegation/direct-attempts" / (_sha({"parent": parent_session_id, "task_id": task["id"]}) + ".json")
                reservation.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with reservation.open("x", encoding="utf-8") as target:
                        json.dump({"task_sha256": _sha(task), "route_pin": pin, "receipt": receipt,
                                   "execution_outcome": "unknown", "replay_allowed": False}, target)
                except FileExistsError as exc:
                    raise RuntimeError("direct task already has an owned attempt; explicit reconciliation required before replay") from exc
                reservations[index] = reservation
            for index, task, receipt, _dispatch, _pin in model_selected:
                child = _prepare_child(
                    parent,
                    task,
                    receipt,
                    index,
                    len(model_selected),
                    max_iterations,
                    build=runtime["build"],
                    validate_request=runtime.get("validate_request"),
                    on_built=lambda child, i=index, t=task, r=receipt: prepared.append((i, t, r, child)),
                    budget_summary=runtime.get("budget_summary"),
                )
                if _pin is not None:
                    _guard_v3_child(child, task, _pin)
        except Exception as exc:
            for item in prepared:
                errors = _dispose_unentered(item[3], parent, runtime.get("detach"))
                _schedule_finalization(runtime["finalize"], parent, item, _child_error(item[0], item[3], exc))
                preparation_cleanup.append({"task_id": item[1]["id"], "close_returned": item[3]._routed_closed,
                                            "cleanup_errors": errors, "finalization": item[3]._routed_accounting})
            _poll_accounting([item[3] for item in prepared])
            raise
        results = (
            _execute_children(
                prepared,
                parent,
                runtime["run"],
                runtime["finalize"],
                max_children=max_children,
                owner_kwargs=owner_kwargs,
                interrupt=runtime.get("interrupt"),
                detach=runtime.get("detach"),
            )
            if prepared
            else []
        )
        wrapped_by_index = {}
        by_index = {index: (task, receipt) for index, task, receipt, _child in prepared}
        for result in results:
            task, receipt = by_index[result["task_index"]]
            pin = next(item[4] for item in selected if item[0] == result["task_index"])
            if pin is None:
                wrapped_by_index[result["task_index"]] = {
                    "task_id": task["id"],
                    "route": receipt["route"],
                    "route_receipt": receipt,
                    "result": result,
                }
            else:
                wrapped_by_index[result["task_index"]] = {
                    "task_id": task["id"],
                    "route": receipt["route"],
                    "route_request": pin["request"],
                    "route_receipt": receipt,
                    "decision_id": receipt["decision_id"],
                    "request_sha256": _sha(pin["request"]),
                    "result": result,
                    "acceptance_required": {
                        "owner": "parent",
                        "verifier": pin["request"]["verifier"],
                        "message": "The parent must run the declared independent acceptance check; native completion is not task-quality qualification.",
                    },
                }
        for index, task, receipt, dispatch, pin in selected:
            if dispatch["kind"] == "model":
                continue
            wrapped_by_index[index] = {
                "task_id": task["id"],
                "parent_action_required": True,
                "action": dispatch,
                "route_request": pin["request"],
                "route_receipt": receipt,
                "decision_id": receipt["decision_id"],
                "request_sha256": _sha(pin["request"]),
                "catalog_sha256": _sha(pin["catalog"]),
                "selector_identity": pin["selector_identity"],
            }
        wrapped = [wrapped_by_index[index] for index in range(len(tasks))]
        prepared_by_index = {item[0]: item for item in prepared}
        pins_by_index = {item[0]: item[4] for item in selected}
        for index, item in enumerate(wrapped):
            prepared_item = prepared_by_index.get(index)
            persisted = {
                "receipt": item["route_receipt"],
                "route_pin": pins_by_index[index],
                "result": item.get("result"),
                "action": item.get("action"),
                "native_result": (
                    getattr(prepared_item[3], "_routed_raw_result", None)
                    if prepared_item is not None
                    else None
                ),
                "replay_allowed": False,
            }
            _atomic_text(reservations[index], json.dumps(persisted, ensure_ascii=False))
        success = bool(wrapped) and all(
            "result" in item
            and _definitive_result(item["result"])
            and item["result"].get("status") == "completed"
            and item["result"].get("finalization_status") == "returned"
            and not item["result"].get("cleanup_errors")
            for item in wrapped
        )
        return json.dumps({"success": success, "results": wrapped,
                           "pending_parent_actions": sum("action" in item for item in wrapped),
                           "accounting_assurance": "native-finalizer-return-only; internally suppressed outcomes are unverified"}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc) or type(exc).__name__,
                           "preparation_cleanup": preparation_cleanup}, ensure_ascii=False)


def _workflow_handle(params: dict[str, Any], **_kwargs: Any) -> str:
    try:
        action = str(params.get("action") or "").strip()
        if action not in {"init", "run", "status", "resume", "complete-parent"}:
            raise ValueError("action must be init, run, status, resume, or complete-parent")
        workflow = _workflow_state_module()
        if action == "init":
            plan_value = str(params.get("plan_path") or "").strip()
            if not plan_value:
                raise ValueError("action=init requires plan_path")
            if params.get("run_dir"):
                raise ValueError("action=init does not accept run_dir")
            if any(params.get(field) is not None for field in ("task_id", "output_path", "summary")):
                raise ValueError("action=init does not accept completion fields")
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
        if action != "complete-parent" and any(
            params.get(field) is not None for field in ("task_id", "output_path", "summary")
        ):
            raise ValueError(f"action={action} does not accept completion fields")
        if action == "complete-parent" and any(
            params.get(field) is not None for field in ("retry_failed", "retry_interrupted")
        ):
            raise ValueError("action=complete-parent does not accept retry flags")
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
        if action == "complete-parent":
            task_id = str(params.get("task_id") or "").strip()
            output_value = str(params.get("output_path") or "").strip()
            summary = params.get("summary", "")
            if not task_id or not output_value:
                raise ValueError("action=complete-parent requires task_id and output_path")
            if not isinstance(summary, str):
                raise ValueError("action=complete-parent summary must be a string")
            from agent.subagent_lifecycle import get_active_subagent_parent
            parent = get_active_subagent_parent()
            if parent is None or int(getattr(parent, "_delegate_depth", 0) or 0) != 0:
                raise RuntimeError("complete-parent requires the active top-level Hermes parent")
            with workflow.execution_lock(run_dir):
                _plan, _state, trusted_manifest_sha256 = _validate_hermes_workflow_run(
                    workflow, run_dir
                )
                _complete_workflow_parent_action(
                    workflow, run_dir, task_id, Path(output_value), summary,
                    trusted_manifest_sha256,
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
                runtime = _private_runtime() if retry_interrupted or any(t["status"] == "running" for t in _state["tasks"].values()) else {}
                reconciled = _reconcile_workflow_results(workflow, run_dir, trusted_manifest_sha256, runtime)
                if retry_interrupted:
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
                snapshot["reconciled_completed_tasks"] = reconciled
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


def _require_routed_delegation(*, tool_name: str, args: Any = None, **_kwargs: Any) -> dict | None:
    """Route new workers through the selector; never obstruct existing-worker control.

    Hermes dispatches delegate_task inline, ahead of registry handlers. Its
    supported pre-tool hook is therefore the ingress boundary, not a tool alias.
    This is routing policy, not an approval decision or a sandbox boundary.
    """
    if tool_name != "delegate_task":
        return None
    action = args.get("action") if isinstance(args, dict) else None
    if action in ("list", "steer", "stop"):
        return None
    return {
        "action": "block",
        "message": (
            "New delegation is owned by the task router. Submit this task to "
            "routed_delegate_task with a V3 route_request (or routed_workflow for a DAG). "
            "Do not retry native spawn or bypass routing with a subprocess. "
            "A keep_parent/defer decision is not permission to launch an inherited worker. "
            "Missing quality evidence may permit a bounded independently verified trial; "
            "missing callability requires an explicit bounded availability check first. "
            "Existing worker list/steer/stop controls remain available."
        ),
    }


def register(ctx: Any) -> None:
    ctx.register_hook("pre_tool_call", _require_routed_delegation)
    schema = {
        "name": "routed_delegate_task",
        "description": (
            "Delegate 1-4 independent tasks. Use route_request for task-aware V3; legacy tier fields retain V2. "
            "The tool deterministically "
            "selects and pins each exact provider/model/reasoning route. A task id owns one execution "
            "attempt; repeated calls with that id are blocked."
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
                        "required": ["id", "goal"],
                        "oneOf": [
                            {
                                "required": ["intelligence_tier", "latency_sensitive"],
                                "not": {"required": ["route_request"]},
                            },
                            {
                                "required": ["route_request"],
                                "not": {
                                    "anyOf": [
                                        {"required": ["intelligence_tier"]},
                                        {"required": ["latency_sensitive"]},
                                        {"required": ["failure_cost"]},
                                        {"required": ["task_class"]},
                                        {"required": ["verifier_plan"]},
                                    ]
                                },
                            },
                        ],
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
                            "route_request": {"type": "object", "description":
                                "Task-aware V3 template from openai-delegation-route-research/references/"
                                "hermes-direct-v3.md. Requires schema_version, task_class, requirements, "
                                "verifier, effects, failure_cost, deterministic and budget. Controller fields "
                                "(task_id/input_sha256/as_of/continuation/host/transport) are supplied by this tool. "
                                "Declare the exact native tool names; inherited tools are checked before execution. "
                                "Non-model decisions return parent actions. Parent verifies every model result."},
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
                "action": {"enum": ["init", "run", "status", "resume", "complete-parent"]},
                "plan_path": {"type": "string", "minLength": 1},
                "run_root": {"type": "string", "minLength": 1},
                "run_dir": {"type": "string", "minLength": 1},
                "variables": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
                "retry_failed": {"type": "boolean"},
                "retry_interrupted": {"type": "boolean"},
                "task_id": {"type": "string", "minLength": 1},
                "output_path": {"type": "string", "minLength": 1},
                "summary": {"type": "string"},
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
