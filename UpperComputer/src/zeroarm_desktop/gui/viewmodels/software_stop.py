"""Safety-gated software STOP command for the global shell control."""

from time import monotonic_ns

from PySide6.QtCore import QObject, Signal

from zeroarm_desktop.application.device_session import DeviceSession
from zeroarm_desktop.domain.safety import (
    AppMode,
    CommandFamily,
    CommandIntent,
    SafetyContext,
    SafetyGate,
)


class SoftwareStopViewModel(QObject):
    """Send STOP without an Arm step; STOP must remain available in Observer mode."""

    status_changed = Signal(str)

    def __init__(self, session_provider: object) -> None:
        super().__init__()
        self._provider = session_provider
        self._gate = SafetyGate()

    def request_stop(self) -> bool:
        session = getattr(self._provider, "session", None)
        if not isinstance(session, DeviceSession):
            self.status_changed.emit("软件 STOP | 本地调度已停止 | 当前无设备会话")
            return False
        if not session.actions_allowed:
            self.status_changed.emit("软件 STOP | 本地调度已停止 | Serial 只读，未发送设备命令")
            return False
        context = SafetyContext(
            session.state,
            AppMode.OBSERVER,
            session.latest_snapshot,
            monotonic_ns(),
            500_000_000,
            None,
            False,
            False,
            False,
            True,
        )
        decision = self._gate.evaluate(CommandIntent(CommandFamily.STOP), context)
        if not decision.allowed:
            self.status_changed.emit("软件 STOP 拒绝: " + ", ".join(decision.denials))
            return False
        try:
            result = session.send_stop()
        except (PermissionError, RuntimeError, ValueError) as error:
            self.status_changed.emit(f"软件 STOP 发送失败: {error} | 结果未知")
            return False
        raw = getattr(result, "raw_value", "n/a")
        self.status_changed.emit(f"软件 STOP 已发送 | V1 result={raw} | 不是机械急停")
        return True
