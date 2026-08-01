"""Semantic command codec for the current MCU V1 protocol."""

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum

from zeroarm_desktop.domain.errors import ProtocolDecodeError
from zeroarm_desktop.domain.models import FirmwareIdentity, JointTarget, JointVector, RobotSnapshot
from zeroarm_desktop.protocol.frame_codec import FrameCodec, ProtocolFrame


class V1Command(IntEnum):
    HELLO = 0x00
    GET_STATE = 0x01
    ENABLE = 0x02
    DISABLE = 0x03
    STOP = 0x04
    SET_JOINT_TARGET = 0x05
    HOME = 0x06
    TEACH_START = 0x07
    TEACH_STOP = 0x08
    CLEAR_FAULT = 0x09


class V1BenchCommand(IntEnum):
    """Motor bench commands compiled under CONFIG_MOTOR_BENCH_TEST (MCU messages.c)."""

    QUERY = 0x20
    ENABLE = 0x21
    DISABLE = 0x22
    STOP = 0x23
    MOVE_REL = 0x24
    SET_ZERO = 0x25
    GET_PROTECTION = 0x26
    SET_PROTECTION = 0x27


class V1GripperCommand(IntEnum):
    """ST-3215 STS gripper bridge commands (MCU messages.c)."""

    PING = 0x30
    READ = 0x31
    WRITE = 0x32
    MOVE = 0x33
    TORQUE = 0x34


class V1RunState(IntEnum):
    BOOT = 0
    READY = 1
    HOMING = 2
    TEACHING = 3
    RUNNING = 4
    FAULT = 5


class V1ResultCode(IntEnum):
    OK = 0
    ERR_ARGUMENT = 1
    ERR_STATE = 2
    ERR_RANGE = 3
    ERR_NOT_READY = 4
    ERR_NOT_CONFIGURED = 5
    ERR_QUEUE_FULL = 6
    ERR_IO = 7
    ERR_NOT_IMPLEMENTED = 8


class V1FaultFlag(IntEnum):
    """Fault bits from MCU Robot/Inc/robot_state.h."""

    TARGET_RANGE = 1 << 0
    HOST_TX = 1 << 1
    INTERNAL_STATE = 1 << 2
    MOTOR_TX = 1 << 3
    MOTOR_FEEDBACK = 1 << 4
    UART_RX_OVERFLOW = 1 << 5
    CAN_RX_DROP = 1 << 6
    SERVICE_PARTIAL = 1 << 7
    FEEDBACK_STALE = 1 << 8
    STARTUP = 1 << 9
    HOMING = 1 << 10
    ESTOP = 1 << 11


RESET_REQUIRED_FAULTS = V1FaultFlag.STARTUP | V1FaultFlag.HOMING | V1FaultFlag.ESTOP
"""STARTUP/HOMING/ESTOP cannot be cleared by CMD_CLEAR_FAULT; an MCU reset is required."""

_ALL_KNOWN_FAULTS = 0xFFF


@dataclass(frozen=True, slots=True)
class V1FaultDecoding:
    flags_raw: int
    known: tuple[V1FaultFlag, ...]
    unknown_bits: int
    reset_required: bool


def decode_fault_flags(raw: int) -> V1FaultDecoding:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise TypeError("fault flags must be an integer")
    if not 0 <= raw <= 0xFFFFFFFF:
        raise ValueError("fault flags must fit in uint32")
    known = tuple(flag for flag in V1FaultFlag if raw & flag.value)
    unknown_bits = raw & ~_ALL_KNOWN_FAULTS
    return V1FaultDecoding(
        flags_raw=raw,
        known=known,
        unknown_bits=unknown_bits,
        reset_required=(raw & RESET_REQUIRED_FAULTS) != 0,
    )


