"""MockDevice current-MCU semantics: limit gate, ordered HOME, E-stop, auto-home."""

from datetime import UTC, datetime
from typing import cast

from zeroarm_desktop.domain.models import JointTarget, JointVector, RobotSnapshot
from zeroarm_desktop.protocol.frame_codec import FrameCodec
from zeroarm_desktop.protocol.v1_codec import (
    V1Command,
    V1CommandCodec,
    V1FaultFlag,
    V1ResultCode,
)
from zeroarm_desktop.transport.mock import MockTransport
from zeroarm_desktop.transport.mock_device import (
    AUTO_HOME_IDLE_MS_DEFAULT,
    PROFILE_HOME_MASK,
    MockDevice,
    MockDeviceSettings,
)


def _result_raw(device: MockDevice, frame_bytes: bytes) -> int:
    response = device.receive(frame_bytes)[0]
    frame = FrameCodec().decode_complete(response)
    return V1CommandCodec().decode_result(frame).raw_value


def _cmd_result(device: MockDevice, command: int, payload: bytes) -> int:
    return _result_raw(device, FrameCodec().encode(command, payload))


def _snapshot(device: MockDevice) -> RobotSnapshot:
    response = device.receive(V1CommandCodec().get_state_request())[0]
    frame = FrameCodec().decode_complete(response)
    return V1CommandCodec().decode_state(frame, generation=1, received_wall_utc=datetime.now(UTC))


def test_mock__default_boot_reaches_ready_with_limits_active() -> None:
    device = MockDevice()
    snapshot = _snapshot(device)
    assert snapshot.run_state_raw == 1
    assert snapshot.fault_flags_raw == 0
    assert snapshot.enabled_mask == 0
    assert snapshot.homed_mask == 0
    assert device.motion_authorized


def test_mock__startup_limit_gate_blocks_motion() -> None:
    device = MockDevice(settings=MockDeviceSettings(startup_limits_active=False))
    snapshot = _snapshot(device)
    assert snapshot.run_state_raw == 5
    assert snapshot.fault_flags_raw == V1FaultFlag.STARTUP
    assert not device.motion_authorized
    assert _cmd_result(device, V1Command.ENABLE, b"\x1d") == V1ResultCode.ERR_NOT_READY
    target = JointTarget((10_000, 0, 0, 0, 0, 0), 100, 0)
    assert (
        _result_raw(device, V1CommandCodec().encode_joint_target(target))
        == V1ResultCode.ERR_NOT_READY
    )


def test_mock__enable_disable_and_stop_semantics() -> None:
    device = MockDevice()
    assert _cmd_result(device, V1Command.ENABLE, b"\x1d") == V1ResultCode.OK
    assert _snapshot(device).enabled_mask == 0x1D
    assert _cmd_result(device, V1Command.ENABLE, b"\x00") == V1ResultCode.ERR_ARGUMENT
    assert _cmd_result(device, V1Command.ENABLE, b"\x40") == V1ResultCode.ERR_RANGE
    assert _cmd_result(device, V1Command.DISABLE, b"\x05") == V1ResultCode.OK
    assert _snapshot(device).enabled_mask == 0x18

    target = JointTarget((100_000, 0, 0, 0, 0, 0), 100, 0)
    codec = V1CommandCodec()
    assert _result_raw(device, codec.encode_joint_target(target)) == (V1ResultCode.OK)
    assert _cmd_result(device, V1Command.STOP, b"") == V1ResultCode.OK
    snapshot = _snapshot(device)
    assert snapshot.moving_mask == 0
    assert snapshot.actual_joint_urad == (0, 0, 0, 0, 0, 0)
    assert snapshot.target_joint_urad == (0, 0, 0, 0, 0, 0)


def test_mock__ordered_home_j5_j4_j3_j1() -> None:
    device = MockDevice()
    assert _cmd_result(device, V1Command.HOME, bytes((PROFILE_HOME_MASK,))) == V1ResultCode.OK
    assert not device.motion_authorized

    expected_sequence = [0x10, 0x18, 0x1C, 0x1D]
    for index, expected_homed in enumerate(expected_sequence):
        snapshot = _snapshot(device)
        if index < 3:
            assert snapshot.run_state_raw == 2
        else:
            assert snapshot.run_state_raw == 1
        assert snapshot.homed_mask == expected_homed
    assert device.motion_authorized


def test_mock__home_rejects_j2_j6_and_unconfigured_masks() -> None:
    device = MockDevice()
    assert _cmd_result(device, V1Command.HOME, b"\x00") == V1ResultCode.ERR_ARGUMENT
    assert _cmd_result(device, V1Command.HOME, b"\x40") == V1ResultCode.ERR_RANGE
    assert _cmd_result(device, V1Command.HOME, b"\x02") == V1ResultCode.ERR_NOT_CONFIGURED
    assert _cmd_result(device, V1Command.HOME, b"\x20") == V1ResultCode.ERR_NOT_CONFIGURED
    assert _cmd_result(device, V1Command.HOME, b"\x3f") == V1ResultCode.ERR_NOT_CONFIGURED


