"""Configuration, SQLite recording, migration, and export tests."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from zeroarm_desktop.application.recorder import Recorder, RecordEvent
from zeroarm_desktop.infrastructure.config import AppConfig, ConfigStore
from zeroarm_desktop.infrastructure.database import (
    connect_database,
    migrate_database,
)
from zeroarm_desktop.infrastructure.export import export_session_csv, export_session_json


def test_config_roundtrip_uses_safe_defaults(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    assert store.load().transport_kind == "mock"
    assert not store.load().auto_reconnect
    config = AppConfig(theme="light", poll_rate_hz=100)
    store.save(config)
    assert store.load() == config


def test_database_migration_is_idempotent_and_rejects_newer_schema(tmp_path: Path) -> None:
    connection = connect_database(tmp_path / "events.sqlite3")
    migrate_database(connection)
    migrate_database(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    connection.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError, match="newer"):
        migrate_database(connection)
    connection.close()


def test_recorder_batches_and_exports_roundtrip(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    recorder = Recorder(database)
    session_id = recorder.start({"transport": "mock"})
    for index in range(75):
        assert recorder.append(
            RecordEvent(
                monotonic_ns=index,
                wall_utc=datetime(2026, 7, 29, tzinfo=UTC),
                kind="snapshot",
                payload={"generation": index},
                raw_blob=bytes((index % 256,)),
            )
        )
    recorder.close()
    assert recorder.statistics.events_written == 75
    assert recorder.statistics.batches_written >= 2

    connection = connect_database(database)
    json_path = tmp_path / "events.json"
    csv_path = tmp_path / "events.csv"
    assert export_session_json(connection, session_id, json_path) == 75
    assert export_session_csv(connection, session_id, csv_path) == 75
    document = json.loads(json_path.read_text(encoding="utf-8"))
    assert document["events"][0]["payload_json"] == '{"generation": 0}'
    assert "monotonic_ns" in csv_path.read_text(encoding="utf-8-sig")
    connection.close()


def test_recorder_reports_bounded_queue_drops(tmp_path: Path) -> None:
    recorder = Recorder(tmp_path / "events.sqlite3", queue_capacity=1)
    recorder.start()
    event = RecordEvent(1, datetime.now(UTC), "test")
    accepted = [recorder.append(event) for _ in range(10_000)]
    recorder.close()
    assert not all(accepted)
    assert recorder.statistics.events_dropped > 0


def test_recorder_stops_accepting_events_after_database_write_failure(tmp_path: Path) -> None:
    database = tmp_path / "failed-events.sqlite3"
    connection_count = 0

    def failing_worker_connection(path: Path) -> sqlite3.Connection:
        nonlocal connection_count
        connection_count += 1
        connection = connect_database(path)
        if connection_count == 2:
            connection.execute(
                """
                CREATE TRIGGER fail_event_insert
                BEFORE INSERT ON events
                BEGIN
                    SELECT RAISE(FAIL, 'simulated recorder write failure');
                END
                """
            )
        return connection

    recorder = Recorder(database, connection_factory=failing_worker_connection)
    recorder.start()
    assert recorder.append(RecordEvent(1, datetime.now(UTC), "will_fail"))

    recorder.flush()

    assert recorder.failed
    assert recorder.statistics.last_error == "simulated recorder write failure"
    assert recorder.statistics.events_dropped == 1
    assert not recorder.append(RecordEvent(2, datetime.now(UTC), "rejected"))
    recorder.close()
