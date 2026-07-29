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


@dataclass(frozen=True, slots=True)
class WireResult:
    command: int
    raw_value: int
    known: V1ResultCode | None

    @property
    def is_ok(self) -> bool:
        return self.known is V1ResultCode.OK


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

    @staticmethod
    def _expect_command(frame: ProtocolFrame, command: V1Command) -> None:
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
