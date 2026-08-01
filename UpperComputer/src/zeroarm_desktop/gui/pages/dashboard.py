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
        self.profile = QLabel("PROFILE --")
        self.profile.setObjectName("dashboard_profile")
        self.readiness = QLabel("READINESS --")
        self.readiness.setObjectName("dashboard_readiness")
        self.fault_names = QLabel("FAULT 位 --")
        self.fault_names.setObjectName("dashboard_fault_names")
        self.freshness = QLabel("新鲜度 --")
        self.freshness.setObjectName("dashboard_freshness")
        self.auto_home = QLabel("")
        self.auto_home.setObjectName("dashboard_auto_home")
        self.joint_labels = [QLabel(f"J{index}: --") for index in range(1, 7)]
        grid = QGridLayout()
        for index, label in enumerate(self.joint_labels):
            label.setObjectName(f"dashboard_joint_{index + 1}")
            grid.addWidget(label, index // 3, index % 3)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(title)
        layout.addWidget(self.run_state)
        layout.addWidget(self.profile)
        layout.addWidget(self.readiness)
        layout.addWidget(self.fault)
        layout.addWidget(self.fault_names)
        layout.addWidget(self.freshness)
        layout.addWidget(self.auto_home)
        layout.addLayout(grid)
        self.session_metrics = QLabel("会话指标 --")
        self.session_metrics.setObjectName("dashboard_session_metrics")
        layout.addWidget(self.session_metrics)
        layout.addWidget(QLabel("3D / 监控 / 手动 / 轨迹 / 示教 已接入 | 状态来自 V1 快照。"))
        layout.addStretch()
        view_model.state_changed.connect(self.apply_state)

    def set_session_metrics(self, text: str) -> None:
        self.session_metrics.setText(text)

    @Slot(object)
    def apply_state(self, state: SnapshotViewState) -> None:
        self.run_state.setText(f"运行状态: {state.run_state_text}")
        fault = "--" if state.fault_flags_raw is None else f"0x{state.fault_flags_raw:08X}"
        self.fault.setText(f"FAULT {fault}")
        readiness = state.readiness
        if readiness is None:
            self.profile.setText("PROFILE --")
            self.readiness.setText("READINESS 未连接")
            self.fault_names.setText("FAULT 位 --")
            self.freshness.setText("新鲜度 --")
            self.auto_home.setText("")
        else:
            self.profile.setText(
                "PROFILE zeroarm_g474_v1_partial | 可用 J1/J3/J4/J5 | J2/J6 Unavailable"
            )
            authorized = "运动已授权" if readiness.motion_authorized else "运动未授权"
            homed = "已回零" if readiness.homed_complete else "未回零"
            reset = " | RESET-REQUIRED" if readiness.reset_required else ""
            self.readiness.setText(f"READINESS {authorized} | {homed}{reset}")
            known = ", ".join(state.fault_names) if state.fault_names else "无"
            unknown = (
                f" | 未知位 0x{state.fault_unknown_bits:X}" if state.fault_unknown_bits else ""
            )
            self.fault_names.setText(f"FAULT 位 {known}{unknown}")
            age = "--" if state.snapshot_age_ms is None else f"{state.snapshot_age_ms} ms"
            self.freshness.setText(f"新鲜度 {age}")
            self.auto_home.setText(state.auto_home_warning or "")
        for label, joint in zip(self.joint_labels, state.joints, strict=False):
            if joint.index - 1 in state.unavailable_axes:
                label.setText(f"J{joint.index}  Unavailable")
                continue
            label.setText(
                f"J{joint.index}  目标 {joint.target_urad / 1_000_000:.3f} rad  "
                f"实际 {joint.actual_urad / 1_000_000:.3f} rad  误差 {joint.error_urad} urad"
            )
