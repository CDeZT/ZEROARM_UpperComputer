"""HOME 0x1D wizard page: order display, progress, reset-required hints."""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from zeroarm_desktop.gui.viewmodels.home import HOME_SEQUENCE, HomeViewModel


class HomePage(QWidget):
    def __init__(self, view_model: HomeViewModel) -> None:
        super().__init__()
        self.setObjectName("page_home")
        title = QLabel("回零向导 (HOME 0x1D)")
        title.setObjectName("page_title")
        self.order = QLabel("顺序: " + " → ".join(HOME_SEQUENCE))
        self.order.setObjectName("home_order")
        self.status = QLabel("未连接 | 仅 Mock 会话可执行")
        self.status.setObjectName("home_status")
        self.progress = QLabel("已回零: --")
        self.progress.setObjectName("home_progress")
        start = QPushButton("开始回零 0x1D")
        start.setObjectName("home_start_button")
        start.clicked.connect(view_model.start_home)
        clear = QPushButton("清除可清除故障 (CLEAR_FAULT)")
        clear.setObjectName("home_clear_fault_button")
        clear.clicked.connect(view_model.clear_fault)
        actions = QHBoxLayout()
        actions.addWidget(start)
        actions.addWidget(clear)
        hint = QLabel(
            "说明: MCU 回零顺序固定 J5→J4→J3→J1, 回零期间运动未授权。"
            "STARTUP/HOMING/ESTOP 故障属 RESET-REQUIRED, CLEAR_FAULT 无法清除, 需复位 MCU。"
        )
        hint.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(title)
        layout.addWidget(self.order)
        layout.addWidget(self.progress)
        layout.addLayout(actions)
        layout.addWidget(self.status)
        layout.addWidget(hint)
        layout.addStretch()
        view_model.status_changed.connect(self.status.setText)
        view_model.homed_changed.connect(self._apply_homed)

    @Slot(int)
    def _apply_homed(self, homed: int) -> None:
        axes = " ".join(f"J{index}" for index in range(6) if homed & (1 << index))
        self.progress.setText(f"已回零: 0x{homed:02X} [{axes}]")
