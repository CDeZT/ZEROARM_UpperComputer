"""Read-only system overview page."""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from zeroarm_desktop.gui.viewmodels.snapshot import SnapshotViewModel, SnapshotViewState


class DashboardPage(QWidget):
    def __init__(self, view_model: SnapshotViewModel) -> None:
        super().__init__()
        self.setObjectName("page_dashboard")
        title = QLabel("系统总览")
        title.setObjectName("page_title")
        self.run_state = QLabel("未连接")
        self.run_state.setObjectName("dashboard_run_state")
        self.fault = QLabel("FAULT --")
        self.joint_labels = [QLabel(f"J{index}: --") for index in range(1, 7)]
        grid = QGridLayout()
        for index, label in enumerate(self.joint_labels):
            label.setObjectName(f"dashboard_joint_{index + 1}")
            grid.addWidget(label, index // 3, index % 3)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(title)
        layout.addWidget(self.run_state)
        layout.addWidget(self.fault)
        layout.addLayout(grid)
        layout.addWidget(QLabel("3D 工作区将在单元12加载 | 当前仅展示协议真实状态。"))
        layout.addStretch()
        view_model.state_changed.connect(self.apply_state)

    @Slot(object)
    def apply_state(self, state: SnapshotViewState) -> None:
        self.run_state.setText(f"运行状态: {state.run_state_text}")
        fault = "--" if state.fault_flags_raw is None else f"0x{state.fault_flags_raw:08X}"
        self.fault.setText(f"FAULT {fault}")
        for label, joint in zip(self.joint_labels, state.joints, strict=False):
            label.setText(
                f"J{joint.index}  目标 {joint.target_urad / 1_000_000:.3f} rad  "
                f"实际 {joint.actual_urad / 1_000_000:.3f} rad  误差 {joint.error_urad} urad"
            )
