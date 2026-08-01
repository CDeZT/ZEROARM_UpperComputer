"""Local calibration candidate view aligned with HOME wizard and profile."""

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from zeroarm_desktop.domain.calibration import DEFAULT_CALIBRATION, calibration_to_json
from zeroarm_desktop.domain.hardware_profile import HardwareProfile
from zeroarm_desktop.gui.viewmodels.home import HOME_SEQUENCE, HomeViewModel
from zeroarm_desktop.infrastructure.paths import default_data_root


class CalibrationPage(QWidget):
    def __init__(self, home_view_model: HomeViewModel) -> None:
        super().__init__()
        self.setObjectName("page_calibration")
        self.home_view_model = home_view_model
        profile = HardwareProfile.default()
        title = QLabel("标定与 Homing")
        title.setObjectName("page_title")
        subtitle = QLabel(
            "V1 不支持读写固件标定 | 本机候选可导出 | 真实回零走下方 HOME 0x1D (仅 Mock)"
        )
        subtitle.setWordWrap(True)
        self.status = QLabel("等待操作")
        self.status.setObjectName("calibration_status")
        self.status.setWordWrap(True)
        checksum = QLabel(f"候选配置 checksum: {DEFAULT_CALIBRATION.checksum[:16]}…")
        checksum.setObjectName("calibration_checksum")
        axes = QLabel(
            "Profile 可用轴: "
            + ", ".join(
                f"J{c.index + 1}[{c.min_urad // 17453}°..{c.max_urad // 17453}°]"
                if not c.continuous
                else f"J{c.index + 1} continuous"
                for c in profile.capabilities
                if c.available
            )
            + " | J2/J6 Unavailable"
        )
        axes.setWordWrap(True)
        order = QLabel(
            "HOME 顺序: " + " → ".join(HOME_SEQUENCE) + f" | mask 0x{profile.home_mask:02X}"
        )
        order.setObjectName("calibration_home_order")
        save = QPushButton("导出本机候选 JSON")
        save.setObjectName("save_calibration_candidate")
        save.clicked.connect(self.export_candidate)
        write = QPushButton("写入固件 (V1 不支持)")
        write.setObjectName("write_calibration_firmware")
        write.setEnabled(False)
        home = QPushButton("请求 Mock HOME 0x1D")
        home.setObjectName("mock_home_button")
        home.clicked.connect(self.start_home)
        home_view_model.status_changed.connect(self.status.setText)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        for widget in (title, subtitle, checksum, axes, order, save, write, home, self.status):
            layout.addWidget(widget)
        layout.addStretch()

    def export_candidate(self) -> None:
        path = default_data_root() / "calibration" / "candidate_v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(calibration_to_json(DEFAULT_CALIBRATION), encoding="utf-8")
        self.status.setText(f"本机候选已导出: {path.name} | 未写入固件")

    def start_home(self) -> None:
        self.home_view_model.start_home()
