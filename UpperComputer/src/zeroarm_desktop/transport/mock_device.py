"""Deterministic byte-level V1 mock device with current MCU semantics.

Simulates the zero_arm_mcu main @ 48c11d8 behavior relevant to the host:
startup limit gate (0x1D), ordered HOME (J5->J4->J3->J1), E-stop latch with
reset-required faults, 20 s link-silence auto-home, unavailable J2/J6 axes,
and motion authorization gating. Time is virtual (`advance_time_ms`) so all
behavior is deterministic in tests.
"""

from dataclasses import dataclass

from zeroarm_desktop.protocol.frame_codec import FrameCodec, ProtocolFrame
from zeroarm_desktop.protocol.stream_parser import StreamParser
from zeroarm_desktop.protocol.v1_codec import V1Command, V1FaultFlag, V1ResultCode

MOTION_STEP_URAD = 20_000
AUTO_HOME_IDLE_MS_DEFAULT = 20_000
PROFILE_HOME_MASK = 0x1D
ALL_JOINTS_MASK = 0x3F
RESET_REQUIRED_FAULT_BITS = V1FaultFlag.STARTUP | V1FaultFlag.HOMING | V1FaultFlag.ESTOP


@dataclass(frozen=True, slots=True)
class MockFaults:
    drop_response_numbers: frozenset[int] = frozenset()
    corrupt_crc_response_numbers: frozenset[int] = frozenset()
    duplicate_response_numbers: frozenset[int] = frozenset()
    truncate_response_numbers: frozenset[int] = frozenset()
    noise_prefix: bytes = b""


@dataclass(frozen=True, slots=True)
class MockDeviceSettings:
    startup_limits_active: bool = True
    auto_home_idle_ms: int = AUTO_HOME_IDLE_MS_DEFAULT
    home_fails: bool = False


