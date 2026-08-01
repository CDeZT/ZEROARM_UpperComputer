"""Playback monotonic scheduling, late-point dropping, and pause tests."""

from datetime import UTC, datetime

from zeroarm_desktop.application.playback import (
    MIN_SEND_INTERVAL_NS,
    PlaybackEngine,
    PlaybackState,
    PlaybackSupervisor,
)
from zeroarm_desktop.domain.models import RobotSnapshot
from zeroarm_desktop.domain.trajectory import Trajectory, TrajectoryPoint


def _trajectory() -> Trajectory:
    points = tuple(
        TrajectoryPoint(index * 20_000_000, (index, 1_570_770, 0, 0, 0, 0), 0) for index in range(5)
    )
    return Trajectory(1, "play", points, "test", {})


def test_playback_drops_late_points_without_burst() -> None:
    now = [0]
    sent: list[TrajectoryPoint] = []
    engine = PlaybackEngine(sent.append, clock=lambda: now[0])
    engine.start(_trajectory())
    engine.tick()
    now[0] = 65_000_000
    engine.tick()
    assert [point.joint_urad[0] for point in sent] == [0, 3]
    assert engine.progress.late_points_dropped == 2
    now[0] = 80_000_000
    engine.tick()
    assert len(sent) == 2
    now[0] = 85_000_000
    engine.tick()
    assert len(sent) == 3
    assert engine.progress.state is PlaybackState.COMPLETED


def test_playback_pause_resume_shifts_deadlines() -> None:
    now = [0]
    sent: list[TrajectoryPoint] = []
    engine = PlaybackEngine(sent.append, clock=lambda: now[0])
    engine.start(_trajectory())
    engine.tick()
    now[0] = 10_000_000
    engine.pause()
    now[0] = 1_000_000_000
    engine.resume()
    engine.tick()
    assert len(sent) == 1
    now[0] += 20_000_000
    engine.tick()
    assert len(sent) == 2
    engine.abort("test")
    assert engine.progress.state is PlaybackState.ABORTED


def test_playback_min_send_interval_uses_latest_due_point_without_burst() -> None:
    now = [0]
    sent: list[TrajectoryPoint] = []
    engine = PlaybackEngine(sent.append, clock=lambda: now[0])
    points = tuple(
        TrajectoryPoint(index * 5_000_000, (index, 0, 0, 0, 0, 0), 0) for index in range(5)
    )
    engine.start(Trajectory(1, "throttle", points, "test", {}))
    engine.tick()
    now[0] = 5_000_000
    engine.tick()
    now[0] = 20_000_000
    engine.tick()
    assert MIN_SEND_INTERVAL_NS == 20_000_000
    assert [point.joint_urad[0] for point in sent] == [0, 4]
    assert engine.progress.state is PlaybackState.COMPLETED
    assert engine.progress.points_sent == 2
    assert engine.progress.late_points_dropped == 3


def _snapshot(
    *,
    actual: tuple[int, int, int, int, int, int] = (0, 0, 0, 0, 0, 0),
    moving: int = 0,
    fault: int = 0,
) -> RobotSnapshot:
    return RobotSnapshot(
        1,
        1,
        datetime.now(UTC),
        None,
        None,
        1,
        actual,
        actual,
        0,
        0,
        moving,
        None,
        None,
        fault,
        None,
        None,
    )


def test_playback_supervisor_completion_fault_and_timeout() -> None:
    supervisor = PlaybackSupervisor(timeout_ns=2_000_000_000)
    point = TrajectoryPoint(0, (87_266, 0, 0, 0, 0, 0), 0)
    supervisor.note_sent(point, 1_000)
    assert supervisor.pending
    assert supervisor.evaluate(_snapshot(actual=(87_266, 0, 0, 0, 0, 0)), 1_100) == "completed"
    assert not supervisor.pending

    supervisor.note_sent(point, 5_000)
    assert supervisor.evaluate(_snapshot(moving=0x3F), 1_000_000_000) == "pending"
    assert supervisor.evaluate(_snapshot(moving=0x3F), 2_100_000_000) == "unknown_outcome"

    supervisor.note_sent(point, 9_000)
    assert supervisor.evaluate(_snapshot(moving=0, fault=0x0001), 9_500) == "faulted"
