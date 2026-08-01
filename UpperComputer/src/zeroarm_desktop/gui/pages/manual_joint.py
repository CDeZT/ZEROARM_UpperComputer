"""Mock-only manual joint page with preview, Arm, send, and hold controls."""

import math

from PySide6.QtCore import QEvent, Qt, Slot
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from zeroarm_desktop.gui.viewmodels.manual_joint import ManualJointViewModel


class ManualJointPage(QWidget):
    def __init__(self, view_model: ManualJointViewModel) -> None:
        super().__init__()
        self.setObjectName("page_manual_joint")
        self.view_model = view_model
        title = QLabel("手动关节控制 (Mock Only)")
        title.setObjectName("page_title")
        self.axis = QComboBox()
        self.axis.setObjectName("manual_axis")
        self.axis.addItems([f"J{index + 1}" for index in view_model.available_axes])
        self._axis_to_index = {
            index: position for position, index in enumerate(view_model.available_axes)
        }
        self.mode = QComboBox()
        self.mode.setObjectName("target_mode")
        self.mode.addItems(["相对", "绝对"])
        self.value = QDoubleSpinBox()
        self.value.setObjectName("target_degrees")
        self.value.setRange(-360, 360)
        self.value.setDecimals(3)
        self.value.setValue(1.0)
        form = QFormLayout()
        form.addRow("关节", self.axis)
        form.addRow("目标方式", self.mode)
        form.addRow("角度 (deg)", self.value)

        preview = QPushButton("预览 Ghost")
        preview.setObjectName("preview_joint_button")
        preview.clicked.connect(self.preview)
        arm = QPushButton("Arm 5秒")
        arm.setObjectName("arm_joint_button")
        arm.clicked.connect(self.arm)
        send = QPushButton("发送到 Mock")
        send.setObjectName("send_joint_button")
        send.clicked.connect(self.send)
        action_row = QHBoxLayout()
        action_row.addWidget(preview)
        action_row.addWidget(arm)
        action_row.addWidget(send)

        negative = QPushButton("按住负向点动")
        negative.setObjectName("hold_negative")
        positive = QPushButton("按住正向点动")
        positive.setObjectName("hold_positive")
        negative.pressed.connect(lambda: self.start_hold(-1))
        positive.pressed.connect(lambda: self.start_hold(1))
        negative.released.connect(lambda: view_model.stop_hold("mouse_release"))
        positive.released.connect(lambda: view_model.stop_hold("mouse_release"))
        hold_row = QHBoxLayout()
        hold_row.addWidget(negative)
        hold_row.addWidget(positive)
        self.status = QLabel("选择Operator模式并连接Mock后可预览")
        self.status.setObjectName("manual_joint_status")
        self.status.setWordWrap(True)
        view_model.status_changed.connect(self.status.setText)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addLayout(action_row)
        layout.addLayout(hold_row)
        layout.addWidget(self.status)
        layout.addWidget(QLabel("所有动作经过统一SafetyGate | Serial连接始终只读。"))
        layout.addStretch()

    @Slot()
    def preview(self) -> None:
        self._guard(
            lambda: self.view_model.preview(
                self._axis_to_index[self.axis.currentIndex()],
                round(math.radians(self.value.value()) * 1_000_000),
                relative=self.mode.currentText() == "相对",
            )
        )

    @Slot()
    def arm(self) -> None:
        self._guard(self.view_model.arm)

    @Slot()
    def send(self) -> None:
        self._guard(self.view_model.send)

    def start_hold(self, direction: int) -> None:
        step = max(1, round(math.radians(abs(self.value.value())) * 1_000_000))
        self.view_model.start_hold(self._axis_to_index[self.axis.currentIndex()], direction, step)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.EnabledChange and not self.isEnabled():
            self.view_model.stop_hold("page_disabled")
        super().changeEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self.view_model.stop_hold("focus_loss")
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.view_model.stop_hold("escape")
            event.accept()
            return
        super().keyPressEvent(event)

    def _guard(self, operation: object) -> None:
        try:
            if callable(operation):
                operation()
        except (PermissionError, RuntimeError, ValueError) as error:
            self.status.setText(str(error))
