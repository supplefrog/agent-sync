from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO / "integrations" / "hermes" / "kanban-caretaker" / "caretaker.py"
)
PLUGIN_DIR = REPO / "integrations" / "hermes" / "kanban-caretaker"


def load_module():
    spec = importlib.util.spec_from_file_location("kanban_caretaker_test_core", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def create_board(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
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
            tenant TEXT,
            idempotency_key TEXT,
            current_run_id INTEGER,
            block_kind TEXT
        );
        CREATE TABLE task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            run_id INTEGER,
            kind TEXT NOT NULL,
            payload TEXT,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE task_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            author TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE task_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL,
            outcome TEXT,
            summary TEXT,
            metadata TEXT,
            ended_at INTEGER
        );
        CREATE TABLE kanban_notify_subs (
            task_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            chat_type TEXT,
            thread_id TEXT NOT NULL DEFAULT '',
            user_id TEXT,
            notifier_profile TEXT,
            created_at INTEGER NOT NULL,
            last_event_id INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (task_id, platform, chat_id, thread_id)
        );
        """
    )
    return connection


class KanbanCaretakerTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "hermes"
        self.board = "test-board"
        self.db = self.home / "kanban" / "boards" / self.board / "kanban.db"
        self.connection = create_board(self.db)
        self.addCleanup(self.connection.close)
        self.settings = self.module.Settings(
            hermes_home=self.home,
            boards=(self.board,),
            assignee="default",
            workspace=self.root / "workspace",
            tenant="test",
            priority=100,
            skills=("agent-orchestration-operations",),
            max_runtime="1h",
            max_retries=1,
            hermes_command="hermes",
            audit_log=self.root / "audit.jsonl",
        )

    def test_board_scoped_subprocess_pin_overrides_inherited_db_pin(self):
        with patch.dict(
            os.environ,
            {"HERMES_KANBAN_DB": "stale.db", "HERMES_KANBAN_BOARD": "default"},
        ):
            env = self.module._hermes_subprocess_env(
                ["kanban", "--board", "test-board", "notify-list"]
            )

        self.assertEqual(env["HERMES_KANBAN_BOARD"], "test-board")
        self.assertNotIn("HERMES_KANBAN_DB", env)
        self.assertEqual(
            self.module._hermes_subprocess_args(
                ["kanban", "--board", "test-board", "notify-list"]
            ),
            ["kanban", "notify-list"],
        )

    def add_task(
        self,
        task_id: str,
        *,
        status: str,
        title: str = "source",
        created_by: str = "worker",
        block_kind: str | None = "needs_input",
        priority: int = 0,
        idempotency_key: str | None = None,
        body: str = "",
    ) -> None:
        self.connection.execute(
            "INSERT INTO tasks(id,title,body,status,priority,created_by,created_at,"
            "block_kind,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                task_id,
                title,
                body,
                status,
                priority,
                created_by,
                10,
                block_kind,
                idempotency_key,
            ),
        )
        self.connection.commit()

    def add_event(self, task_id: str, kind: str, payload: dict, run_id: int = 1) -> int:
        cursor = self.connection.execute(
            "INSERT INTO task_events(task_id,run_id,kind,payload,created_at) "
            "VALUES(?,?,?,?,?)",
            (task_id, run_id, kind, json.dumps(payload), 11),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_comment(
        self, task_id: str, body: str, created_at: int = 12, author: str = "caretaker"
    ) -> int:
        cursor = self.connection.execute(
            "INSERT INTO task_comments(task_id,author,body,created_at) VALUES(?,?,?,?)",
            (task_id, author, body, created_at),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_run(
        self,
        task_id: str,
        summary: str,
        *,
        status: str = "done",
        outcome: str = "completed",
        ended_at: int = 14,
        metadata: dict | None = None,
    ) -> None:
        self.connection.execute(
            "INSERT INTO task_runs(task_id,status,outcome,summary,metadata,ended_at) "
            "VALUES(?,?,?,?,?,?)",
            (task_id, status, outcome, summary, json.dumps(metadata) if metadata else None, ended_at),
        )
        self.connection.commit()

    def add_blocked_source_run(self, run_id: int = 7) -> None:
        self.connection.execute(
            "INSERT INTO task_runs(id,task_id,status,outcome,summary,ended_at) "
            "VALUES(?,?,?,?,?,?)",
            (run_id, "t_source", "blocked", "blocked", "bounded blocker", 11),
        )
        self.connection.commit()

    def terminal_review_metadata(
        self,
        *,
        event_id: int,
        source_run: int,
        body: str,
        evidence_comment_id: int,
        evidence_comment: str,
        external_readbacks: list[dict] | None = None,
        unresolved_decision: bool = False,
        contradictory_evidence: list[str] | None = None,
    ) -> dict:
        acceptance = body.split("Acceptance:", 1)[1].strip()
        items = [item.strip() for item in acceptance.replace(";", ",").split(",")]
        return {
            "source_task": "t_source",
            "source_event": event_id,
            "source_run": source_run,
            "terminal_review": {
                "version": 1,
                "source_body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                "acceptance_sha256": hashlib.sha256(acceptance.encode()).hexdigest(),
                "acceptance_evidence": {item: f"verified {item}" for item in items},
                "evidence_comment_id": evidence_comment_id,
                "evidence_comment_sha256": hashlib.sha256(evidence_comment.encode()).hexdigest(),
                "checks": ["focused tests passed", "independent readback passed"],
                "external_readbacks": external_readbacks or [],
                "unresolved_decisions": {
                    "user": unresolved_decision,
                    "product": False,
                    "security": False,
                },
                "irreversible_external_actions": [],
                "contradictory_evidence": contradictory_evidence or [],
                "honest_blocker": "honest blocker" in acceptance.casefold(),
                "receipt": {
                    "what_was_done": "Completed the bounded investigation.",
                    "how_checked": "Focused tests and independent readback passed.",
                    "remaining_external_follow_up": "The external issue remains open for new evidence.",
                },
            },
        }

    def test_scan_selects_actionable_block_and_uses_latest_block_event(self):
        self.add_task("t_source", status="blocked")
        first = self.add_event("t_source", "blocked", {"reason": "old"}, run_id=7)
        latest = self.add_event("t_source", "blocked", {"reason": "new"}, run_id=8)

        candidates = self.module.scan_board(self.settings, self.board)

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.task_id, "t_source")
        self.assertEqual(candidate.event_id, latest)
        self.assertNotEqual(candidate.event_id, first)
        self.assertEqual(candidate.reason, "new")
        self.assertEqual(candidate.run_id, 8)

    def test_scan_excludes_dependency_waits_and_caretaker_cards(self):
        self.add_task("t_dependency", status="blocked", block_kind="dependency")
        self.add_task(
            "t_caretaker",
            status="blocked",
            title="[caretaker] reconcile t_source",
            created_by=self.module.CARETAKER_CREATED_BY,
        )
        self.add_event("t_dependency", "blocked", {"reason": "parent open"})
        self.add_event("t_caretaker", "blocked", {"reason": "question"})

        self.assertEqual(self.module.scan_board(self.settings, self.board), [])

    def test_ensure_candidate_creates_bounded_idempotent_card(self):
        self.add_task("t_source", status="triage", block_kind="capability")
        event_id = self.add_event(
            "t_source", "block_loop_detected", {"reason": "same failure twice"}, run_id=4
        )
        candidate = self.module.scan_board(self.settings, self.board)[0]
        calls: list[list[str]] = []

        def runner(_settings, args):
            calls.append(args)
            return subprocess.CompletedProcess(args=args, returncode=0, stdout='{"id":"t_new"}', stderr="")

        result = self.module.ensure_candidate(self.settings, candidate, runner=runner)

        self.assertEqual(result["status"], "created")
        self.assertEqual(result["task_id"], "t_new")
        self.assertEqual(len(calls), 1)
        args = calls[0]
        self.assertIn("kanban-caretaker:v1:test-board:t_source:" + str(event_id), args)
        self.assertIn("--max-retries", args)
        self.assertIn("1", args)
        self.assertIn("--skill", args)
        body = args[args.index("--body") + 1]
        self.assertIn("partial evidence only", body)
        self.assertIn(self.module.AMBIGUITY_PREFIX, body)
        self.assertIn(self.module.RESOLUTION_PREFIX, body)
        self.assertIn("action=<terminal_review|complete|unblock|specify|", body)
        self.assertIn(f"event={event_id}", body)

    def test_caretaker_inherits_source_desktop_subscription(self):
        self.add_task("t_source", status="blocked")
        self.add_event("t_source", "blocked", {"reason": "needs review"})
        self.connection.execute(
            "INSERT INTO kanban_notify_subs(task_id,platform,chat_id,chat_type,"
            "thread_id,user_id,notifier_profile,created_at) VALUES(?,?,?,?,?,?,?,?)",
            ("t_source", "tui", "session-1", "dm", "", "user-1", "default", 9),
        )
        self.connection.commit()
        candidate = self.module.scan_board(self.settings, self.board)[0]
        calls: list[list[str]] = []

        def runner(_settings, args):
            calls.append(args)
            output = '{"id":"t_new"}' if args[3] == "create" else "{}"
            return subprocess.CompletedProcess(args=args, returncode=0, stdout=output, stderr="")

        result = self.module.ensure_candidate(self.settings, candidate, runner=runner)

        self.assertEqual(result["subscriptions_inherited"], 1)
        self.assertEqual([call[3] for call in calls], ["create", "notify-subscribe"])
        notify = calls[1]
        self.assertIn("t_new", notify)
        self.assertEqual(notify[notify.index("--platform") + 1], "tui")
        self.assertEqual(notify[notify.index("--chat-id") + 1], "session-1")
        self.assertEqual(notify[notify.index("--notifier-profile") + 1], "default")

    def test_existing_caretaker_repairs_missing_subscription(self):
        self.add_task("t_source", status="blocked")
        event_id = self.add_event("t_source", "blocked", {"reason": "needs review"})
        candidate = self.module.scan_board(self.settings, self.board)[0]
        self.add_task(
            "t_existing",
            status="blocked",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.connection.execute(
            "INSERT INTO kanban_notify_subs(task_id,platform,chat_id,thread_id,"
            "created_at) VALUES(?,?,?,?,?)",
            ("t_source", "tui", "session-1", "", 9),
        )
        self.connection.commit()
        calls: list[list[str]] = []

        def runner(_settings, args):
            calls.append(args)
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="{}", stderr="")

        result = self.module.ensure_candidate(self.settings, candidate, runner=runner)

        self.assertEqual(result["status"], "existing")
        self.assertEqual(result["subscriptions_inherited"], 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][3], "notify-subscribe")
        self.assertIn("t_existing", calls[0])

    def test_existing_idempotency_key_suppresses_recreation(self):
        self.add_task("t_source", status="blocked")
        event_id = self.add_event("t_source", "blocked", {"reason": "needs input"})
        candidate = self.module.scan_board(self.settings, self.board)[0]
        self.add_task(
            "t_existing",
            status="ready",
            title="[caretaker] reconcile t_source",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )

        def forbidden_runner(_settings, _args):
            raise AssertionError("runner must not be called")

        result = self.module.ensure_candidate(
            self.settings, candidate, runner=forbidden_runner
        )
        self.assertEqual(result, {
            "status": "existing",
            "task_id": "t_existing",
            "source_task_id": "t_source",
            "subscriptions_inherited": 0,
        })

    def test_operationally_failed_caretaker_retries_once_when_source_is_current(self):
        self.add_task("t_source", status="blocked")
        event_id = self.add_event("t_source", "blocked", {"reason": "review"})
        self.add_task(
            "t_caretaker",
            status="blocked",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_event("t_caretaker", "gave_up", {"error": "worker disappeared"})
        calls: list[list[str]] = []

        def runner(_settings, args):
            calls.append(args)
            connection = sqlite3.connect(self.db)
            try:
                connection.execute(
                    "UPDATE tasks SET status='ready' WHERE id='t_caretaker'"
                )
                connection.execute(
                    "INSERT INTO task_events(task_id,kind,payload,created_at) "
                    "VALUES('t_caretaker','unblocked',NULL,20)"
                )
                connection.commit()
            finally:
                connection.close()
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        outcome = self.module.recover_failed_caretakers(
            self.settings, runner=runner
        )

        self.assertEqual(outcome["errors"], [])
        self.assertEqual(outcome["recovered"][0]["caretaker_id"], "t_caretaker")
        self.assertEqual(calls[0][3], "unblock")
        self.assertIn("source t_source", calls[0][-1])
        self.assertEqual(
            self.module.recover_failed_caretakers(self.settings, runner=runner),
            {"recovered": [], "errors": []},
        )
        self.assertEqual(len(calls), 1)

    def test_ambiguity_blocked_caretaker_is_never_operationally_retried(self):
        self.add_task("t_source", status="blocked")
        event_id = self.add_event("t_source", "blocked", {"reason": "review"})
        self.add_task(
            "t_caretaker",
            status="blocked",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_event(
            "t_caretaker",
            "blocked",
            {"reason": f"{self.module.AMBIGUITY_PREFIX} source=t_source question=Choose A or B?"},
        )

        def forbidden_runner(_settings, _args):
            raise AssertionError("user decisions must remain blocked")

        self.assertEqual(
            self.module.recover_failed_caretakers(
                self.settings, runner=forbidden_runner
            ),
            {"recovered": [], "errors": []},
        )

    def test_concurrent_check_create_boundary_emits_one_caretaker(self):
        self.add_task("t_source", status="blocked")
        self.add_event("t_source", "blocked", {"reason": "race"})
        candidate = self.module.scan_board(self.settings, self.board)[0]
        barrier = threading.Barrier(8)
        counter_lock = threading.Lock()
        calls = 0
        results = []
        errors = []

        def runner(_settings, args):
            nonlocal calls
            with counter_lock:
                calls += 1
                index = calls
            connection = sqlite3.connect(self.db)
            try:
                connection.execute(
                    "INSERT INTO tasks(id,title,status,priority,created_by,created_at,"
                    "block_kind,idempotency_key) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        f"t_created_{index}",
                        "[caretaker] race",
                        "ready",
                        100,
                        self.module.CARETAKER_CREATED_BY,
                        20,
                        None,
                        candidate.idempotency_key,
                    ),
                )
                connection.commit()
            finally:
                connection.close()
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps({"id": f"t_created_{index}"}),
                stderr="",
            )

        def worker():
            try:
                barrier.wait()
                results.append(
                    self.module.ensure_candidate(self.settings, candidate, runner=runner)
                )
            except Exception as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        self.assertEqual(errors, [])
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(calls, 1)
        self.assertEqual(sum(result["status"] == "created" for result in results), 1)
        self.assertEqual(sum(result["status"] == "existing" for result in results), 7)

    def test_pending_ambiguity_surfaces_exactly_one_high_priority_question(self):
        self.add_task(
            "t_operational",
            status="blocked",
            title="[caretaker] operational failure",
            created_by=self.module.CARETAKER_CREATED_BY,
            priority=1000,
        )
        self.add_task(
            "t_low",
            status="blocked",
            title="[caretaker] low",
            created_by=self.module.CARETAKER_CREATED_BY,
            priority=1,
        )
        self.add_task(
            "t_high",
            status="blocked",
            title="[caretaker] high",
            created_by=self.module.CARETAKER_CREATED_BY,
            priority=100,
        )
        self.add_event(
            "t_operational",
            "blocked",
            {"reason": "worker could not mutate the source card"},
        )
        self.add_event(
            "t_low",
            "blocked",
            {"reason": "KANBAN_CARETAKER_AMBIGUITY source=t_a question=low?"},
        )
        self.add_event(
            "t_high",
            "blocked",
            {"reason": "KANBAN_CARETAKER_AMBIGUITY source=t_b question=high?"},
        )

        context = self.module.pending_ambiguity_context(self.settings)

        self.assertIsNotNone(context)
        self.assertIn("Question: high?", context)
        self.assertIn("source card t_b", context)
        self.assertNotIn("low?", context)
        self.assertIn("Do not dump the board", context)

    def test_recovery_scan_is_healthy_and_quiet_when_no_actionable_tasks(self):
        self.add_task("t_done", status="done", block_kind=None)
        outcome = self.module.scan_all(self.settings)
        self.assertEqual(outcome, {"created": [], "existing": [], "errors": []})
        self.assertFalse(self.settings.audit_log.exists())

    def test_resolution_context_surfaces_only_current_nonterminal_recommendation(self):
        self.add_task("t_source", status="blocked", priority=50)
        old_event = self.add_event("t_source", "blocked", {"reason": "old"})
        current_event = self.add_event("t_source", "blocked", {"reason": "current"})
        self.add_task(
            "t_old_caretaker",
            status="done",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{old_event}",
        )
        self.add_run(
            "t_old_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={old_event} "
            "action=complete recommendation=stale",
        )
        self.add_task(
            "t_current_caretaker",
            status="done",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{current_event}",
        )
        self.add_run(
            "t_current_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={current_event} "
            "action=update recommendation=remove the obsolete resource edge",
        )

        context = self.module.pending_resolution_context(self.settings)

        self.assertIsNotNone(context)
        self.assertIn("Suggested action: update", context)
        self.assertIn("remove the obsolete resource edge", context)
        self.assertNotIn("stale", context)
        self.assertIn("never bypass a rejected gate", context)

    def test_keep_blocked_resolution_does_not_wake_parent(self):
        self.add_task("t_source", status="blocked")
        event_id = self.add_event("t_source", "blocked", {"reason": "valid gate"})
        self.add_task(
            "t_caretaker",
            status="done",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=keep_blocked recommendation=await external evidence",
        )

        self.assertIsNone(self.module.pending_resolution_context(self.settings))

    def test_recovery_operator_applies_verified_unblock_once(self):
        self.add_task("t_source", status="blocked", priority=50)
        event_id = self.add_event("t_source", "blocked", {"reason": "fix then retry"})
        self.add_task(
            "t_caretaker",
            status="done",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=unblock recommendation=apply the bounded correction",
        )
        calls: list[list[str]] = []

        def runner(_settings, args):
            calls.append(args)
            connection = sqlite3.connect(self.db)
            try:
                connection.execute("UPDATE tasks SET status='todo' WHERE id='t_source'")
                connection.commit()
            finally:
                connection.close()
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        outcome = self.module.apply_verified_unblocks(self.settings, runner=runner)

        self.assertEqual(outcome["errors"], [])
        self.assertEqual(len(outcome["applied"]), 1)
        self.assertEqual(outcome["applied"][0]["source_task_id"], "t_source")
        self.assertEqual(calls[0][:4], ["kanban", "--board", self.board, "unblock"])
        self.assertIn("Caretaker-verified event", calls[0][-1])
        self.assertIsNone(self.module.pending_resolution_context(self.settings))
        self.assertEqual(
            self.module.apply_verified_unblocks(self.settings, runner=runner),
            {"applied": [], "errors": []},
        )
        self.assertEqual(len(calls), 1)

    def test_recovery_operator_terminally_completes_evidence_complete_honest_blocker(self):
        url = "https://github.com/NousResearch/hermes-agent/issues/85561"
        body = (
            f"Investigate {url}. Acceptance: reproduction or honest blocker, causal mechanism, "
            "test result, changed files, upstream readback"
        )
        self.add_task("t_source", status="blocked", body=body)
        event_id = self.add_event(
            "t_source", "blocked", {"reason": "need unavailable reporter evidence"}, run_id=7
        )
        self.add_blocked_source_run()
        evidence = (
            "Non-reproduction and causal boundary verified; 55/55 tests and 5/5 probes passed. "
            "The open issue remains the authority for future reporter evidence."
        )
        comment_id = self.add_comment("t_source", evidence)
        self.add_task(
            "t_caretaker",
            status="done",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        metadata = self.terminal_review_metadata(
            event_id=event_id,
            source_run=7,
            body=body,
            evidence_comment_id=comment_id,
            evidence_comment=evidence,
            external_readbacks=[
                {"url": url, "checked_at": int(time.time()), "observed_state": "OPEN"}
            ],
        )
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=terminal_review recommendation=bounded investigation is evidence-complete",
            metadata=metadata,
        )
        calls: list[list[str]] = []

        def runner(_settings, args):
            calls.append(args)
            connection = sqlite3.connect(self.db)
            try:
                connection.execute("UPDATE tasks SET status='done' WHERE id='t_source'")
                connection.commit()
            finally:
                connection.close()
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        outcome = self.module.apply_verified_recovery_actions(
            self.settings, runner=runner
        )

        self.assertEqual(outcome["errors"], [])
        self.assertEqual(outcome["applied"][0]["action"], "complete")
        self.assertEqual(calls[0][3], "complete")
        summary = calls[0][calls[0].index("--summary") + 1]
        self.assertIn("Completed the bounded investigation.", summary)
        self.assertIn("Focused tests and independent readback passed.", summary)
        self.assertIn("external issue remains open", summary)
        self.assertIn(f"caretaker t_caretaker, source event {event_id}, source run 7", summary)
        metadata_arg = json.loads(calls[0][calls[0].index("--metadata") + 1])
        self.assertEqual(metadata_arg["terminal_review"]["caretaker_id"], "t_caretaker")

        self.assertEqual(
            self.module.apply_verified_recovery_actions(self.settings, runner=runner),
            {"applied": [], "errors": []},
        )
        self.assertEqual(len(calls), 1)

    def test_ordinary_complete_remains_parent_reviewed(self):
        self.add_task("t_source", status="blocked", body="Acceptance: tests pass")
        event_id = self.add_event("t_source", "blocked", {"reason": "review"}, run_id=7)
        self.add_task(
            "t_caretaker",
            status="done",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=complete recommendation=accept the result",
        )

        def forbidden_runner(_settings, _args):
            raise AssertionError("ordinary completion must remain parent-reviewed")

        self.assertEqual(
            self.module.apply_verified_recovery_actions(
                self.settings, runner=forbidden_runner
            ),
            {"applied": [], "errors": []},
        )

    def test_terminal_review_rejects_genuine_ambiguity(self):
        body = "Acceptance: tests pass, product choice resolved"
        self.add_task("t_source", status="blocked", body=body)
        event_id = self.add_event("t_source", "blocked", {"reason": "choose A or B"}, run_id=7)
        self.add_blocked_source_run()
        evidence = "Tests pass, but A versus B still changes the product outcome."
        comment_id = self.add_comment("t_source", evidence)
        self.add_task(
            "t_caretaker", status="done", created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=terminal_review recommendation=close anyway",
            metadata=self.terminal_review_metadata(
                event_id=event_id, source_run=7, body=body,
                evidence_comment_id=comment_id, evidence_comment=evidence,
                unresolved_decision=True,
            ),
        )

        self.assertEqual(self.module._verified_resolutions(self.settings), [])

    def test_terminal_review_rejects_stale_forged_or_contradictory_evidence(self):
        body = "Acceptance: tests pass, review complete"
        self.add_task("t_source", status="blocked", body=body)
        event_id = self.add_event("t_source", "blocked", {"reason": "review"}, run_id=7)
        self.add_blocked_source_run()
        evidence = "All checks pass."
        comment_id = self.add_comment("t_source", evidence)
        self.add_comment("t_source", "Later review found a regression.", created_at=13)
        self.add_task(
            "t_caretaker", status="done", created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        metadata = self.terminal_review_metadata(
            event_id=event_id, source_run=7, body=body,
            evidence_comment_id=comment_id, evidence_comment=evidence,
            contradictory_evidence=["later regression"],
        )
        metadata["terminal_review"]["evidence_comment_sha256"] = "forged"
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=terminal_review recommendation=close anyway",
            metadata=metadata,
        )

        self.assertEqual(self.module._verified_resolutions(self.settings), [])

    def test_terminal_review_requires_current_external_readback(self):
        url = "https://example.test/issues/1"
        body = f"Inspect {url}. Acceptance: honest blocker, upstream readback"
        self.add_task("t_source", status="blocked", body=body)
        event_id = self.add_event("t_source", "blocked", {"reason": "evidence unavailable"}, run_id=7)
        self.add_blocked_source_run()
        evidence = "Bounded investigation complete."
        comment_id = self.add_comment("t_source", evidence)
        self.add_task(
            "t_caretaker", status="done", created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=terminal_review recommendation=close anyway",
            metadata=self.terminal_review_metadata(
                event_id=event_id, source_run=7, body=body,
                evidence_comment_id=comment_id, evidence_comment=evidence,
                external_readbacks=[
                    {"url": url, "checked_at": 1, "observed_state": "OPEN"}
                ],
            ),
        )

        self.assertEqual(self.module._verified_resolutions(self.settings), [])

    def test_terminal_review_reports_readback_failure_and_retries_without_duplicate_receipt(self):
        body = "Acceptance: tests pass"
        self.add_task("t_source", status="blocked", body=body)
        event_id = self.add_event("t_source", "blocked", {"reason": "review-required"}, run_id=7)
        self.add_blocked_source_run()
        evidence = "Repair and review checks passed."
        comment_id = self.add_comment("t_source", evidence)
        self.add_task(
            "t_caretaker", status="done", created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=terminal_review recommendation=review passed",
            metadata=self.terminal_review_metadata(
                event_id=event_id, source_run=7, body=body,
                evidence_comment_id=comment_id, evidence_comment=evidence,
            ),
        )
        calls: list[list[str]] = []

        def runner(_settings, args):
            calls.append(args)
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        first = self.module.apply_verified_recovery_actions(self.settings, runner=runner)
        second = self.module.apply_verified_recovery_actions(self.settings, runner=runner)

        self.assertEqual(first["applied"], [])
        self.assertEqual(len(first["errors"]), 1)
        self.assertEqual(second["applied"], [])
        self.assertEqual(len(second["errors"]), 1)
        self.assertEqual(len(calls), 2)

    def test_terminal_review_rejects_missing_acceptance_evidence(self):
        body = "Acceptance: tests pass, review complete"
        self.add_task("t_source", status="blocked", body=body)
        event_id = self.add_event("t_source", "blocked", {"reason": "review-required"}, run_id=7)
        self.add_blocked_source_run()
        evidence = "Repair and review checks passed."
        comment_id = self.add_comment("t_source", evidence)
        self.add_task(
            "t_caretaker", status="done", created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        metadata = self.terminal_review_metadata(
            event_id=event_id, source_run=7, body=body,
            evidence_comment_id=comment_id, evidence_comment=evidence,
        )
        del metadata["terminal_review"]["acceptance_evidence"]["review complete"]
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=terminal_review recommendation=review passed",
            metadata=metadata,
        )

        self.assertEqual(self.module._verified_resolutions(self.settings), [])

    def test_concurrent_terminal_review_scans_complete_once(self):
        body = "Acceptance: tests pass"
        self.add_task("t_source", status="blocked", body=body)
        event_id = self.add_event("t_source", "blocked", {"reason": "review-required"}, run_id=7)
        self.add_blocked_source_run()
        evidence = "Repair and review checks passed."
        comment_id = self.add_comment("t_source", evidence)
        self.add_task(
            "t_caretaker", status="done", created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=terminal_review recommendation=review passed",
            metadata=self.terminal_review_metadata(
                event_id=event_id, source_run=7, body=body,
                evidence_comment_id=comment_id, evidence_comment=evidence,
            ),
        )
        calls: list[list[str]] = []
        call_lock = threading.Lock()
        barrier = threading.Barrier(2)
        outcomes: list[dict] = []

        def runner(_settings, args):
            with call_lock:
                calls.append(args)
            connection = sqlite3.connect(self.db)
            try:
                connection.execute("UPDATE tasks SET status='done' WHERE id='t_source'")
                connection.commit()
            finally:
                connection.close()
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        def worker():
            barrier.wait()
            outcomes.append(
                self.module.apply_verified_recovery_actions(self.settings, runner=runner)
            )

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(calls), 1)
        self.assertEqual(sum(len(outcome["applied"]) for outcome in outcomes), 1)
        self.assertTrue(all(outcome["errors"] == [] for outcome in outcomes))

    def test_recovery_operator_applies_verified_archive_without_purge(self):
        self.add_task("t_source", status="blocked")
        event_id = self.add_event("t_source", "blocked", {"reason": "obsolete"})
        self.add_task(
            "t_caretaker",
            status="done",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=archive recommendation=superseded by the admitted implementation",
        )
        calls: list[list[str]] = []

        def runner(_settings, args):
            calls.append(args)
            connection = sqlite3.connect(self.db)
            try:
                connection.execute("UPDATE tasks SET status='archived' WHERE id='t_source'")
                connection.commit()
            finally:
                connection.close()
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        outcome = self.module.apply_verified_recovery_actions(
            self.settings, runner=runner
        )

        self.assertEqual(outcome["errors"], [])
        self.assertEqual(outcome["applied"][0]["action"], "archive")
        self.assertEqual(calls[0][3], "archive")
        self.assertNotIn("--rm", calls[0])

    def test_recovery_operator_applies_verified_triage_specification_once(self):
        self.add_task("t_source", status="triage", priority=50)
        event_id = self.add_event(
            "t_source", "block_loop_detected", {"reason": "concrete correction"}
        )
        self.add_task(
            "t_caretaker",
            status="done",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=specify recommendation=fold in the concrete correction",
        )
        calls: list[list[str]] = []

        def runner(_settings, args):
            calls.append(args)
            connection = sqlite3.connect(self.db)
            try:
                connection.execute("UPDATE tasks SET status='todo' WHERE id='t_source'")
                connection.commit()
            finally:
                connection.close()
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="{}", stderr="")

        outcome = self.module.apply_verified_recovery_actions(
            self.settings, runner=runner
        )

        self.assertEqual(outcome["errors"], [])
        self.assertEqual(len(outcome["applied"]), 1)
        self.assertEqual(outcome["applied"][0]["action"], "specify")
        self.assertEqual(calls[0][:4], ["kanban", "--board", self.board, "specify"])
        self.assertIn("kanban-caretaker-operator", calls[0])
        self.assertIsNone(self.module.pending_resolution_context(self.settings))
        self.assertEqual(
            self.module.apply_verified_recovery_actions(self.settings, runner=runner),
            {"applied": [], "errors": []},
        )
        self.assertEqual(len(calls), 1)

    def test_recovery_operator_maps_legacy_triage_update_to_specify_only(self):
        self.add_task("t_source", status="triage")
        event_id = self.add_event(
            "t_source", "block_loop_detected", {"reason": "concrete correction"}
        )
        self.add_task(
            "t_caretaker",
            status="done",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=update recommendation=apply the concrete correction",
        )
        calls: list[list[str]] = []

        def runner(_settings, args):
            calls.append(args)
            if args[3] == "specify":
                connection = sqlite3.connect(self.db)
                try:
                    connection.execute("UPDATE tasks SET status='todo' WHERE id='t_source'")
                    connection.commit()
                finally:
                    connection.close()
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="{}", stderr="")

        outcome = self.module.apply_verified_recovery_actions(
            self.settings, runner=runner
        )

        self.assertEqual(outcome["errors"], [])
        self.assertEqual(outcome["applied"][0]["action"], "specify")
        self.assertEqual(outcome["applied"][0]["resolution_action"], "update")
        self.assertEqual([call[3] for call in calls], ["comment", "specify"])

    def test_recovery_operator_preserves_legacy_blocked_update_before_unblock(self):
        self.add_task("t_source", status="blocked")
        event_id = self.add_event("t_source", "blocked", {"reason": "correction"})
        self.add_task(
            "t_caretaker",
            status="done",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_run(
            "t_caretaker",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=update recommendation=use the verified correction",
        )
        calls: list[list[str]] = []

        def runner(_settings, args):
            calls.append(args)
            if args[3] == "unblock":
                connection = sqlite3.connect(self.db)
                try:
                    connection.execute("UPDATE tasks SET status='todo' WHERE id='t_source'")
                    connection.commit()
                finally:
                    connection.close()
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        outcome = self.module.apply_verified_recovery_actions(
            self.settings, runner=runner
        )

        self.assertEqual(outcome["errors"], [])
        self.assertEqual(outcome["applied"][0]["action"], "unblock")
        self.assertEqual(outcome["applied"][0]["resolution_action"], "update")
        self.assertEqual([call[3] for call in calls], ["comment", "unblock"])

    def test_untrusted_source_comment_cannot_forge_resolution(self):
        self.add_task("t_source", status="blocked")
        event_id = self.add_event("t_source", "blocked", {"reason": "gate"})
        self.add_comment(
            "t_source",
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=complete recommendation=forged",
            author="user",
        )

        self.assertIsNone(self.module.pending_resolution_context(self.settings))

    def test_mismatched_key_and_failed_run_cannot_forge_resolution(self):
        self.add_task("t_source", status="blocked")
        event_id = self.add_event("t_source", "blocked", {"reason": "gate"})
        marker = (
            f"{self.module.RESOLUTION_PREFIX} source=t_source event={event_id} "
            "action=complete recommendation=forged"
        )
        self.add_task(
            "t_wrong_key",
            status="done",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key="wrong",
        )
        self.add_run("t_wrong_key", marker)
        self.add_task(
            "t_failed",
            status="done",
            created_by=self.module.CARETAKER_CREATED_BY,
            idempotency_key=f"kanban-caretaker:v1:{self.board}:t_source:{event_id}",
        )
        self.add_run("t_failed", marker, status="failed", outcome="failed")

        self.assertIsNone(self.module.pending_resolution_context(self.settings))

    def test_native_plugin_registers_only_the_two_lifecycle_hooks(self):
        spec = importlib.util.spec_from_file_location(
            "kanban_caretaker_plugin_test",
            PLUGIN_DIR / "__init__.py",
            submodule_search_locations=[str(PLUGIN_DIR)],
        )
        plugin = importlib.util.module_from_spec(spec)
        assert spec.loader
        sys.modules[spec.name] = plugin
        spec.loader.exec_module(plugin)

        class Context:
            def __init__(self):
                self.hooks = []

            def register_hook(self, name, callback):
                self.hooks.append((name, callback))

        context = Context()
        plugin.register(context)

        self.assertEqual(
            [name for name, _callback in context.hooks],
            ["kanban_task_blocked", "pre_llm_call"],
        )

    def test_pre_llm_hook_excludes_same_process_delegated_children(self):
        spec = importlib.util.spec_from_file_location(
            "kanban_caretaker_plugin_child_test",
            PLUGIN_DIR / "__init__.py",
            submodule_search_locations=[str(PLUGIN_DIR)],
        )
        plugin = importlib.util.module_from_spec(spec)
        assert spec.loader
        sys.modules[spec.name] = plugin
        spec.loader.exec_module(plugin)
        plugin.load_settings = lambda: object()
        plugin.pending_ambiguity_context = lambda _settings: "ONE QUESTION"
        plugin.pending_resolution_context = lambda _settings: None

        from agent.delegation_context import delegated_child_context

        with patch.dict(
            os.environ,
            {"HERMES_DELEGATED_CHILD_CONTEXT": "", "HERMES_KANBAN_TASK": ""},
        ):
            self.assertEqual(plugin._on_pre_llm_call(), {"context": "ONE QUESTION"})
            with delegated_child_context("child-session"):
                self.assertIsNone(plugin._on_pre_llm_call())


if __name__ == "__main__":
    unittest.main()
