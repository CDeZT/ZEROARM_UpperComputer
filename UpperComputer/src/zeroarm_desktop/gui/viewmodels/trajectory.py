"""Trajectory editor ViewModel and 3D cursor integration."""

from time import monotonic_ns

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from zeroarm_desktop.application.device_session import DeviceSession
from zeroarm_desktop.application.playback import (
    PlaybackEngine,
    PlaybackEvidence,
    PlaybackState,
    PlaybackSupervisor,
)
from zeroarm_desktop.application.trajectory_editor import TrajectoryEditor
from zeroarm_desktop.domain.hardware_profile import HardwareProfile
from zeroarm_desktop.domain.models import JointTarget
from zeroarm_desktop.domain.safety import (
    AppMode,
    CommandFamily,
    CommandIntent,
    CommandService,
    SafetyContext,
    SafetyGate,
)
from zeroarm_desktop.domain.trajectory import (
    Trajectory,
    TrajectoryPoint,
    resample_linear,
    smooth_moving_average,
    trajectory_from_json,
    trajectory_to_json,
    validate_trajectory,
)


class PlaybackTargetExecutor:
    def __init__(self, session_provider: object) -> None:
        self._session_provider = session_provider

    def execute(self, intent: CommandIntent) -> object:
        session = getattr(self._session_provider, "session", None)
        if not isinstance(session, DeviceSession) or intent.target is None:
            raise RuntimeError("Mock Session不可用")
        return session.send_joint_target(intent.target)


