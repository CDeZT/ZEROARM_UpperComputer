"""Immutable trajectory schema, validation, and pure processing operations."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace

from zeroarm_desktop.domain.models import JointVector
from zeroarm_desktop.model3d.joint_mapping import JointModelMapping

type JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class TrajectoryPoint:
    time_ns: int
    joint_urad: JointVector
    gripper_u16: int | None = None


@dataclass(frozen=True, slots=True)
class Trajectory:
    schema_version: int
    name: str
    points: tuple[TrajectoryPoint, ...]
    source: str
    metadata: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    point_index: int | None = None
    joint_index: int | None = None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    valid: bool
    issues: tuple[ValidationIssue, ...]
    point_count: int
    duration_ns: int


def validate_trajectory(
    trajectory: Trajectory,
    *,
    max_velocity_urad_s: int = 523_590,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    if trajectory.schema_version != 1:
        issues.append(ValidationIssue("schema_unsupported"))
    mapping = JointModelMapping()
    previous: TrajectoryPoint | None = None
    for point_index, point in enumerate(trajectory.points):
        if point.time_ns < 0 or (previous is not None and point.time_ns <= previous.time_ns):
            issues.append(ValidationIssue("time_not_strictly_increasing", point_index))
        for joint_index in mapping.validate_robot_limits(point.joint_urad):
            issues.append(ValidationIssue("joint_limit", point_index, joint_index))
        if point.gripper_u16 is not None and not 0 <= point.gripper_u16 <= 0xFFFF:
            issues.append(ValidationIssue("gripper_range", point_index))
        if previous is not None and point.time_ns > previous.time_ns:
            duration_s = (point.time_ns - previous.time_ns) / 1_000_000_000
            for joint_index, (current, before) in enumerate(
                zip(point.joint_urad, previous.joint_urad, strict=True)
            ):
                if abs(current - before) / duration_s > max_velocity_urad_s:
                    issues.append(ValidationIssue("velocity_limit", point_index, joint_index))
        previous = point
    duration = trajectory.points[-1].time_ns if trajectory.points else 0
    return ValidationReport(not issues, tuple(issues), len(trajectory.points), duration)


def resample_linear(trajectory: Trajectory, period_ns: int) -> Trajectory:
    if period_ns <= 0:
        raise ValueError("resample period must be positive")
    if len(trajectory.points) < 2:
        return trajectory
    end = trajectory.points[-1].time_ns
    times = [*range(trajectory.points[0].time_ns, end, period_ns), end]
    output: list[TrajectoryPoint] = []
    right = 1
    for time_ns in times:
        while right < len(trajectory.points) - 1 and trajectory.points[right].time_ns < time_ns:
            right += 1
        before, after = trajectory.points[right - 1], trajectory.points[right]
        span = after.time_ns - before.time_ns
        ratio = 0.0 if span == 0 else (time_ns - before.time_ns) / span
        joints = tuple(
            round(left + (right_value - left) * ratio)
            for left, right_value in zip(before.joint_urad, after.joint_urad, strict=True)
        )
        gripper = before.gripper_u16 if ratio < 0.5 else after.gripper_u16
        output.append(TrajectoryPoint(time_ns, joints, gripper))  # type: ignore[arg-type]
    return _processed(trajectory, tuple(output), "linear_resample")


def smooth_moving_average(trajectory: Trajectory, radius: int = 1) -> Trajectory:
    if radius < 1:
        raise ValueError("smoothing radius must be positive")
    points = []
    for index, point in enumerate(trajectory.points):
        start, end = max(0, index - radius), min(len(trajectory.points), index + radius + 1)
        window = trajectory.points[start:end]
        joints = tuple(
            round(sum(item.joint_urad[axis] for item in window) / len(window)) for axis in range(6)
        )
        points.append(replace(point, joint_urad=joints))  # type: ignore[arg-type]
    return _processed(trajectory, tuple(points), "moving_average")


def scale_speed(trajectory: Trajectory, factor: float) -> Trajectory:
    if not 0 < factor <= 10:
        raise ValueError("speed factor must be within (0, 10]")
    points = tuple(
        replace(point, time_ns=round(point.time_ns / factor)) for point in trajectory.points
    )
    return _processed(trajectory, points, "speed_scale")


def trajectory_hash(trajectory: Trajectory) -> str:
    return hashlib.sha256(trajectory_to_json(trajectory).encode()).hexdigest()


def trajectory_to_json(trajectory: Trajectory) -> str:
    document = {
        "schema_version": trajectory.schema_version,
        "name": trajectory.name,
        "source": trajectory.source,
        "metadata": dict(trajectory.metadata),
        "points": [
            {
                "time_ns": point.time_ns,
                "joint_urad": list(point.joint_urad),
                "gripper_u16": point.gripper_u16,
            }
            for point in trajectory.points
        ],
    }
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def trajectory_from_json(text: str) -> Trajectory:
    document = json.loads(text)
    if document.get("schema_version") != 1 or not isinstance(document.get("points"), list):
        raise ValueError("unsupported or invalid trajectory document")
    points = []
    for raw in document["points"]:
        values = raw["joint_urad"]
        if len(values) != 6 or any(
            isinstance(value, bool) or not isinstance(value, int) for value in values
        ):
            raise ValueError("trajectory joint values must be six integers")
        points.append(TrajectoryPoint(raw["time_ns"], tuple(values), raw.get("gripper_u16")))
    return Trajectory(
        1, document["name"], tuple(points), document["source"], document.get("metadata", {})
    )


def _processed(
    parent: Trajectory,
    points: tuple[TrajectoryPoint, ...],
    operation: str,
) -> Trajectory:
    metadata = dict(parent.metadata)
    metadata.update({"parent_sha256": trajectory_hash(parent), "operation": operation})
    return Trajectory(1, parent.name, points, "processed", metadata)
