"""Bounded high-frequency Snapshot ingestion and throttled rendering."""

from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from zeroarm_desktop.application.device_session import DeviceSession
from zeroarm_desktop.domain.models import JointVector, RobotSnapshot
from zeroarm_desktop.transport.base import Subscription


@dataclass(frozen=True, slots=True)
class PlotSample:
    monotonic_ns: int
    target: JointVector
    actual: JointVector


@dataclass(frozen=True, slots=True)
class JointView:
    index: int
    target_urad: int
    actual_urad: int
    error_urad: int
    velocity_text: str
    current_text: str
    online_text: str


@dataclass(frozen=True, slots=True)
class SnapshotViewState:
    generation: int | None
    run_state_raw: int | None
    run_state_text: str
    fault_flags_raw: int | None
    joints: tuple[JointView, ...]
    samples: tuple[PlotSample, ...]


_RUN_STATES = {0: "BOOT", 1: "READY", 2: "HOMING", 3: "TEACHING", 4: "RUNNING", 5: "FAULT"}


class SnapshotViewModel(QObject):
    state_changed = Signal(object)
    _snapshot_received = Signal(object)

    def __init__(self, *, capacity: int = 6000, render_fps: int = 60) -> None:
        super().__init__()
        if capacity <= 0 or not 1 <= render_fps <= 60:
            raise ValueError("capacity must be positive and render_fps must be 1..60")
        self._ring: deque[PlotSample] = deque(maxlen=capacity)
        self._latest: RobotSnapshot | None = None
        self._subscription: Subscription | None = None
        self._snapshot_received.connect(self.ingest_snapshot)
        self._timer = QTimer(self)
        self._timer.setInterval(round(1000 / render_fps))
        self._timer.timeout.connect(self.render_now)
        self._timer.start()

    @property
    def sample_count(self) -> int:
        return len(self._ring)

    def bind_session(self, session: DeviceSession | None) -> None:
        if self._subscription is not None:
            self._subscription.cancel()
            self._subscription = None
        self._latest = None
        self._ring.clear()
        if session is not None:
            self._subscription = session.subscribe_snapshots(self._snapshot_received.emit)
            if session.latest_snapshot is not None:
                self.ingest_snapshot(session.latest_snapshot)

    @Slot(object)
    def ingest_snapshot(self, snapshot: RobotSnapshot) -> None:
        self._latest = snapshot
        self._ring.append(
            PlotSample(
                snapshot.received_monotonic_ns,
                snapshot.target_joint_urad,
                snapshot.actual_joint_urad,
            )
        )

    @Slot()
    def render_now(self) -> SnapshotViewState:
        state = self.current_state()
        self.state_changed.emit(state)
        return state

    def current_state(self) -> SnapshotViewState:
        snapshot = self._latest
        if snapshot is None:
            return SnapshotViewState(None, None, "未连接", None, (), tuple(self._ring))
        joints = tuple(
            JointView(
                index=index + 1,
                target_urad=target,
                actual_urad=actual,
                error_urad=target - actual,
                velocity_text="-- / V1 未提供",
                current_text="-- / V1 未提供",
                online_text="-- / V1 未提供",
            )
            for index, (target, actual) in enumerate(
                zip(snapshot.target_joint_urad, snapshot.actual_joint_urad, strict=True)
            )
        )
        run_state = _RUN_STATES.get(snapshot.run_state_raw, f"UNKNOWN ({snapshot.run_state_raw})")
        return SnapshotViewState(
            snapshot.generation,
            snapshot.run_state_raw,
            run_state,
            snapshot.fault_flags_raw,
            joints,
            tuple(self._ring),
        )

    def close(self) -> None:
        self._timer.stop()
        self.bind_session(None)
