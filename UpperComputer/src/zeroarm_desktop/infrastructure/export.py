"""CSV and JSON export from the versioned event database."""

import csv
import json
import sqlite3
from pathlib import Path


def export_session_json(connection: sqlite3.Connection, session_id: str, output: Path) -> int:
    rows = _event_rows(connection, session_id)
    document = {"schema_version": 1, "session_id": session_id, "events": rows}
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows)


def export_session_csv(connection: sqlite3.Connection, session_id: str, output: Path) -> int:
    rows = _event_rows(connection, session_id)
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]) if rows else _EVENT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


_EVENT_COLUMNS = (
    "monotonic_ns",
    "wall_utc",
    "device_time_ms",
    "sample_sequence",
    "kind",
    "payload_json",
    "raw_hex",
)


def _event_rows(connection: sqlite3.Connection, session_id: str) -> list[dict[str, object]]:
    records = connection.execute(
        """
        SELECT monotonic_ns, wall_utc, device_time_ms, sample_sequence,
               kind, payload_json, raw_blob
        FROM events WHERE session_id = ? ORDER BY monotonic_ns, id
        """,
        (session_id,),
    ).fetchall()
    return [
        dict(
            zip(
                _EVENT_COLUMNS,
                (*record[:-1], record[-1].hex() if record[-1] is not None else None),
                strict=True,
            )
        )
        for record in records
    ]