class TrajectoryViewModel(QObject):
    changed = Signal(object)
    ghost_changed = Signal(object)

    def __init__(self, session_provider: object) -> None:
        super().__init__()
        initial = Trajectory(
            1,
            "Demo trajectory",
            (
                TrajectoryPoint(0, (0, 0, 0, 0, 0, 0), 0),
                TrajectoryPoint(1_000_000_000, (87_266, 0, 0, 0, 0, 0), 0),
                TrajectoryPoint(2_000_000_000, (0, 0, 0, 0, 0, 0), 0),
            ),
            "created",
            {},
        )
        self.editor = TrajectoryEditor(initial)
        self._session_provider = session_provider
        self._profile = HardwareProfile.default()
        self._mode = AppMode.OBSERVER
        self._service = CommandService(SafetyGate(), PlaybackTargetExecutor(session_provider))
        self.playback = PlaybackEngine(self._send_point, clock=monotonic_ns)
        self._supervisor = PlaybackSupervisor()
        self._evidence: list[PlaybackEvidence] = []
        self._last_evidence_index: int | None = None
        self._poller_paused = False
        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(10)
        self._playback_timer.timeout.connect(self._playback_tick)

    @property
    def trajectory(self) -> Trajectory:
        return self.editor.current

    @property
    def evidence(self) -> tuple[PlaybackEvidence, ...]:
        return tuple(self._evidence)

    def set_mode(self, mode: AppMode) -> None:
        self.abort_playback("mode_changed")
        self._mode = mode

    def select(self, index: int) -> None:
        self.ghost_changed.emit(self.trajectory.points[index].joint_urad)

    def load_trajectory(self, trajectory: Trajectory) -> None:
        self.abort_playback("load_trajectory")
        self.editor.apply(trajectory)
        self.changed.emit(self.trajectory)

    def import_json_text(self, text: str) -> Trajectory:
        trajectory = trajectory_from_json(text)
        report = validate_trajectory(trajectory)
        if not report.valid:
            raise ValueError(
                "导入轨迹验证失败: " + ",".join(issue.code for issue in report.issues[:4])
            )
        self.load_trajectory(trajectory)
        return trajectory

    def export_json_text(self) -> str:
        return trajectory_to_json(self.trajectory)

    def resample(self) -> None:
        self.editor.apply(resample_linear(self.trajectory, 100_000_000))
        self.changed.emit(self.trajectory)

    def smooth(self) -> None:
        self.editor.apply(smooth_moving_average(self.trajectory))
        self.changed.emit(self.trajectory)

    def undo(self) -> None:
        self.changed.emit(self.editor.undo())

    def redo(self) -> None:
        self.changed.emit(self.editor.redo())

    def validation_text(self) -> str:
        report = validate_trajectory(self.trajectory)
        if report.valid:
            return f"有效 | {report.point_count}点 | {report.duration_ns / 1e9:.3f}s"
        details = []
        for issue in report.issues[:4]:
            location = f"点{issue.point_index}" if issue.point_index is not None else "全局"
            joint = f" J{issue.joint_index + 1}" if issue.joint_index is not None else ""
            details.append(f"{location}{joint} {issue.code}")
        return "拒绝: " + ", ".join(details)

    def start_playback(self) -> None:
        session = getattr(self._session_provider, "session", None)
        if not isinstance(session, DeviceSession) or not session.actions_allowed:
            raise PermissionError("轨迹回放只允许Mock")
        report = validate_trajectory(self.trajectory)
        if not report.valid:
            raise ValueError("轨迹验证失败")
        intent = CommandIntent(CommandFamily.TRAJECTORY, joint_mask=self._profile.home_mask)
        context = self._context()
        preview = self._service.preview(intent, context)
        if not preview.decision.allowed:
            raise PermissionError("回放被拒绝: " + ", ".join(preview.decision.denials))
        self._service.arm(preview, context)
        self.playback.start(self.trajectory)
        self._evidence = []
        self._last_evidence_index = None
        self._supervisor = PlaybackSupervisor()
        try:
            session.pause_polling()
        except Exception:
            self._service.disarm("start_failed")
            raise
        self._poller_paused = True
        self._playback_timer.start()
        self.changed.emit(self.trajectory)

    def pause_playback(self) -> None:
        self.playback.pause()

    def resume_playback(self) -> None:
        self.playback.resume()

    def abort_playback(self, reason: str = "user_abort") -> None:
        self.playback.abort(reason)
        self._playback_timer.stop()
        self._mark_pending_unknown()
        self._resume_poller()
        self._service.disarm(reason)

    @Slot()
    def _playback_tick(self) -> None:
        try:
            progress = self.playback.tick()
        except (PermissionError, RuntimeError, ValueError) as error:
            self.abort_playback(f"发送失败: {error}")
            return
        session = getattr(self._session_provider, "session", None)
        outcome = "idle"
        if isinstance(session, DeviceSession):
            snapshot = session.latest_snapshot
            if snapshot is not None:
                outcome = self._supervisor.evaluate(snapshot, monotonic_ns())
        if outcome == "completed":
            self._mark_last_completed()
            outcome = "idle"
        elif outcome in {"faulted", "unknown_outcome"}:
            self.abort_playback(f"UnknownOutcome: {outcome}")
            return
        if progress.state is PlaybackState.COMPLETED and outcome == "pending":
            if isinstance(session, DeviceSession):
                session.poll_once()
        elif progress.state in {PlaybackState.COMPLETED, PlaybackState.ABORTED}:
            self._playback_timer.stop()
            self._resume_poller()
        self.changed.emit(self.trajectory)

    def _send_point(self, raw: TrajectoryPoint) -> None:
        session = self._session()
        if raw.gripper_u16 is None:
            raise ValueError("回放点缺少gripper值")
        target = JointTarget(raw.joint_urad, 20, raw.gripper_u16)
        intent = CommandIntent(
            CommandFamily.JOINT_TARGET,
            joint_mask=self._profile.home_mask,
            target=target,
        )
        context = self._context()
        preview = self._service.preview(intent, context)
        if not preview.decision.allowed:
            raise PermissionError("回放点被拒绝: " + ", ".join(preview.decision.denials))
        arm = self._service.arm(preview, context)
        result = self._service.execute(preview, arm, context)
        session.poll_once()
        playback_id = self.playback.progress.playback_id
        if playback_id is None:
            raise RuntimeError("回放未启动")
        result_raw = getattr(result, "raw_value", None)
        evidence = PlaybackEvidence(
            playback_id,
            len(self._evidence),
            monotonic_ns(),
            raw.joint_urad,
            raw.gripper_u16,
            result_raw,
            context.snapshot.generation if context.snapshot is not None else None,
            "accepted",
        )
        self._evidence.append(evidence)
        self._last_evidence_index = len(self._evidence) - 1
        self._supervisor.note_sent(raw, monotonic_ns())

    def _mark_last_completed(self) -> None:
        if self._last_evidence_index is None or self._last_evidence_index >= len(self._evidence):
            return
        last = self._evidence[self._last_evidence_index]
        self._evidence.append(
            PlaybackEvidence(
                last.playback_id,
                last.point_index,
                last.sent_monotonic_ns,
                last.joint_urad,
                last.gripper_u16,
                last.result_raw,
                last.snapshot_generation,
                "completed",
            )
        )
        self._last_evidence_index = None

    def _mark_pending_unknown(self) -> None:
        if not self._supervisor.pending or self._last_evidence_index is None:
            return
        if self._last_evidence_index >= len(self._evidence):
            return
        last = self._evidence[self._last_evidence_index]
        self._evidence.append(
            PlaybackEvidence(
                last.playback_id,
                last.point_index,
                last.sent_monotonic_ns,
                last.joint_urad,
                last.gripper_u16,
                last.result_raw,
                last.snapshot_generation,
                "unknown_outcome",
            )
        )
        self._last_evidence_index = None

    def _resume_poller(self) -> None:
        if not self._poller_paused:
            return
        self._poller_paused = False
        session = getattr(self._session_provider, "session", None)
        if isinstance(session, DeviceSession):
            session.resume_polling()

    def _session(self) -> DeviceSession:
        session = getattr(self._session_provider, "session", None)
        if not isinstance(session, DeviceSession):
            raise RuntimeError("请先连接Mock")
        if not session.actions_allowed:
            raise PermissionError("真实Serial保持只读 | 轨迹回放仅允许Mock")
        return session

    def _context(self) -> SafetyContext:
        session = self._session()
        return SafetyContext(
            session.state,
            self._mode,
            session.latest_snapshot,
            monotonic_ns(),
            500_000_000,
            "mock-model-v1",
            False,
            False,
            False,
            True,
        )
