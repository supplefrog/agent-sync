import base64
from contextlib import contextmanager
import json
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from codex_workspace_mcp import Service, ToolError, TOOLS, preflight_action, absolute_cloud_path, save_export


class FakeBackend:
    account_hash = "one-account"

    def __init__(self):
        self.requests = []
        self.native = Mock()
        self.file = b"abc"
        self.fail_after_submission = False
        self.publication_state = "RUNNING"

    def http(self, method, path, body=None):
        self.requests.append((method, path, body))
        if self.fail_after_submission:
            raise TimeoutError("response lost after the server accepted the action")
        if path.endswith("/approve/begin"):
            return {"id": "publication", "kind": "APPROVE_ENVIRONMENT_CONFIG_DRAFT", "environment_id": "environment", "state": "RUNNING"}
        if path.endswith("/approve/complete"):
            return {"id": "test-config", "status": "ready", "latest_ready_version_id": "ready-version"}
        if path.startswith("/v1/environment-operations/"):
            return {"id": "publication", "kind": "APPROVE_ENVIRONMENT_CONFIG_DRAFT", "environment_id": "environment", "state": self.publication_state, "failure": {"code": "example", "message": "private-diagnostic"}}
        if path == "/v1/environment-configs/test-config":
            return {"id": "test-config", "status": "pending", "secrets": "private", "draft": {"id": "draft", "revision": 2, "secrets": "private"}}
        if method == "GET":
            return {"data": [{"id": "test-config", "name": "Saved", "secrets": "must-omit", "env_vars": {"key": "must-omit"}}], "next_cursor": "next"}
        if path == "/v1/environment-configs":
            return {"id": "test-config", "name": body["name"], "status": "pending"}
        return {"resource": {"gizmo": {"id": "g-p-verification"}}}

    @contextmanager
    def cloud(self):
        def call(method, params):
            self.requests.append((method, params))
            if method == "fs/readFile":
                return {"dataBase64": base64.b64encode(self.file).decode()}
            if method == "thread/start":
                return {"thread": {"id": "test-thread"}}
            if method == "turn/start":
                raise TimeoutError("lost turn response")
            return {}
        yield call


class WorkspaceToolsTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.gettempdir()) / ("codex-workspace-test-" + str(uuid.uuid4()))
        self.root.mkdir()  # Ordinary inherited access; no ACL/permission changes.
        self.service = Service(self.root / "state", self.root / "exports")
        self.backend = FakeBackend()

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_creation_catalog_retires_only_local_desktop_mode(self):
        tools = {tool["name"]: tool for tool in TOOLS}
        self.assertEqual(set(tools), {"read_cloud_environment", "publish_cloud_environment",
                         "read_cloud_environment_operation", "complete_cloud_environment_publication",
                         "list_cloud_environments", "read_cloud_thread_environment", "create_cloud_environment",
                         "create_project", "create_cloud_thread", "export_cloud_file"})
        self.assertEqual(tools["create_project"]["inputSchema"]["properties"]["kind"]["enum"], ["chatgpt"])
        self.assertNotIn("roots", tools["create_project"]["inputSchema"]["properties"])

    def test_stale_local_request_refuses_before_native_or_receipt_writes(self):
        args = dict(self.project_args(), kind="local", roots=[str(self.root)])
        with self.assertRaisesRegex(ToolError, "Local Desktop project creation is retired"):
            preflight_action("create_project", args)
        with self.assertRaisesRegex(ToolError, "Existing native registrations are preserved"):
            self.service.execute("create_project", args, self.backend)
        self.backend.native.call.assert_not_called()
        self.assertEqual(self.backend.requests, [])
        self.assertFalse((self.root / "state").exists())

    def test_retired_local_mode_does_not_replay_old_native_creation_receipt(self):
        args = dict(self.project_args(), kind="local", roots=[str(self.root)])
        self.service.state_root.mkdir()
        receipt = self.service.state_root / (args["operation_id"] + ".json")
        receipt.write_text('{"status":"complete","result":{"project":{"id":"existing"}}}', encoding="utf8")
        before = receipt.read_bytes()
        with self.assertRaisesRegex(ToolError, "retired"):
            self.service.execute("create_project", args, self.backend)
        self.assertEqual(receipt.read_bytes(), before)
        self.backend.native.call.assert_not_called()

    def project_args(self):
        return {"kind": "chatgpt", "name": "Verification", "operation_id": str(uuid.uuid4())}

    def test_environment_listing_uses_durable_catalog_and_omits_sensitive_fields(self):
        result = self.service.execute("list_cloud_environments", {"limit": 1}, self.backend)
        self.assertEqual(self.backend.requests, [("GET", "/v1/environment-configs?scope=user&limit=1&omitDraft=true", None)])
        self.assertEqual(result, {"scope": "user", "items": [{"id": "test-config", "name": "Saved"}], "cursor": "next"})

    def test_environment_creation_uses_same_backend_and_disables_onboarding(self):
        configuration = {"name": "Requested", "repositories": [], "network_policy": {"type": "disabled"}, "share_settings": "private"}
        result = self.service.execute("create_cloud_environment", {"operation_id": str(uuid.uuid4()), "configuration": configuration}, self.backend)
        self.assertEqual(self.backend.requests, [("POST", "/v1/environment-configs", dict(configuration, start_onboarding=False))])
        self.assertEqual(result["status"], "pending")

    def test_publication_requires_success_and_exact_account_bound_receipt(self):
        begin = {"operation_id": str(uuid.uuid4()), "configuration_id": "test-config", "expected_revision": 2}
        result = self.service.execute("publish_cloud_environment", begin, self.backend)
        self.assertEqual(result["state"], "RUNNING")
        complete = {"operation_id": str(uuid.uuid4()), "configuration_id": "test-config", "backend_operation_id": "publication"}
        with self.assertRaisesRegex(ToolError, "has not succeeded"):
            self.service.execute("complete_cloud_environment_publication", complete, self.backend)
        self.assertFalse(any(r[1].endswith("/approve/complete") for r in self.backend.requests))
        self.backend.publication_state = "SUCCEEDED"
        result = self.service.execute("complete_cloud_environment_publication", complete, self.backend)
        self.assertEqual(result["latest_ready_version_id"], "ready-version")
        self.backend.account_hash = "another-account"
        with self.assertRaisesRegex(ToolError, "exact publication receipt"):
            self.service.execute("complete_cloud_environment_publication", complete, self.backend)

    def test_publication_cannot_complete_an_unbound_operation(self):
        args = {"operation_id": str(uuid.uuid4()), "configuration_id": "test-config", "backend_operation_id": "publication"}
        with self.assertRaisesRegex(ToolError, "exact publication receipt"):
            self.service.execute("complete_cloud_environment_publication", args, self.backend)
        self.assertEqual(self.backend.requests, [])

    def test_configuration_readback_omits_private_fields_and_preserves_revision(self):
        result = self.service.execute("read_cloud_environment", {"configuration_id": "test-config"}, self.backend)
        self.assertEqual(result, {"id": "test-config", "status": "pending", "draft": {"id": "draft", "revision": 2}})
        with self.assertRaises(ToolError):
            self.service.execute("read_cloud_environment", {"configuration_id": "../another-route"}, self.backend)

    def test_duplicate_creation_is_not_sent_again_after_service_restart(self):
        args = self.project_args()
        first = self.service.execute("create_project", args, self.backend)
        restarted = Service(self.root / "state", self.root / "exports")
        second = restarted.execute("create_project", args, self.backend)
        self.assertEqual(first["projectId"], "g-p-verification")
        self.assertEqual(first, second)
        self.assertEqual(len(self.backend.requests), 1)

    def test_lost_response_blocks_replay_after_restart(self):
        args = self.project_args()
        self.backend.fail_after_submission = True
        with self.assertRaises(TimeoutError):
            self.service.execute("create_project", args, self.backend)
        self.backend.fail_after_submission = False
        restarted = Service(self.root / "state", self.root / "exports")
        with self.assertRaisesRegex(ToolError, "may already have executed"):
            restarted.execute("create_project", args, self.backend)
        self.assertEqual(len(self.backend.requests), 1)

    def test_payload_or_account_change_cannot_reuse_operation(self):
        args = self.project_args()
        self.service.execute("create_project", args, self.backend)
        changed = dict(args, name="Another project")
        with self.assertRaises(ToolError):
            self.service.execute("create_project", changed, self.backend)
        self.backend.account_hash = "another-account"
        with self.assertRaises(ToolError):
            self.service.execute("create_project", args, self.backend)
        self.assertEqual(len(self.backend.requests), 1)

    def test_local_creation_rejects_missing_root_before_remote_action(self):
        args = dict(self.project_args(), kind="local", roots=[str(self.root / "missing")])
        with self.assertRaises(ToolError):
            self.service.execute("create_project", args, self.backend)
        self.backend.native.call.assert_not_called()
        self.assertFalse((self.root / "state").exists())

    def test_saved_configuration_is_selected_and_lost_first_turn_keeps_identity(self):
        args = {"operation_id": str(uuid.uuid4()), "environment_config_id": "verified-saved-config", "cwd": "/workspace/repo", "prompt": "Requested task"}
        result = self.service.execute("create_cloud_thread", args, self.backend)
        self.assertEqual(self.backend.requests[0], ("thread/start", {"ephemeral": False, "threadSource": "user", "deferredEnvironment": True,
                          "environments": [{"environmentConfigId": "verified-saved-config", "cwd": "/workspace/repo"}]}))
        self.assertEqual(result["threadId"], "test-thread")
        self.assertTrue(result["followupUnconfirmed"])
        self.assertFalse(result["firstTurnStarted"])
        before = len(self.backend.requests)
        self.service.execute("create_cloud_thread", args, self.backend)
        self.assertEqual(len(self.backend.requests), before)

    def test_private_export_has_exact_bytes_hash_and_no_base64_in_result(self):
        result = self.service.execute("export_cloud_file", {"environment_id": "exact-environment", "path": "/workspace/still.png", "relative_destination": "lane/still.png"}, self.backend)
        self.assertEqual(Path(result["path"]).read_bytes(), b"abc")
        self.assertEqual(result["sha256"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertEqual(result["bytes"], 3)
        self.assertNotIn("dataBase64", result)
        self.assertEqual(self.backend.requests, [("fs/readFile", {"environmentId": "exact-environment", "path": "/workspace/still.png"})])

    def test_export_rejects_wrong_hash_and_limit_without_publication(self):
        for kwargs in [{"expected": "0" * 64}, {"max_bytes": 2}]:
            with self.assertRaises(ToolError):
                save_export(self.root / "exports", "still.png", b"abc", **kwargs)
        self.assertFalse((self.root / "exports" / "still.png").exists())

    def test_export_rejects_traversal_and_preserves_conflicting_file(self):
        with self.assertRaises(ToolError):
            save_export(self.root / "exports", "../escape.png", b"abc")
        first = save_export(self.root / "exports", "existing.png", b"abc")
        with self.assertRaises(ToolError):
            save_export(self.root / "exports", "existing.png", b"changed")
        self.assertEqual(Path(first["path"]).read_bytes(), b"abc")
        self.assertTrue(save_export(self.root / "exports", "existing.png", b"abc")["reused"])

    def test_cloud_path_boundary(self):
        self.assertEqual(absolute_cloud_path("/workspace/a.mp4"), "/workspace/a.mp4")
        for path in ["relative.mp4", "/workspace/../secret", "//host/file", "/workspace/\\x", "/x\x00"]:
            with self.assertRaises(ToolError):
                absolute_cloud_path(path)


if __name__ == "__main__":
    unittest.main()
