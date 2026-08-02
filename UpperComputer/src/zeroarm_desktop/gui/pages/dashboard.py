"""Read-only system overview page."""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from zeroarm_desktop.domain.hardware_profile import HardwareProfile
from zeroarm_desktop.gui.viewmodels.snapshot import SnapshotViewModel, SnapshotViewState


class DashboardPage(QWidget):
    def __init__(self, view_model: SnapshotViewModel) -> None:
        super().__init__()
        self.setObjectName("page_dashboard")
        title = QLabel("系统总览")
        title.setObjectName("page_title")
        subtitle = QLabel("设备健康、运动授权和六轴偏差的单屏概览")
        subtitle.setObjectName("page_subtitle")
        self.run_state = QLabel("未连接")
        self.run_state.setObjectName("dashboard_run_state")
        self.run_state.setWordWrap(True)
        self.fault = QLabel("FAULT --")
        self.fault.setObjectName("dashboard_fault")
        self.fault.setWordWrap(True)
        self.profile = QLabel("PROFILE --")
        self.profile.setObjectName("dashboard_profile")
        self.readiness = QLabel("READINESS --")
        self.readiness.setObjectName("dashboard_readiness")
        self.readiness.setWordWrap(True)
        self.fault_names = QLabel("FAULT 位 --")
        self.fault_names.setObjectName("dashboard_fault_names")
        self.freshness = QLabel("新鲜度 --")
        self.freshness.setObjectName("dashboard_freshness")
        self.auto_home = QLabel("")
        self.auto_home.setObjectName("dashboard_auto_home")
        self.auto_home.setVisible(False)
        summary = QGridLayout()
        summary.setSpacing(12)
        self.state_card = self._status_card(
            "dashboard_state_card", "运行状态", self.run_state
        )
        self.readiness_card = self._status_card(
            "dashboard_readiness_card", "运动授权", self.readiness
        )
        self.fault_card = self._status_card(
            "dashboard_fault_card", "故障", self.fault
        )
        self.freshness_card = self._status_card(
            "dashboard_freshness_card", "快照", self.freshness
        )
        for column, card in enumerate(
            (self.state_card, self.readiness_card, self.fault_card, self.freshness_card)
        ):
            summary.addWidget(card, 0, column)
            summary.setColumnStretch(column, 1)

        profile_card = QFrame()
        profile_card.setObjectName("dashboard_profile_card")
        profile_card.setProperty("class", "status_card")
        profile_card.setMaximumHeight(76)
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.setContentsMargins(14, 12, 14, 12)
        profile_layout.addWidget(self.profile)
        profile_layout.addWidget(self.fault_names)

        self.joint_labels = [QLabel(f"J{index}: --") for index in range(1, 7)]
        joint_grid = QGridLayout()
        joint_grid.setSpacing(12)
        for index, label in enumerate(self.joint_labels):
            label.setObjectName(f"dashboard_joint_{index + 1}")
            label.setWordWrap(True)
            card = QFrame()
            card.setObjectName(f"dashboard_joint_card_{index + 1}")
            card.setProperty("class", "metric_card")
            card.setMinimumHeight(58)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.addWidget(label)
            joint_grid.addWidget(card, index // 3, index % 3)
            joint_grid.setColumnStretch(index % 3, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(summary)
        layout.addWidget(profile_card)
        layout.addWidget(self.auto_home)
        layout.addLayout(joint_grid)
        self.session_metrics = QLabel("会话指标 --")
        self.session_metrics.setObjectName("dashboard_session_metrics")
        layout.addWidget(self.session_metrics)
        layout.addStretch()
        view_model.state_changed.connect(self.apply_state)

    @staticmethod
    def _status_card(object_name: str, caption: str, value: QLabel) -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        card.setProperty("class", "status_card")
        card.setProperty("tone", "neutral")
        card.setMinimumHeight(92)
        card.setMaximumHeight(112)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        caption_label = QLabel(caption)
        caption_label.setObjectName("dashboard_card_caption")
        value.setProperty("class", "dashboard_card_value")
        card_layout.addWidget(caption_label)
        card_layout.addWidget(value)
        return card

    def set_session_metrics(self, text: str) -> None:
        self.session_metrics.setText(text)

    @Slot(object)
    def apply_state(self, state: SnapshotViewState) -> None:
        self.run_state.setText(f"运行状态: {state.run_state_text}")
        fault = "--" if state.fault_flags_raw is None else f"0x{state.fault_flags_raw:08X}"
        self.fault.setText(f"FAULT {fault}")
        self._set_tone(self.state_card, "danger" if "FAULT" in state.run_state_text else "ok")
        self._set_tone(
            self.fault_card,
            "danger" if state.fault_flags_raw not in {None, 0} else "ok",
        )
        readiness = state.readiness
        if readiness is None:
            self.profile.setText("PROFILE --")
            self.readiness.setText("READINESS 未连接")
            self.fault_names.setText("FAULT 位 --")
            self.freshness.setText("新鲜度 --")
            self.auto_home.setText("")
            self.auto_home.setVisible(False)
        else:
            profile = HardwareProfile.default()
            available = "/".join(
                f"J{capability.index + 1}"
                for capability in profile.capabilities
                if capability.available
            )
            unavailable = "/".join(
                f"J{capability.index + 1}"
                for capability in profile.capabilities
                if not capability.available
            )
            self.profile.setText(
                f"PROFILE {profile.profile_id} | 可用 {available} | "
                f"{unavailable or '无'} Unavailable"
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
            auto_home_text = state.auto_home_warning or ""
            self.auto_home.setText(auto_home_text)
            self.auto_home.setVisible(bool(auto_home_text))
            self._set_tone(
                self.readiness_card,
                "ok" if readiness.motion_authorized else "warning",
            )
        for label, joint in zip(self.joint_labels, state.joints, strict=False):
            if joint.index - 1 in state.unavailable_axes:
                label.setText(f"J{joint.index}  Unavailable")
                continue
            label.setText(
                f"J{joint.index}  目标 {joint.target_urad / 1_000_000:.3f} rad  "
                f"实际 {joint.actual_urad / 1_000_000:.3f} rad  误差 {joint.error_urad} urad"
            )

    @staticmethod
    def _set_tone(card: QFrame, tone: str) -> None:
        if card.property("tone") == tone:
            return
        card.setProperty("tone", tone)
        card.style().unpolish(card)
        card.style().polish(card)
