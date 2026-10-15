from pathlib import Path
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import codex_project as cp


class FakeRPC:
    def __init__(self, root, rows=None):
        self.root = root
        self.rows = rows or []
        self.calls = []
        self.stored = {"id": "stored", "cwd": str(root / "old"), "projectId": None}

    def call(self, method, params):
        self.calls.append((method, params))
        if method == "thread/read":
            return {"thread": dict(self.stored)}
        if method == "project/list":
            return {"data": self.rows}
        if method == "project/create":
            project = {"id": "created", "roots": params["roots"]}
            self.rows.append(project)
            return {"project": project}
        if method == "project/read":
            return {"project": next(p for p in self.rows if p["id"] == params["projectId"])}
        if method == "thread/metadata/update":
            self.stored["projectId"] = params["projectId"]
            return {}
        raise AssertionError(method)


class AssociationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.gettempdir()) / ("codex-project-test-" + str(uuid.uuid4()))
        self.root.mkdir()  # Ordinary inherited access; no ACL/permission changes.
        self.addCleanup(shutil.rmtree, self.root)

    def test_durable_host_refuses_before_rpc_or_mutation(self):
        rpc = FakeRPC(self.root)
        with self.assertRaisesRegex(cp.AssociationError, "Unsupported association host 'durable'"):
            cp.associate(rpc, root=self.root, name="Project", thread_id="stored", apply=True,
                         expect_project="none", key=str(uuid.uuid4()), host_id="durable")
        self.assertEqual(rpc.calls, [])

    def test_cli_host_refusal_does_not_connect(self):
        with patch.object(cp, "connected") as connect, contextlib.redirect_stderr(io.StringIO()) as errors:
            result = cp.main(["--codex-exe", "unused.exe", "--root", str(self.root),
                              "--name", "Project", "--thread-id", "stored", "--host-id", "durable"])
        self.assertEqual(result, 1)
        connect.assert_not_called()
        self.assertIn("actual host", errors.getvalue())

    def test_existing_sidebar_project_remains_native_only_without_duplicate_write(self):
        rpc = FakeRPC(self.root, [{"id": "existing", "roots": [{"path": str(self.root)}]}])
        rpc.stored["projectId"] = "existing"
        result = cp.associate(rpc, root=self.root, name="Project", thread_id="stored",
                              apply=True, expect_project="existing")
        self.assertEqual(result["project_id"], "existing")
        self.assertEqual(result["scope"], "local_native_registry_only")
        self.assertEqual(result["outcomes"], {"native_registry": "verified",
                         "desktop_sidebar_adoption": "unsupported", "thread_association": "verified"})
        self.assertFalse(result["ui_refresh_verified"])
        self.assertFalse(any(method in {"project/create", "thread/metadata/update"} for method, _ in rpc.calls))

    def test_unloaded_thread_error_identifies_local_routing_without_resume(self):
        rpc = FakeRPC(self.root)
        with patch.object(rpc, "call", side_effect=cp.AssociationError("thread/read refused: thread not loaded: stored")) as call:
            with self.assertRaisesRegex(cp.AssociationError, "actual host and persistence"):
                cp.associate(rpc, root=self.root, name="Project", thread_id="stored")
        call.assert_called_once_with("thread/read", {"threadId": "stored", "includeTurns": False})

    def test_preview_does_not_write_or_resume(self):
        rpc = FakeRPC(self.root)
        result = cp.associate(rpc, root=self.root, name="Project", thread_id="stored")
        self.assertEqual(result["status"], "planned")
        self.assertEqual(result["outcomes"]["native_registry"], "not_created")
        self.assertEqual(result["outcomes"]["thread_association"], "not_attempted")
        self.assertEqual([m for m, _ in rpc.calls], ["thread/read", "project/list"])

    def test_create_assign_readback_without_cwd_change(self):
        rpc = FakeRPC(self.root)
        result = cp.associate(rpc, root=self.root, name="Project", thread_id="stored",
                              apply=True, expect_project="none", key=str(uuid.uuid4()))
        self.assertEqual(result["status"], "persisted")
        self.assertEqual(rpc.stored["projectId"], "created")
        self.assertEqual(rpc.stored["cwd"], str(self.root / "old"))
        self.assertNotIn("thread/resume", [m for m, _ in rpc.calls])

    def test_reuse_existing_root_does_not_create(self):
        rpc = FakeRPC(self.root, [{"id": "existing", "roots": [{"path": str(self.root)}]}])
        result = cp.associate(rpc, root=self.root, name="New Name", thread_id="stored",
                              apply=True, expect_project="none")
        self.assertEqual(result["project_id"], "existing")
        self.assertNotIn("project/create", [m for m, _ in rpc.calls])

    def test_ambiguous_root_and_changed_expectation_block_before_mutation(self):
        for rows, expected in [([{"id": str(i), "roots": [{"path": str(self.root)}]} for i in range(2)], "none"), ([], "other")]:
            rpc = FakeRPC(self.root, rows)
            with self.assertRaises(cp.AssociationError):
                cp.associate(rpc, root=self.root, name="Project", thread_id="stored",
                             apply=True, expect_project=expected, key=str(uuid.uuid4()))
            self.assertFalse(any(m in {"project/create", "thread/metadata/update"} for m, _ in rpc.calls))

    def test_unknown_api_or_unpersisted_thread_creates_nothing(self):
        class Unsupported(FakeRPC):
            def call(self, method, params):
                self.calls.append((method, params))
                raise cp.AssociationError("no rollout found")
        rpc = Unsupported(self.root)
        with self.assertRaises(cp.AssociationError):
            cp.associate(rpc, root=self.root, name="Project", thread_id="stored", apply=True, expect_project="none")
        self.assertEqual(len(rpc.calls), 1)

    def test_pagination_checks_all_projects_and_refuses_loop(self):
        class Paged:
            def call(self, method, params):
                if "cursor" not in params:
                    return {"data": [{"id": "one"}], "nextCursor": "next"}
                return {"data": [{"id": "two"}]}
        self.assertEqual([p["id"] for p in cp.projects(Paged())], ["one", "two"])
        class Looped:
            def call(self, method, params):
                return {"data": [], "nextCursor": "same"}
        with self.assertRaises(cp.AssociationError):
            cp.projects(Looped())

    def test_concurrent_membership_change_after_creation_is_preserved(self):
        class Changed(FakeRPC):
            def call(self, method, params):
                value = super().call(method, params)
                if method == "project/create":
                    self.stored["projectId"] = "another-writer"
                return value
        rpc = Changed(self.root)
        with self.assertRaises(cp.AssociationError):
            cp.associate(rpc, root=self.root, name="Project", thread_id="stored",
                         apply=True, expect_project="none", key=str(uuid.uuid4()))
        self.assertEqual(rpc.stored["projectId"], "another-writer")
        self.assertNotIn("thread/metadata/update", [m for m, _ in rpc.calls])




