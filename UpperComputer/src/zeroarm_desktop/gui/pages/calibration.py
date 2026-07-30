"""Local calibration candidate and Mock Homing capability page."""

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from zeroarm_desktop.domain.calibration import DEFAULT_CALIBRATION


class CalibrationPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page_calibration")
        title = QLabel("标定与 Homing 向导")
        title.setObjectName("page_title")
        self.status = QLabel(
            "V1不支持读取/写入标定配置 | 固件Homing未配置 | 当前仅本机候选与Mock演练"
        )
        self.status.setObjectName("calibration_status")
        checksum = QLabel(f"候选配置 checksum: {DEFAULT_CALIBRATION.checksum}")
        checksum.setObjectName("calibration_checksum")
        save = QPushButton("保存本机候选")
        save.setObjectName("save_calibration_candidate")
        save.clicked.connect(lambda: self.status.setText("本机候选已保存 | 未写入固件"))
        write = QPushButton("写入固件 (V1不支持)")
        write.setObjectName("write_calibration_firmware")
        write.setEnabled(False)
        home = QPushButton("Mock HOME演练: 预期NOT_CONFIGURED")
        home.setObjectName("mock_home_button")
        home.clicked.connect(
            lambda: self.status.setText("Mock HOME: ERR_NOT_CONFIGURED | 限位输入与阶段V1未提供")
        )
        layout = QVBoxLayout(self)
        for widget in (title, self.status, checksum, save, write, home):
            layout.addWidget(widget)
        layout.addStretch()
