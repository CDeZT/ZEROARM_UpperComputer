"""Trajectory editor ViewModel and 3D cursor integration."""

from time import monotonic_ns

from PySide6.QtCore import QObject, QTimer, Signal

from zeroarm_desktop.application.playback import PlaybackEngine, PlaybackState
from zeroarm_desktop.application.trajectory_editor import TrajectoryEditor
from zeroarm_desktop.domain.models import JointTarget
from zeroarm_desktop.domain.trajectory import (
    Trajectory,
    TrajectoryPoint,
    resample_linear,
    smooth_moving_average,
    validate_trajectory,
)


class TrajectoryViewModel(QObject):
    changed = Signal(object)
    ghost_changed = Signal(object)

    def __init__(self, session_provider: object) -> None:
        super().__init__()
        initial = Trajectory(
            1,
            "Demo trajectory",
            (
                TrajectoryPoint(0, (0, 1_570_770, 0, 0, 0, 0), 0),
                TrajectoryPoint(1_000_000_000, (87_266, 1_570_770, 0, 0, 0, 0), 0),
                TrajectoryPoint(2_000_000_000, (0, 1_570_770, 0, 0, 0, 0), 0),
            ),
            "created",
            {},
        )
        self.editor = TrajectoryEditor(initial)
        self._session_provider = session_provider
        self.playback = PlaybackEngine(self._send_point, clock=monotonic_ns)
        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(10)
        self._playback_timer.timeout.connect(self._playback_tick)

    @property
    def trajectory(self) -> Trajectory:
        return self.editor.current

    def select(self, index: int) -> None:
        self.ghost_changed.emit(self.trajectory.points[index].joint_urad)

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
        return "拒绝: " + ", ".join(issue.code for issue in report.issues)

    def start_playback(self) -> None:
        session = getattr(self._session_provider, "session", None)
        if session is None or not session.actions_allowed:
            raise PermissionError("轨迹回放只允许Mock")
        report = validate_trajectory(self.trajectory)
        if not report.valid:
            raise ValueError("轨迹验证失败")
        self.playback.start(self.trajectory)
        self._playback_timer.start()
        self.changed.emit(self.trajectory)

    def pause_playback(self) -> None:
        self.playback.pause()

    def resume_playback(self) -> None:
        self.playback.resume()

    def abort_playback(self, reason: str = "user_abort") -> None:
        self.playback.abort(reason)
        self._playback_timer.stop()

    def _playback_tick(self) -> None:
        progress = self.playback.tick()
        if progress.state in {PlaybackState.COMPLETED, PlaybackState.ABORTED}:
            self._playback_timer.stop()
        self.changed.emit(self.trajectory)

    def _send_point(self, raw: TrajectoryPoint) -> None:
        from zeroarm_desktop.application.device_session import DeviceSession

        session = getattr(self._session_provider, "session", None)
        if not isinstance(session, DeviceSession):
            raise RuntimeError("Mock Session不可用")
        if raw.gripper_u16 is None:
            raise ValueError("回放点缺少gripper值")
        session.send_joint_target(JointTarget(raw.joint_urad, 20, raw.gripper_u16))
