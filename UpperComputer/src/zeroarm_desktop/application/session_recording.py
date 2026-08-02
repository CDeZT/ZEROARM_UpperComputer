"""Wire DeviceSession snapshots/events into the bounded SQLite Recorder."""

from __future__ import annotations

import sqlite3
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic_ns

from zeroarm_desktop.application.device_session import DeviceSession, SessionEvent, SessionState
from zeroarm_desktop.application.recorder import Recorder, RecordEvent
from zeroarm_desktop.domain.models import RobotSnapshot
from zeroarm_desktop.infrastructure.paths import default_data_root
from zeroarm_desktop.transport.base import Subscription
from zeroarm_desktop.version import __version__


class SessionRecordingBridge:
    """Start/stop recorder with session lifecycle and append snapshot samples."""

    def __init__(self, database_path: Path | None = None) -> None:
        path = database_path or (default_data_root() / "sessions" / "zeroarm-sessions.sqlite3")
        self.recorder = Recorder(path, on_error=self._on_recorder_error)
        self._session: DeviceSession | None = None
        self._snapshot_sub: Subscription | None = None
        self._event_sub: Subscription | None = None
        self._session_id: str | None = None
        self._last_error: str | None = None

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def bind_session(self, session: DeviceSession | None) -> bool:
        self.unbind()
        self._last_error = None
        if session is None:
            return False
        try:
            self._session_id = self.recorder.start(
                {
                    "app_version": __version__,
                    "actions_allowed": session.actions_allowed,
                    "transport": "mock" if session.actions_allowed else "serial_or_unknown",
                }
            )
        except (OSError, sqlite3.Error, RuntimeError) as error:
            self._last_error = str(error)
            self._session_id = None
            return False
        self._session = session
        self._event_sub = session.subscribe_events(self._on_event)
        self._snapshot_sub = session.subscribe_snapshots(self._on_snapshot)
        self._append(
            RecordEvent(
                monotonic_ns(),
                datetime.now(UTC),
                "session_bound",
                {"session_state": session.state.value},
            )
        )
        return True

    def unbind(self) -> None:
        if self._snapshot_sub is not None:
            self._snapshot_sub.cancel()
            self._snapshot_sub = None
        if self._event_sub is not None:
            self._event_sub.cancel()
            self._event_sub = None
        if self._session_id is not None or self.recorder.failed:
            with suppress(TimeoutError):
                self.recorder.close(timeout_s=2.0)
        self._session = None
        self._session_id = None

    def note(self, kind: str, payload: dict[str, object] | None = None) -> None:
        if self._session_id is None:
            return
        self._append(RecordEvent(monotonic_ns(), datetime.now(UTC), kind, payload))

    def _on_snapshot(self, snapshot: RobotSnapshot) -> None:
        self._append(
            RecordEvent(
                snapshot.received_monotonic_ns,
                snapshot.received_wall_utc,
                "snapshot",
                {
                    "generation": snapshot.generation,
                    "run_state_raw": snapshot.run_state_raw,
                    "fault_flags_raw": snapshot.fault_flags_raw,
                    "target_joint_urad": list(snapshot.target_joint_urad),
                    "actual_joint_urad": list(snapshot.actual_joint_urad),
                    "enabled_mask": snapshot.enabled_mask,
                    "homed_mask": snapshot.homed_mask,
                    "moving_mask": snapshot.moving_mask,
                },
                device_time_ms=snapshot.device_time_ms,
                sample_sequence=snapshot.sample_sequence,
            )
        )

    def _on_event(self, event: SessionEvent) -> None:
        self._append(
            RecordEvent(
                monotonic_ns(),
                datetime.now(UTC),
                "session_event",
                {"kind": event.kind, "state": event.state.value, "detail": event.detail},
            )
        )
        if event.state is SessionState.DISCONNECTED:
            self.unbind()

    def _append(self, event: RecordEvent) -> bool:
        try:
            accepted = self.recorder.append(event)
        except RuntimeError as error:
            self._last_error = str(error)
            return False
        if not accepted:
            self._last_error = self.recorder.statistics.last_error or "recording queue full"
        return accepted

    def _on_recorder_error(self, detail: str) -> None:
        self._last_error = detail
        self._session_id = None
        self._session = None
        if self._snapshot_sub is not None:
            self._snapshot_sub.cancel()
            self._snapshot_sub = None
        if self._event_sub is not None:
            self._event_sub.cancel()
            self._event_sub = None
