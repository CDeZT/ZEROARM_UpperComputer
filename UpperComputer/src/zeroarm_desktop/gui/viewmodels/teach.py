"""Teach ViewModel: mask selection, support gate, Arm, record, stop review."""

from __future__ import annotations

from contextlib import suppress
from time import monotonic_ns

from PySide6.QtCore import QObject, QTimer, Signal

from zeroarm_desktop.application.device_session import DeviceSession, SessionState
from zeroarm_desktop.application.teach import (
    TeachRecorder,
    TeachState,
    TeachStopReview,
    recording_to_trajectory,
)
from zeroarm_desktop.domain.hardware_profile import HardwareProfile
from zeroarm_desktop.domain.safety import (
    AppMode,
    ArmContext,
    CommandFamily,
    CommandIntent,
    CommandPreview,
    CommandService,
    SafetyContext,
    SafetyGate,
)
from zeroarm_desktop.domain.trajectory import Trajectory
from zeroarm_desktop.transport.base import Subscription


class TeachExecutor:
    def __init__(self, session_provider: object) -> None:
        self._session_provider = session_provider

    def execute(self, intent: CommandIntent) -> object:
        session = getattr(self._session_provider, "session", None)
        if not isinstance(session, DeviceSession):
            raise RuntimeError("Session 不可用")
        if intent.family is CommandFamily.GRAVITY_RELEASE:
            return session.send_teach_start(intent.joint_mask)
        raise RuntimeError(f"unsupported teach intent {intent.family}")


