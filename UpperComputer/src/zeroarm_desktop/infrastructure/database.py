"""Transactional SQLite schema and append/query operations."""

import sqlite3
from collections.abc import Iterable
from pathlib import Path

SCHEMA_VERSION = 1


def connect_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5.0)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def migrate_database(connection: sqlite3.Connection) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError(f"database schema {version} is newer than supported {SCHEMA_VERSION}")
    if version == 0:
        with connection:
            connection.executescript(
                """
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    started_wall_utc TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    monotonic_ns INTEGER NOT NULL,
                    wall_utc TEXT NOT NULL,
                    device_time_ms INTEGER,
                    sample_sequence INTEGER,
                    kind TEXT NOT NULL,
                    payload_json TEXT,
                    raw_blob BLOB
                );
                CREATE INDEX events_session_order ON events(session_id, monotonic_ns, id);
                PRAGMA user_version = 1;
                """
            )


def insert_events(connection: sqlite3.Connection, rows: Iterable[tuple[object, ...]]) -> None:
    with connection:
        connection.executemany(
            """
            INSERT INTO events (
                session_id, monotonic_ns, wall_utc, device_time_ms,
                sample_sequence, kind, payload_json, raw_blob
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
