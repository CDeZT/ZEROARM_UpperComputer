"""Firmware update page with argument-array programmer invocation."""

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from zeroarm_desktop.application.firmware import (
    FlashRequest,
    build_programmer_command,
    inspect_firmware_artifact,
)


class FirmwarePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page_firmware")
        title = QLabel("固件升级工具")
        title.setObjectName("page_title")
        self.tool_path = QLineEdit("STM32_Programmer_CLI.exe")
        self.tool_path.setObjectName("firmware_tool_path")
        self.artifact_path = QLineEdit("build/Debug/zero_arm_mcu.elf")
        self.artifact_path.setObjectName("firmware_artifact_path")
        browse = QPushButton("浏览…")
        browse.setObjectName("browse_firmware_button")
        browse.clicked.connect(self.browse_artifact)
        artifact_row = QHBoxLayout()
        artifact_row.addWidget(self.artifact_path, 1)
        artifact_row.addWidget(browse)
        self.expected_hash = QLineEdit()
        self.expected_hash.setObjectName("firmware_expected_hash")
        self.stlink_sn = QLineEdit()
        self.stlink_sn.setObjectName("firmware_stlink_sn")
        inspect = QPushButton("检查固件文件")
        inspect.setObjectName("inspect_firmware_button")
        inspect.clicked.connect(self.inspect_artifact)
        dry_run = QPushButton("构造参数数组 (不执行)")
        dry_run.setObjectName("dry_run_firmware_button")
        dry_run.clicked.connect(self.dry_run)
        self.status = QLabel("仅支持参数数组调用 | 禁止shell拼接 | 当前默认不自动刷写")
        self.status.setObjectName("firmware_status")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        for widget in (
            title,
            QLabel("Programmer"),
            self.tool_path,
        ):
            layout.addWidget(widget)
        layout.addWidget(QLabel("Artifact"))
        layout.addLayout(artifact_row)
        for item in (
            QLabel("Expected SHA-256"),
            self.expected_hash,
            QLabel("ST-Link SN"),
            self.stlink_sn,
            inspect,
            dry_run,
            self.status,
        ):
            layout.addWidget(item)
        layout.addStretch()

    def browse_artifact(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择固件文件",
            self.artifact_path.text() or str(Path.cwd()),
            "固件 (*.elf *.bin *.hex);;所有文件 (*)",
        )
        if path:
            self.artifact_path.setText(path)
            self.status.setText("已选择固件文件 | 点击「检查固件文件」计算 SHA-256")

    def inspect_artifact(self) -> None:
        try:
            artifact = inspect_firmware_artifact(Path(self.artifact_path.text()))
            self.expected_hash.setText(artifact.sha256)
            self.status.setText(
                f"固件OK | size={artifact.size} | ext={artifact.extension} | sha256已填充"
            )
        except (OSError, ValueError) as error:
            self.status.setText(str(error))

    def dry_run(self) -> None:
        try:
            artifact = inspect_firmware_artifact(Path(self.artifact_path.text()))
            expected = self.expected_hash.text().strip() or artifact.sha256
            request = FlashRequest(
                artifact,
                expected,
                Path(self.tool_path.text()),
                "STM32G474",
                self.stlink_sn.text().strip() or None,
                True,
                True,
            )
            command = build_programmer_command(request)
            self.status.setText("命令: " + " | ".join(command))
        except (OSError, ValueError) as error:
            self.status.setText(str(error))