class TeachViewModel(QObject):
    status_changed = Signal(str)
    state_changed = Signal(str)
    stats_changed = Signal(str)
    review_changed = Signal(str)
    trajectory_saved = Signal(object)

    def __init__(self, session_provider: object) -> None:
        super().__init__()
        self._provider = session_provider
        self._profile = HardwareProfile.default()
        self._service = CommandService(SafetyGate(), TeachExecutor(session_provider))
        self.recorder = TeachRecorder()
        self._preview: CommandPreview | None = None
        self._arm: ArmContext | None = None
        self._mode = AppMode.OBSERVER
        self._support_confirmed = False
        self._joint_mask = self._profile.home_mask
        self._subscription: Subscription | None = None
        self._stats_timer = QTimer(self)
        self._stats_timer.setInterval(200)
        self._stats_timer.timeout.connect(self._emit_stats)
        self._saved_trajectory: Trajectory | None = None

    @property
    def available_axes(self) -> tuple[int, ...]:
        return tuple(
            capability.index for capability in self._profile.capabilities if capability.available
        )

    @property
    def joint_mask(self) -> int:
        return self._joint_mask

    @property
    def state(self) -> TeachState:
        return self.recorder.state

    @property
    def last_review(self) -> TeachStopReview | None:
        return self.recorder.last_review

    @property
    def saved_trajectory(self) -> Trajectory | None:
        return self._saved_trajectory

    def set_mode(self, mode: AppMode) -> None:
        if self.recorder.state is TeachState.RECORDING:
            with suppress(PermissionError, RuntimeError, ValueError):
                self.stop()
        self._service.disarm("mode_changed")
        self._preview = None
        self._arm = None
        self._mode = mode
        self.status_changed.emit(f"模式切换为 {mode.value}")

    def set_joint_mask(self, mask: int) -> None:
        if self.recorder.state is TeachState.RECORDING:
            raise RuntimeError("录制中不能修改轴掩码")
        available = sum(1 << axis for axis in self.available_axes)
        if mask <= 0 or mask & ~available:
            raise ValueError("示教掩码只能包含可用轴 J1/J3/J4/J5")
        self._joint_mask = mask
        self._preview = None
        self._arm = None
        self.status_changed.emit(f"示教掩码 0x{mask:02X}")

    def set_support_confirmed(self, confirmed: bool) -> None:
        self._support_confirmed = confirmed
        self._preview = None
        self._arm = None
        self.status_changed.emit("支撑已确认" if confirmed else "支撑未确认")

    def preview(self) -> CommandPreview:
        intent = CommandIntent(CommandFamily.GRAVITY_RELEASE, joint_mask=self._joint_mask)
        context = self._context()
        preview = self._service.preview(intent, context)
        self._preview = preview
        self._arm = None
        if preview.decision.allowed:
            self.status_changed.emit(
                f"预览通过 | mask=0x{self._joint_mask:02X} | 确认后 Arm 再开始"
            )
        else:
            self.status_changed.emit("拒绝: " + ", ".join(preview.decision.denials))
        return preview

    def arm(self) -> ArmContext:
        if self._preview is None:
            raise RuntimeError("请先预览")
        arm = self._service.arm(self._preview, self._context())
        self._arm = arm
        self.recorder.mark_armed(self._joint_mask)
        self.state_changed.emit(self.recorder.state.value)
        self.status_changed.emit("已 Arm 5 秒 | 立即开始示教")
        return arm

    def start(self) -> None:
        if self._preview is None or self._arm is None:
            raise RuntimeError("请先预览并 Arm")
        session = self._session()
        result = self._service.execute(self._preview, self._arm, self._context())
        raw = getattr(result, "raw_value", "n/a")
        if not getattr(result, "is_ok", False):
            raise RuntimeError(f"TEACH_START 失败 raw={raw}")
        self._preview = None
        self._arm = None
        self.recorder.start(self._joint_mask)
        self._unsubscribe()
        self._subscription = session.subscribe_snapshots(self.recorder.append)
        if session.latest_snapshot is not None:
            self.recorder.append(session.latest_snapshot)
        self._stats_timer.start()
        self.state_changed.emit(self.recorder.state.value)
        self.status_changed.emit(f"RECORDING | TEACH_START OK raw={raw} | 保持支撑")
        self._emit_stats()

    def stop(self) -> None:
        if self.recorder.state is not TeachState.RECORDING:
            raise RuntimeError("当前未在录制")
        session = self._session()
        result = session.send_teach_stop()
        snapshot = session.latest_snapshot
        recording, review = self.recorder.stop(snapshot)
        self._unsubscribe()
        self._stats_timer.stop()
        self.state_changed.emit(self.recorder.state.value)
        disabled = "失能OK" if review.disabled_ok else "失能异常"
        self.status_changed.emit(
            f"REVIEW | samples={len(recording.samples)} dropped={recording.dropped_samples} | "
            f"{disabled} | 不自动ENABLE | TEACH_STOP raw={result.raw_value}"
        )
        self.review_changed.emit(self._format_review(review, recording.sha256))
        self._emit_stats()

    def save_trajectory(self, name: str = "teach_raw") -> Trajectory:
        recording = self.recorder.last_recording
        if recording is None:
            raise RuntimeError("没有可保存的示教记录")
        trajectory = recording_to_trajectory(recording, name)
        self._saved_trajectory = trajectory
        self.trajectory_saved.emit(trajectory)
        self.status_changed.emit(
            f"已另存轨迹 {trajectory.name} | points={len(trajectory.points)} | "
            f"parent={recording.sha256[:12]}"
        )
        return trajectory

    def reset(self) -> None:
        if self.recorder.state is TeachState.RECORDING:
            with suppress(PermissionError, RuntimeError, ValueError):
                self.stop()
        self._unsubscribe()
        self._stats_timer.stop()
        self._service.disarm("reset")
        self._preview = None
        self._arm = None
        self._saved_trajectory = None
        self.recorder.reset()
        self.state_changed.emit(self.recorder.state.value)
        self.review_changed.emit("")
        self.stats_changed.emit("samples=0 | dropped=0 | Hz=--")
        self.status_changed.emit("已重置为 IDLE")

    def _emit_stats(self) -> None:
        recording = self.recorder.last_recording
        if self.recorder.state is TeachState.RECORDING:
            count = self.recorder.sample_count
            dropped = self.recorder.dropped_samples
            span = self.recorder.recording_span_ns
            hz = "--" if span <= 0 or count < 2 else f"{(count - 1) / (span / 1e9):.1f}"
            self.stats_changed.emit(f"samples={count} | dropped={dropped} | Hz={hz}")
            return
        if recording is not None:
            span = max(0, recording.stopped_monotonic_ns - recording.started_monotonic_ns)
            hz = (
                "--"
                if span <= 0 or len(recording.samples) < 2
                else f"{(len(recording.samples) - 1) / (span / 1e9):.1f}"
            )
            self.stats_changed.emit(
                f"samples={len(recording.samples)} | dropped={recording.dropped_samples} | Hz={hz}"
            )

    def _format_review(self, review: TeachStopReview, sha256: str) -> str:
        enabled = "--" if review.enabled_mask is None else f"0x{review.enabled_mask:02X}"
        run_state = "--" if review.run_state_raw is None else str(review.run_state_raw)
        return (
            f"mask=0x{review.joint_mask:02X} enabled={enabled} run_state={run_state} "
            f"disabled_ok={review.disabled_ok} sha={sha256[:16]} "
            f"warnings={','.join(review.warnings)}"
        )

    def _session(self) -> DeviceSession:
        session = getattr(self._provider, "session", None)
        if not isinstance(session, DeviceSession):
            raise RuntimeError("请先连接设备")
        if not session.actions_allowed:
            raise PermissionError("真实 Serial 保持只读 | 示教仅允许 Mock")
        return session

    def _context(self) -> SafetyContext:
        session = self._session()
        return SafetyContext(
            session.state is SessionState.READONLY_READY,
            self._mode,
            session.latest_snapshot,
            monotonic_ns(),
            500_000_000,
            "mock-model-v1",
            False,
            self._support_confirmed,
            False,
            True,
        )

    def _unsubscribe(self) -> None:
        if self._subscription is not None:
            self._subscription.cancel()
            self._subscription = None
