"""V1 command payload layout, boundary, and unknown-value tests."""

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from zeroarm_desktop.domain.errors import ProtocolDecodeError
from zeroarm_desktop.domain.models import JointTarget
from zeroarm_desktop.protocol.fixtures import V1_HELLO_REQUEST, V1_HELLO_RESPONSE
from zeroarm_desktop.protocol.frame_codec import FrameCodec, ProtocolFrame
from zeroarm_desktop.protocol.v1_codec import (
    V1Command,
    V1CommandCodec,
    V1ResultCode,
)

WALL_TIME = datetime(2026, 7, 29, 5, 0, tzinfo=UTC)


def _frame(command: int, payload: bytes, timestamp: int = 100) -> ProtocolFrame:
    raw = FrameCodec().encode(command, payload)
    return FrameCodec().decode_complete(raw, received_monotonic_ns=timestamp)


def _state_payload(
    *,
    run_state: int = 1,
    target: tuple[int, int, int, int, int, int] = (1, -2, 3, -4, 5, -6),
    actual: tuple[int, int, int, int, int, int] = (-7, 8, -9, 10, -11, 12),
) -> bytes:
    payload = bytearray(run_state.to_bytes(4, "little", signed=True))
    for value in target + actual:
        payload.extend(value.to_bytes(4, "little", signed=True))
    payload.extend(bytes((0x15, 0x0A, 0x03, 0xA5)))
    payload.extend((0x89ABCDEF).to_bytes(4, "little"))
    assert len(payload) == 60
    return bytes(payload)


def test_v1_fixture__hello_request_and_response() -> None:
    codec = V1CommandCodec()

    assert codec.hello_request() == V1_HELLO_REQUEST.raw
    identity = codec.decode_hello(FrameCodec().decode_complete(V1_HELLO_RESPONSE.raw))
    assert identity.hello_text == "ZEROARM/1.0"
    assert identity.protocol_generation == 1
    assert identity.schema_version is None
    assert identity.capabilities is None


def test_v1_codec_decodes_explicit_60_byte_state_layout() -> None:
    codec = V1CommandCodec()
    frame = _frame(V1Command.GET_STATE, _state_payload(), timestamp=456)

    snapshot = codec.decode_state(frame, generation=7, received_wall_utc=WALL_TIME)

    assert snapshot.generation == 7
    assert snapshot.received_monotonic_ns == 456
    assert snapshot.received_wall_utc == WALL_TIME
    assert snapshot.run_state_raw == 1
    assert snapshot.target_joint_urad == (1, -2, 3, -4, 5, -6)
    assert snapshot.actual_joint_urad == (-7, 8, -9, 10, -11, 12)
    assert snapshot.enabled_mask == 0x15
    assert snapshot.homed_mask == 0x0A
    assert snapshot.moving_mask == 0x03
    assert snapshot.fault_flags_raw == 0x89ABCDEF
    assert snapshot.online_mask is None
    assert snapshot.teach_mask is None
    assert snapshot.velocity_urad_s is None
    assert snapshot.current_ma is None
    assert snapshot.device_time_ms is None
    assert snapshot.sample_sequence is None


def test_v1_codec_preserves_unknown_run_state() -> None:
    snapshot = V1CommandCodec().decode_state(
        _frame(V1Command.GET_STATE, _state_payload(run_state=12345)),
        generation=1,
        received_wall_utc=WALL_TIME,
    )
    assert snapshot.run_state_raw == 12345


def test_v1_fixture__mixed_sign_target_is_big_endian() -> None:
    target = JointTarget(
        joint_urad=(-2_147_483_648, -1_570_770, -1, 0, 1_570_770, 2_147_483_647),
        duration_ms=0x1234,
        gripper_u16=0xABCD,
    )

    frame = FrameCodec().decode_complete(V1CommandCodec().encode_joint_target(target))

    assert frame.command == V1Command.SET_JOINT_TARGET
    assert frame.payload.hex() == ("80000000ffe8082effffffff000000000017f7d27fffffff1234abcd")
    assert len(frame.payload) == 28


