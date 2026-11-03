"""Use supported Hermes middleware; never register a global restricted skill."""
from __future__ import annotations

import importlib.util
import json
import threading
from collections import OrderedDict
from pathlib import Path


def load_engine():
    spec = importlib.util.spec_from_file_location("agent_sync_model_skill_engine", Path(__file__).with_name("engine.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Adapter:
    def __init__(self, engine, is_disabled=None):
        self.engine = engine
        self.runtime = engine.Runtime()
        self.requests = OrderedDict()
        self.lock = threading.Lock()
        self.is_disabled = is_disabled or self.native_disabled

    @staticmethod
    def native_disabled(name):
        from tools.skills_tool import _is_skill_disabled
        return _is_skill_disabled(name)

    @staticmethod
    def key(context):
        key = tuple(context.get(name, "") for name in ("session_id", "turn_id", "api_request_id"))
        return key if all(isinstance(item, str) and item for item in key) else None

    def llm_request(self, request, provider="", model="", **context):
        # The host supplies these identities. Tool arguments cannot set them.
        actual = request.get("model", model)
        actual = actual if isinstance(actual, str) else ""
        rows = self.runtime.available("hermes", provider, actual)
        if not self.engine.tool_enabled(request, "skill_view"):
            rows = []
        rows = [row for row in rows if not self.is_disabled(row["name"])]
        key = self.key(context)
        if key:
            with self.lock:
                self.requests[key] = (provider, actual) if rows else ("", "")
                self.requests.move_to_end(key)
                while len(self.requests) > 1024:
                    self.requests.popitem(last=False)
        filtered = self.engine.scrub(request, {row["name"] for row in rows})
        self.engine.attach_catalog(filtered, self.engine.catalog_text(rows, "skill_view(name)"))
        return {"request": filtered, "source": "agent-sync-model-skills"}

    def tool_execution(self, tool_name, args, next_call, **context):
        if tool_name not in ("skills_list", "skill_view"):
            return next_call(args)
        key = self.key(context)
        with self.lock:
            provider, model = self.requests.get(key, ("", ""))
        rows = [row for row in self.runtime.available("hermes", provider, model) if not self.is_disabled(row["name"])]
        if tool_name == "skill_view" and args.get("name") in self.runtime.managed_names():
            if not rows:
                return json.dumps({"success": False, "error": "Skill not available for the current model."})
            # Run the native authorization/approval pipeline before providing a
            # canonical package absent from normal filesystem discovery.
            result = next_call(args)
            value = None
            try:
                value = json.loads(result) if isinstance(result, str) else result
                missing = value.get("success") is False and value.get("error") == f"Skill '{args['name']}' not found."
            except (ValueError, TypeError, AttributeError):
                missing = False
            if missing:
                if not self.is_disabled(args["name"]):
                    return json.dumps(self.runtime.view("hermes", provider, model, args["name"], args.get("file_path")))
            elif isinstance(value, dict) and value.get("success") is True:
                return json.dumps({"success": False, "error": "Model-scoped skill conflicts with an installed native skill."})
            return result
        result = next_call(args)
        if tool_name == "skills_list" and rows and args.get("category") in (None, "model-scoped"):
            try:
                value = json.loads(result)
                if value.get("success") is True and isinstance(value.get("skills"), list):
                    existing = {row.get("name") for row in value["skills"]}
                    value["skills"].extend({**row, "category": "model-scoped", "_agent_sync_model_skill": row["name"]} for row in rows if row["name"] not in existing)
                    value["count"] = len(value["skills"])
                    value["categories"] = sorted(set(value.get("categories", [])) | {"model-scoped"})
                    return json.dumps(value)
            except (ValueError, TypeError, AttributeError):
                pass
        return result


def register(ctx):
    adapter = Adapter(load_engine())
    ctx.register_middleware("llm_request", adapter.llm_request)
    ctx.register_middleware("tool_execution", adapter.tool_execution)
