from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_module():
    path = REPO / "tools" / "reconciliation_monitor.py"
    spec = importlib.util.spec_from_file_location("reconciliation_monitor", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def create_hermes_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            parent_session_id TEXT,
            started_at REAL NOT NULL,
            ended_at REAL,
            end_reason TEXT,
            message_count INTEGER DEFAULT 0,
            archived INTEGER NOT NULL DEFAULT 0,
            last_activity_at REAL
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            timestamp REAL NOT NULL
        );
        """
    )
    connection.execute(
        "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("session-1", "desktop", None, 1.0, None, None, 1, 0, 1.0),
    )
    connection.execute(
        "INSERT INTO messages(session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        ("session-1", "user", "baseline secret prompt", 1.0),
    )
    connection.commit()
    connection.close()


def create_kanban_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT,
            assignee TEXT,
            status TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            created_by TEXT,
            created_at INTEGER NOT NULL,
            started_at INTEGER,
            completed_at INTEGER,
            workspace_kind TEXT NOT NULL DEFAULT 'scratch',
            workspace_path TEXT,
            branch_name TEXT,
            tenant TEXT,
            idempotency_key TEXT,
            project_id TEXT
        );
        CREATE TABLE task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            run_id INTEGER,
            kind TEXT NOT NULL,
            payload TEXT,
            created_at INTEGER NOT NULL
        );
        """
    )
    connection.commit()
    connection.close()