class V1GripperResultCode(IntEnum):
    """feetech_sts_result_t from MCU Gripper/Inc/feetech_sts.h."""

    OK = 0
    ERR_ARGUMENT = 1
    ERR_NOT_INITIALIZED = 2
    ERR_TX = 3
    ERR_RX_TIMEOUT = 4
    ERR_PACKET = 5
    ERR_SERVO = 6


@dataclass(frozen=True, slots=True)
class WireResult:
    command: int
    raw_value: int
    known: V1ResultCode | None

    @property
    def is_ok(self) -> bool:
        return self.known is V1ResultCode.OK


@dataclass(frozen=True, slots=True)
class BenchState:
    """Decoded 40-byte little-endian motor_bench_state_t (MCU motor_types.h)."""

    motor_id: int
    online: bool
    position_urad: int
    velocity_tenths_rpm: int
    current_ma: int
    status: int
    fault_flags: int
    can_tx_errors: int
    feedback_faults: int
    position_sample_count: int
    target_submit_count: int
    target_send_count: int


@dataclass(frozen=True, slots=True)
class MotorProtection:
    """Decoded 7-byte bench protection response."""

    motor_id: int
    temperature_c: int
    current_ma: int
    detection_time_ms: int


@dataclass(frozen=True, slots=True)
class GripperResponse:
    command: int
    raw_result: int
    known_result: V1GripperResultCode | None
    id: int
    servo_error: int
    data: bytes

    @property
    def is_ok(self) -> bool:
        return self.known_result is V1GripperResultCode.OK


_EMPTY_COMMANDS = {
    V1Command.HELLO,
    V1Command.GET_STATE,
    V1Command.STOP,
    V1Command.TEACH_STOP,
    V1Command.CLEAR_FAULT,
}
_MASK_COMMANDS = {
    V1Command.ENABLE,
    V1Command.DISABLE,
    V1Command.HOME,
    V1Command.TEACH_START,
}

_BENCH_ID_COMMANDS = {
    V1BenchCommand.QUERY,
    V1BenchCommand.ENABLE,
    V1BenchCommand.DISABLE,
    V1BenchCommand.STOP,
    V1BenchCommand.SET_ZERO,
    V1BenchCommand.GET_PROTECTION,
}

MOTOR_BENCH_MAX_MOTOR_ID = 6
MOTOR_BENCH_MAX_DEGREES_TENTHS = 5_400_000
MOTOR_BENCH_MAX_VELOCITY_TENTHS = 15_000
MOTOR_BENCH_MAX_ACCEL_RPM_S = 2_000
MOTOR_PROTECTION_MIN_TEMP_C = 40
MOTOR_PROTECTION_MAX_TEMP_C = 150
MOTOR_PROTECTION_MIN_CURRENT_MA = 500
MOTOR_PROTECTION_MAX_CURRENT_MA = 10_000
MOTOR_PROTECTION_MIN_TIME_MS = 50
MOTOR_PROTECTION_MAX_TIME_MS = 5_000
FEETECH_STS_MAX_DATA_SIZE = 32
GRIPPER_MAX_POSITION = 4095


