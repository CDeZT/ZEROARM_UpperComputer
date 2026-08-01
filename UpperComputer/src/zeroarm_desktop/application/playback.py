"""Deterministic monotonic trajectory scheduler with no burst catch-up."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from uuid import UUID, uuid4

from zeroarm_desktop.domain.models import JointVector, RobotSnapshot
from zeroarm_desktop.domain.trajectory import Trajectory, TrajectoryPoint

MIN_SEND_INTERVAL_NS = 20_000_000
"""Desktop V1 host action rate limit: at most one target per 20 ms (50 Hz)."""

COMPLETION_TOLERANCE_URAD = 35_000
"""Observed arrival tolerance (~2 deg) shared with the manual-joint page."""

COMPLETION_TIMEOUT_NS = 2_000_000_000
"""Per-point completion deadline; beyond this the outcome is UnknownOutcome."""


class PlaybackState(Enum):
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"


@dataclass(frozen=True, slots=True)
class PlaybackProgress:
    playback_id: UUID | None
    state: PlaybackState
    current_index: int
    points_sent: int
    late_points_dropped: int
    reason: str | None = None


class PlaybackEngine:
    def __init__(
        self, sender: Callable[[TrajectoryPoint], None], *, clock: Callable[[], int]
    ) -> None:
        self._sender = sender
        self._clock = clock
        self._trajectory: Trajectory | None = None
        self._start_ns = 0
        self._pause_started_ns = 0
        self._index = 0
        self._last_send_ns: int | None = None
        self.progress = PlaybackProgress(None, PlaybackState.IDLE, -1, 0, 0)

    def start(self, trajectory: Trajectory) -> UUID:
        if not trajectory.points:
            raise ValueError("cannot play an empty trajectory")
        playback_id = uuid4()
        self._trajectory = trajectory
        self._start_ns = self._clock()
        self._index = 0
        self._last_send_ns = None
        self.progress = PlaybackProgress(playback_id, PlaybackState.PLAYING, -1, 0, 0)
        return playback_id

    def tick(self) -> PlaybackProgress:
        trajectory = self._trajectory
        if trajectory is None or self.progress.state is not PlaybackState.PLAYING:
            return self.progress
        now = self._clock()
        elapsed = now - self._start_ns
        due = self._index
        while due < len(trajectory.points) and trajectory.points[due].time_ns <= elapsed:
            due += 1
        if due == self._index:
            return self.progress
        latest = due - 1
        dropped = latest - self._index
        if self._last_send_ns is not None and now - self._last_send_ns < MIN_SEND_INTERVAL_NS:
            return self.progress
        point = trajectory.points[latest]
        self._sender(point)
        self._last_send_ns = now
        self._index = due
        state = (
            PlaybackState.COMPLETED
            if self._index == len(trajectory.points)
            else PlaybackState.PLAYING
        )
        self.progress = PlaybackProgress(
            self.progress.playback_id,
            state,
            latest,
            self.progress.points_sent + 1,
            self.progress.late_points_dropped + dropped,
        )
        return self.progress

    def pause(self) -> None:
        if self.progress.state is PlaybackState.PLAYING:
            self._pause_started_ns = self._clock()
            self.progress = dataclass_replace(self.progress, state=PlaybackState.PAUSED)

    def resume(self) -> None:
        if self.progress.state is PlaybackState.PAUSED:
            self._start_ns += self._clock() - self._pause_started_ns
            self.progress = dataclass_replace(self.progress, state=PlaybackState.PLAYING)

    def abort(self, reason: str) -> None:
        if self.progress.state in {PlaybackState.PLAYING, PlaybackState.PAUSED}:
            self.progress = dataclass_replace(
                self.progress, state=PlaybackState.ABORTED, reason=reason
            )


def dataclass_replace(progress: PlaybackProgress, **changes: object) -> PlaybackProgress:
    values = {
        "playback_id": progress.playback_id,
        "state": progress.state,
        "current_index": progress.current_index,
        "points_sent": progress.points_sent,
        "late_points_dropped": progress.late_points_dropped,
        "reason": progress.reason,
        **changes,
    }
    return PlaybackProgress(**values)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class PlaybackEvidence:
    """One auditable record per target actually sent during playback."""

    playback_id: UUID
    point_index: int
    sent_monotonic_ns: int
    joint_urad: JointVector
    gripper_u16: int | None
    result_raw: int | None
    snapshot_generation: int | None
    outcome: str


class PlaybackSupervisor:
    """Observe whether a sent playback point reached its target or timed out.

    Completion requires moving_mask == 0 and every axis within tolerance.
    A fault or an expired deadline is an UnknownOutcome-style abort; the caller
    must never automatically retry a dangerous command.
    """

    def __init__(
        self,
        *,
        tolerance_urad: int = COMPLETION_TOLERANCE_URAD,
        timeout_ns: int = COMPLETION_TIMEOUT_NS,
    ) -> None:
        self._tolerance_urad = tolerance_urad
        self._timeout_ns = timeout_ns
        self._pending: TrajectoryPoint | None = None
        self._deadline_ns: int | None = None

    def note_sent(self, point: TrajectoryPoint, now_ns: int) -> None:
        self._pending = point
        self._deadline_ns = now_ns + self._timeout_ns

    @property
    def pending(self) -> bool:
        return self._pending is not None

    def evaluate(self, snapshot: RobotSnapshot, now_ns: int) -> str:
        point = self._pending
        if point is None:
            return "idle"
        if snapshot.fault_flags_raw != 0:
            return "faulted"
        arrived = snapshot.moving_mask == 0 and all(
            abs(actual - target) <= self._tolerance_urad
            for actual, target in zip(snapshot.actual_joint_urad, point.joint_urad, strict=True)
        )
        if arrived:
            self._pending = None
            self._deadline_ns = None
            return "completed"
        if self._deadline_ns is not None and now_ns > self._deadline_ns:
            return "unknown_outcome"
        return "pending"
