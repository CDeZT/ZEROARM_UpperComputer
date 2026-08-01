"""Trajectory validation, processing, JSON, and editor history tests."""

import pytest

from zeroarm_desktop.application.trajectory_editor import TrajectoryEditor
from zeroarm_desktop.domain.hardware_profile import URAD_PER_DEGREE
from zeroarm_desktop.domain.trajectory import (
    Trajectory,
    TrajectoryPoint,
    require_partial_profile_points,
    resample_linear,
    scale_speed,
    smooth_moving_average,
    trajectory_from_json,
    trajectory_hash,
    trajectory_to_json,
    validate_trajectory,
)


def _trajectory() -> Trajectory:
    return Trajectory(
        1,
        "test",
        (
            TrajectoryPoint(0, (0, 0, 0, 0, 0, 0), 0),
            TrajectoryPoint(1_000_000_000, (100_000, 0, 0, 0, 0, 0), 0),
            TrajectoryPoint(2_000_000_000, (0, 0, 0, 0, 0, 0), 0),
        ),
        "created",
        {},
    )


def test_trajectory_json_roundtrip_and_hash() -> None:
    original = _trajectory()
    decoded = trajectory_from_json(trajectory_to_json(original))
    assert decoded == original
    assert trajectory_hash(decoded) == trajectory_hash(original)


def test_validation_reports_time_limit_velocity_and_gripper() -> None:
    invalid = Trajectory(
        1,
        "bad",
        (
            TrajectoryPoint(0, (0, 0, 0, 0, 0, 0), 0),
            TrajectoryPoint(0, (0, 0, -1, 0, 0, 0), 70_000),
        ),
        "created",
        {},
    )
    codes = {issue.code for issue in validate_trajectory(invalid).issues}
    assert {"time_not_strictly_increasing", "joint_limit", "gripper_range"} <= codes


def test_validate_trajectory_rejects_nonzero_unavailable_axes() -> None:
    trajectory = Trajectory(
        1,
        "unavailable",
        (
            TrajectoryPoint(0, (0, 0, 0, 0, 0, 0)),
            TrajectoryPoint(1_000_000_000, (0, 1, 0, 0, 0, 0)),
            TrajectoryPoint(2_000_000_000, (0, 0, 0, 0, 0, -1)),
        ),
        "created",
        {},
    )
    issues = validate_trajectory(trajectory).issues
    assert [issue.code for issue in issues] == ["unavailable_axis", "unavailable_axis"]
    assert issues[0].joint_index == 1
    assert issues[1].joint_index == 5


def test_validate_trajectory_rejects_dangerous_midpoint_even_if_endpoints_legal() -> None:
    deg = URAD_PER_DEGREE
    trajectory = Trajectory(
        1,
        "midpoint",
        (
            TrajectoryPoint(0, (0, 0, 10 * deg, 0, 0, 0)),
            TrajectoryPoint(1_000_000_000, (0, 0, 50 * deg, 0, 80 * deg, 0)),
            TrajectoryPoint(2_000_000_000, (0, 0, 50 * deg, 0, 60 * deg, 0)),
        ),
        "created",
        {},
    )
    report = validate_trajectory(trajectory)
    assert not report.valid
    codes = {issue.code for issue in report.issues}
    assert {
        "j5_midrange_requires_j3_already_clear",
        "j5_extended_requires_j3_already_clear",
    } <= codes
    midpoint_issues = [
        issue for issue in report.issues if issue.point_index == 1 and issue.code.startswith("j5")
    ]
    assert midpoint_issues
    assert all(issue.joint_index == 4 for issue in midpoint_issues)
    assert all(issue.detail is not None and "°" in issue.detail for issue in midpoint_issues)


def test_validate_trajectory_rejects_lowering_without_clearance() -> None:
    deg = URAD_PER_DEGREE
    trajectory = Trajectory(
        1,
        "lowering",
        (
            TrajectoryPoint(0, (0, 0, 50 * deg, 20 * deg, 60 * deg, 0)),
            TrajectoryPoint(1_000_000_000, (0, 0, 10 * deg, 0, 0, 0)),
        ),
        "created",
        {},
    )
    codes = {issue.code for issue in validate_trajectory(trajectory).issues}
    assert {"lower_j3_requires_j4_centered", "lower_j3_requires_j5_midrange"} <= codes


def test_validate_trajectory_accepts_continuous_j1_outside_old_mapping_range() -> None:
    trajectory = Trajectory(
        1,
        "continuous",
        (
            TrajectoryPoint(0, (10_000_000, 0, 0, 0, 0, 0)),
            TrajectoryPoint(100_000_000_000, (-10_000_000, 0, 0, 0, 0, 0)),
        ),
        "created",
        {},
    )
    report = validate_trajectory(trajectory)
    assert report.valid


def test_require_partial_profile_points_rejects_unavailable_axis_motion() -> None:
    valid = (TrajectoryPoint(0, (0, 0, 0, 0, 0, 0)),)
    assert require_partial_profile_points(valid) == valid
    for axis in (1, 5):
        raw = [0, 0, 0, 0, 0, 0]
        raw[axis] = 1
        with pytest.raises(ValueError, match="partial profile"):
            require_partial_profile_points(
                (TrajectoryPoint(0, tuple(raw)),)  # type: ignore[arg-type]
            )


def test_processing_preserves_endpoints_and_parent() -> None:
    original = _trajectory()
    resampled = resample_linear(original, 250_000_000)
    assert resampled.points[0] == original.points[0]
    assert resampled.points[-1] == original.points[-1]
    assert resampled.metadata["parent_sha256"] == trajectory_hash(original)
    assert smooth_moving_average(original) is not original
    assert scale_speed(original, 2).points[-1].time_ns == 1_000_000_000


def test_editor_undo_redo_roundtrip() -> None:
    original = _trajectory()
    processed = smooth_moving_average(original)
    editor = TrajectoryEditor(original)
    editor.apply(processed)
    assert editor.undo() == original
    assert editor.redo() == processed
