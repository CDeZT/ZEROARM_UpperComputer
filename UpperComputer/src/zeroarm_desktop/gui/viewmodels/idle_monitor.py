"""Desktop operator-idle auto-HOME monitor (R8).

Distinct from the MCU link-silence auto-home: this timer counts *user action*
idle (20 s) on the Desktop side, independent of GET_STATE polling. When it
fires and the session is authorized (Mock), it triggers the HOME wizard's
SafetyGate path with mask 0x1D. Read-only Serial sessions never auto-send.
"""

import math
from time import monotonic_ns

from PySide6.QtCore import QObject, QTimer, Signal

from zeroarm_desktop.application.device_session import DeviceSession
from zeroarm_desktop.gui.viewmodels.home import HomeViewModel

OPERATOR_IDLE_TIMEOUT_MS = 20_000
TICK_INTERVAL_MS = 500


class OperatorIdleHomeMonitor(QObject):
    countdown_changed = Signal(int)
    home_triggered = Signal(str)

    def __init__(
        self,
        session_provider: object,
        home_view_model: HomeViewModel,
        *,
        idle_timeout_ms: int = OPERATOR_IDLE_TIMEOUT_MS,
    ) -> None:
        super().__init__()
        self._provider = session_provider
        self._home = home_view_model
        self._timeout_ms = idle_timeout_ms
        self._deadline_ns: int | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

    @property
    def active(self) -> bool:
        return self._timer.isActive()

    def start(self) -> None:
        self.note_activity()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self._deadline_ns = None

    def note_activity(self) -> None:
        self._deadline_ns = monotonic_ns() + self._timeout_ms * 1_000_000
        self.countdown_changed.emit(self._remaining_s())

    def _remaining_s(self) -> int:
        if self._deadline_ns is None:
            return 0
        return max(0, math.ceil((self._deadline_ns - monotonic_ns()) / 1_000_000_000))

    def _tick(self) -> None:
        remaining = self._remaining_s()
        if remaining > 0:
            self.countdown_changed.emit(remaining)
            return
        session = getattr(self._provider, "session", None)
        if not isinstance(session, DeviceSession) or not session.actions_allowed:
            self.home_triggered.emit("自动回零跳过: 会话非动作授权 (Serial 只读)")
            self.note_activity()
            return
        snapshot = session.latest_snapshot
        if (
            snapshot is not None
            and snapshot.run_state_raw == 1
            and snapshot.fault_flags_raw == 0
            and (snapshot.homed_mask or 0) == 0x1D
        ):
            self.home_triggered.emit("自动回零跳过: 已处于回零完成")
            self.note_activity()
            return
        self.home_triggered.emit("Desktop 空闲 20 秒: 触发自动回零 0x1D")
        self._home.start_home()
        self.note_activity()
