"""Read-only V1 session handshake, polling, and failure tests."""

from threading import Event
from time import monotonic

import pytest

from zeroarm_desktop.application.device_session import (
    ActionStatus,
    DeviceSession,
    SessionEvent,
    SessionState,
)
from zeroarm_desktop.domain.models import RobotSnapshot
from zeroarm_desktop.transport.mock import MockSettings, MockTransport
from zeroarm_desktop.transport.mock_device import MockFaults


def _wait_until(predicate: object, timeout_s: float = 1.0) -> None:
    deadline = monotonic() + timeout_s
    while monotonic() < deadline:
        if callable(predicate) and predicate():
            return
        Event().wait(0.005)
    raise AssertionError("condition was not met before timeout")


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


def test_session_failed_hello_reconnects_and_reaches_ready() -> None:
    transport = MockTransport(
        MockSettings(faults=MockFaults(corrupt_crc_response_numbers=frozenset({1})))
    )
    session = DeviceSession(transport, request_timeout_s=0.03, reconnect_delay_s=0.01)

    session.connect()

    _wait_until(lambda: session.state is SessionState.READONLY_READY)
    assert session.statistics.request_timeouts == 1
    assert session.identity is not None
    assert session.latest_snapshot is not None
    session.disconnect()


def test_session_dropped_initial_state_reconnects_and_reaches_ready() -> None:
    transport = MockTransport(MockSettings(faults=MockFaults(drop_response_numbers=frozenset({2}))))
    session = DeviceSession(transport, request_timeout_s=0.03, reconnect_delay_s=0.01)
    session.connect()

    _wait_until(lambda: session.state is SessionState.READONLY_READY)
    assert session.statistics.request_timeouts == 1
    assert session.identity is not None
    assert session.latest_snapshot is not None
    session.disconnect()


def test_session_permanent_handshake_loss_faults_after_bounded_reconnects() -> None:
    transport = MockTransport(
        MockSettings(faults=MockFaults(drop_response_numbers=frozenset(range(1, 20))))
    )
    session = DeviceSession(
        transport,
        request_timeout_s=0.02,
        reconnect_delay_s=0.005,
        max_reconnect_attempts=2,
    )
    session.connect()

    _wait_until(lambda: session.state is SessionState.FAULTED)

    assert session.statistics.request_timeouts == 3
    session.disconnect()


def test_stop_supersedes_an_unanswered_state_poll() -> None:
    transport = MockTransport(MockSettings(faults=MockFaults(drop_response_numbers=frozenset({3}))))
    session = DeviceSession(
        transport,
        actions_allowed=True,
        request_timeout_s=1.0,
    )
    session.connect()
    assert session.poll_once()

    result = session.send_stop()

    assert result.raw_value == 0
    assert "STOP" in session.command_audit
    session.disconnect()


def test_action_request_completes_after_delayed_transport_response() -> None:
    transport = MockTransport(MockSettings(response_delay_ms=20))
    session = DeviceSession(
        transport,
        actions_allowed=True,
        request_timeout_s=0.5,
    )
    session.connect()
    _wait_until(lambda: session.state is SessionState.READONLY_READY)

    request = session.send_stop()
    completions: list[ActionStatus] = []
    request.subscribe(lambda completed: completions.append(completed.status))

    assert request.status is ActionStatus.PENDING
    _wait_until(lambda: request.done)
    assert request.status is ActionStatus.COMPLETED
    assert request.raw_value == 0
    assert completions == [ActionStatus.COMPLETED]
    late_completions: list[ActionStatus] = []
    request.subscribe(lambda completed: late_completions.append(completed.status))
    assert late_completions == [ActionStatus.COMPLETED]
    session.disconnect()


def test_action_timeout_reports_unknown_outcome_without_retry() -> None:
    transport = MockTransport(MockSettings(faults=MockFaults(drop_response_numbers=frozenset({3}))))
    session = DeviceSession(
        transport,
        actions_allowed=True,
        request_timeout_s=0.02,
    )
    session.connect()

    request = session.send_home(0x1D)
    _wait_until(lambda: request.done)

    assert request.status is ActionStatus.UNKNOWN_OUTCOME
    assert session.command_audit.count("HOME") == 1
    session.disconnect()
