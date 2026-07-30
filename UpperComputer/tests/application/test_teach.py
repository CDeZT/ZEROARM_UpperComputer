"""Teach raw recording, bounds, unknown time fields, and processing tests."""

from datetime import UTC, datetime

from zeroarm_desktop.application.teach import TeachRecorder, TeachState, recording_to_trajectory
from zeroarm_desktop.domain.models import RobotSnapshot


def _snapshot(index: int) -> RobotSnapshot:
    joints = (index, 1_570_770, 0, 0, 0, 0)
    return RobotSnapshot(
        index,
        index,
        datetime.now(UTC),
        None,
        None,
        3,
        joints,
        joints,
        0,
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
    recorder.start()
    for index in range(4):
        recorder.append(_snapshot(index))
    raw = recorder.stop(0x3F)
    assert recorder.state is TeachState.REVIEW
    assert len(raw.samples) == 2
    assert raw.dropped_samples == 2
    assert raw.samples[0].device_time_ms is None
    assert raw.samples[0].sample_sequence is None
    trajectory = recording_to_trajectory(raw, "teach")
    assert trajectory.metadata["parent_raw_sha256"] == raw.sha256
