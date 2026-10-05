from pathlib import Path
import sys
import tempfile
import unittest
import uuid

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
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_preview_does_not_write_or_resume(self):
        rpc = FakeRPC(self.root)
        result = cp.associate(rpc, root=self.root, name="Project", thread_id="stored")
        self.assertEqual(result["status"], "planned")
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


if __name__ == "__main__":
    unittest.main()
