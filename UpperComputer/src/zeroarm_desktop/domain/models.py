"""Core immutable data transferred between protocol, application, and GUI."""

from dataclasses import dataclass
from datetime import datetime

type JointVector = tuple[int, int, int, int, int, int]


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
