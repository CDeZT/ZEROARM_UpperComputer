"""Read-only V1 session handshake, polling, and failure tests."""

import pytest

from zeroarm_desktop.application.device_session import DeviceSession, SessionEvent, SessionState
from zeroarm_desktop.domain.models import RobotSnapshot
from zeroarm_desktop.transport.mock import MockSettings, MockTransport
from zeroarm_desktop.transport.mock_device import MockFaults


def test_session_transition__mock_handshake_reaches_readonly_ready() -> None:
    session = DeviceSession(MockTransport())
    snapshots: list[RobotSnapshot] = []
    events: list[SessionEvent] = []
    session.subscribe_snapshots(snapshots.append)
    session.subscribe_events(events.append)

    session.connect()

    assert session.state is SessionState.READONLY_READY
    assert session.identity is not None
    assert session.identity.hello_text == "ZEROARM/1.0"
    assert session.latest_snapshot is snapshots[-1]
    assert session.latest_snapshot.generation == 1
    assert session.statistics.requests_sent == 2
    assert session.statistics.responses_received == 2
    assert [event.state for event in events if event.kind == "state_changed"] == [
        SessionState.OPENING,
        SessionState.HANDSHAKING,
        SessionState.READONLY_READY,
    ]
    session.disconnect()
    final_state = session.state
    assert final_state.value == SessionState.DISCONNECTED.value


def test_session_poll_publishes_new_generation() -> None:
    session = DeviceSession(MockTransport())
    session.connect()
    first_snapshot = session.latest_snapshot
    assert first_snapshot is not None

    assert session.poll_once()

    latest_snapshot = session.latest_snapshot
    assert latest_snapshot is not None
    assert latest_snapshot.generation == first_snapshot.generation + 1
    assert session.statistics.poll_sent == 1
    session.disconnect()


@pytest.mark.parametrize("rate", [20, 50, 100])
def test_session_accepts_documented_poll_rates(rate: int) -> None:
    session = DeviceSession(MockTransport(), poll_rate_hz=rate)
    session.set_poll_rate_hz(rate)


def test_session_rejects_unsupported_poll_rate() -> None:
    with pytest.raises(ValueError, match="20, 50, or 100"):
        DeviceSession(MockTransport(), poll_rate_hz=200)


def test_session_failed_hello_does_not_claim_ready() -> None:
    transport = MockTransport(
        MockSettings(faults=MockFaults(corrupt_crc_response_numbers=frozenset({1})))
    )
    session = DeviceSession(transport)

    session.connect()

    assert session.state is SessionState.HANDSHAKING
    assert session.identity is None
    assert session.latest_snapshot is None
    session.disconnect()


def test_session_dropped_initial_state_remains_handshaking() -> None:
    transport = MockTransport(MockSettings(faults=MockFaults(drop_response_numbers=frozenset({2}))))
    session = DeviceSession(transport)
    session.connect()

    assert session.identity is not None
    assert session.latest_snapshot is None
    assert session.state is SessionState.HANDSHAKING
    session.disconnect()
