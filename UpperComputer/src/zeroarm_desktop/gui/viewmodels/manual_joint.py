"""Mock-only manual joint preview, Arm, execution, and hold-to-run ViewModel."""

from time import monotonic_ns

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from zeroarm_desktop.application.device_session import DeviceSession
from zeroarm_desktop.domain.models import JointTarget
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


class SessionCommandExecutor:
    def __init__(self, session_provider: object) -> None:
        self._session_provider = session_provider

    def execute(self, intent: CommandIntent) -> object:
        session = getattr(self._session_provider, "session", None)
        if not isinstance(session, DeviceSession) or intent.target is None:
            raise RuntimeError("Mock Session is unavailable")
        return session.send_joint_target(intent.target)


class ManualJointViewModel(QObject):
    status_changed = Signal(str)
    ghost_target_changed = Signal(object)

    def __init__(self, session_provider: object) -> None:
        super().__init__()
        self._provider = session_provider
        self._service = CommandService(SafetyGate(), SessionCommandExecutor(session_provider))
        self._preview: CommandPreview | None = None
        self._arm: ArmContext | None = None
        self._mode = AppMode.OBSERVER
        self._hold_axis = 0
        self._hold_direction = 1
        self._hold_step_urad = 17_453
        self._hold_timer = QTimer(self)
        self._hold_timer.setInterval(20)
        self._hold_timer.timeout.connect(self._hold_tick)

    def set_mode(self, mode: AppMode) -> None:
        self.stop_hold("mode_changed")
        self._service.disarm("mode_changed")
        self._mode = mode

    def preview(self, axis: int, value_urad: int, *, relative: bool) -> CommandPreview:
        session = self._session()
        snapshot = session.latest_snapshot
        if snapshot is None:
            raise RuntimeError("设备状态不可用")
        target = list(snapshot.actual_joint_urad)
        target[axis] = target[axis] + value_urad if relative else value_urad
        intent = CommandIntent(
            CommandFamily.JOINT_TARGET,
            1 << axis,
            JointTarget(tuple(target), 100, 0),  # type: ignore[arg-type]
        )
        context = self._context(hold_active=False)
        preview = self._service.preview(intent, context)
        self._preview = preview
        self._arm = None
        assert intent.target is not None
        self.ghost_target_changed.emit(intent.target.joint_urad)
        self.status_changed.emit(
            "预览通过 | 可Arm发送"
            if preview.decision.allowed
            else "拒绝: " + ", ".join(preview.decision.denials)
        )
        return preview

    def arm(self) -> ArmContext:
        if self._preview is None:
            raise RuntimeError("请先预览")
        self._arm = self._service.arm(self._preview, self._context(hold_active=False))
        self.status_changed.emit("已Arm | 5秒内可发送")
        return self._arm

    def send(self) -> object:
        if self._preview is None or self._arm is None:
            raise RuntimeError("请先预览并Arm")
        result = self._service.execute(
            self._preview,
            self._arm,
            self._context(hold_active=False),
        )
        self._preview = None
        self._arm = None
        self.status_changed.emit("Mock已接受目标 | 等待状态反馈")
        return result

    def start_hold(self, axis: int, direction: int, step_urad: int) -> None:
        self._hold_axis = axis
        self._hold_direction = direction
        self._hold_step_urad = step_urad
        self._hold_timer.start()
        self._hold_tick()

    def stop_hold(self, reason: str) -> None:
        self._hold_timer.stop()
        self._service.disarm(reason)
        self._arm = None
        self.status_changed.emit(f"连续点动已停止: {reason}")

    @property
    def holding(self) -> bool:
        return self._hold_timer.isActive()

    @Slot()
    def _hold_tick(self) -> None:
        try:
            session = self._session()
            snapshot = session.latest_snapshot
            if snapshot is None:
                raise RuntimeError("状态不可用")
            target = list(snapshot.actual_joint_urad)
            target[self._hold_axis] += self._hold_direction * self._hold_step_urad
            intent = CommandIntent(
                CommandFamily.JOINT_TARGET,
                1 << self._hold_axis,
                JointTarget(tuple(target), 20, 0),  # type: ignore[arg-type]
                continuous=True,
            )
            context = self._context(hold_active=True)
            preview = self._service.preview(intent, context)
            arm = self._service.arm(preview, context)
            assert intent.target is not None
            self.ghost_target_changed.emit(intent.target.joint_urad)
            self._service.execute(preview, arm, context)
        except (PermissionError, RuntimeError, ValueError) as error:
            self.stop_hold(str(error))

    def _session(self) -> DeviceSession:
        session = getattr(self._provider, "session", None)
        if not isinstance(session, DeviceSession):
            raise RuntimeError("请先连接Mock")
        if not session.actions_allowed:
            raise PermissionError("真实Serial保持只读 | 手动动作仅允许Mock")
        return session

    def _context(self, *, hold_active: bool) -> SafetyContext:
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
            hold_active,
            True,
        )
