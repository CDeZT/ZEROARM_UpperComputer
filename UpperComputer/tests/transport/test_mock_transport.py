"""Transport contract and byte-level MockDevice tests."""

from datetime import UTC, datetime

import pytest

from zeroarm_desktop.domain.errors import TransportDisconnected
from zeroarm_desktop.domain.models import JointTarget
from zeroarm_desktop.protocol.frame_codec import FrameCodec
from zeroarm_desktop.protocol.stream_parser import StreamParser
from zeroarm_desktop.protocol.v1_codec import V1Command, V1CommandCodec
from zeroarm_desktop.transport.base import LinkState
from zeroarm_desktop.transport.mock import MockSettings, MockTransport
from zeroarm_desktop.transport.mock_device import MockDevice, MockFaults


def test_transport_contract__open_close_are_idempotent_and_ordered() -> None:
    transport = MockTransport()
    states = []
    subscription = transport.subscribe_state(lambda event: states.append(event.current))

    transport.open()
    transport.open()
    transport.close()
    transport.close()

    assert states == [LinkState.OPENING, LinkState.OPEN, LinkState.CLOSING, LinkState.CLOSED]
    assert transport.state is LinkState.CLOSED
    subscription.cancel()
    subscription.cancel()


def test_transport_contract__write_requires_open_link() -> None:
    with pytest.raises(TransportDisconnected):
        MockTransport().write(b"data")


def test_mock_device_consumes_real_v1_bytes() -> None:
    device = MockDevice()
    parser = StreamParser()

    responses = device.receive(V1CommandCodec().hello_request())
    frames = parser.feed(b"".join(responses), received_monotonic_ns=1)

    assert len(frames) == 1
    assert frames[0].command == V1Command.HELLO
    assert frames[0].payload == b"ZEROARM/1.0"


def test_mock_transport_returns_state_and_updates_statistics() -> None:
    transport = MockTransport()
    received: list[bytes] = []
    transport.subscribe_bytes(received.append)
    transport.open()

    request = V1CommandCodec().get_state_request()
    transport.write(request)

    frames = StreamParser().feed(b"".join(received), received_monotonic_ns=1)
    assert len(frames) == 1
    assert frames[0].command == V1Command.GET_STATE
    assert len(frames[0].payload) == 60
    assert transport.statistics.bytes_tx == len(request)
    assert transport.statistics.bytes_rx == len(received[0])
    assert transport.statistics.writes_accepted == 1


def test_mock_target_changes_following_state_samples() -> None:
    transport = MockTransport()
    received: list[bytes] = []
    transport.subscribe_bytes(received.append)
    transport.open()
    codec = V1CommandCodec()
    target = JointTarget((100_000, -100_000, 60_000, -60_000, 20_000, -20_000), 100, 0)

    transport.write(codec.encode_joint_target(target))
    transport.write(codec.get_state_request())

    parser = StreamParser()
    frames = parser.feed(b"".join(received), received_monotonic_ns=1)
    state_frame = frames[-1]
    snapshot = codec.decode_state(
        state_frame,
        generation=1,
        received_wall_utc=datetime.now(UTC),
    )
    assert snapshot.target_joint_urad == target.joint_urad
    assert snapshot.actual_joint_urad == (20_000, 1_550_770, 20_000, -20_000, 20_000, -20_000)


def test_mock_faults_are_deterministic_at_byte_boundary() -> None:
    settings = MockSettings(
        seed=7,
        faults=MockFaults(
            corrupt_crc_response_numbers=frozenset({1}),
            duplicate_response_numbers=frozenset({2}),
            noise_prefix=b"\x01\x02",
        ),
    )
    transport = MockTransport(settings)
    received: list[bytes] = []
    transport.subscribe_bytes(received.append)
    transport.open()

    transport.write(V1CommandCodec().hello_request())
    transport.write(V1CommandCodec().get_state_request())

    parser = StreamParser()
    frames = parser.feed(b"".join(received), received_monotonic_ns=1)
    assert parser.statistics.crc_errors == 1
    assert parser.statistics.noise_bytes == 7
    assert len(frames) == 2
    assert frames[0].raw == frames[1].raw


def test_mock_device_rejects_unknown_command_with_wire_result() -> None:
    response = MockDevice().receive(FrameCodec().encode(0x7F))[0]
    frame = FrameCodec().decode_complete(response)
    result = V1CommandCodec().decode_result(frame)
    assert result.raw_value == 8
