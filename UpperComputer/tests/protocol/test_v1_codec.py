"""V1 command payload layout, boundary, and unknown-value tests."""

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from zeroarm_desktop.domain.errors import ProtocolDecodeError
from zeroarm_desktop.domain.models import JointTarget
from zeroarm_desktop.protocol.fixtures import (
    V1_BENCH_GET_PROTECTION_RSP_MOTOR3,
    V1_BENCH_MOVE_REL_MOTOR1,
    V1_BENCH_QUERY_MOTOR1,
    V1_BENCH_QUERY_RSP_MOTOR1,
    V1_BENCH_SET_PROTECTION,
    V1_GRIPPER_MOVE_ID1,
    V1_GRIPPER_PING_ID1,
    V1_GRIPPER_PING_RSP_ID1,
    V1_GRIPPER_READ_ID1_POS,
    V1_GRIPPER_READ_RSP_ID1,
    V1_GRIPPER_TORQUE_ID1_ON,
    V1_HELLO_REQUEST,
    V1_HELLO_RESPONSE,
    V1_HOME_MASK_1D,
    V1_STATE_ESTOP_FAULT,
    V1_STATE_READY_HOMED_1D,
    V1_STATE_READY_ZERO,
    V1_STATE_STARTUP_FAULT,
    V1_TARGET_FORBIDDEN_J2,
    V1_TARGET_FORBIDDEN_J6,
    V1_TARGET_MIXED_SIGNS,
)
from zeroarm_desktop.protocol.frame_codec import FrameCodec, ProtocolFrame
from zeroarm_desktop.protocol.v1_codec import (
    RESET_REQUIRED_FAULTS,
    V1BenchCommand,
    V1Command,
    V1CommandCodec,
    V1FaultFlag,
    V1GripperCommand,
    V1GripperResultCode,
    V1ResultCode,
    V1RunState,
    decode_fault_flags,
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


def test_v1_fixture__state_fixtures_decode() -> None:
    codec = V1CommandCodec()
    ready = codec.decode_state(
        FrameCodec().decode_complete(V1_STATE_READY_ZERO.raw),
        generation=1,
        received_wall_utc=WALL_TIME,
    )
    assert ready.run_state_raw == V1RunState.READY
    assert ready.enabled_mask == 0
    assert ready.homed_mask == 0
    assert ready.moving_mask == 0
    assert ready.fault_flags_raw == 0

    homed = codec.decode_state(
        FrameCodec().decode_complete(V1_STATE_READY_HOMED_1D.raw),
        generation=2,
        received_wall_utc=WALL_TIME,
    )
    assert homed.run_state_raw == V1RunState.READY
    assert homed.homed_mask == 0x1D

    startup = codec.decode_state(
        FrameCodec().decode_complete(V1_STATE_STARTUP_FAULT.raw),
        generation=3,
        received_wall_utc=WALL_TIME,
    )
    assert startup.run_state_raw == V1RunState.FAULT
    assert startup.fault_flags_raw == V1FaultFlag.STARTUP

    estop = codec.decode_state(
        FrameCodec().decode_complete(V1_STATE_ESTOP_FAULT.raw),
        generation=4,
        received_wall_utc=WALL_TIME,
    )
    assert estop.run_state_raw == V1RunState.FAULT
    assert estop.fault_flags_raw == V1FaultFlag.ESTOP


def test_v1_fixture__home_and_target_frames_round_trip() -> None:
    home_frame = FrameCodec().decode_complete(V1_HOME_MASK_1D.raw)
    assert home_frame.command == V1Command.HOME
    assert home_frame.payload == b"\x1d"

    target_frame = FrameCodec().decode_complete(V1_TARGET_MIXED_SIGNS.raw)
    assert target_frame.command == V1Command.SET_JOINT_TARGET
    assert len(target_frame.payload) == 28
    joints = tuple(
        int.from_bytes(target_frame.payload[i : i + 4], "big", signed=True) for i in range(0, 24, 4)
    )
    assert joints == (-2_147_483_648, -1_570_770, -1, 0, 1_570_770, 2_147_483_647)
    assert int.from_bytes(target_frame.payload[24:26], "big") == 0x1234
    assert int.from_bytes(target_frame.payload[26:28], "big") == 0xABCD

    for forbidden in (V1_TARGET_FORBIDDEN_J2, V1_TARGET_FORBIDDEN_J6):
        frame = FrameCodec().decode_complete(forbidden.raw)
        assert frame.command == V1Command.SET_JOINT_TARGET
        assert len(frame.payload) == 28


@pytest.mark.parametrize(
    "raw_value,expected_bits",
    [
        (0, ()),
        (1 << 0, (V1FaultFlag.TARGET_RANGE,)),
        (1 << 9, (V1FaultFlag.STARTUP,)),
        (1 << 11, (V1FaultFlag.ESTOP,)),
        (0x0FFF, tuple(V1FaultFlag)),
        (0xFFFF, tuple(V1FaultFlag)),
    ],
)
def test_v1_fault__known_bits_are_decoded(
    raw_value: int, expected_bits: tuple[V1FaultFlag, ...]
) -> None:
    decoding = decode_fault_flags(raw_value)
    assert decoding.known == expected_bits
    assert decoding.unknown_bits == (raw_value & ~0x0FFF)


def test_v1_fault__reset_required_classification() -> None:
    assert RESET_REQUIRED_FAULTS == (1 << 9) | (1 << 10) | (1 << 11)
    assert decode_fault_flags(0).reset_required is False
    assert decode_fault_flags(1 << 9).reset_required is True
    assert decode_fault_flags(1 << 10).reset_required is True
    assert decode_fault_flags(1 << 11).reset_required is True
    assert decode_fault_flags(1 << 0).reset_required is False


def test_v1_fault__invalid_inputs_are_rejected() -> None:
    with pytest.raises(TypeError):
        decode_fault_flags(True)
    with pytest.raises(TypeError):
        decode_fault_flags(1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        decode_fault_flags(-1)
    with pytest.raises(ValueError):
        decode_fault_flags(1 << 32)


def test_v1_bench__fixture_requests_round_trip() -> None:
    codec = V1CommandCodec()
    assert codec.encode_bench_id_command(V1BenchCommand.QUERY, 1) == V1_BENCH_QUERY_MOTOR1.raw
    assert codec.encode_bench_move_relative(1, 1, 10800, 100, 50) == V1_BENCH_MOVE_REL_MOTOR1.raw
    assert codec.encode_bench_set_protection(3, True, 100, 3500, 300) == V1_BENCH_SET_PROTECTION.raw


def test_v1_bench__state_response_decodes_little_endian() -> None:
    frame = FrameCodec().decode_complete(V1_BENCH_QUERY_RSP_MOTOR1.raw)
    state = V1CommandCodec().decode_bench_state(frame)
    assert state.motor_id == 1
    assert state.online is True
    assert state.position_urad == 12345
    assert state.velocity_tenths_rpm == -500
    assert state.current_ma == 0x1234
    assert state.status == 0x0083
    assert state.fault_flags == 2
    assert state.can_tx_errors == 3
    assert state.feedback_faults == 1
    assert state.position_sample_count == 42
    assert state.target_submit_count == 7
    assert state.target_send_count == 9


def test_v1_bench__protection_response_decodes_big_endian() -> None:
    frame = FrameCodec().decode_complete(V1_BENCH_GET_PROTECTION_RSP_MOTOR3.raw)
    protection = V1CommandCodec().decode_bench_protection(frame)
    assert protection.motor_id == 3
    assert protection.temperature_c == 100
    assert protection.current_ma == 3500
    assert protection.detection_time_ms == 300


def test_v1_bench__rejects_bad_lengths_and_ids() -> None:
    codec = V1CommandCodec()
    with pytest.raises(ValueError, match="motor id"):
        codec.encode_bench_id_command(V1BenchCommand.QUERY, 0)
    with pytest.raises(ValueError, match="motor id"):
        codec.encode_bench_id_command(V1BenchCommand.QUERY, 7)
    with pytest.raises(ValueError, match="does not accept"):
        codec.encode_bench_id_command(V1BenchCommand.MOVE_REL, 1)
    with pytest.raises(ValueError, match="degrees_tenths"):
        codec.encode_bench_move_relative(1, 0, 5_400_001, 100, 50)
    with pytest.raises(ValueError, match="velocity_tenths"):
        codec.encode_bench_move_relative(1, 0, 100, 15_001, 50)
    with pytest.raises(ValueError, match="acceleration_rpm_s"):
        codec.encode_bench_move_relative(1, 0, 100, 100, 2_001)
    with pytest.raises(ValueError, match="temperature_c"):
        codec.encode_bench_set_protection(3, True, 39, 3500, 300)
    with pytest.raises(ValueError, match="current_ma"):
        codec.encode_bench_set_protection(3, True, 100, 499, 300)
    with pytest.raises(ValueError, match="detection_time_ms"):
        codec.encode_bench_set_protection(3, True, 100, 3500, 5001)
    with pytest.raises(TypeError, match="save"):
        codec.encode_bench_set_protection(3, 1, 100, 3500, 300)  # type: ignore[arg-type]

    with pytest.raises(ProtocolDecodeError, match="40 bytes"):
        codec.decode_bench_state(_frame(V1BenchCommand.QUERY, bytes(39)))
    with pytest.raises(ProtocolDecodeError, match="7 bytes"):
        codec.decode_bench_protection(_frame(V1BenchCommand.GET_PROTECTION, bytes(6)))


def test_v1_gripper__fixture_requests_round_trip() -> None:
    codec = V1CommandCodec()
    assert codec.encode_gripper_ping(1) == V1_GRIPPER_PING_ID1.raw
    assert codec.encode_gripper_read(1, 0x38, 2) == V1_GRIPPER_READ_ID1_POS.raw
    assert codec.encode_gripper_move(1, 0x0800, 1000, 20) == V1_GRIPPER_MOVE_ID1.raw
    assert codec.encode_gripper_torque(1, 1) == V1_GRIPPER_TORQUE_ID1_ON.raw


def test_v1_gripper__responses_decode() -> None:
    codec = V1CommandCodec()
    ping = codec.decode_gripper_response(FrameCodec().decode_complete(V1_GRIPPER_PING_RSP_ID1.raw))
    assert ping.command is V1GripperCommand.PING
    assert ping.raw_result == 0
    assert ping.known_result is V1GripperResultCode.OK
    assert ping.id == 1
    assert ping.servo_error == 0
    assert ping.data == b""
    assert ping.is_ok

    read = codec.decode_gripper_response(FrameCodec().decode_complete(V1_GRIPPER_READ_RSP_ID1.raw))
    assert read.command is V1GripperCommand.READ
    assert read.data == b"\x18\x05"


def test_v1_gripper__unknown_result_and_short_payload() -> None:
    codec = V1CommandCodec()
    response = codec.decode_gripper_response(_frame(V1GripperCommand.PING, b"\x09\x01\x00"))
    assert response.raw_result == 9
    assert response.known_result is None
    assert not response.is_ok

    with pytest.raises(ProtocolDecodeError, match="at least 3 bytes"):
        codec.decode_gripper_response(_frame(V1GripperCommand.PING, b"\x00\x01"))
    with pytest.raises(ProtocolDecodeError, match="gripper command"):
        codec.decode_gripper_response(_frame(V1Command.HELLO, b"\x00\x01\x00"))


def test_v1_gripper__validates_input_ranges() -> None:
    codec = V1CommandCodec()
    with pytest.raises(ValueError, match="servo id"):
        codec.encode_gripper_ping(0xFE)
    with pytest.raises(ValueError, match="read length"):
        codec.encode_gripper_read(1, 0, 0)
    with pytest.raises(ValueError, match="read length"):
        codec.encode_gripper_read(1, 0, 33)
    with pytest.raises(ValueError, match="data length"):
        codec.encode_gripper_write(1, 0, b"")
    with pytest.raises(ValueError, match="data length"):
        codec.encode_gripper_write(1, 0, bytes(32))
    with pytest.raises(TypeError, match="data must be bytes"):
        codec.encode_gripper_write(1, 0, "x")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="position"):
        codec.encode_gripper_move(1, 4096, 1, 1)
    with pytest.raises(ValueError, match="torque mode"):
        codec.encode_gripper_torque(1, 3)
