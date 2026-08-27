from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_module():
    path = REPO / "tools" / "context_ledger.py"
    spec = importlib.util.spec_from_file_location("context_ledger", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class ContextLedgerTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "ledger.sqlite"
        self.ledger = self.module.ContextLedger(self.db)
        self.addCleanup(lambda: self.ledger.close())

    def test_execution_identity_is_native_and_idempotent(self):
        first = self.ledger.observe_execution(
            provider="codex",
            native_id="thread-1",
            provider_version="0.147.0-alpha.6.6",
            observed_at="2026-08-13T00:00:00Z",
        )
        second = self.ledger.observe_execution(
            provider="codex",
            native_id="thread-1",
            provider_version="0.147.0-alpha.6.6",
            observed_at="2026-08-13T00:01:00Z",
        )
        imported = self.ledger.observe_execution(
            provider="omp",
            native_id="imported-thread-1",
            provider_version="1.0",
            observed_at="2026-08-13T00:02:00Z",
        )

        self.assertEqual(first, second)
        self.assertNotEqual(first, imported)
        self.assertEqual(self.ledger.count("executions"), 2)

    def test_execution_observation_bounds_survive_out_of_order_reads(self):
        execution = self.ledger.observe_execution(
            "hermes", "session-1", "0.2", "2026-08-13T00:02:00Z"
        )
        self.ledger.observe_execution(
            "hermes", "session-1", "0.1", "2026-08-13T00:01:00Z"
        )

        row = self.ledger.connection.execute(
            """
            SELECT provider_version, first_observed_at, last_observed_at
            FROM executions WHERE execution_id = ?
            """,
            (execution,),
        ).fetchone()
        self.assertEqual(
            row,
            (
                "0.2",
                "2026-08-13T00:01:00.000000Z",
                "2026-08-13T00:02:00.000000Z",
            ),
        )

    def test_execution_observations_are_normalized_before_comparison(self):
        execution = self.ledger.observe_execution(
            "hermes", "session-offset", "0.1", "2026-08-13T00:30:00+01:00"
        )
        self.ledger.observe_execution(
            "hermes", "session-offset", "0.2", "2026-08-12T23:45:00Z"
        )

        row = self.ledger.connection.execute(
            """
            SELECT provider_version, first_observed_at, last_observed_at
            FROM executions WHERE execution_id = ?
            """,
            (execution,),
        ).fetchone()
        self.assertEqual(
            row,
            ("0.2", "2026-08-12T23:30:00.000000Z", "2026-08-12T23:45:00.000000Z"),
        )

    def test_jsonl_ingestion_is_idempotent_and_never_stores_payloads(self):
        source = self.root / "rollout.jsonl"
        secret = "do-not-copy-this-payload"
        source.write_text(
            json.dumps({"id": "e1", "type": "message", "content": secret}) + "\n"
            + json.dumps({"id": "e2", "type": "compaction", "content": "summary"}) + "\n",
            encoding="utf-8",
        )

        first = self.ledger.ingest_jsonl(
            provider="codex",
            source=source,
            provider_version="0.147.0-alpha.6.6",
            extractor_version="test-v1",
        )
        second = self.ledger.ingest_jsonl(
            provider="codex",
            source=source,
            provider_version="0.147.0-alpha.6.6",
            extractor_version="test-v1",
        )

        self.assertEqual(first["events_added"], 2)
        self.assertEqual(second["events_added"], 0)
        self.assertEqual(self.ledger.count("source_events"), 2)
        self.assertNotIn(secret.encode(), self.db.read_bytes())

    def test_payload_field_cannot_be_persisted_as_event_time(self):
        source = self.root / "payload-time.jsonl"
        secret = "do-not-copy-this-payload"
        source.write_text(
            json.dumps({"id": "e1", "content": secret}) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        with self.assertRaisesRegex(ValueError, "timestamp-shaped"):
            self.ledger.ingest_jsonl(
                "codex",
                source,
                "1",
                "test-v1",
                event_time_field="content",
            )

        self.ledger.close()
        stored = b"".join(
            path.read_bytes()
            for path in (self.db, Path(str(self.db) + "-wal"), Path(str(self.db) + "-shm"))
            if path.exists()
        )
        self.assertNotIn(secret.encode(), stored)
        self.ledger = self.module.ContextLedger(self.db)
        self.assertEqual(self.ledger.count("source_events"), 0)
        self.assertEqual(self.ledger.count("source_event_derivations"), 0)
        self.assertEqual(self.ledger.count("ingestion_cursors"), 0)

    def test_partial_jsonl_tail_does_not_advance_cursor(self):
        source = self.root / "session.jsonl"
        first = (json.dumps({"id": "e1", "type": "message"}) + "\n").encode()
        partial = b'{"id":"e2","type":"tool"'
        source.write_bytes(first + partial)

        initial = self.ledger.ingest_jsonl(
            provider="omp",
            source=source,
            provider_version="1.0",
            extractor_version="test-v1",
        )
        self.assertEqual(initial["events_added"], 1)
        self.assertEqual(initial["cursor_bytes"], len(first))

        with source.open("ab") as handle:
            handle.write(b"}\n")
        completed = self.ledger.ingest_jsonl(
            provider="omp",
            source=source,
            provider_version="1.0",
            extractor_version="test-v1",
        )
        self.assertEqual(completed["events_added"], 1)
        self.assertEqual(self.ledger.count("source_events"), 2)

    def test_source_replacement_below_cursor_fails_closed(self):
        source = self.root / "session.jsonl"
        original = (json.dumps({"id": "e1", "type": "message"}) + "\n").encode()
        source.write_bytes(original)
        self.ledger.ingest_jsonl("omp", source, "1.0", "test-v1")
        source.write_bytes(b"x" * len(original))

        with self.assertRaisesRegex(ValueError, "changed before durable cursor"):
            self.ledger.ingest_jsonl("omp", source, "1.0", "test-v1")

        self.assertEqual(self.ledger.count("source_events"), 1)

    def test_provider_time_and_observation_time_are_preserved_separately(self):
        source = self.root / "out-of-order.jsonl"
        source.write_text(
            json.dumps({"id": "later", "timestamp": "2026-08-13T00:02:00Z"}) + "\n"
            + json.dumps({"id": "earlier", "timestamp": "2026-08-13T00:01:00Z"}) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self.ledger.ingest_jsonl(
            "codex",
            source,
            "0.147.0-alpha.6.6",
            "test-v1",
            event_time_field="timestamp",
        )

        rows = self.ledger.connection.execute(
            "SELECT provider_event_time, observed_at FROM source_events ORDER BY source_locator"
        ).fetchall()
        self.assertEqual([row[0] for row in rows], ["2026-08-13T00:02:00Z", "2026-08-13T00:01:00Z"])
        self.assertTrue(all(row[1] for row in rows))

    def test_malformed_complete_record_does_not_advance_cursor(self):
        source = self.root / "malformed.jsonl"
        source.write_bytes(b'{"id":"broken"\n')

        with self.assertRaisesRegex(ValueError, "malformed complete JSONL record"):
            self.ledger.ingest_jsonl("omp", source, "1.0", "test-v1")

        self.assertEqual(self.ledger.count("source_events"), 0)
        self.assertEqual(self.ledger.count("ingestion_cursors"), 0)

    def test_replay_reconstructs_equivalent_source_event_ids(self):
        source = self.root / "replay.jsonl"
        source.write_text(
            json.dumps({"id": "e1"}) + "\n" + json.dumps({"id": "e2"}) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self.ledger.ingest_jsonl("codex", source, "1", "test-v1")
        original_ids = {
            row[0]
            for row in self.ledger.connection.execute("SELECT source_event_id FROM source_events")
        }
        self.ledger.close()
        self.db.unlink()
        self.ledger = self.module.ContextLedger(self.db)
        self.ledger.ingest_jsonl("codex", source, "1", "test-v1")
        replayed_ids = {
            row[0]
            for row in self.ledger.connection.execute("SELECT source_event_id FROM source_events")
        }

        self.assertEqual(original_ids, replayed_ids)

    def test_replay_with_new_versions_preserves_each_derivation(self):
        source = self.root / "versioned.jsonl"
        source.write_text(
            json.dumps({"id": "e1", "timestamp": "2026-08-13T00:00:00Z"}) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        first = self.ledger.ingest_jsonl(
            "codex", source, "provider-v1", "extractor-v1", "timestamp"
        )
        second = self.ledger.ingest_jsonl(
            "codex", source, "provider-v2", "extractor-v1", "timestamp"
        )
        third = self.ledger.ingest_jsonl(
            "codex", source, "provider-v2", "extractor-v2", "timestamp"
        )

        rows = self.ledger.connection.execute(
            """
            SELECT provider_version, extractor_version
            FROM source_event_derivations
            ORDER BY provider_version, extractor_version
            """
        ).fetchall()
        self.assertEqual(first["events_added"], 1)
        self.assertEqual(second["events_added"], 1)
        self.assertEqual(third["events_added"], 1)
        self.assertEqual(self.ledger.count("source_events"), 1)
        self.assertEqual(
            rows,
            [
                ("provider-v1", "extractor-v1"),
                ("provider-v2", "extractor-v1"),
                ("provider-v2", "extractor-v2"),
            ],
        )

    def test_lineage_and_contradictory_assertions_are_append_only(self):
        parent = self.ledger.observe_execution("hermes", "parent", "0.20.0", "2026-08-13T00:00:00Z")
        child = self.ledger.observe_execution("hermes", "child", "0.20.0", "2026-08-13T00:00:01Z")
        event_a = self.ledger.record_source_event(
            provider="hermes",
            source_locator="sqlite:///state.db#table=sessions&row=child",
            source_digest="a" * 64,
            provider_version="0.20.0",
            extractor_version="test-v1",
            observed_at="2026-08-13T00:00:02Z",
        )
        event_b = self.ledger.record_source_event(
            provider="hermes",
            source_locator="sqlite:///state.db#table=sessions&row=child&field=end_reason",
            source_digest="b" * 64,
            provider_version="0.20.0",
            extractor_version="test-v1",
            observed_at="2026-08-13T00:00:03Z",
        )

        self.ledger.assert_lineage(child, parent, "continuation", event_a, "test-v1")
        self.ledger.record_assertion(child, "task-status", "running", event_a, "test-v1")
        self.ledger.record_assertion(child, "task-status", "completed", event_b, "test-v1")

        self.assertEqual(self.ledger.count("lineage_assertions"), 1)
        self.assertEqual(self.ledger.count("assertions"), 2)
        values = self.ledger.assertion_values(child, "task-status")
        self.assertEqual(values, ["running", "completed"])

    def test_direct_source_event_write_survives_reopen(self):
        event_id = self.ledger.record_source_event(
            provider="hermes",
            source_locator="sqlite:///state.db#table=sessions&row=one",
            source_digest="c" * 64,
            provider_version="0.20.0",
            extractor_version="test-v1",
            observed_at="2026-08-13T00:00:00Z",
        )
        self.ledger.close()
        self.ledger = self.module.ContextLedger(self.db)

        row = self.ledger.connection.execute(
            "SELECT source_event_id FROM source_events WHERE source_event_id = ?",
            (event_id,),
        ).fetchone()
        self.assertEqual(row, (event_id,))

    def test_direct_metadata_apis_reject_payload_shaped_strings(self):
        with self.assertRaisesRegex(ValueError, "source locator"):
            self.ledger.record_source_event(
                provider="codex",
                source_locator="user said: please keep this complete prompt",
                source_digest="a" * 64,
                provider_version="1",
                extractor_version="test-v1",
                observed_at="2026-08-13T00:00:00Z",
            )
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.ledger.record_source_event(
                provider="codex",
                source_locator="file:///safe.jsonl#bytes=0-2",
                source_digest="not-a-digest",
                provider_version="1",
                extractor_version="test-v1",
                observed_at="2026-08-13T00:00:00Z",
            )
        child = self.ledger.observe_execution(
            "hermes", "child", "0.20.0", "2026-08-13T00:00:00Z"
        )
        event = self.ledger.record_source_event(
            provider="hermes",
            source_locator="file:///safe.jsonl#bytes=0-2",
            source_digest="a" * 64,
            provider_version="0.20.0",
            extractor_version="test-v1",
            observed_at="2026-08-13T00:00:00Z",
        )
        with self.assertRaisesRegex(ValueError, "assertion value"):
            self.ledger.record_assertion(
                child,
                "task-status",
                "This is a complete free-form transcript payload with spaces.",
                event,
                "test-v1",
            )
        self.assertEqual(self.ledger.count("assertions"), 0)

    def test_source_locators_require_canonical_local_ranges(self):
        for locator in (
            "file:///safe.jsonl#bytes=9-2",
            "file://host/safe.jsonl#bytes=0-2",
            "file:////host/safe.jsonl#bytes=0-2",
            "sqlite://host/state.db#table=sessions&row=one",
            "file:///x%00#bytes=0-1",
            "file:///x%0A#bytes=0-1",
            "file:///C:\\x#bytes=0-1",
            "file:///safe/../secret#bytes=0-1",
        ):
            with self.subTest(locator=locator):
                with self.assertRaisesRegex(ValueError, "source locator"):
                    self.ledger.record_source_event(
                        provider="codex",
                        source_locator=locator,
                        source_digest="a" * 64,
                        provider_version="1",
                        extractor_version="test-v1",
                        observed_at="2026-08-13T00:00:00Z",
                    )
        self.assertEqual(self.ledger.count("source_events"), 0)

    def test_provider_event_times_require_complete_offset_aware_datetimes(self):
        for provider_event_time in (
            "2026-08-13T00:00:00",
            "2026-08-13",
            1700000000,
            1.5,
        ):
            with self.subTest(provider_event_time=provider_event_time):
                with self.assertRaisesRegex(ValueError, "timestamp-shaped"):
                    self.ledger.record_source_event(
                        provider="codex",
                        source_locator="file:///safe.jsonl#bytes=0-2",
                        source_digest="a" * 64,
                        provider_version="1",
                        extractor_version="test-v1",
                        observed_at="2026-08-13T00:00:00Z",
                        provider_event_time=provider_event_time,
                    )
        self.assertEqual(self.ledger.count("source_events"), 0)

    def test_configured_event_time_requires_object_and_present_field(self):
        for index, record in enumerate(([], {"id": "missing"})):
            source = self.root / f"invalid-event-time-{index}.jsonl"
            source.write_text(json.dumps(record) + "\n", encoding="utf-8", newline="\n")

            with self.subTest(record=record):
                with self.assertRaisesRegex(ValueError, "event time field"):
                    self.ledger.ingest_jsonl(
                        "codex", source, "1", "test-v1", event_time_field="timestamp"
                    )

        self.assertEqual(self.ledger.count("source_events"), 0)
        self.assertEqual(self.ledger.count("ingestion_cursors"), 0)

    def test_legacy_provider_version_sentinel_cannot_be_ingested(self):
        source = self.root / "legacy-sentinel.jsonl"
        source.write_text("{}\n", encoding="utf-8", newline="\n")

        with self.assertRaisesRegex(ValueError, "reserved legacy"):
            self.ledger.ingest_jsonl(
                "codex", source, "unknown-legacy", "extractor-v1"
            )

        self.assertEqual(self.ledger.count("source_events"), 0)
        self.assertEqual(self.ledger.count("ingestion_cursors"), 0)

    def test_mutation_outbox_is_disabled_in_validation_mode(self):
        with self.assertRaises(self.module.MutationsDisabled):
            self.ledger.enqueue_action("codex", "archive", "thread-1", "key-1")
        self.assertEqual(self.ledger.count("outbox"), 0)

    def test_public_connection_facade_rejects_writes(self):
        external = self.root / "external.sqlite"
        for statement in (
            "DELETE FROM source_events",
            f"ATTACH DATABASE '{external.as_posix()}' AS external",
            "PRAGMA query_only=OFF",
        ):
            with self.subTest(statement=statement):
                with self.assertRaisesRegex(ValueError, "read-only queries"):
                    self.ledger.connection.execute(statement)
        self.assertEqual(self.ledger.count("source_events"), 0)
        self.assertFalse(external.exists())

    def test_schema_contains_no_raw_payload_columns(self):
        connection = sqlite3.connect(self.db)
        try:
            columns = {
                row[1]
                for table in ("source_events", "assertions", "lineage_assertions")
                for row in connection.execute(f"PRAGMA table_info({table})")
            }
        finally:
            connection.close()
        self.assertTrue({"source_locator", "source_digest"}.issubset(columns))
        self.assertIn("provider_event_time", columns)
        self.assertFalse({"payload", "content", "prompt", "tool_result"} & columns)

    def test_legacy_cursor_schema_migrates_without_reusing_unknown_version(self):
        self.ledger.close()
        self.db.unlink()
        connection = sqlite3.connect(self.db)
        connection.executescript(
            """
            CREATE TABLE source_events (
                source_event_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                source_locator TEXT NOT NULL,
                source_digest TEXT NOT NULL,
                provider_version TEXT NOT NULL,
                extractor_version TEXT NOT NULL,
                provider_event_time TEXT,
                observed_at TEXT NOT NULL,
                UNIQUE(provider, source_locator, source_digest)
            );
            CREATE TABLE ingestion_cursors (
                provider TEXT NOT NULL,
                source_path TEXT NOT NULL,
                extractor_version TEXT NOT NULL,
                cursor_bytes INTEGER NOT NULL,
                cursor_digest TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(provider, source_path, extractor_version)
            );
            """
        )
        connection.execute(
            """
            INSERT INTO source_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-event",
                "codex",
                "file:///legacy#bytes=0-2",
                "a" * 64,
                "provider-v1",
                "extractor-v1",
                None,
                "2026-08-13T00:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO ingestion_cursors VALUES (?, ?, ?, ?, ?, ?)",
            ("codex", "C:/legacy.jsonl", "extractor-v1", 2, "b" * 64, "2026-08-13T00:00:00Z"),
        )
        connection.commit()
        connection.close()

        self.ledger = self.module.ContextLedger(self.db)

        cursor_columns = {
            row[1]
            for row in self.ledger.connection.execute(
                "PRAGMA table_info(ingestion_cursors)"
            )
        }
        cursor = self.ledger.connection.execute(
            "SELECT provider_version, cursor_bytes FROM ingestion_cursors"
        ).fetchone()
        derivation = self.ledger.connection.execute(
            """
            SELECT provider_version, extractor_version
            FROM source_event_derivations
            WHERE source_event_id = 'legacy-event'
            """
        ).fetchone()
        self.assertIn("provider_version", cursor_columns)
        self.assertEqual(cursor, ("unknown-legacy", 2))
        self.assertEqual(derivation, ("provider-v1", "extractor-v1"))

        self.ledger.close()
        self.ledger = self.module.ContextLedger(self.db)
        self.assertEqual(
            self.ledger.connection.execute(
                "SELECT COUNT(*) FROM source_event_derivations"
            ).fetchone()[0],
            1,
        )
        self.assertEqual(
            self.ledger.connection.execute(
                "SELECT provider_version, cursor_bytes FROM ingestion_cursors"
            ).fetchone(),
            ("unknown-legacy", 2),
        )

    def test_partial_legacy_cursor_copy_is_restartable(self):
        self.ledger.close()
        self.db.unlink()
        connection = sqlite3.connect(self.db)
        connection.executescript(
            """
            CREATE TABLE ingestion_cursors (
                provider TEXT NOT NULL,
                source_path TEXT NOT NULL,
                provider_version TEXT NOT NULL,
                extractor_version TEXT NOT NULL,
                cursor_bytes INTEGER NOT NULL,
                cursor_digest TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(provider, source_path, provider_version, extractor_version)
            );
            CREATE TABLE ingestion_cursors_legacy (
                provider TEXT NOT NULL,
                source_path TEXT NOT NULL,
                extractor_version TEXT NOT NULL,
                cursor_bytes INTEGER NOT NULL,
                cursor_digest TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(provider, source_path, extractor_version)
            );
            """
        )
        row = (
            "codex",
            "C:/legacy.jsonl",
            "extractor-v1",
            2,
            "b" * 64,
            "2026-08-13T00:00:00Z",
        )
        connection.execute("INSERT INTO ingestion_cursors_legacy VALUES (?, ?, ?, ?, ?, ?)", row)
        connection.execute(
            "INSERT INTO ingestion_cursors VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row[0], row[1], "unknown-legacy", *row[2:]),
        )
        connection.commit()
        connection.close()

        self.ledger = self.module.ContextLedger(self.db)

        self.assertEqual(self.ledger.count("ingestion_cursors"), 1)
        tables = {
            item[0]
            for item in self.ledger.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertNotIn("ingestion_cursors_legacy", tables)

    def test_old_cursor_schema_plus_legacy_table_converges(self):
        self.ledger.close()
        self.db.unlink()
        connection = sqlite3.connect(self.db)
        connection.executescript(
            """
            CREATE TABLE ingestion_cursors (
                provider TEXT NOT NULL,
                source_path TEXT NOT NULL,
                extractor_version TEXT NOT NULL,
                cursor_bytes INTEGER NOT NULL,
                cursor_digest TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(provider, source_path, extractor_version)
            );
            CREATE TABLE ingestion_cursors_legacy (
                provider TEXT NOT NULL,
                source_path TEXT NOT NULL,
                extractor_version TEXT NOT NULL,
                cursor_bytes INTEGER NOT NULL,
                cursor_digest TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(provider, source_path, extractor_version)
            );
            """
        )
        row = (
            "codex",
            "C:/legacy.jsonl",
            "extractor-v1",
            2,
            "b" * 64,
            "2026-08-13T00:00:00Z",
        )
        connection.execute("INSERT INTO ingestion_cursors VALUES (?, ?, ?, ?, ?, ?)", row)
        connection.execute("INSERT INTO ingestion_cursors_legacy VALUES (?, ?, ?, ?, ?, ?)", row)
        connection.commit()
        connection.close()

        self.ledger = self.module.ContextLedger(self.db)

        self.assertEqual(
            self.ledger.connection.execute(
                "SELECT provider_version, cursor_bytes FROM ingestion_cursors"
            ).fetchone(),
            ("unknown-legacy", 2),
        )

    def test_legacy_cursor_collision_fails_closed(self):
        self.ledger.close()
        self.db.unlink()
        connection = sqlite3.connect(self.db)
        connection.executescript(
            """
            CREATE TABLE ingestion_cursors (
                provider TEXT NOT NULL,
                source_path TEXT NOT NULL,
                provider_version TEXT NOT NULL,
                extractor_version TEXT NOT NULL,
                cursor_bytes INTEGER NOT NULL,
                cursor_digest TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(provider, source_path, provider_version, extractor_version)
            );
            CREATE TABLE ingestion_cursors_legacy (
                provider TEXT NOT NULL,
                source_path TEXT NOT NULL,
                extractor_version TEXT NOT NULL,
                cursor_bytes INTEGER NOT NULL,
                cursor_digest TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(provider, source_path, extractor_version)
            );
            """
        )
        connection.execute(
            "INSERT INTO ingestion_cursors VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "codex",
                "C:/legacy.jsonl",
                "unknown-legacy",
                "extractor-v1",
                1,
                "a" * 64,
                "2026-08-13T00:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO ingestion_cursors_legacy VALUES (?, ?, ?, ?, ?, ?)",
            (
                "codex",
                "C:/legacy.jsonl",
                "extractor-v1",
                2,
                "b" * 64,
                "2026-08-13T00:00:00Z",
            ),
        )
        connection.commit()
        connection.close()

        with self.assertRaisesRegex(ValueError, "conflicting legacy cursor"):
            self.module.ContextLedger(self.db)

        connection = sqlite3.connect(self.db)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        finally:
            connection.close()
        self.assertTrue({"ingestion_cursors", "ingestion_cursors_legacy"}.issubset(tables))

    def test_cli_initializes_ingests_and_reports_metadata_counts(self):
        source = self.root / "cli.jsonl"
        source.write_text(json.dumps({"id": "e1"}) + "\n", encoding="utf-8", newline="\n")
        tool = REPO / "tools" / "context_ledger.py"

        init = subprocess.run(
            [sys.executable, str(tool), "--db", str(self.root / "cli.sqlite"), "init"],
            text=True,
            capture_output=True,
            check=False,
        )
        ingest = subprocess.run(
            [
                sys.executable,
                str(tool),
                "--db",
                str(self.root / "cli.sqlite"),
                "ingest-jsonl",
                "--provider",
                "codex",
                "--provider-version",
                "1",
                "--extractor-version",
                "test-v1",
                str(source),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        stats = subprocess.run(
            [sys.executable, str(tool), "--db", str(self.root / "cli.sqlite"), "stats"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(init.returncode, 0, init.stdout + init.stderr)
        self.assertEqual(ingest.returncode, 0, ingest.stdout + ingest.stderr)
        self.assertEqual(json.loads(ingest.stdout)["events_added"], 1)
        self.assertEqual(stats.returncode, 0, stats.stdout + stats.stderr)
        self.assertEqual(json.loads(stats.stdout)["source_events"], 1)


if __name__ == "__main__":
    unittest.main()
