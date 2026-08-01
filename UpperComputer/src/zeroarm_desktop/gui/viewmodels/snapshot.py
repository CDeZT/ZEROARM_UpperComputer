"""Bounded high-frequency Snapshot ingestion and throttled rendering."""

from collections import deque
from dataclasses import dataclass
from time import monotonic_ns

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from zeroarm_desktop.application.device_session import DeviceSession
from zeroarm_desktop.domain.hardware_profile import (
    HardwareProfile,
    ReadinessReport,
    evaluate_readiness,
)
from zeroarm_desktop.domain.models import JointVector, RobotSnapshot
from zeroarm_desktop.protocol.v1_codec import V1RunState
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
    readiness: ReadinessReport | None
    fault_names: tuple[str, ...]
    fault_unknown_bits: int
    unavailable_axes: tuple[int, ...]
    snapshot_age_ms: int | None
    auto_home_warning: str | None


def _run_state_text(raw: int) -> str:
    try:
        return V1RunState(raw).name
    except ValueError:
        return f"UNKNOWN ({raw})"


class SnapshotViewModel(QObject):
    state_changed = Signal(object)
    _snapshot_received = Signal(object)

    def __init__(
        self,
        *,
        capacity: int = 6000,
        render_fps: int = 60,
        profile: HardwareProfile | None = None,
    ) -> None:
        super().__init__()
        if capacity <= 0 or not 1 <= render_fps <= 60:
            raise ValueError("capacity must be positive and render_fps must be 1..60")
        self._profile = profile or HardwareProfile.default()
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
            return SnapshotViewState(
                None,
                None,
                "未连接",
                None,
                (),
                tuple(self._ring),
                None,
                (),
                0,
                (),
                None,
                None,
            )
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
        readiness = evaluate_readiness(snapshot, self._profile)
        fault_names = tuple(flag.name for flag in readiness.fault_known)
        age_ms = (monotonic_ns() - snapshot.received_monotonic_ns) // 1_000_000
        warning = None
        if (
            readiness.run_state_name == "READY"
            and readiness.motion_authorized
            and not readiness.homed_complete
        ):
            warning = "未回零: 若连续 20 秒无任何主机帧且空闲 MCU 会自动执行回零 (0x1D)"
        unavailable_axes = tuple(
            capability.index
            for capability in self._profile.capabilities
            if not capability.available
        )
        return SnapshotViewState(
            snapshot.generation,
            snapshot.run_state_raw,
            _run_state_text(snapshot.run_state_raw),
            snapshot.fault_flags_raw,
            joints,
            tuple(self._ring),
            readiness,
            fault_names,
            readiness.fault_unknown_bits,
            unavailable_axes,
            age_ms,
            warning,
        )

    def close(self) -> None:
        self._timer.stop()
        self.bind_session(None)
