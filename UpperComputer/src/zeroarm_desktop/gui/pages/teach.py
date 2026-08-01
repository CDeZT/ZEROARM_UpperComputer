"""Teach page: axis mask, support checklist, Arm, record, stop review."""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from zeroarm_desktop.gui.viewmodels.teach import TeachViewModel


class TeachPage(QWidget):
    def __init__(self, view_model: TeachViewModel) -> None:
        super().__init__()
        self.setObjectName("page_teach")
        self.view_model = view_model
        title = QLabel("拖动示教 (Mock)")
        title.setObjectName("page_title")
        subtitle = QLabel(
            "仅可用轴 J1/J3/J4/J5 | 必须确认支撑 | TEACH_STOP 后保持失能且不自动 ENABLE"
        )
        subtitle.setWordWrap(True)

        self.axis_boxes: list[QCheckBox] = []
        axis_row = QHBoxLayout()
        axis_row.addWidget(QLabel("示教轴:"))
        for axis in view_model.available_axes:
            box = QCheckBox(f"J{axis + 1}")
            box.setObjectName(f"teach_axis_j{axis + 1}")
            box.setChecked(True)
            box.stateChanged.connect(self._mask_changed)
            self.axis_boxes.append(box)
            axis_row.addWidget(box)
        axis_row.addStretch()

        self.support = QCheckBox("已确认重力轴支撑 / 急停 / 工作空间无人")
        self.support.setObjectName("teach_support_confirmed")
        self.support.stateChanged.connect(
            lambda _value: view_model.set_support_confirmed(self.support.isChecked())
        )

        preview = QPushButton("预览")
        preview.setObjectName("teach_preview_button")
        preview.clicked.connect(self.preview)
        arm = QPushButton("Arm 5秒")
        arm.setObjectName("teach_arm_button")
        arm.clicked.connect(self.arm)
        start = QPushButton("开始示教")
        start.setObjectName("teach_start_button")
        start.clicked.connect(self.start)
        stop = QPushButton("停止并 Review")
        stop.setObjectName("teach_stop_button")
        stop.clicked.connect(self.stop)
        action_row = QHBoxLayout()
        for button in (preview, arm, start, stop):
            action_row.addWidget(button)

        self.name_input = QLineEdit("teach_raw")
        self.name_input.setObjectName("teach_trajectory_name")
        save = QPushButton("另存为轨迹")
        save.setObjectName("teach_save_button")
        save.clicked.connect(self.save)
        reset = QPushButton("重置")
        reset.setObjectName("teach_reset_button")
        reset.clicked.connect(self.reset)
        save_row = QHBoxLayout()
        save_row.addWidget(self.name_input, 1)
        save_row.addWidget(save)
        save_row.addWidget(reset)

        self.state = QLabel("状态: idle")
        self.state.setObjectName("teach_state")
        self.stats = QLabel("samples=0 | dropped=0 | Hz=--")
        self.stats.setObjectName("teach_stats")
        self.status = QLabel("选择 Operator 模式、连接 Mock、确认支撑后可预览")
        self.status.setObjectName("teach_status")
        self.status.setWordWrap(True)
        self.review = QLabel("Review: --")
        self.review.setObjectName("teach_review")
        self.review.setWordWrap(True)

        view_model.status_changed.connect(self.status.setText)
        view_model.state_changed.connect(lambda value: self.state.setText(f"状态: {value}"))
        view_model.stats_changed.connect(self.stats.setText)
        view_model.review_changed.connect(
            lambda text: self.review.setText(f"Review: {text or '--'}")
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        for widget in (title, subtitle):
            layout.addWidget(widget)
        layout.addLayout(axis_row)
        layout.addWidget(self.support)
        layout.addLayout(action_row)
        layout.addLayout(save_row)
        for widget in (self.state, self.stats, self.status, self.review):
            layout.addWidget(widget)
        layout.addWidget(QLabel("raw 记录只追加不覆盖 | 处理后轨迹另存并记录 parent_raw_sha256。"))
        layout.addStretch()
        self._mask_changed()

    @Slot()
    def preview(self) -> None:
        self._guard(self.view_model.preview)

    @Slot()
    def arm(self) -> None:
        self._guard(self.view_model.arm)

    @Slot()
    def start(self) -> None:
        self._guard(self.view_model.start)

    @Slot()
    def stop(self) -> None:
        self._guard(self.view_model.stop)

    @Slot()
    def save(self) -> None:
        self._guard(
            lambda: self.view_model.save_trajectory(self.name_input.text().strip() or "teach_raw")
        )

    @Slot()
    def reset(self) -> None:
        self._guard(self.view_model.reset)

    def _mask_changed(self) -> None:
        mask = 0
        for box in self.axis_boxes:
            if box.isChecked():
                axis = int(box.text()[1:]) - 1
                mask |= 1 << axis
        try:
            if mask == 0:
                self.status.setText("至少选择一个可用轴")
                return
            self.view_model.set_joint_mask(mask)
        except (RuntimeError, ValueError) as error:
            self.status.setText(str(error))

    def _guard(self, operation: object) -> None:
        try:
            if callable(operation):
                operation()
        except (PermissionError, RuntimeError, ValueError) as error:
            self.status.setText(str(error))