class AppPlacementTests(unittest.TestCase):
    def test_exact_active_app_host_and_project(self):
        self.assertEqual(cp.verify_app_placement({'id': 'chat', 'hostId': 'local', 'projectId': 'saved'},
            thread_id='chat', project_id='saved')['status'], 'verified')

    def test_wrong_host_null_project_wrong_identity_and_cwd_only_fail(self):
        for observed in ({'id': 'chat', 'hostId': 'durable', 'projectId': 'saved'},
                         {'id': 'chat', 'hostId': 'local', 'projectId': None},
                         {'id': 'chat', 'hostId': 'local', 'projectId': 'other'},
                         {'id': 'other', 'hostId': 'local', 'projectId': 'saved'},
                         {'id': 'chat', 'cwd': '/workspace', 'projectId': 'saved'}):
            with self.subTest(observed=observed), self.assertRaises(cp.AssociationError):
                cp.verify_app_placement(observed, thread_id='chat', project_id='saved')


    def test_readback_cli_never_connects_to_native_server(self):
        with tempfile.TemporaryDirectory() as folder:
            readback = Path(folder) / 'app-readback.json'
            readback.write_text(json.dumps({'id': 'chat', 'hostId': 'local', 'projectId': 'saved'}))
            with patch.object(cp, 'connected') as connect, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cp.main(['--verify-app-readback', str(readback), '--thread-id', 'chat', '--project-id', 'saved']), 0)
                connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
