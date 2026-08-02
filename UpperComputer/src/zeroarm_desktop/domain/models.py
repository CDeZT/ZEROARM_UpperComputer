"""Core immutable data transferred between protocol, application, and GUI."""

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum

type JointVector = tuple[int, int, int, int, int, int]


class RobotRunState(IntEnum):
    """Protocol-independent robot lifecycle states exposed to the domain."""

    BOOT = 0
    READY = 1
    HOMING = 2
    TEACHING = 3
    RUNNING = 4
    FAULT = 5


class RobotFaultFlag(IntEnum):
    """Known robot fault bits used by readiness and safety policies."""

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


@dataclass(frozen=True, slots=True)
class FirmwareIdentity:
    hello_text: str
    protocol_generation: int
    schema_version: int | None
    build_id: str | None
    capabilities: int | None


@dataclass(frozen=True, slots=True)
class JointTarget:
    joint_urad: JointVector
    duration_ms: int
    gripper_u16: int


@dataclass(frozen=True, slots=True)
class RobotSnapshot:
    generation: int
    received_monotonic_ns: int
    received_wall_utc: datetime
    device_time_ms: int | None
    sample_sequence: int | None
    run_state_raw: int
    target_joint_urad: JointVector
    actual_joint_urad: JointVector
    enabled_mask: int | None
    homed_mask: int | None
    moving_mask: int | None
    online_mask: int | None
    teach_mask: int | None
    fault_flags_raw: int
    velocity_urad_s: JointVector | None
    current_ma: JointVector | None