@given(
    joints=st.tuples(*(st.integers(-(2**31), 2**31 - 1) for _ in range(6))),
    duration=st.integers(0, 0xFFFF),
    gripper=st.integers(0, 0xFFFF),
)
def test_protocol_property__joint_target_fields_round_trip_as_big_endian(
    joints: tuple[int, int, int, int, int, int],
    duration: int,
    gripper: int,
) -> None:
    frame = FrameCodec().decode_complete(
        V1CommandCodec().encode_joint_target(JointTarget(joints, duration, gripper))
    )
    decoded_joints = tuple(
        int.from_bytes(frame.payload[index : index + 4], "big", signed=True)
        for index in range(0, 24, 4)
    )
    assert decoded_joints == joints
    assert int.from_bytes(frame.payload[24:26], "big") == duration
    assert int.from_bytes(frame.payload[26:28], "big") == gripper


@pytest.mark.parametrize("raw", range(9))
def test_v1_codec_decodes_all_known_results(raw: int) -> None:
    result = V1CommandCodec().decode_result(_frame(V1Command.ENABLE, bytes((raw,))))
    assert result.raw_value == raw
    assert result.known is V1ResultCode(raw)
    assert result.is_ok is (raw == 0)


def test_v1_codec_preserves_unknown_result() -> None:
    result = V1CommandCodec().decode_result(_frame(0x7F, b"\xfe"))
    assert result.command == 0x7F
    assert result.raw_value == 0xFE
    assert result.known is None
    assert not result.is_ok


def test_v1_codec_encodes_only_valid_mask_and_empty_commands() -> None:
    codec = V1CommandCodec()
    mask_frame = FrameCodec().decode_complete(codec.encode_joint_mask(V1Command.ENABLE, 0x3F))
    assert mask_frame.payload == b"\x3f"
    assert FrameCodec().decode_complete(codec.get_state_request()).command == V1Command.GET_STATE

    with pytest.raises(ValueError, match="joint mask"):
        codec.encode_joint_mask(V1Command.ENABLE, 0)
    with pytest.raises(ValueError, match="joint mask"):
        codec.encode_joint_mask(V1Command.ENABLE, 0x40)
    with pytest.raises(ValueError, match="does not accept"):
        codec.encode_joint_mask(V1Command.STOP, 1)
    with pytest.raises(ValueError, match="requires"):
        codec.encode_empty_command(V1Command.SET_JOINT_TARGET)


@pytest.mark.parametrize("length", [0, 1, 59, 61])
def test_v1_codec_rejects_non_60_byte_state(length: int) -> None:
    with pytest.raises(ProtocolDecodeError, match="60 bytes"):
        V1CommandCodec().decode_state(
            _frame(V1Command.GET_STATE, bytes(length)),
            generation=0,
            received_wall_utc=WALL_TIME,
        )


def test_v1_codec_rejects_invalid_identity_and_result_lengths() -> None:
    codec = V1CommandCodec()
    with pytest.raises(ProtocolDecodeError, match="ASCII"):
        codec.decode_hello(_frame(V1Command.HELLO, b"\xff"))
    with pytest.raises(ProtocolDecodeError, match="unsupported"):
        codec.decode_hello(_frame(V1Command.HELLO, b"OTHER/1.0"))
    with pytest.raises(ProtocolDecodeError, match="one byte"):
        codec.decode_result(_frame(V1Command.ENABLE, b""))


def test_v1_codec_validates_target_ranges() -> None:
    codec = V1CommandCodec()
    with pytest.raises(ValueError, match="joint position"):
        codec.encode_joint_target(JointTarget((0, 0, 0, 0, 0, 2**31), 1, 1))
    with pytest.raises(ValueError, match="duration"):
        codec.encode_joint_target(JointTarget((0, 0, 0, 0, 0, 0), 0x10000, 1))
    with pytest.raises(TypeError, match="gripper"):
        codec.encode_joint_target(JointTarget((0, 0, 0, 0, 0, 0), 1, True))
