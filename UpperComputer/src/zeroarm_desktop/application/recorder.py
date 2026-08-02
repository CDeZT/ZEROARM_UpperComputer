"""Bounded asynchronous SQLite event recorder."""

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, RLock, Thread, current_thread
from uuid import uuid4

from zeroarm_desktop.infrastructure.database import (
    connect_database,
    insert_events,
    migrate_database,
)


@dataclass(frozen=True, slots=True)
class RecordEvent:
    monotonic_ns: int
    wall_utc: datetime
    kind: str
    payload: dict[str, object] | None = None
    raw_blob: bytes | None = None
    device_time_ms: int | None = None
    sample_sequence: int | None = None


@dataclass(frozen=True, slots=True)
class RecorderStatistics:
    events_written: int = 0
    events_dropped: int = 0
    batches_written: int = 0
    last_error: str | None = None


class Recorder:
    def __init__(
        self,
        database_path: Path,
        *,
        queue_capacity: int = 20_000,
        connection_factory: Callable[[Path], sqlite3.Connection] = connect_database,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self.database_path = database_path
        self._connection_factory = connection_factory
        self._on_error = on_error
        self._queue: Queue[RecordEvent] = Queue(maxsize=queue_capacity)
        self._statistics = RecorderStatistics()
        self._stop = Event()
        self._failed = Event()
        self._thread: Thread | None = None
        self._session_id: str | None = None
        self._lock = RLock()

    @property
    def statistics(self) -> RecorderStatistics:
        with self._lock:
            return self._statistics

    @property
    def failed(self) -> bool:
        return self._failed.is_set()

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self, metadata: dict[str, object] | None = None) -> str:
        if self._thread is not None:
            if not self._thread.is_alive():
                self._thread = None
            elif self._session_id is None:
                raise RuntimeError("recorder session is unavailable")
            else:
                return self._session_id
        self._session_id = str(uuid4())
        self._failed.clear()
        try:
            connection = self._connection_factory(self.database_path)
            try:
                migrate_database(connection)
                with connection:
                    connection.execute(
                        "INSERT INTO sessions VALUES (?, ?, ?)",
                        (
                            self._session_id,
                            datetime.now(UTC).isoformat(),
                            json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                        ),
                    )
            finally:
                connection.close()
        except (OSError, sqlite3.Error, RuntimeError) as error:
            self._session_id = None
            self._record_failure(str(error))
            raise
        self._stop.clear()
        self._thread = Thread(target=self._run, name="zeroarm-recorder", daemon=True)
        self._thread.start()
        return self._session_id

    def append(self, event: RecordEvent) -> bool:
        if self._thread is None:
            raise RuntimeError("recorder is not started")
        if self._failed.is_set():
            self._update_statistics(events_dropped=1)
            return False
        try:
            self._queue.put_nowait(event)
            return True
        except Full:
            self._update_statistics(events_dropped=1)
            return False

    def flush(self, timeout_s: float = 5.0) -> None:
        if self._thread is None:
            return
        deadline = __import__("time").monotonic() + timeout_s
        while self._queue.unfinished_tasks and __import__("time").monotonic() < deadline:
            Event().wait(0.01)
        if self._queue.unfinished_tasks:
            raise TimeoutError("recorder flush timed out")

    def close(self, timeout_s: float = 5.0) -> None:
        if self._thread is None:
            return
        self.flush(timeout_s)
        self._stop.set()
        thread = self._thread
        if thread is not current_thread():
            thread.join(timeout_s)
        if thread.is_alive() and thread is not current_thread():
            raise TimeoutError("recorder worker did not stop")
        self._thread = None
        self._session_id = None

    def _run(self) -> None:
        try:
            connection = self._connection_factory(self.database_path)
        except (OSError, sqlite3.Error) as error:
            self._record_failure(str(error))
            self._discard_queued_events()
            return
        try:
            while not self._stop.is_set() or not self._queue.empty():
                batch = self._take_batch()
                if not batch:
                    continue
                try:
                    session_id = self._session_id
                    if session_id is None:
                        raise RuntimeError("recorder session is unavailable")
                    insert_events(connection, (self._row(session_id, event) for event in batch))
                    self._update_statistics(events_written=len(batch), batches_written=1)
                except sqlite3.Error as error:
                    self._record_failure(str(error), dropped=len(batch))
                finally:
                    for _ in batch:
                        self._queue.task_done()
                if self._failed.is_set():
                    self._discard_queued_events()
                    return
        finally:
            connection.close()

    def _record_failure(self, detail: str, *, dropped: int = 0) -> None:
        self._failed.set()
        self._stop.set()
        self._update_statistics(events_dropped=dropped, last_error=detail)
        if self._on_error is not None:
            self._on_error(detail)

    def _discard_queued_events(self) -> None:
        dropped = 0
        while True:
            try:
                self._queue.get_nowait()
            except Empty:
                break
            self._queue.task_done()
            dropped += 1
        if dropped:
            self._update_statistics(events_dropped=dropped)

    def _take_batch(self) -> list[RecordEvent]:
        try:
            first = self._queue.get(timeout=0.1)
        except Empty:
            return []
        batch = [first]
        while len(batch) < 50:
            try:
                batch.append(self._queue.get_nowait())
            except Empty:
                break
        return batch

    @staticmethod
    def _row(session_id: str, event: RecordEvent) -> tuple[object, ...]:
        return (
            session_id,
            event.monotonic_ns,
            event.wall_utc.isoformat(),
            event.device_time_ms,
            event.sample_sequence,
            event.kind,
            json.dumps(event.payload, ensure_ascii=False, sort_keys=True)
            if event.payload
            else None,
            event.raw_blob,
        )

    def _update_statistics(
        self,
        *,
        events_written: int = 0,
        events_dropped: int = 0,
        batches_written: int = 0,
        last_error: str | None = None,
    ) -> None:
        with self._lock:
            current = self._statistics
            self._statistics = RecorderStatistics(
                events_written=current.events_written + events_written,
                events_dropped=current.events_dropped + events_dropped,
                batches_written=current.batches_written + batches_written,
                last_error=last_error if last_error is not None else current.last_error,
            )
