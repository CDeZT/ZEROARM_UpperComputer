"""Diagnostics page and safe read-only protocol console."""

from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget

from zeroarm_desktop.application.device_session import DeviceSession
from zeroarm_desktop.application.diagnostics import collect_diagnostics, create_diagnostic_bundle
from zeroarm_desktop.infrastructure.paths import default_data_root


class DiagnosticsPage(QWidget):
    def __init__(self, provider: object) -> None:
        super().__init__()
        self.setObjectName("page_diagnostics")
        self.provider = provider
        title = QLabel("诊断")
        title.setObjectName("page_title")
        self.text = QLabel("等待刷新")
        self.text.setObjectName("diagnostics_text")
        refresh = QPushButton("刷新诊断")
        refresh.setObjectName("refresh_diagnostics")
        refresh.clicked.connect(self.refresh)
        bundle = QPushButton("导出脱敏诊断包")
        bundle.setObjectName("export_diagnostic_bundle")
        bundle.clicked.connect(self.export)
        layout = QVBoxLayout(self)
        for widget in (title, refresh, bundle, self.text):
            layout.addWidget(widget)
        layout.addStretch()

    def refresh(self) -> None:
        snapshot = collect_diagnostics(getattr(self.provider, "session", None))
        self.text.setText(
            f"Session={snapshot.session_state} Firmware={snapshot.firmware or '--'}\n"
            f"SessionStats={snapshot.session_statistics}\nParserStats={snapshot.parser_statistics}\n"
            + "\n".join(snapshot.capability_gaps)
        )

    def export(self) -> None:
        path = default_data_root() / "diagnostics" / "zeroarm-diagnostics.zip"
        create_diagnostic_bundle(
            collect_diagnostics(getattr(self.provider, "session", None)),
            path,
        )
        self.text.setText(f"诊断包已导出: {path.name}")


class ProtocolConsolePage(QWidget):
    def __init__(self, provider: object) -> None:
        super().__init__()
        self.setObjectName("page_protocol_console")
        self.provider = provider
        title = QLabel("安全协议终端")
        title.setObjectName("page_title")
        self.command = QComboBox()
        self.command.setObjectName("console_command")
        self.command.addItems(["HELLO", "GET_STATE"])
        send = QPushButton("发送只读请求")
        send.setObjectName("console_send")
        send.clicked.connect(self.send)
        self.result = QLabel("仅允许HELLO/GET_STATE | 不提供任意HEX直发")
        self.result.setObjectName("console_result")
        layout = QVBoxLayout(self)
        for widget in (title, self.command, send, self.result):
            layout.addWidget(widget)
        layout.addStretch()

    def send(self) -> None:
        session = getattr(self.provider, "session", None)
        if not isinstance(session, DeviceSession):
            self.result.setText("未连接")
            return
        if self.command.currentText() == "GET_STATE":
            session.poll_once()
            self.result.setText("GET_STATE只读请求完成")
        else:
            identity = session.identity
            self.result.setText(f"HELLO缓存身份: {identity.hello_text if identity else '--'}")
