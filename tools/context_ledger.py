#!/usr/bin/env python
"""Read-only cross-provider identity and provenance ledger.

Native provider stores remain authoritative. This module stores locators, digests,
versioned derivations, and lifecycle assertions; it never stores transcript
payloads and cannot mutate providers.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import quote, unquote_to_bytes, urlsplit


class MutationsDisabled(RuntimeError):
    """Raised when validation-only code is asked to enqueue a provider mutation."""


class _ReadOnlyConnection:
    """Expose query cursors without exposing the ledger's writable connection."""

    def __init__(self, path: Path):
        self.__connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        self.__connection.set_authorizer(self._authorize)

    @staticmethod
    def _authorize(
        action: int,
        argument1: str | None,
        _argument2: str | None,
        _database: str | None,
        _trigger: str | None,
    ) -> int:
        allowed = {
            sqlite3.SQLITE_FUNCTION,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_RECURSIVE,
            sqlite3.SQLITE_SELECT,
        }
        if action in allowed:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_PRAGMA and argument1 == "table_info":
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    def execute(
        self, sql: str, parameters: tuple[object, ...] = ()
    ) -> sqlite3.Cursor:
        statement = sql.strip()
        is_select = re.match(r"(?is)^SELECT\b", statement) is not None
        is_table_info = re.fullmatch(
            r"(?is)PRAGMA\s+(?:main\.)?table_info\s*\(\s*[A-Za-z_]"
            r"[A-Za-z0-9_]*\s*\)\s*;?",
            statement,
        ) is not None
        if not (is_select or is_table_info):
            raise ValueError("diagnostic connection accepts only read-only queries")
        return self.__connection.execute(sql, parameters)

    def close(self) -> None:
        self.__connection.close()


