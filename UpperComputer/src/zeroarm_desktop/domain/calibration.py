"""Versioned local calibration candidates and stable diffs."""

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class AxisCalibration:
    axis: int
    motor_id: int
    direction: int
    gear_ratio_milli: int
    mechanical_zero_urad: int
    soft_min_urad: int
    soft_max_urad: int
    max_velocity_urad_s: int
    verified: bool = False


@dataclass(frozen=True, slots=True)
class CalibrationProfile:
    schema_version: int
    revision: int
    axes: tuple[AxisCalibration, ...]

    @property
    def checksum(self) -> str:
        return hashlib.sha256(calibration_to_json(self).encode()).hexdigest()


def validate_calibration(profile: CalibrationProfile) -> tuple[str, ...]:
    issues = []
    if profile.schema_version != 1 or len(profile.axes) != 6:
        issues.append("schema_or_axis_count")
    if len({axis.motor_id for axis in profile.axes}) != len(profile.axes):
        issues.append("duplicate_motor_id")
    for axis in profile.axes:
        if axis.direction not in {-1, 1}:
            issues.append(f"axis_{axis.axis}_direction")
        if axis.gear_ratio_milli <= 0 or axis.max_velocity_urad_s <= 0:
            issues.append(f"axis_{axis.axis}_positive_values")
        if axis.soft_min_urad >= axis.soft_max_urad:
            issues.append(f"axis_{axis.axis}_limits")
    return tuple(issues)


def calibration_to_json(profile: CalibrationProfile) -> str:
    return json.dumps(
        {
            "schema_version": profile.schema_version,
            "revision": profile.revision,
            "axes": [asdict(axis) for axis in profile.axes],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def calibration_from_json(text: str) -> CalibrationProfile:
    raw = json.loads(text)
    profile = CalibrationProfile(
        raw["schema_version"],
        raw["revision"],
        tuple(AxisCalibration(**axis) for axis in raw["axes"]),
    )
    if validate_calibration(profile):
        raise ValueError("invalid calibration profile")
    return profile


def calibration_diff(before: CalibrationProfile, after: CalibrationProfile) -> tuple[str, ...]:
    return tuple(
        f"J{index + 1}: {old} -> {new}"
        for index, (old, new) in enumerate(zip(before.axes, after.axes, strict=True))
        if old != new
    )


DEFAULT_CALIBRATION = CalibrationProfile(
    1,
    1,
    tuple(
        AxisCalibration(index, index + 1, 1, 50_000, 0, -1_570_770, 1_570_770, 523_590)
        for index in range(6)
    ),
)
