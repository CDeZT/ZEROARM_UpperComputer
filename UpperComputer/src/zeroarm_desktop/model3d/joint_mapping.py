"""Central MCU joint-unit to URDF model-coordinate mapping."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from zeroarm_desktop.domain.models import JointVector


@dataclass(frozen=True, slots=True)
class JointMappingEntry:
    robot_index: int
    model_joint: str
    sign: int
    offset_rad: float
    wrap: bool
    robot_min_urad: int
    robot_max_urad: int
    model_min_rad: float | None
    model_max_rad: float | None
    hardware_verified: bool


class JointModelMapping:
    """Map current MCU public joint coordinates into URDF joint coordinates."""

    schema_version = 1

    def __init__(self, entries: tuple[JointMappingEntry, ...] | None = None) -> None:
        self.entries = entries or DEFAULT_JOINT_MAPPING
        if len(self.entries) != 6 or {entry.robot_index for entry in self.entries} != set(range(6)):
            raise ValueError("joint mapping must define each of six robot axes exactly once")
        if len({entry.model_joint for entry in self.entries}) != 6:
            raise ValueError("joint mapping model names must be unique")
        if any(entry.sign not in {-1, 1} for entry in self.entries):
            raise ValueError("joint mapping signs must be -1 or 1")

    def robot_to_model_rad(self, robot_urad: JointVector) -> tuple[float, ...]:
        values = []
        for entry in self.entries:
            robot_rad = robot_urad[entry.robot_index] / 1_000_000
            model_rad = entry.sign * robot_rad + entry.offset_rad
            values.append(_wrap_signed(model_rad) if entry.wrap else model_rad)
        return tuple(values)

    def model_to_robot_urad(self, model_rad: Sequence[float]) -> JointVector:
        if len(model_rad) != 6 or any(not math.isfinite(value) for value in model_rad):
            raise ValueError("model joint vector must contain six finite values")
        robot = [0] * 6
        for entry, value in zip(self.entries, model_rad, strict=True):
            robot_rad = (value - entry.offset_rad) / entry.sign
            if entry.wrap:
                robot_rad %= math.tau
            robot[entry.robot_index] = round(robot_rad * 1_000_000)
        return tuple(robot)  # type: ignore[return-value]

    def validate_robot_limits(self, robot_urad: JointVector) -> tuple[int, ...]:
        return tuple(
            entry.robot_index
            for entry in self.entries
            if not entry.robot_min_urad <= robot_urad[entry.robot_index] <= entry.robot_max_urad
        )


def _wrap_signed(value: float) -> float:
    wrapped = (value + math.pi) % math.tau - math.pi
    return math.pi if math.isclose(wrapped, -math.pi) and value > 0 else wrapped


_DEG_URAD = 17_453
DEFAULT_JOINT_MAPPING = (
    JointMappingEntry(0, "joint1", 1, 0.0, True, 0, 360 * _DEG_URAD, None, None, False),
    JointMappingEntry(
        1,
        "joint2",
        1,
        -math.pi,
        False,
        90 * _DEG_URAD,
        180 * _DEG_URAD,
        -math.pi / 2,
        math.pi / 2,
        False,
    ),
    JointMappingEntry(
        2,
        "joint3",
        1,
        math.pi / 2,
        False,
        0,
        135 * _DEG_URAD,
        0.0,
        math.pi,
        False,
    ),
    JointMappingEntry(
        3,
        "joint4",
        1,
        0.0,
        False,
        -90 * _DEG_URAD,
        90 * _DEG_URAD,
        None,
        None,
        False,
    ),
    JointMappingEntry(
        4,
        "joint5",
        1,
        -math.pi / 2,
        False,
        -35 * _DEG_URAD,
        135 * _DEG_URAD,
        -math.pi / 2,
        0.0,
        False,
    ),
    JointMappingEntry(5, "joint6", 1, 0.0, True, 0, 360 * _DEG_URAD, None, None, False),
)
