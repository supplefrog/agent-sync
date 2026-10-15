"""ChatGPT project/cloud creation and private file export over MCP stdio.

Uses the signed-in native app-server; never reads, stores, or returns auth files.
Remote contracts are private and version-sensitive. See docs/codex-workspace-mcp.md.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from codex_project import connected


MAX_FILE = 256 * 1024 * 1024


class ToolError(Exception):
    pass


def preflight_action(name, args):
    if name == "create_project" and args.get("kind") == "local":
        raise ToolError("Local Desktop project creation is retired: native registry creation does not "
                        "adopt a project into the Desktop sidebar. Use supported Desktop setup and "
                        "verify its saved project ID. Existing native registrations are preserved.")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required),
            "additionalProperties": False}


STR = {"type": "string", "minLength": 1}
OP = {"type": "string", "format": "uuid", "description": "Fresh UUID for this action. Retain it across retries; an uncertain submitted action is never automatically replayed."}
CONFIGURATION = schema({
    "name": STR, "repositories": {"type": "array", "items": schema({"repository_id": STR, "ref": STR, "depth": {"type": "integer", "minimum": 1, "maximum": 2147483647}}, ("repository_id", "ref"))},
    "install_script": {"type": "string"}, "cwd": STR, "start_skill": {"type": "string"},
    "network_policy": {"oneOf": [schema({"type": {"const": "disabled"}}, ("type",)), schema({"type": {"const": "unrestricted"}}, ("type",)), schema({"type": {"const": "restricted"}, "presets": {"type": "array", "items": {"const": "package_managers"}}, "egress_rules": {"type": "array", "items": schema({"host": STR}, ("host",))}}, ("type", "egress_rules"))]},
    "share_settings": {"enum": ["private", "workspace"]},
}, ("name", "repositories", "network_policy", "share_settings"))
TOOLS = [
    {"name": "read_cloud_environment", "description": "Read a verified cloud configuration ID, including publication status and safe draft revision metadata. Excludes scripts, secrets and runtime values.", "inputSchema": schema({"configuration_id": STR}, ("configuration_id",)), "annotations": {"readOnlyHint": True}},
    {"name": "publish_cloud_environment", "description": "Begin explicitly requested cloud configuration publication using the exact revision just read. Returns a backend operation ID; does not claim readiness or start a task. Read the operation and complete publication after SUCCEEDED. Retain the caller UUID across retries.", "inputSchema": schema({"operation_id": OP, "configuration_id": STR, "draft_id": STR, "expected_revision": {"type": "integer", "minimum": 0}}, ("operation_id", "configuration_id", "expected_revision")), "annotations": {"readOnlyHint": False, "destructiveHint": False}},
    {"name": "read_cloud_environment_operation", "description": "Read a verified cloud publication operation's state and failure code without retrying it or returning private diagnostics.", "inputSchema": schema({"backend_operation_id": STR}, ("backend_operation_id",)), "annotations": {"readOnlyHint": True}},
    {"name": "complete_cloud_environment_publication", "description": "Finalize previously authorized cloud publication after its backend operation succeeds. Verifies the operation belongs to this configuration/draft before the write. Returns current status; readiness requires a ready version. Does not launch a task.", "inputSchema": schema({"operation_id": OP, "configuration_id": STR, "draft_id": STR, "backend_operation_id": STR}, ("operation_id", "configuration_id", "backend_operation_id")), "annotations": {"readOnlyHint": False, "destructiveHint": False}},
    {"name": "list_cloud_environments", "description": "List real reusable durable Codex cloud configurations in user or workspace scope. Returns safe summaries and a pagination cursor, without secrets.", "inputSchema": schema({"scope": {"enum": ["user", "workspace"]}, "cursor": STR, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}), "annotations": {"readOnlyHint": True}},
    {"name": "read_cloud_thread_environment", "description": "Read one durable Codex task's stored environment IDs and working directories, without loading history or resuming the task. Use exact returned environment IDs for private file export. An empty selection is inconclusive; do not invent a container ID.", "inputSchema": schema({"thread_id": STR}, ("thread_id",)), "annotations": {"readOnlyHint": True}},
    {"name": "create_cloud_environment", "description": "Create a real durable Codex cloud configuration, only when requested. Supply verified native repository IDs and refs. Onboarding is disabled for this write; creation alone does not establish a published ready environment. Complete setup/publication in the native UI, including any secrets, before launching work.", "inputSchema": schema({"operation_id": OP, "configuration": CONFIGURATION}, ("operation_id", "configuration")), "annotations": {"readOnlyHint": False, "destructiveHint": False}},
    {"name": "create_project", "description": "Create a requested ChatGPT project. Local Desktop project creation/adoption is unsupported by this adapter; use supported Desktop setup. This does not assign threads or change their execution host.", "inputSchema": schema({"operation_id": OP, "kind": {"enum": ["chatgpt"]}, "name": STR}, ("operation_id", "kind", "name")), "annotations": {"readOnlyHint": False, "destructiveHint": False}},
    {"name": "create_cloud_thread", "description": "Create a requested persistent Codex task on host durable from an existing saved cloud configuration. Optional prompt starts its first turn; omit it to create an idle task. Model/effort overrides require the user's selection. Does not attach the task to a ChatGPT project. Do not use to create subagents in a side conversation.", "inputSchema": schema({"operation_id": OP, "environment_config_id": STR, "cwd": STR, "prompt": STR, "title": STR, "model": STR, "reasoning_effort": {"enum": ["low", "medium", "high", "xhigh", "max", "ultra"]}}, ("operation_id", "environment_config_id", "cwd")), "annotations": {"readOnlyHint": False, "destructiveHint": False}},
    {"name": "export_cloud_file", "description": "Privately copy an explicitly selected cloud recording, still, patch or other file to the configured local export root. Requires an exact cloud environment ID and absolute POSIX path. Returns only the local path, bytes and SHA256. No public hosting, cloud writes, or local overwrites. File size ceiling is 256 MiB.", "inputSchema": schema({"environment_id": STR, "path": STR, "relative_destination": STR, "expected_sha256": {"type": "string", "pattern": "^[0-9a-fA-F]{64}$"}, "max_bytes": {"type": "integer", "minimum": 1, "maximum": MAX_FILE}}, ("environment_id", "path", "relative_destination")), "annotations": {"readOnlyHint": False, "destructiveHint": False}},
]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Backend:
    def __init__(self, native, token):
        self.native, self.token = native, token
        claims = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "==="))
        account = claims.get("https://api.openai.com/auth", {}).get("chatgpt_account_id")
        if not account:
            raise ToolError("A signed-in ChatGPT account is required.")
        self.account_hash = digest(account.encode())
        self.headers = {"Authorization": "Bearer " + token, "ChatGPT-Account-Id": account,
                        "User-Agent": "codex_desktop", "originator": "codex_desktop",
                        "X-OpenAI-Product-Sku": "codex", "Content-Type": "application/json"}

    def http(self, method, path, body=None):
        # Only fixed backend paths assembled by the tool implementations reach here.
        if not path.startswith(("/v1/environment-configs", "/v1/environment-operations/", "/projects")):
            raise ToolError("Unsupported backend path.")
        origin = "https://codex-cloud-backend.chatgpt.com" if path.startswith("/v1/") else "https://chatgpt.com/backend-api"
        request = urllib.request.Request(origin + path,
                                        data=None if body is None else json.dumps(body).encode(),
                                        headers=self.headers, method=method)
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # Never include headers, tokens, request bodies, or raw remote responses.
            raise ToolError(f"Backend returned HTTP {exc.code}; no automatic retry.") from None

    @contextmanager
    def cloud(self):
        import websocket
        ws = websocket.create_connection(
            "wss://codex-cloud-backend.chatgpt.com/", timeout=30,
            subprotocols=["codex-app-server", "codex-client.desktop", "openai-bearer." + self.token],
            header={"X-OpenAI-Product-Sku": "codex", "ChatGPT-Account-Id": self.headers["ChatGPT-Account-Id"],
                    "X-OpenAI-Allow-Environmentless-Fallback": "true"})
        sequence = 0

        def call(method, params):
            nonlocal sequence
            sequence += 1
            ws.send(json.dumps({"id": sequence, "method": method, "params": params}))
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                ws.settimeout(max(.1, deadline - time.monotonic()))
                response = json.loads(ws.recv())
                if response.get("id") != sequence:
                    continue  # Never answer approvals, server requests, or notifications.
                if "error" in response:
                    raise ToolError(f"Cloud {method} returned error {response['error'].get('code')}; no automatic retry.")
                return response["result"]
            raise ToolError(f"Cloud {method} timed out; inspect remote state before retrying.")

        try:
            call("initialize", {"clientInfo": {"name": "codex_desktop", "version": "1"},
                                "capabilities": {"experimentalApi": True}})
            ws.send(json.dumps({"method": "initialized"}))
            yield call
        finally:
            ws.close()


def summary(environment):
    return {k: environment[k] for k in ("id", "name", "repositories", "share_settings", "version_id", "version_revision", "latest_ready_version_id", "status", "environment_id", "thread_id", "cwd") if k in environment}


def config_path(args):
    if not re.fullmatch(r"[A-Za-z0-9_~-]+", args["configuration_id"]) or ("draft_id" in args and not re.fullmatch(r"[A-Za-z0-9_~-]+", args["draft_id"])):
        raise ToolError("Use an exact native configuration/draft identifier.")
    return "/v1/environment-configs/" + urllib.parse.quote(args["configuration_id"], safe="")


def draft_path(args):
    return config_path(args) + ("/drafts/" + urllib.parse.quote(args["draft_id"], safe="") if "draft_id" in args else "/draft")


def operation_summary(operation):
    result = {k: operation[k] for k in ("id", "kind", "environment_id", "state") if k in operation}
    if operation.get("failure"):
        result["failureCode"] = operation["failure"].get("code")
    return result


def absolute_cloud_path(value):
    path = PurePosixPath(value)
    if not value.startswith("/") or value.startswith("//") or ".." in path.parts or "\x00" in value or "\\" in value:
        raise ToolError("Cloud paths must be absolute POSIX paths without traversal.")
    return str(path)


def save_export(root, relative, data, expected=None, max_bytes=MAX_FILE):
    if len(data) > max_bytes:
        raise ToolError("File exceeds the selected byte limit.")
    sha = digest(data)
    if expected is not None and sha != expected.lower():
        raise ToolError("Source SHA256 mismatch; no file written.")
    root = root.resolve()
    destination = (root / relative).resolve()
    if Path(relative).is_absolute() or not destination.is_relative_to(root) or destination == root:
        raise ToolError("Destination must stay inside the configured export root.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not destination.is_file() or digest(destination.read_bytes()) != sha:
            raise ToolError("Destination exists with different bytes; no overwrite.")
        return {"path": str(destination), "bytes": len(data), "sha256": sha, "reused": True}
    temporary = destination.parent / (".codex-export-" + str(uuid.uuid4()))
    try:
        with temporary.open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, destination)  # Atomic exclusive publication; never replace another file.
    finally:
        temporary.unlink(missing_ok=True)
    return {"path": str(destination), "bytes": len(data), "sha256": sha, "reused": False}


class Service:
    def __init__(self, state_root, export_root):
        self.state_root, self.export_root = Path(state_root), Path(export_root)

    def creation(self, tool, args, backend, perform):
        operation = str(uuid.UUID(args["operation_id"]))
        fingerprint = digest(json.dumps({"tool": tool, "args": args, "account": backend.account_hash}, sort_keys=True).encode())
        self.state_root.mkdir(parents=True, exist_ok=True)
        record = self.state_root / (operation + ".json")
        # Exclusive reservation also prevents simultaneous creators/processes.
        try:
            with record.open("x", encoding="utf8") as output:
                json.dump({"fingerprint": fingerprint, "status": "submitted"}, output)
                output.flush()
                os.fsync(output.fileno())
        except FileExistsError:
            prior = json.loads(record.read_text(encoding="utf8"))
            if prior["fingerprint"] != fingerprint:
                raise ToolError("Operation ID belongs to a different request or account.")
            if prior["status"] != "complete":
                raise ToolError("This operation may already have executed. Reconcile remote state; do not replay it.")
            return prior["result"]
        result = perform()
        temporary = record.with_suffix(".complete")
        with temporary.open("x", encoding="utf8") as output:
            json.dump({"fingerprint": fingerprint, "account": backend.account_hash, "status": "complete", "result": result}, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, record)
        return result

    def execute(self, name, args, backend):
        preflight_action(name, args)
        if name == "read_cloud_environment":
            result = backend.http("GET", config_path(args))
            if result["id"] != args["configuration_id"]:
                raise ToolError("Configuration identity did not match the request.")
            value = summary(result)
            if result.get("draft"):
                value["draft"] = {k: result["draft"][k] for k in ("id", "revision", "base_version_id") if k in result["draft"]}
            return value
        if name == "read_cloud_environment_operation":
            result = backend.http("GET", "/v1/environment-operations/" + urllib.parse.quote(args["backend_operation_id"], safe=""))
            if result["id"] != args["backend_operation_id"]:
                raise ToolError("Operation identity did not match the request.")
            return operation_summary(result)
        if name == "publish_cloud_environment":
            def begin():
                result = backend.http("POST", draft_path(args) + "/approve/begin", {"expected_revision": args["expected_revision"], "idempotency_key": args["operation_id"]})
                if not result.get("id") or result.get("kind") != "APPROVE_ENVIRONMENT_CONFIG_DRAFT":
                    raise ToolError("Publication submission was not confirmed; reconcile before retrying.")
                return {**operation_summary(result), "configurationId": args["configuration_id"], "draftId": args.get("draft_id")}
            return self.creation(name, args, backend, begin)
        if name == "complete_cloud_environment_publication":
            matches = []
            for record in self.state_root.glob("*.json"):
                prior = json.loads(record.read_text(encoding="utf8"))
                value = prior.get("result", {})
                if prior.get("status") == "complete" and value.get("id") == args["backend_operation_id"] and value.get("configurationId") == args["configuration_id"] and value.get("draftId") == args.get("draft_id") and prior.get("account") == backend.account_hash:
                    matches.append(value)
            if len(matches) != 1:
                raise ToolError("An exact publication receipt for this account/configuration/draft is required.")
            result = self.execute("read_cloud_environment_operation", {"backend_operation_id": args["backend_operation_id"]}, backend)
            if result.get("kind") != "APPROVE_ENVIRONMENT_CONFIG_DRAFT" or result.get("state") != "SUCCEEDED" or result.get("environment_id") != matches[0].get("environment_id"):
                raise ToolError("Publication operation has not succeeded for the selected environment.")
            def complete():
                result = backend.http("POST", draft_path(args) + "/approve/complete", {"operation_id": args["backend_operation_id"]})
                if result.get("id") != args["configuration_id"]:
                    raise ToolError("Publication completion was not confirmed; reconcile before retrying.")
                return summary(result)
            return self.creation(name, args, backend, complete)
        if name == "read_cloud_thread_environment":
            with backend.cloud() as call:
                thread = call("thread/read", {"threadId": args["thread_id"], "includeTurns": False})["thread"]
            if thread["id"] != args["thread_id"]:
                raise ToolError("Cloud thread identity did not match the request.")
            return {"threadId": thread["id"], "hostId": "durable", "environments": [
                {k: e[k] for k in ("environmentId", "cwd", "environmentConfigId") if k in e}
                for e in (thread.get("environments") or [])]}
        if name == "list_cloud_environments":
            query = urllib.parse.urlencode({"scope": args.get("scope", "user"), "limit": args.get("limit", 100), "omitDraft": "true",
                                            **({"cursor": args["cursor"]} if "cursor" in args else {})})
            result = backend.http("GET", "/v1/environment-configs?" + query)
            return {"scope": args.get("scope", "user"), "items": [summary(e) for e in result["data"]], "cursor": result.get("next_cursor")}
        if name == "create_cloud_environment":
            config = args["configuration"]
            if "cwd" in config:
                absolute_cloud_path(config["cwd"])
            def create():
                result = backend.http("POST", "/v1/environment-configs", {**config, "start_onboarding": False})
                if not result.get("id"):
                    raise ToolError("Environment creation was not confirmed; reconcile before retrying.")
                return summary(result)
            return self.creation(name, args, backend, create)
        if name == "create_project":
            if "roots" in args or not 1 <= len(args["name"].strip()) <= 50:
                raise ToolError("ChatGPT projects take a 1–50 character name and no local roots.")
            def create():
                response = backend.http("POST", "/projects", {"name": args["name"].strip(),
                    "creation_request_id": args["operation_id"], "instructions": "", "emoji": None,
                    "theme": None, "memory_scope": "unset"})
                project_id = response.get("resource", {}).get("gizmo", {}).get("id")
                if not project_id or response.get("error") is not None:
                    raise ToolError("Project creation was not confirmed; reconcile before retrying.")
                return {"projectId": project_id, "url": f"https://chatgpt.com/g/{project_id}/project"}
            return self.creation(name, args, backend, create)
        if name == "create_cloud_thread":
            cwd = absolute_cloud_path(args["cwd"])
            def create():
                with backend.cloud() as call:
                    params = {"ephemeral": False, "threadSource": "user", "deferredEnvironment": True,
                              "environments": [{"environmentConfigId": args["environment_config_id"], "cwd": cwd}]}
                    if "model" in args:
                        params["model"] = args["model"]
                    if "reasoning_effort" in args:
                        params["config"] = {"model_reasoning_effort": args["reasoning_effort"]}
                    response = call("thread/start", params)
                    thread_id = response["thread"]["id"]
                    result = {"threadId": thread_id, "hostId": "durable", "firstTurnStarted": False}
                    # Persist the durable identity before optional further mutations.
                    self.state_root.joinpath(str(uuid.UUID(args["operation_id"])) + ".thread.json").write_text(json.dumps(result), encoding="utf8")
                    try:
                        if "title" in args:
                            call("thread/name/set", {"threadId": thread_id, "name": args["title"]})
                        if "prompt" in args:
                            turn = call("turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": args["prompt"]}]})
                            result.update(firstTurnStarted=True, turnId=turn.get("turn", {}).get("id"))
                    except Exception:
                        result["followupUnconfirmed"] = True
                    return result
            return self.creation(name, args, backend, create)
        if name == "export_cloud_file":
            path = absolute_cloud_path(args["path"])
            with backend.cloud() as call:
                response = call("fs/readFile", {"environmentId": args["environment_id"], "path": path})
            encoded = response["dataBase64"]
            limit = args.get("max_bytes", MAX_FILE)
            if len(encoded) > ((limit + 2) // 3) * 4:
                raise ToolError("File exceeds the selected byte limit.")
            data = base64.b64decode(encoded, validate=True)
            return save_export(self.export_root, args["relative_destination"], data, args.get("expected_sha256"), limit)
        raise ToolError("Unknown tool.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-exe", type=Path, required=True)
    parser.add_argument("--deps", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--export-root", type=Path, required=True)
    options = parser.parse_args()
    sys.path.insert(0, str(options.deps))
    import jsonschema
    service = Service(options.state_root, options.export_root)
    by_name = {t["name"]: t for t in TOOLS}
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError()
        except ValueError:
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Invalid JSON-RPC request."}}), flush=True)
            continue
        if "id" not in request:
            continue
        response = {"jsonrpc": "2.0", "id": request["id"]}
        try:
            method = request["method"]
            if method == "initialize":
                response["result"] = {"protocolVersion": request.get("params", {}).get("protocolVersion", "2025-06-18"),
                    "capabilities": {"tools": {}}, "serverInfo": {"name": "codex-workspace", "version": "0.1.1"}}
            elif method == "ping":
                response["result"] = {}
            elif method == "tools/list":
                response["result"] = {"tools": TOOLS}
            elif method == "tools/call":
                params = request["params"]
                tool = by_name.get(params["name"])
                if tool is None:
                    raise ToolError("Unknown tool.")
                args = params.get("arguments", {})
                preflight_action(params["name"], args)  # Stale clients fail before auth/RPC/receipt writes.
                jsonschema.validate(args, tool["inputSchema"], format_checker=jsonschema.FormatChecker())
                with connected(options.codex_exe) as native:
                    auth = native.call("getAuthStatus", {"includeToken": True, "refreshToken": False})
                    if auth.get("authMethod") != "chatgpt" or not auth.get("authToken"):
                        raise ToolError("Sign in to ChatGPT in Codex first.")
                    result = service.execute(params["name"], args, Backend(native, auth["authToken"]))
                response["result"] = {"content": [{"type": "text", "text": json.dumps(result)}], "structuredContent": result}
            else:
                response["error"] = {"code": -32601, "message": "Unsupported MCP method."}
        except Exception as exc:
            message = str(exc) if isinstance(exc, ToolError) else "Request failed (" + type(exc).__name__ + "); no automatic retry."
            response["result"] = {"isError": True, "content": [{"type": "text", "text": message}]}
        print(json.dumps(response), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
