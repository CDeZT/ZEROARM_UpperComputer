"""Trajectory validation, processing, JSON, and editor history tests."""

from zeroarm_desktop.application.trajectory_editor import TrajectoryEditor
from zeroarm_desktop.domain.trajectory import (
    Trajectory,
    TrajectoryPoint,
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
            TrajectoryPoint(0, (0, 1_570_770, 0, 0, 0, 0), 0),
            TrajectoryPoint(1_000_000_000, (100_000, 1_570_770, 0, 0, 0, 0), 0),
            TrajectoryPoint(2_000_000_000, (0, 1_570_770, 0, 0, 0, 0), 0),
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
            TrajectoryPoint(0, (0, 1_570_770, 0, 0, 0, 0), 0),
            TrajectoryPoint(0, (-1, 1_570_770, 0, 0, 0, 0), 70_000),
        ),
        "created",
        {},
    )
    codes = {issue.code for issue in validate_trajectory(invalid).issues}
    assert {"time_not_strictly_increasing", "joint_limit", "gripper_range"} <= codes


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