class MockDevice:
    """Consume host V1 bytes and produce deterministic V1 response bytes."""

    def __init__(
        self,
        *,
        faults: MockFaults | None = None,
        settings: MockDeviceSettings | None = None,
    ) -> None:
        self._parser = StreamParser()
        self._frames = FrameCodec()
        self._faults = faults or MockFaults()
        self._settings = settings or MockDeviceSettings()
        self._response_number = 0
        self._now_ms = 0
        self._last_activity_ms = 0
        self._homing_sequence: list[int] = []
        self._motion_authorized = False
        self.target_joint_urad = (0, 0, 0, 0, 0, 0)
        self.actual_joint_urad = (0, 0, 0, 0, 0, 0)
        self.run_state = 5
        self.enabled_mask = 0
        self.homed_mask = 0
        self.moving_mask = 0
        self.fault_flags: int = 0
        self.estop_latched = False
        self._reset_machine()

    @property
    def now_ms(self) -> int:
        return self._now_ms

    @property
    def motion_authorized(self) -> bool:
        return self._motion_authorized

    def advance_time_ms(self, delta_ms: int) -> None:
        if not isinstance(delta_ms, int) or delta_ms < 0:
            raise ValueError("time delta must be a non-negative integer")
        self._now_ms += delta_ms
        self._maybe_start_auto_home()

    def trigger_estop(self) -> None:
        """Simulate PD15 low-level E-stop: stop, disable, latch, reset-required fault."""
        self._homing_sequence.clear()
        self.moving_mask = 0
        self.target_joint_urad = self.actual_joint_urad
        self.enabled_mask = 0
        self._motion_authorized = False
        self.estop_latched = True
        self.fault_flags |= V1FaultFlag.ESTOP
        self.run_state = 5

    def simulate_startup_limits_missing(self) -> None:
        """Simulate the required startup limit gate not active (FAULT_STARTUP)."""
        self._homing_sequence.clear()
        self.moving_mask = 0
        self.enabled_mask = 0
        self.target_joint_urad = self.actual_joint_urad
        self._motion_authorized = False
        self.fault_flags |= V1FaultFlag.STARTUP
        self.run_state = 5

    def simulate_reset(self) -> None:
        """Simulate an MCU power/reset cycle (the only way out of an E-stop latch)."""
        self.estop_latched = False
        self._reset_machine()

    def _reset_machine(self) -> None:
        self.target_joint_urad = (0, 0, 0, 0, 0, 0)
        self.actual_joint_urad = (0, 0, 0, 0, 0, 0)
        self.enabled_mask = 0
        self.homed_mask = 0
        self.moving_mask = 0
        self._homing_sequence.clear()
        self._motion_authorized = False
        if self._settings.startup_limits_active:
            self.run_state = 1
            self.fault_flags = 0
            self._motion_authorized = True
        else:
            self.run_state = 5
            self.fault_flags = V1FaultFlag.STARTUP

    def receive(self, data: bytes) -> tuple[bytes, ...]:
        responses: list[bytes] = []
        for frame in self._parser.feed(data, received_monotonic_ns=0):
            self._last_activity_ms = self._now_ms
            response = self._handle_frame(frame)
            if response is not None:
                responses.extend(self._apply_faults(response))
        return tuple(responses)

    def _handle_frame(self, frame: ProtocolFrame) -> bytes | None:
        if frame.command == V1Command.HELLO and not frame.payload:
            return self._frames.encode(V1Command.HELLO, b"ZEROARM/1.0")
        if frame.command == V1Command.GET_STATE and not frame.payload:
            self._maybe_start_auto_home()
            self._advance_homing()
            self._advance_motion()
            return self._frames.encode(V1Command.GET_STATE, self._state_payload())
        if frame.command == V1Command.SET_JOINT_TARGET and len(frame.payload) == 28:
            return self._handle_joint_target(frame)
        if frame.command == V1Command.ENABLE and len(frame.payload) == 1:
            return self._handle_enable(frame.payload[0])
        if frame.command == V1Command.DISABLE and len(frame.payload) == 1:
            if frame.payload[0] == 0:
                return self._result(frame.command, V1ResultCode.ERR_ARGUMENT)
            if frame.payload[0] & ~ALL_JOINTS_MASK:
                return self._result(frame.command, V1ResultCode.ERR_RANGE)
            self.enabled_mask &= ~frame.payload[0]
            return self._result(frame.command, V1ResultCode.OK)
        if frame.command == V1Command.STOP and not frame.payload:
            self.moving_mask = 0
            self.target_joint_urad = self.actual_joint_urad
            return self._result(frame.command, V1ResultCode.OK)
        if frame.command == V1Command.HOME and len(frame.payload) == 1:
            return self._handle_home(frame.payload[0])
        if frame.command == V1Command.TEACH_START and len(frame.payload) == 1:
            if self.run_state != 1 or self.fault_flags != 0:
                return self._result(frame.command, V1ResultCode.ERR_NOT_READY)
            self.run_state = 3
            self._motion_authorized = False
            self.enabled_mask &= ~frame.payload[0]
            return self._result(frame.command, V1ResultCode.OK)
        if frame.command == V1Command.TEACH_STOP and not frame.payload:
            if self.run_state != 3:
                return self._result(frame.command, V1ResultCode.ERR_STATE)
            self.run_state = 1
            self._motion_authorized = True
            self.target_joint_urad = self.actual_joint_urad
            return self._result(frame.command, V1ResultCode.OK)
        if frame.command == V1Command.CLEAR_FAULT and not frame.payload:
            return self._handle_clear_fault()
        return self._result(frame.command, V1ResultCode.ERR_NOT_IMPLEMENTED)

    def _handle_joint_target(self, frame: ProtocolFrame) -> bytes:
        if self.estop_latched or not self._motion_authorized or self.fault_flags != 0:
            return self._result(frame.command, V1ResultCode.ERR_NOT_READY)
        if self.run_state != 1:
            return self._result(frame.command, V1ResultCode.ERR_NOT_READY)
        target = tuple(
            int.from_bytes(frame.payload[index : index + 4], "big", signed=True)
            for index in range(0, 24, 4)
        )
        if target[1] != 0 or target[5] != 0:
            return self._result(frame.command, V1ResultCode.ERR_RANGE)
        duration_ms = int.from_bytes(frame.payload[24:26], "big")
        if not 1 <= duration_ms <= 0xFFFF:
            return self._result(frame.command, V1ResultCode.ERR_ARGUMENT)
        self.target_joint_urad = target  # type: ignore[assignment]
        self.moving_mask = ALL_JOINTS_MASK
        return self._result(frame.command, V1ResultCode.OK)

    def _handle_enable(self, mask: int) -> bytes:
        if mask == 0:
            return self._result(V1Command.ENABLE, V1ResultCode.ERR_ARGUMENT)
        if mask & ~ALL_JOINTS_MASK:
            return self._result(V1Command.ENABLE, V1ResultCode.ERR_RANGE)
        if self.estop_latched or not self._motion_authorized or self.fault_flags != 0:
            return self._result(V1Command.ENABLE, V1ResultCode.ERR_NOT_READY)
        if self.run_state != 1:
            return self._result(V1Command.ENABLE, V1ResultCode.ERR_NOT_READY)
        self.enabled_mask |= mask
        return self._result(V1Command.ENABLE, V1ResultCode.OK)

    def _handle_home(self, mask: int) -> bytes:
        if mask == 0:
            return self._result(V1Command.HOME, V1ResultCode.ERR_ARGUMENT)
        if mask & ~ALL_JOINTS_MASK:
            return self._result(V1Command.HOME, V1ResultCode.ERR_RANGE)
        if mask & ~PROFILE_HOME_MASK:
            return self._result(V1Command.HOME, V1ResultCode.ERR_NOT_CONFIGURED)
        if self.estop_latched or not self._motion_authorized or self.fault_flags != 0:
            return self._result(V1Command.HOME, V1ResultCode.ERR_NOT_READY)
        if self.run_state != 1:
            return self._result(V1Command.HOME, V1ResultCode.ERR_NOT_READY)
        self.run_state = 2
        self._motion_authorized = False
        self.moving_mask = 0
        self.target_joint_urad = self.actual_joint_urad
        self._homing_sequence = [joint for joint in (4, 3, 2, 0) if mask & (1 << joint)]
        return self._result(V1Command.HOME, V1ResultCode.OK)

    def _handle_clear_fault(self) -> bytes:
        clearable = self.fault_flags & ~RESET_REQUIRED_FAULT_BITS
        if self.fault_flags == 0:
            return self._result(V1Command.CLEAR_FAULT, V1ResultCode.OK)
        if clearable == 0 and self.fault_flags & RESET_REQUIRED_FAULT_BITS:
            return self._result(V1Command.CLEAR_FAULT, V1ResultCode.ERR_STATE)
        self.fault_flags = self.fault_flags & RESET_REQUIRED_FAULT_BITS
        if self.fault_flags == 0:
            self.run_state = 1
            self._motion_authorized = self._settings.startup_limits_active
        return self._result(V1Command.CLEAR_FAULT, V1ResultCode.OK)

    def _maybe_start_auto_home(self) -> None:
        idle_ms = self._now_ms - self._last_activity_ms
        if (
            self._settings.auto_home_idle_ms > 0
            and idle_ms >= self._settings.auto_home_idle_ms
            and self.run_state == 1
            and self.fault_flags == 0
            and self._motion_authorized
            and self.moving_mask == 0
            and self.homed_mask != PROFILE_HOME_MASK
            and not self._homing_sequence
        ):
            self._handle_home(PROFILE_HOME_MASK)

    def _advance_homing(self) -> None:
        if not self._homing_sequence:
            return
        if self._settings.home_fails:
            self._homing_sequence.clear()
            self.fault_flags |= V1FaultFlag.HOMING
            self.run_state = 5
            self._motion_authorized = False
            return
        joint = self._homing_sequence.pop(0)
        self.homed_mask |= 1 << joint
        if not self._homing_sequence:
            self.run_state = 1
            self._motion_authorized = True

    def _advance_motion(self) -> None:
        actual = []
        moving = 0
        for index, (current, target) in enumerate(
            zip(self.actual_joint_urad, self.target_joint_urad, strict=True)
        ):
            difference = target - current
            step = max(-MOTION_STEP_URAD, min(MOTION_STEP_URAD, difference))
            value = current + step
            actual.append(value)
            if value != target:
                moving |= 1 << index
        self.actual_joint_urad = tuple(actual)  # type: ignore[assignment]
        self.moving_mask = moving

    def _state_payload(self) -> bytes:
        payload = bytearray(self.run_state.to_bytes(4, "little", signed=True))
        for value in self.target_joint_urad + self.actual_joint_urad:
            payload.extend(value.to_bytes(4, "little", signed=True))
        payload.extend(bytes((self.enabled_mask, self.homed_mask, self.moving_mask, 0)))
        payload.extend(self.fault_flags.to_bytes(4, "little"))
        return bytes(payload)

    def _result(self, command: int, result: V1ResultCode) -> bytes:
        return self._frames.encode(command, bytes((result,)))

    def _apply_faults(self, response: bytes) -> tuple[bytes, ...]:
        self._response_number += 1
        number = self._response_number
        if number in self._faults.drop_response_numbers:
            return ()
        output = self._faults.noise_prefix + response
        if number in self._faults.corrupt_crc_response_numbers:
            corrupted = bytearray(output)
            corrupted[-2] ^= 0x01
            output = bytes(corrupted)
        if number in self._faults.truncate_response_numbers:
            output = output[:-2]
        return (output, output) if number in self._faults.duplicate_response_numbers else (output,)
