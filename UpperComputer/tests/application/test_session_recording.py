"""Session recorder bridge lifecycle tests."""

from pathlib import Path

from zeroarm_desktop.application.device_session import DeviceSession
from zeroarm_desktop.application.session_recording import SessionRecordingBridge
from zeroarm_desktop.transport.mock import MockTransport


def test_session_recording_bridge_records_snapshots(tmp_path: Path) -> None:
    db = tmp_path / "sessions.sqlite3"
    bridge = SessionRecordingBridge(db)
    transport = MockTransport()
    session = DeviceSession(transport, actions_allowed=True)
    session.connect()
    bridge.bind_session(session)
    session.poll_once()
    bridge.note("operator_note", {"text": "hello"})
    bridge.unbind()
    assert bridge.session_id is None
    assert bridge.recorder.statistics.events_written >= 1
    assert db.is_file()


def test_session_recording_start_failure_is_reported_without_raising(tmp_path: Path) -> None:
    invalid_parent = tmp_path / "not-a-directory"
    invalid_parent.write_text("occupied", encoding="utf-8")
    bridge = SessionRecordingBridge(invalid_parent / "sessions.sqlite3")
    session = DeviceSession(MockTransport(), actions_allowed=True)
    session.connect()

    started = bridge.bind_session(session)

    assert not started
    assert bridge.session_id is None
    assert bridge.last_error is not None
    session.disconnect()