def create_omp_history_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            cwd TEXT,
            session_id TEXT
        )
        """
    )
    connection.execute(
        "INSERT INTO history(prompt, created_at, cwd, session_id) VALUES (?, ?, ?, ?)",
        ("baseline OMP secret", 1, "C:/work", "omp-1"),
    )
    connection.commit()
    connection.close()


class ReconciliationMonitorTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.hermes_db = self.root / "state.db"
        self.kanban_db = self.root / "kanban.db"
        self.kanban_boards_root = self.root / "kanban" / "boards"
        self.kanban_boards_root.mkdir(parents=True)
        self.omp_history_db = self.root / "history.db"
        self.codex_sessions = self.root / "codex-sessions"
        self.codex_archived_sessions = self.root / "codex-archived-sessions"
        self.omp_sessions = self.root / "omp-sessions"
        self.codex_sessions.mkdir()
        self.codex_archived_sessions.mkdir()
        self.omp_sessions.mkdir()
        self.codex_file = self.codex_sessions / "rollout-1.jsonl"
        self.omp_file = self.omp_sessions / "session-1.jsonl"
        self.codex_file.write_text('{"content":"baseline Codex secret"}\n', encoding="utf-8")
        self.omp_file.write_text('{"content":"baseline OMP file secret"}\n', encoding="utf-8")
        create_hermes_db(self.hermes_db)
        create_kanban_db(self.kanban_db)
        create_omp_history_db(self.omp_history_db)
        self.state = self.root / "monitor-state.json"
        self.reports = self.root / "reports"

    def scan(self):
        return self.module.scan_and_update(
            state_path=self.state,
            reports_dir=self.reports,
            hermes_db=self.hermes_db,
            kanban_db=self.kanban_db,
            kanban_boards_root=self.kanban_boards_root,
            codex_sessions=self.codex_sessions,
            codex_archived_sessions=self.codex_archived_sessions,
            omp_history_db=self.omp_history_db,
            omp_sessions=self.omp_sessions,
            excluded_hermes_roots=set(),
        )

    def test_first_scan_baselines_without_queueing_historical_work_or_payloads(self):
        output = self.scan()

        self.assertEqual(output["status"], "baseline")
        self.assertEqual(output["pending"], [])
        serialized = self.state.read_text(encoding="utf-8") + json.dumps(output)
        for secret in (
            "baseline secret prompt",
            "baseline Codex secret",
            "baseline OMP secret",
            "baseline OMP file secret",
        ):
            self.assertNotIn(secret, serialized)

    def test_detects_deltas_from_sessions_kanban_codex_and_omp_without_payloads(self):
        self.scan()
        connection = sqlite3.connect(self.hermes_db)
        connection.execute(
            "INSERT INTO messages(session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            ("session-1", "user", "new Hermes secret", 2.0),
        )
        connection.execute(
            "UPDATE sessions SET message_count = 2, last_activity_at = 2.0 WHERE id = 'session-1'"
        )
        connection.commit()
        connection.close()

        connection = sqlite3.connect(self.kanban_db)
        connection.execute(
            "INSERT INTO tasks(id, title, body, status, created_at, created_by) VALUES (?, ?, ?, ?, ?, ?)",
            ("task-1", "Private title", "new Kanban secret", "todo", 2, "user"),
        )
        connection.execute(
            "INSERT INTO task_events(task_id, kind, payload, created_at) VALUES (?, ?, ?, ?)",
            ("task-1", "created", '{"secret":"new event secret"}', 2),
        )
        connection.commit()
        connection.close()

        connection = sqlite3.connect(self.omp_history_db)
        connection.execute(
            "INSERT INTO history(prompt, created_at, cwd, session_id) VALUES (?, ?, ?, ?)",
            ("new OMP history secret", 2, "C:/work", "omp-1"),
        )
        connection.commit()
        connection.close()

        with self.codex_file.open("a", encoding="utf-8") as handle:
            handle.write('{"content":"new Codex secret"}\n')
        with self.omp_file.open("a", encoding="utf-8") as handle:
            handle.write('{"content":"new OMP file secret"}\n')

        output = self.scan()

        self.assertEqual(output["status"], "pending")
        changes = output["pending"][0]["changes"]
        providers = {change["provider"] for change in changes}
        self.assertEqual(providers, {"hermes", "kanban", "codex", "omp"})
        self.assertTrue(any(change.get("native_id") == "task-1" for change in changes))
        self.assertTrue(any(change.get("native_id") == "session-1" for change in changes))
        serialized = self.state.read_text(encoding="utf-8") + json.dumps(output)
        for secret in (
            "new Hermes secret",
            "Private title",
            "new Kanban secret",
            "new event secret",
            "new OMP history secret",
            "new Codex secret",
            "new OMP file secret",
        ):
            self.assertNotIn(secret, serialized)

    def test_pending_event_retries_until_matching_receipt_then_clears(self):
        self.scan()
        with self.codex_file.open("a", encoding="utf-8") as handle:
            handle.write("{}\n")

        first = self.scan()
        second = self.scan()
        self.assertEqual(first["pending"][0]["attempt"], 1)
        self.assertEqual(second["pending"][0]["attempt"], 2)

        event = second["pending"][0]
        report = Path(event["report_path"])
        receipt = Path(event["receipt_path"])
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("verified reconciliation\n", encoding="utf-8")
        receipt.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "event_id": event["event_id"],
                    "status": "completed",
                    "report_path": event["report_path"],
                }
            ),
            encoding="utf-8",
        )

        completed = self.scan()
        self.assertEqual(completed, second)
        state = self.module.load_state(self.state)
        self.assertEqual(state["pending"], [])
        self.assertIn(event["event_id"], state["completed_event_ids"])

    def test_excluded_hermes_root_omits_the_entire_descendant_lineage(self):
        self.scan()
        connection = sqlite3.connect(self.hermes_db)
        connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("orchestrator-child", "desktop", "session-1", 2.0, None, None, 1, 0, 2.0),
        )
        connection.execute(
            "INSERT INTO messages(session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            ("orchestrator-child", "user", "excluded secret", 2.0),
        )
        connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("independent", "desktop", None, 3.0, None, None, 1, 0, 3.0),
        )
        connection.execute(
            "INSERT INTO messages(session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            ("independent", "user", "included secret", 3.0),
        )
        connection.commit()
        connection.close()

        output = self.module.scan_and_update(
            state_path=self.state,
            reports_dir=self.reports,
            hermes_db=self.hermes_db,
            kanban_db=self.kanban_db,
            kanban_boards_root=self.kanban_boards_root,
            codex_sessions=self.codex_sessions,
            codex_archived_sessions=self.codex_archived_sessions,
            omp_history_db=self.omp_history_db,
            omp_sessions=self.omp_sessions,
            excluded_hermes_roots={"session-1"},
        )

        changes = output["pending"][0]["changes"]
        hermes_ids = {
            change["native_id"]
            for change in changes
            if change["provider"] == "hermes"
        }
        self.assertIn("independent", hermes_ids)
        self.assertNotIn("session-1", hermes_ids)
        self.assertNotIn("orchestrator-child", hermes_ids)

    def test_task_metadata_change_is_detected_without_requiring_an_event_row(self):
        self.scan()
        connection = sqlite3.connect(self.kanban_db)
        connection.execute(
            "INSERT INTO tasks(id, title, status, created_at) VALUES (?, ?, ?, ?)",
            ("task-1", "Task", "todo", 1),
        )
        connection.commit()
        connection.close()
        self.scan()
        event = self.module.load_state(self.state)["pending"][0]
        report = Path(event["report_path"])
        receipt = Path(event["receipt_path"])
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("done\n", encoding="utf-8")
        receipt.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "event_id": event["event_id"],
                    "status": "completed",
                    "report_path": event["report_path"],
                }
            ),
            encoding="utf-8",
        )
        self.scan()

        connection = sqlite3.connect(self.kanban_db)
        connection.execute("UPDATE tasks SET status = 'done' WHERE id = 'task-1'")
        connection.commit()
        connection.close()

        output = self.scan()
        task_changes = [
            change
            for change in output["pending"][0]["changes"]
            if change["provider"] == "kanban" and change.get("native_id") == "task-1"
        ]
        self.assertEqual(task_changes[0]["kind"], "task-changed")

    def test_same_size_jsonl_rewrite_is_detected_as_rewrite(self):
        self.scan()
        original = self.codex_file.read_bytes()
        self.codex_file.write_bytes(b"x" * len(original))

        output = self.scan()
        codex_changes = [
            change for change in output["pending"][0]["changes"] if change["provider"] == "codex"
        ]
        self.assertEqual(codex_changes[0]["kind"], "source-rewritten")

    def test_archived_codex_session_append_is_detected(self):
        archived = self.codex_archived_sessions / "archived.jsonl"
        archived.write_text("{}\n", encoding="utf-8")
        self.scan()
        with archived.open("a", encoding="utf-8") as handle:
            handle.write("{}\n")

        output = self.scan()

        self.assertTrue(
            any(
                change["provider"] == "codex"
                and change["kind"] == "source-appended"
                and change["native_id"] == "archived"
                for change in output["pending"][0]["changes"]
            )
        )

    def test_cron_sessions_do_not_retrigger_but_their_kanban_tasks_do(self):
        self.scan()
        connection = sqlite3.connect(self.hermes_db)
        connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("cron-1", "cron", None, 2.0, None, None, 1, 0, 2.0),
        )
        connection.execute(
            "INSERT INTO messages(session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            ("cron-1", "assistant", "cron secret", 2.0),
        )
        connection.commit()
        connection.close()
        connection = sqlite3.connect(self.kanban_db)
        connection.execute(
            "INSERT INTO tasks(id, title, status, created_at, created_by) VALUES (?, ?, ?, ?, ?)",
            ("task-from-cron", "Cron-created task", "todo", 2, "cron"),
        )
        connection.commit()
        connection.close()

        output = self.scan()

        changes = output["pending"][0]["changes"]
        self.assertFalse(any(change["provider"] == "hermes" for change in changes))
        self.assertTrue(
            any(
                change["provider"] == "kanban"
                and change["native_id"] == "task-from-cron"
                for change in changes
            )
        )
        self.assertNotIn("cron secret", json.dumps(output))

    def test_new_board_and_task_are_discovered_without_switching_boards(self):
        self.scan()
        project_db = self.kanban_boards_root / "project-x" / "kanban.db"
        project_db.parent.mkdir()
        create_kanban_db(project_db)
        connection = sqlite3.connect(project_db)
        connection.execute(
            "INSERT INTO tasks(id, title, status, created_at) VALUES (?, ?, ?, ?)",
            ("project-task", "Project task", "todo", 2),
        )
        connection.commit()
        connection.close()

        output = self.scan()

        self.assertTrue(
            any(
                change["provider"] == "kanban"
                and change["board"] == "project-x"
                and change["native_id"] == "project-task"
                for change in output["pending"][0]["changes"]
            )
        )


if __name__ == "__main__":
    unittest.main()