def test_mock__home_failure_latches_homing_fault() -> None:
    device = MockDevice(settings=MockDeviceSettings(home_fails=True))
    assert _cmd_result(device, V1Command.HOME, bytes((PROFILE_HOME_MASK,))) == V1ResultCode.OK
    snapshot = _snapshot(device)
    assert snapshot.run_state_raw == 5
    assert snapshot.fault_flags_raw == V1FaultFlag.HOMING
    assert not device.motion_authorized
    assert _cmd_result(device, V1Command.CLEAR_FAULT, b"") == V1ResultCode.ERR_STATE


def test_mock__estop_latches_reset_required() -> None:
    device = MockDevice()
    device.trigger_estop()
    snapshot = _snapshot(device)
    assert snapshot.run_state_raw == 5
    assert snapshot.fault_flags_raw == V1FaultFlag.ESTOP
    assert snapshot.enabled_mask == 0
    assert not device.motion_authorized
    assert _cmd_result(device, V1Command.ENABLE, b"\x1d") == V1ResultCode.ERR_NOT_READY
    assert _cmd_result(device, V1Command.CLEAR_FAULT, b"") == V1ResultCode.ERR_STATE
    assert snapshot.fault_flags_raw == V1FaultFlag.ESTOP

    device.simulate_reset()
    snapshot = _snapshot(device)
    assert snapshot.run_state_raw == 1
    assert snapshot.fault_flags_raw == 0
    assert device.motion_authorized


def test_mock__clear_fault_clears_only_clearable_bits() -> None:
    device = MockDevice()
    device.fault_flags = V1FaultFlag.TARGET_RANGE | V1FaultFlag.HOST_TX
    device.run_state = 5
    device._motion_authorized = False
    assert _cmd_result(device, V1Command.CLEAR_FAULT, b"") == V1ResultCode.OK
    snapshot = _snapshot(device)
    assert snapshot.run_state_raw == 1
    assert snapshot.fault_flags_raw == 0
    assert device.motion_authorized


def test_mock__unavailable_axes_reject_nonzero_targets() -> None:
    device = MockDevice()
    codec = V1CommandCodec()
    for axis in (1, 5):
        joints = [0] * 6
        joints[axis] = 10_000
        result = _result_raw(
            device, codec.encode_joint_target(JointTarget(cast(JointVector, tuple(joints)), 100, 0))
        )
        assert result == V1ResultCode.ERR_RANGE
    assert _snapshot(device).target_joint_urad == (0, 0, 0, 0, 0, 0)


def test_mock__auto_home_after_link_silence() -> None:
    device = MockDevice()
    snapshot = _snapshot(device)
    assert snapshot.homed_mask == 0

    device.advance_time_ms(AUTO_HOME_IDLE_MS_DEFAULT)
    snapshot = _snapshot(device)
    assert snapshot.run_state_raw == 2

    for _ in range(4):
        _snapshot(device)
    snapshot = _snapshot(device)
    assert snapshot.homed_mask == PROFILE_HOME_MASK
    assert snapshot.run_state_raw == 1


def test_mock__auto_home_timer_resets_on_any_frame() -> None:
    device = MockDevice()
    _snapshot(device)
    for _ in range(100):
        device.advance_time_ms(AUTO_HOME_IDLE_MS_DEFAULT - 200)
        assert _snapshot(device).run_state_raw == 1


def test_mock__estop_latch_survives_reconnect() -> None:
    transport = MockTransport()
    transport.open()
    transport.device.trigger_estop()
    transport.close()
    transport.open()
    assert transport.device.estop_latched
    assert not transport.device.motion_authorized
    assert transport.device.fault_flags == V1FaultFlag.ESTOP


def test_mock__teach_gates_motion_authorization() -> None:
    device = MockDevice()
    assert _cmd_result(device, V1Command.TEACH_START, b"\x1d") == V1ResultCode.OK
    snapshot = _snapshot(device)
    assert snapshot.run_state_raw == 3
    assert not device.motion_authorized
    target = JointTarget((10_000, 0, 0, 0, 0, 0), 100, 0)
    assert (
        _result_raw(device, V1CommandCodec().encode_joint_target(target))
        == V1ResultCode.ERR_NOT_READY
    )
    assert _cmd_result(device, V1Command.TEACH_STOP, b"") == V1ResultCode.OK
    snapshot = _snapshot(device)
    assert snapshot.run_state_raw == 1
    assert device.motion_authorized


def test_mock__unknown_command_still_returns_not_implemented() -> None:
    response = MockDevice().receive(FrameCodec().encode(0x7F))[0]
    frame = FrameCodec().decode_complete(response)
    assert V1CommandCodec().decode_result(frame).raw_value == V1ResultCode.ERR_NOT_IMPLEMENTED
