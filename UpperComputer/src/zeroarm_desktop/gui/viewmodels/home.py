"""HOME 0x1D wizard ViewModel: preview, arm, execute, and progress observation."""

from time import monotonic_ns

from PySide6.QtCore import QObject, QTimer, Signal

from zeroarm_desktop.application.device_session import DeviceSession, SessionState
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

HOME_SEQUENCE = ("J5", "J4", "J3", "J1")
"""Fixed homing order for mask 0x1D (MCU homing.c, descending joint index)."""


class HomeExecutor:
    def __init__(self, session_provider: object) -> None:
        self._session_provider = session_provider

    def execute(self, intent: CommandIntent) -> object:
        session = getattr(self._session_provider, "session", None)
        if not isinstance(session, DeviceSession):
            raise RuntimeError("Session 不可用")
        if intent.family is CommandFamily.FAULT_CLEAR:
            return session.send_clear_fault()
        return session.send_home(intent.joint_mask)


class HomeViewModel(QObject):
    status_changed = Signal(str)
    homed_changed = Signal(int)

    def __init__(self, session_provider: object) -> None:
        super().__init__()
        self._provider = session_provider
        self._profile = HardwareProfile.default()
        self._service = CommandService(SafetyGate(), HomeExecutor(session_provider))
        self._preview: CommandPreview | None = None
        self._arm: ArmContext | None = None
        self._mode = AppMode.OBSERVER
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(100)
        self._watch_timer.timeout.connect(self._watch_tick)

    def set_mode(self, mode: AppMode) -> None:
        self._service.disarm("mode_changed")
        self._preview = None
        self._arm = None
        self._mode = mode

    def start_home(self) -> None:
        try:
            session = self._session()
            snapshot = session.latest_snapshot
            if snapshot is None:
                raise RuntimeError("设备状态不可用")
            if snapshot.homed_mask is not None and snapshot.homed_mask == self._profile.home_mask:
                self.status_changed.emit("已处于回零完成状态 (homed 0x1D)")
                return
            intent = CommandIntent(CommandFamily.HOME, joint_mask=self._profile.home_mask)
            context = self._context()
            preview = self._service.preview(intent, context)
            if not preview.decision.allowed:
                self.status_changed.emit("拒绝: " + ", ".join(preview.decision.denials))
                return
            arm = self._service.arm(preview, context)
            self._service.execute(preview, arm, context)
            self._preview = None
            self._arm = None
            self.status_changed.emit(f"已请求回零 0x1D | 顺序 {(' -> '.join(HOME_SEQUENCE))}")
            self._watch_timer.start()
        except (PermissionError, RuntimeError, ValueError) as error:
            self.status_changed.emit(f"回零失败: {error}")

    def clear_fault(self) -> None:
        try:
            self._session()
            intent = CommandIntent(CommandFamily.FAULT_CLEAR)
            context = self._context()
            preview = self._service.preview(intent, context)
            if not preview.decision.allowed:
                self.status_changed.emit("拒绝: " + ", ".join(preview.decision.denials))
                return
            arm = self._service.arm(preview, context)
            result = self._service.execute(preview, arm, context)
            raw = getattr(result, "raw_value", "n/a")
            self.status_changed.emit(f"已发送 CLEAR_FAULT | 结果 raw={raw}")
            self._watch_timer.start()
        except (PermissionError, RuntimeError, ValueError) as error:
            self.status_changed.emit(f"清除故障失败: {error}")

    @property
    def watching(self) -> bool:
        return self._watch_timer.isActive()

    def _watch_tick(self) -> None:
        try:
            session = self._session()
        except (PermissionError, RuntimeError) as error:
            self._watch_timer.stop()
            self.status_changed.emit(f"监控停止: {error}")
            return
        snapshot = session.latest_snapshot
        if snapshot is None:
            return
        homed = snapshot.homed_mask or 0
        self.homed_changed.emit(homed)
        state = snapshot.run_state_raw
        if state == 1 and homed == self._profile.home_mask:
            self._watch_timer.stop()
            self.status_changed.emit("回零完成 | homed 0x1D | 运动授权恢复")
        elif state == 5:
            self._watch_timer.stop()
            self.status_changed.emit(
                f"故障: 0x{snapshot.fault_flags_raw:08X} | RESET-REQUIRED 需复位 MCU"
                if snapshot.fault_flags_raw & 0x0E00
                else f"故障: 0x{snapshot.fault_flags_raw:08X} | 可尝试清除故障"
            )

    def _session(self) -> DeviceSession:
        session = getattr(self._provider, "session", None)
        if not isinstance(session, DeviceSession):
            raise RuntimeError("请先连接设备")
        if not session.actions_allowed:
            raise PermissionError("真实Serial保持只读 | 回零仅允许Mock")
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
            False,
            False,
            True,
        )