_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/=@+~-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BYTE_RANGE = re.compile(r"^bytes=(\d+)-(\d+)$")
_SQLITE_FRAGMENT = re.compile(
    r"^table=[A-Za-z0-9_.-]{1,64}"
    r"&row=[A-Za-z0-9._:@+~-]{1,128}"
    r"(?:&field=[A-Za-z0-9_.-]{1,64})?$"
)
_ALLOWED_RELATIONS = {
    "compression",
    "continuation",
    "fork",
    "import",
    "resume",
    "spawn",
}
_ALLOWED_ASSERTIONS = {
    "task-status": {
        "blocked",
        "cancelled",
        "completed",
        "pending",
        "running",
        "stale",
        "unknown",
    },
    "lifecycle-status": {
        "active",
        "archived",
        "deleted",
        "ended",
        "open",
        "source-missing",
        "unknown",
    },
    "verification-status": {
        "contradicted",
        "failed",
        "passed",
        "unknown",
        "unverified",
    },
}


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def _stable_id(namespace: str, *parts: str) -> str:
    material = "\0".join((namespace, *parts)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _metadata_token(value: object, label: str, *, max_length: int = 128) -> str:
    if (
        not isinstance(value, str)
        or len(value) > max_length
        or not _TOKEN.fullmatch(value)
    ):
        raise ValueError(f"{label} must be a bounded metadata token")
    return value


def _provider_version(value: object) -> str:
    version = _metadata_token(value, "provider version", max_length=64)
    if version == "unknown-legacy":
        raise ValueError("provider version is a reserved legacy migration sentinel")
    return version


def _source_locator(value: object) -> str:
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError(
            "source locator must be a bounded canonical file or SQLite locator"
        )
    if (
        any(ord(character) < 32 or ord(character) == 127 for character in value)
        or "\\" in value
        or re.search(r"%(?![0-9A-Fa-f]{2})", value)
    ):
        raise ValueError(
            "source locator must be a bounded canonical file or SQLite locator"
        )
    if value.startswith("file:"):
        parsed = urlsplit(value)
        byte_range = _BYTE_RANGE.fullmatch(parsed.fragment)
        valid = (
            value.startswith("file:///")
            and parsed.scheme == "file"
            and not parsed.netloc
            and parsed.path.startswith("/")
            and not parsed.path.startswith("//")
            and not parsed.query
            and byte_range is not None
        )
        try:
            decoded_path = unquote_to_bytes(parsed.path).decode("utf-8")
        except UnicodeDecodeError:
            valid = False
            decoded_path = ""
        valid = valid and not any(
            ord(character) < 32 or ord(character) == 127 or character == "\\"
            for character in decoded_path
        )
        valid = valid and not any(
            segment in {".", ".."} for segment in decoded_path.split("/")
        )
        valid = valid and quote(decoded_path, safe="/:@-._~") == parsed.path
        if valid and byte_range is not None:
            start, end = (int(part) for part in byte_range.groups())
            valid = start <= end
        if not valid:
            raise ValueError(
                "source locator must be a bounded canonical file or SQLite locator"
            )
    elif value.startswith("sqlite:"):
        parsed = urlsplit(value)
        valid = (
            value.startswith("sqlite:///")
            and parsed.scheme == "sqlite"
            and not parsed.netloc
            and parsed.path.startswith("/")
            and not parsed.path.startswith("//")
            and not parsed.query
            and _SQLITE_FRAGMENT.fullmatch(parsed.fragment) is not None
        )
        try:
            decoded_path = unquote_to_bytes(parsed.path).decode("utf-8")
        except UnicodeDecodeError:
            valid = False
            decoded_path = ""
        valid = valid and not any(
            ord(character) < 32 or ord(character) == 127 or character == "\\"
            for character in decoded_path
        )
        valid = valid and not any(
            segment in {".", ".."} for segment in decoded_path.split("/")
        )
        valid = valid and quote(decoded_path, safe="/:@-._~") == parsed.path
        if not valid:
            raise ValueError(
                "source locator must be a bounded canonical file or SQLite locator"
            )
    else:
        raise ValueError(
            "source locator must be a bounded canonical file or SQLite locator"
        )
    return value


def _source_digest(value: object) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError("source digest must be a lowercase SHA-256 hex value")
    return value


def _canonical_observed_time(value: object) -> str:
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("observation time must be an offset-aware ISO timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "observation time must be an offset-aware ISO timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observation time must be an offset-aware ISO timestamp")
    return parsed.astimezone(dt.timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def _provider_event_time(value: object) -> str | None:
    """Return a bounded timestamp scalar without accepting payload text."""
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("provider event time must be a timestamp-shaped scalar")
    candidate = value.strip()
    if not candidate:
        raise ValueError("provider event time must be a timestamp-shaped scalar")
    try:
        parsed = dt.datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "provider event time must be a timestamp-shaped scalar"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("provider event time must be a timestamp-shaped scalar")
    return candidate


class ContextLedger:
    """Append-oriented metadata ledger with read-only provider boundaries."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self.connection = _ReadOnlyConnection(self.path)
        try:
            self._create_schema()
        except BaseException:
            self.connection.close()
            self._connection.close()
            raise

    def close(self) -> None:
        self.connection.close()
        self._connection.close()

    def _create_schema(self) -> None:
        tables = {
            str(row[0])
            for row in self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        cursor_columns = {
            str(row[1])
            for row in self._connection.execute(
                "PRAGMA table_info(ingestion_cursors)"
            )
        }
        legacy_cursor_schema = bool(cursor_columns) and "provider_version" not in cursor_columns
        legacy_cursor_table_exists = "ingestion_cursors_legacy" in tables
        if legacy_cursor_schema:
            with self._connection:
                if legacy_cursor_table_exists:
                    for row in self._connection.execute(
                        """
                        SELECT provider, source_path, extractor_version,
                            cursor_bytes, cursor_digest, updated_at
                        FROM ingestion_cursors
                        """
                    ):
                        existing = self._connection.execute(
                            """
                            SELECT cursor_bytes, cursor_digest, updated_at
                            FROM ingestion_cursors_legacy
                            WHERE provider = ? AND source_path = ?
                            AND extractor_version = ?
                            """,
                            row[:3],
                        ).fetchone()
                        if existing is None:
                            self._connection.execute(
                                "INSERT INTO ingestion_cursors_legacy VALUES (?, ?, ?, ?, ?, ?)",
                                row,
                            )
                        elif tuple(existing) != tuple(row[3:]):
                            raise ValueError("conflicting legacy cursor migration rows")
                    self._connection.execute("DROP TABLE ingestion_cursors")
                else:
                    self._connection.execute(
                        "ALTER TABLE ingestion_cursors RENAME TO ingestion_cursors_legacy"
                    )
            legacy_cursor_table_exists = True
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS executions (
                execution_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                native_id TEXT NOT NULL,
                provider_version TEXT NOT NULL,
                first_observed_at TEXT NOT NULL,
                last_observed_at TEXT NOT NULL,
                UNIQUE(provider, native_id)
            );

            CREATE TABLE IF NOT EXISTS source_events (
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

            CREATE TABLE IF NOT EXISTS source_event_derivations (
                derivation_id TEXT PRIMARY KEY,
                source_event_id TEXT NOT NULL REFERENCES source_events(source_event_id),
                provider_version TEXT NOT NULL,
                extractor_version TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                UNIQUE(source_event_id, provider_version, extractor_version)
            );

            CREATE TABLE IF NOT EXISTS ingestion_cursors (
                provider TEXT NOT NULL,
                source_path TEXT NOT NULL,
                provider_version TEXT NOT NULL,
                extractor_version TEXT NOT NULL,
                cursor_bytes INTEGER NOT NULL,
                cursor_digest TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(
                    provider, source_path, provider_version, extractor_version
                )
            );

            CREATE TABLE IF NOT EXISTS lineage_assertions (
                lineage_id TEXT PRIMARY KEY,
                child_execution_id TEXT NOT NULL REFERENCES executions(execution_id),
                parent_execution_id TEXT NOT NULL REFERENCES executions(execution_id),
                relation TEXT NOT NULL,
                source_event_id TEXT NOT NULL REFERENCES source_events(source_event_id),
                derivation_version TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS assertions (
                assertion_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL REFERENCES executions(execution_id),
                predicate TEXT NOT NULL,
                value TEXT NOT NULL,
                source_event_id TEXT NOT NULL REFERENCES source_events(source_event_id),
                derivation_version TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS outbox (
                action_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                action TEXT NOT NULL,
                native_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        if legacy_cursor_table_exists:
            with self._connection:
                for row in self._connection.execute(
                    """
                    SELECT provider, source_path, extractor_version,
                        cursor_bytes, cursor_digest, updated_at
                    FROM ingestion_cursors_legacy
                    """
                ):
                    existing = self._connection.execute(
                        """
                        SELECT cursor_bytes, cursor_digest, updated_at
                        FROM ingestion_cursors
                        WHERE provider = ? AND source_path = ?
                        AND provider_version = 'unknown-legacy'
                        AND extractor_version = ?
                        """,
                        row[:3],
                    ).fetchone()
                    if existing is None:
                        self._connection.execute(
                            """
                            INSERT INTO ingestion_cursors (
                                provider, source_path, provider_version,
                                extractor_version, cursor_bytes, cursor_digest,
                                updated_at
                            ) VALUES (?, ?, 'unknown-legacy', ?, ?, ?, ?)
                            """,
                            row,
                        )
                    elif tuple(existing) != tuple(row[3:]):
                        raise ValueError("conflicting legacy cursor migration rows")
                self._connection.execute("DROP TABLE ingestion_cursors_legacy")
        for row in self._connection.execute(
            """
            SELECT source_event_id, provider_version, extractor_version, observed_at
            FROM source_events
            """
        ):
            derivation_id = _stable_id(
                "derivation", str(row[0]), str(row[1]), str(row[2])
            )
            self._connection.execute(
                """
                INSERT OR IGNORE INTO source_event_derivations (
                    derivation_id, source_event_id, provider_version,
                    extractor_version, observed_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (derivation_id, row[0], row[1], row[2], row[3]),
            )
        self._connection.commit()

    def count(self, table: str) -> int:
        allowed = {
            "executions",
            "source_events",
            "source_event_derivations",
            "ingestion_cursors",
            "lineage_assertions",
            "assertions",
            "outbox",
        }
        if table not in allowed:
            raise ValueError(f"unsupported table: {table}")
        row = self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        assert row is not None
        return int(row[0])

    def observe_execution(
        self,
        provider: str,
        native_id: str,
        provider_version: str,
        observed_at: str,
    ) -> str:
        provider = _metadata_token(provider, "provider", max_length=32)
        native_id = _metadata_token(native_id, "native ID")
        provider_version = _provider_version(provider_version)
        observed_at = _canonical_observed_time(observed_at)
        execution_id = _stable_id("execution", provider, native_id)
        self._connection.execute(
            """
            INSERT INTO executions (
                execution_id, provider, native_id, provider_version,
                first_observed_at, last_observed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, native_id) DO UPDATE SET
                provider_version = CASE
                    WHEN excluded.last_observed_at >= executions.last_observed_at
                    THEN excluded.provider_version
                    ELSE executions.provider_version
                END,
                first_observed_at = MIN(
                    executions.first_observed_at, excluded.first_observed_at
                ),
                last_observed_at = MAX(
                    executions.last_observed_at, excluded.last_observed_at
                )
            """,
            (execution_id, provider, native_id, provider_version, observed_at, observed_at),
        )
        self._connection.commit()
        return execution_id

    def record_source_event(
        self,
        provider: str,
        source_locator: str,
        source_digest: str,
        provider_version: str,
        extractor_version: str,
        observed_at: str,
        provider_event_time: str | None = None,
        commit: bool = True,
    ) -> str:
        provider = _metadata_token(provider, "provider", max_length=32)
        source_locator = _source_locator(source_locator)
        source_digest = _source_digest(source_digest)
        provider_version = _provider_version(provider_version)
        extractor_version = _metadata_token(
            extractor_version, "extractor version", max_length=64
        )
        observed_at = _canonical_observed_time(observed_at)
        provider_event_time = _provider_event_time(provider_event_time)
        source_event_id = _stable_id(
            "source-event", provider, source_locator, source_digest
        )
        self._connection.execute(
            """
            INSERT OR IGNORE INTO source_events (
                source_event_id, provider, source_locator, source_digest,
                provider_version, extractor_version, provider_event_time, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_event_id,
                provider,
                source_locator,
                source_digest,
                provider_version,
                extractor_version,
                provider_event_time,
                observed_at,
            ),
        )
        derivation_id = _stable_id(
            "source-event-derivation",
            source_event_id,
            provider_version,
            extractor_version,
        )
        self._connection.execute(
            """
            INSERT OR IGNORE INTO source_event_derivations (
                derivation_id, source_event_id, provider_version,
                extractor_version, observed_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                derivation_id,
                source_event_id,
                provider_version,
                extractor_version,
                observed_at,
            ),
        )
        if commit:
            self._connection.commit()
        return source_event_id

    def ingest_jsonl(
        self,
        provider: str,
        source: Path | str,
        provider_version: str,
        extractor_version: str,
        event_time_field: str | None = None,
    ) -> dict[str, int]:
        provider = _metadata_token(provider, "provider", max_length=32)
        provider_version = _provider_version(provider_version)
        extractor_version = _metadata_token(
            extractor_version, "extractor version", max_length=64
        )
        if event_time_field is not None:
            event_time_field = _metadata_token(
                event_time_field, "event time field", max_length=64
            )
        path = Path(source).resolve()
        source_path = str(path)
        cursor_row = self._connection.execute(
            """
            SELECT cursor_bytes, cursor_digest FROM ingestion_cursors
            WHERE provider = ? AND source_path = ? AND provider_version = ?
            AND extractor_version = ?
            """,
            (provider, source_path, provider_version, extractor_version),
        ).fetchone()
        cursor = int(cursor_row[0]) if cursor_row else 0
        cursor_digest = str(cursor_row[1]) if cursor_row else hashlib.sha256(b"").hexdigest()
        size = path.stat().st_size
        if size < cursor:
            raise ValueError(f"source shrank below durable cursor: {path}")
        with path.open("rb") as prefix_handle:
            current_prefix_digest = hashlib.sha256(prefix_handle.read(cursor)).hexdigest()
        if current_prefix_digest != cursor_digest:
            raise ValueError(f"source changed before durable cursor: {path}")

        added = 0
        next_cursor = cursor
        observed_at = _utc_now()
        with path.open("rb") as handle, self._connection:
            handle.seek(cursor)
            while True:
                start = handle.tell()
                raw = handle.readline()
                if not raw:
                    break
                if not raw.endswith(b"\n"):
                    break
                end = handle.tell()
                line = raw[:-1]
                if line.endswith(b"\r"):
                    line = line[:-1]
                if not line.strip():
                    next_cursor = end
                    continue
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise ValueError(f"malformed complete JSONL record at byte {start}") from exc
                if event_time_field is not None:
                    if not isinstance(record, dict) or event_time_field not in record:
                        raise ValueError(
                            "configured event time field requires an object record and present field"
                        )
                    provider_event_time = _provider_event_time(
                        record[event_time_field]
                    )
                    if provider_event_time is None:
                        raise ValueError(
                            "configured event time field requires a timestamp-shaped value"
                        )
                else:
                    provider_event_time = None
                locator = f"{path.as_uri()}#bytes={start}-{end}"
                digest = hashlib.sha256(raw).hexdigest()
                source_event_id = _stable_id(
                    "source-event", provider, locator, digest
                )
                derivation_existed = self._connection.execute(
                    """
                    SELECT 1 FROM source_event_derivations
                    WHERE source_event_id = ? AND provider_version = ?
                    AND extractor_version = ?
                    """,
                    (source_event_id, provider_version, extractor_version),
                ).fetchone()
                self.record_source_event(
                    provider=provider,
                    source_locator=locator,
                    source_digest=digest,
                    provider_version=provider_version,
                    extractor_version=extractor_version,
                    observed_at=observed_at,
                    provider_event_time=provider_event_time,
                    commit=False,
                )
                if derivation_existed is None:
                    added += 1
                next_cursor = end

            self._connection.execute(
                """
                INSERT INTO ingestion_cursors (
                    provider, source_path, provider_version, extractor_version,
                    cursor_bytes, cursor_digest, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(
                    provider, source_path, provider_version, extractor_version
                ) DO UPDATE SET
                    cursor_bytes = excluded.cursor_bytes,
                    cursor_digest = excluded.cursor_digest,
                    updated_at = excluded.updated_at
                """,
                (
                    provider,
                    source_path,
                    provider_version,
                    extractor_version,
                    next_cursor,
                    hashlib.sha256(path.read_bytes()[:next_cursor]).hexdigest(),
                    observed_at,
                ),
            )
        return {"events_added": added, "cursor_bytes": next_cursor}

    def assert_lineage(
        self,
        child_execution_id: str,
        parent_execution_id: str,
        relation: str,
        source_event_id: str,
        derivation_version: str,
    ) -> str:
        child_execution_id = _metadata_token(
            child_execution_id, "child execution ID"
        )
        parent_execution_id = _metadata_token(
            parent_execution_id, "parent execution ID"
        )
        if relation not in _ALLOWED_RELATIONS:
            raise ValueError("lineage relation is not an allowed metadata enum")
        source_event_id = _metadata_token(source_event_id, "source event ID")
        derivation_version = _metadata_token(
            derivation_version, "derivation version", max_length=64
        )
        lineage_id = _stable_id(
            "lineage",
            child_execution_id,
            parent_execution_id,
            relation,
            source_event_id,
            derivation_version,
        )
        self._connection.execute(
            """
            INSERT OR IGNORE INTO lineage_assertions (
                lineage_id, child_execution_id, parent_execution_id, relation,
                source_event_id, derivation_version, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lineage_id,
                child_execution_id,
                parent_execution_id,
                relation,
                source_event_id,
                derivation_version,
                _utc_now(),
            ),
        )
        self._connection.commit()
        return lineage_id

    def record_assertion(
        self,
        execution_id: str,
        predicate: str,
        value: str,
        source_event_id: str,
        derivation_version: str,
    ) -> str:
        execution_id = _metadata_token(execution_id, "execution ID")
        allowed_values = _ALLOWED_ASSERTIONS.get(predicate)
        if allowed_values is None:
            raise ValueError("assertion predicate is not an allowed metadata enum")
        if value not in allowed_values:
            raise ValueError("assertion value is not an allowed metadata enum")
        source_event_id = _metadata_token(source_event_id, "source event ID")
        derivation_version = _metadata_token(
            derivation_version, "derivation version", max_length=64
        )
        assertion_id = _stable_id(
            "assertion",
            execution_id,
            predicate,
            value,
            source_event_id,
            derivation_version,
        )
        self._connection.execute(
            """
            INSERT OR IGNORE INTO assertions (
                assertion_id, execution_id, predicate, value, source_event_id,
                derivation_version, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assertion_id,
                execution_id,
                predicate,
                value,
                source_event_id,
                derivation_version,
                _utc_now(),
            ),
        )
        self._connection.commit()
        return assertion_id

    def assertion_values(self, execution_id: str, predicate: str) -> list[str]:
        execution_id = _metadata_token(execution_id, "execution ID")
        if predicate not in _ALLOWED_ASSERTIONS:
            raise ValueError("assertion predicate is not an allowed metadata enum")
        rows = self._connection.execute(
            """
            SELECT value FROM assertions
            WHERE execution_id = ? AND predicate = ?
            ORDER BY recorded_at, rowid
            """,
            (execution_id, predicate),
        ).fetchall()
        return [str(row[0]) for row in rows]

    def enqueue_action(
        self,
        provider: str,
        action: str,
        native_id: str,
        idempotency_key: str,
    ) -> str:
        del provider, action, native_id, idempotency_key
        raise MutationsDisabled(
            "provider mutations are disabled during read-only ledger validation"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    ingest = commands.add_parser("ingest-jsonl")
    ingest.add_argument("source", type=Path)
    ingest.add_argument("--provider", required=True)
    ingest.add_argument("--provider-version", required=True)
    ingest.add_argument("--extractor-version", required=True)
    ingest.add_argument("--event-time-field")
    commands.add_parser("stats")
    args = parser.parse_args(argv)

    ledger = ContextLedger(args.db)
    try:
        if args.command == "init":
            result: dict[str, object] = {"initialized": True, "db": str(args.db.resolve())}
        elif args.command == "ingest-jsonl":
            result = ledger.ingest_jsonl(
                provider=args.provider,
                source=args.source,
                provider_version=args.provider_version,
                extractor_version=args.extractor_version,
                event_time_field=args.event_time_field,
            )
        else:
            result = {
                table: ledger.count(table)
                for table in (
                    "executions",
                    "source_events",
                    "source_event_derivations",
                    "ingestion_cursors",
                    "lineage_assertions",
                    "assertions",
                    "outbox",
                )
            }
        print(json.dumps(result, sort_keys=True))
        return 0
    finally:
        ledger.close()


if __name__ == "__main__":
    raise SystemExit(main())
