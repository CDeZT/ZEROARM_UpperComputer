"""Playback monotonic scheduling, late-point dropping, and pause tests."""

from zeroarm_desktop.application.playback import PlaybackEngine, PlaybackState
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
