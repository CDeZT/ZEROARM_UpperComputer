"""Teach raw recording, bounds, unknown time fields, and processing tests."""

from datetime import UTC, datetime

from zeroarm_desktop.application.teach import (
    TeachRecorder,
    TeachState,
    build_stop_review,
    recording_to_trajectory,
)
from zeroarm_desktop.domain.models import RobotSnapshot


def _snapshot(index: int, *, enabled_mask: int = 0, run_state: int = 3) -> RobotSnapshot:
    joints = (index, 0, 0, 0, 0, 0)
    return RobotSnapshot(
        index,
        index * 1_000_000,
        datetime.now(UTC),
        None,
        None,
        run_state,
        joints,
        joints,
        enabled_mask,
        0,
        0,
        None,
        None,
        0,
        None,
        None,
    )


def test_teach_recorder_is_bounded_and_preserves_unknown_times() -> None:
    recorder = TeachRecorder(capacity=2)
    recorder.start(0x1D)
    for index in range(4):
        recorder.append(_snapshot(index))
    raw, review = recorder.stop(_snapshot(99, enabled_mask=0, run_state=1))
    assert recorder.state is TeachState.REVIEW
    assert len(raw.samples) == 2
    # 4 appends overflow by 2; stop() appends one final sample and overflows again.
    assert raw.dropped_samples == 3
    assert raw.samples[0].device_time_ms is None
    assert raw.samples[0].sample_sequence is None
    assert review.disabled_ok
    trajectory = recording_to_trajectory(raw, "teach")
    assert trajectory.metadata["parent_raw_sha256"] == raw.sha256
    assert trajectory.metadata["joint_mask"] == 0x1D


def test_teach_stop_review_flags_still_enabled_axes() -> None:
    recorder = TeachRecorder()
    recorder.start(0x1D)
    recorder.append(_snapshot(1, enabled_mask=0x1D, run_state=3))
    raw, review = recorder.stop(_snapshot(2, enabled_mask=0x1D, run_state=1))
    assert not review.disabled_ok
    assert "taught_axes_still_enabled" in review.warnings
    rebuilt = build_stop_review(raw, _snapshot(3, enabled_mask=0, run_state=1))
    assert rebuilt.disabled_ok