class V1CommandCodec:
    """Encode V1 requests and decode validated V1 response frames."""

    def __init__(self, frame_codec: FrameCodec | None = None) -> None:
        self._frames = frame_codec or FrameCodec()

    def hello_request(self) -> bytes:
        return self._frames.encode(V1Command.HELLO)

    def get_state_request(self) -> bytes:
        return self._frames.encode(V1Command.GET_STATE)

    def decode_hello(self, frame: ProtocolFrame) -> FirmwareIdentity:
        self._expect_command(frame, V1Command.HELLO)
        if not frame.payload:
            raise ProtocolDecodeError("HELLO payload must not be empty")
        try:
            hello_text = frame.payload.decode("ascii")
        except UnicodeDecodeError as error:
            raise ProtocolDecodeError("HELLO payload must be ASCII") from error
        if hello_text != "ZEROARM/1.0":
            raise ProtocolDecodeError(f"unsupported V1 identity: {hello_text!r}")
        return FirmwareIdentity(hello_text, 1, None, None, None)

    def decode_state(
        self,
        frame: ProtocolFrame,
        *,
        generation: int,
        received_wall_utc: datetime,
    ) -> RobotSnapshot:
        self._expect_command(frame, V1Command.GET_STATE)
        if len(frame.payload) != 60:
            raise ProtocolDecodeError("V1 state payload must be exactly 60 bytes")
        if generation < 0:
            raise ValueError("generation must not be negative")
        if received_wall_utc.tzinfo is None:
            raise ValueError("received_wall_utc must be timezone-aware")

        payload = frame.payload
        target = self._read_joint_vector(payload, 4)
        actual = self._read_joint_vector(payload, 28)
        return RobotSnapshot(
            generation=generation,
            received_monotonic_ns=frame.received_monotonic_ns,
            received_wall_utc=received_wall_utc,
            device_time_ms=None,
            sample_sequence=None,
            run_state_raw=int.from_bytes(payload[0:4], "little", signed=True),
            target_joint_urad=target,
            actual_joint_urad=actual,
            enabled_mask=payload[52],
            homed_mask=payload[53],
            moving_mask=payload[54],
            online_mask=None,
            teach_mask=None,
            fault_flags_raw=int.from_bytes(payload[56:60], "little", signed=False),
            velocity_urad_s=None,
            current_ma=None,
        )

    def encode_joint_target(self, target: JointTarget) -> bytes:
        if len(target.joint_urad) != 6:
            raise ValueError("joint target must contain exactly six axes")
        payload = bytearray()
        for value in target.joint_urad:
            self._require_integer_range(value, -(2**31), 2**31 - 1, "joint position")
            payload.extend(value.to_bytes(4, "big", signed=True))
        self._require_integer_range(target.duration_ms, 0, 0xFFFF, "duration_ms")
        self._require_integer_range(target.gripper_u16, 0, 0xFFFF, "gripper_u16")
        payload.extend(target.duration_ms.to_bytes(2, "big"))
        payload.extend(target.gripper_u16.to_bytes(2, "big"))
        return self._frames.encode(V1Command.SET_JOINT_TARGET, bytes(payload))

    def encode_joint_mask(self, command: V1Command, mask: int) -> bytes:
        if command not in _MASK_COMMANDS:
            raise ValueError("command does not accept a joint mask")
        self._require_integer_range(mask, 1, 0x3F, "joint mask")
        return self._frames.encode(command, bytes((mask,)))

    def encode_empty_command(self, command: V1Command) -> bytes:
        if command not in _EMPTY_COMMANDS:
            raise ValueError("command requires a payload")
        return self._frames.encode(command)

    def decode_result(self, frame: ProtocolFrame) -> WireResult:
        if len(frame.payload) != 1:
            raise ProtocolDecodeError("V1 result payload must be exactly one byte")
        raw_value = frame.payload[0]
        try:
            known = V1ResultCode(raw_value)
        except ValueError:
            known = None
        return WireResult(command=frame.command, raw_value=raw_value, known=known)

    def encode_bench_id_command(self, command: V1BenchCommand, motor_id: int) -> bytes:
        """Encode a single-motor bench request with a one-byte motor id payload."""
        if command not in _BENCH_ID_COMMANDS:
            raise ValueError("command does not accept a motor id")
        self._require_integer_range(motor_id, 1, MOTOR_BENCH_MAX_MOTOR_ID, "motor id")
        return self._frames.encode(command, bytes((motor_id,)))

    def encode_bench_move_relative(
        self,
        motor_id: int,
        direction: int,
        degrees_tenths: int,
        velocity_tenths: int,
        acceleration_rpm_s: int,
    ) -> bytes:
        """Encode CMD_BENCH_MOVE_REL (10-byte payload, big-endian numeric fields)."""
        self._require_integer_range(motor_id, 1, MOTOR_BENCH_MAX_MOTOR_ID, "motor id")
        self._require_integer_range(direction, 0, 1, "direction")
        self._require_integer_range(
            degrees_tenths, 1, MOTOR_BENCH_MAX_DEGREES_TENTHS, "degrees_tenths"
        )
        self._require_integer_range(
            velocity_tenths, 1, MOTOR_BENCH_MAX_VELOCITY_TENTHS, "velocity_tenths"
        )
        self._require_integer_range(
            acceleration_rpm_s, 1, MOTOR_BENCH_MAX_ACCEL_RPM_S, "acceleration_rpm_s"
        )
        payload = (
            bytes((motor_id, direction))
            + degrees_tenths.to_bytes(4, "big")
            + velocity_tenths.to_bytes(2, "big")
            + acceleration_rpm_s.to_bytes(2, "big")
        )
        return self._frames.encode(V1BenchCommand.MOVE_REL, payload)

    def encode_bench_set_protection(
        self,
        motor_id: int,
        save: bool,
        temperature_c: int,
        current_ma: int,
        detection_time_ms: int,
    ) -> bytes:
        """Encode CMD_BENCH_SET_PROTECTION (8-byte payload, big-endian numeric fields)."""
        self._require_integer_range(motor_id, 1, MOTOR_BENCH_MAX_MOTOR_ID, "motor id")
        if not isinstance(save, bool):
            raise TypeError("save must be a bool")
        self._require_integer_range(
            temperature_c, MOTOR_PROTECTION_MIN_TEMP_C, MOTOR_PROTECTION_MAX_TEMP_C, "temperature_c"
        )
        self._require_integer_range(
            current_ma,
            MOTOR_PROTECTION_MIN_CURRENT_MA,
            MOTOR_PROTECTION_MAX_CURRENT_MA,
            "current_ma",
        )
        self._require_integer_range(
            detection_time_ms,
            MOTOR_PROTECTION_MIN_TIME_MS,
            MOTOR_PROTECTION_MAX_TIME_MS,
            "detection_time_ms",
        )
        payload = (
            bytes((motor_id, 1 if save else 0))
            + temperature_c.to_bytes(2, "big")
            + current_ma.to_bytes(2, "big")
            + detection_time_ms.to_bytes(2, "big")
        )
        return self._frames.encode(V1BenchCommand.SET_PROTECTION, payload)

    def decode_bench_state(self, frame: ProtocolFrame) -> BenchState:
        self._expect_command(frame, V1BenchCommand.QUERY)
        if len(frame.payload) != 40:
            raise ProtocolDecodeError("bench state payload must be exactly 40 bytes")
        payload = frame.payload
        return BenchState(
            motor_id=payload[0],
            online=payload[1] != 0,
            position_urad=int.from_bytes(payload[4:8], "little", signed=True),
            velocity_tenths_rpm=int.from_bytes(payload[8:12], "little", signed=True),
            current_ma=int.from_bytes(payload[12:14], "little"),
            status=int.from_bytes(payload[14:16], "little"),
            fault_flags=int.from_bytes(payload[16:20], "little"),
            can_tx_errors=int.from_bytes(payload[20:24], "little"),
            feedback_faults=int.from_bytes(payload[24:28], "little"),
            position_sample_count=int.from_bytes(payload[28:32], "little"),
            target_submit_count=int.from_bytes(payload[32:36], "little"),
            target_send_count=int.from_bytes(payload[36:40], "little"),
        )

    def decode_bench_protection(self, frame: ProtocolFrame) -> MotorProtection:
        self._expect_command(frame, V1BenchCommand.GET_PROTECTION)
        if len(frame.payload) != 7:
            raise ProtocolDecodeError("bench protection payload must be exactly 7 bytes")
        payload = frame.payload
        return MotorProtection(
            motor_id=payload[0],
            temperature_c=int.from_bytes(payload[1:3], "big"),
            current_ma=int.from_bytes(payload[3:5], "big"),
            detection_time_ms=int.from_bytes(payload[5:7], "big"),
        )

    def encode_gripper_ping(self, servo_id: int) -> bytes:
        self._require_integer_range(servo_id, 0, 0xFD, "servo id")
        return self._frames.encode(V1GripperCommand.PING, bytes((servo_id,)))

    def encode_gripper_read(self, servo_id: int, address: int, length: int) -> bytes:
        self._require_integer_range(servo_id, 0, 0xFD, "servo id")
        self._require_integer_range(address, 0, 0xFF, "register address")
        self._require_integer_range(length, 1, FEETECH_STS_MAX_DATA_SIZE, "read length")
        payload = bytes((servo_id, address, length))
        return self._frames.encode(V1GripperCommand.READ, payload)

    def encode_gripper_write(self, servo_id: int, address: int, data: bytes) -> bytes:
        self._require_integer_range(servo_id, 0, 0xFD, "servo id")
        self._require_integer_range(address, 0, 0xFF, "register address")
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        if not 1 <= len(data) < FEETECH_STS_MAX_DATA_SIZE:
            raise ValueError(f"data length must be between 1 and {FEETECH_STS_MAX_DATA_SIZE - 1}")
        return self._frames.encode(V1GripperCommand.WRITE, bytes((servo_id, address)) + data)

    def encode_gripper_move(
        self, servo_id: int, position: int, speed: int, acceleration: int
    ) -> bytes:
        self._require_integer_range(servo_id, 0, 0xFD, "servo id")
        self._require_integer_range(position, 0, GRIPPER_MAX_POSITION, "position")
        self._require_integer_range(speed, 0, 0xFFFF, "speed")
        self._require_integer_range(acceleration, 0, 0xFF, "acceleration")
        payload = (
            bytes((servo_id,))
            + position.to_bytes(2, "big")
            + speed.to_bytes(2, "big")
            + bytes((acceleration,))
        )
        return self._frames.encode(V1GripperCommand.MOVE, payload)

    def encode_gripper_torque(self, servo_id: int, mode: int) -> bytes:
        self._require_integer_range(servo_id, 0, 0xFD, "servo id")
        self._require_integer_range(mode, 0, 2, "torque mode")
        return self._frames.encode(V1GripperCommand.TORQUE, bytes((servo_id, mode)))

    def decode_gripper_response(self, frame: ProtocolFrame) -> GripperResponse:
        try:
            command = V1GripperCommand(frame.command)
        except ValueError as error:
            raise ProtocolDecodeError(
                f"expected a gripper command, received 0x{frame.command:02X}"
            ) from error
        if len(frame.payload) < 3:
            raise ProtocolDecodeError("gripper response payload must be at least 3 bytes")
        raw_result = frame.payload[0]
        try:
            known_result = V1GripperResultCode(raw_result)
        except ValueError:
            known_result = None
        return GripperResponse(
            command=command,
            raw_result=raw_result,
            known_result=known_result,
            id=frame.payload[1],
            servo_error=frame.payload[2],
            data=frame.payload[3:],
        )

    @staticmethod
    def _expect_command(frame: ProtocolFrame, command: V1Command | V1BenchCommand) -> None:
        if frame.command != command:
            raise ProtocolDecodeError(
                f"expected command 0x{command:02X}, received 0x{frame.command:02X}"
            )

    @staticmethod
    def _read_joint_vector(payload: bytes, offset: int) -> JointVector:
        values = tuple(
            int.from_bytes(
                payload[offset + index * 4 : offset + (index + 1) * 4], "little", signed=True
            )
            for index in range(6)
        )
        return values  # type: ignore[return-value]

    @staticmethod
    def _require_integer_range(value: int, minimum: int, maximum: int, name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer")
        if not minimum <= value <= maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}")
