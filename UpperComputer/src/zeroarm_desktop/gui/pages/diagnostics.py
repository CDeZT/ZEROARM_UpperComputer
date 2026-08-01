"""Diagnostics page and safe read-only protocol console."""

from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget

from zeroarm_desktop.application.device_session import DeviceSession
from zeroarm_desktop.application.diagnostics import collect_diagnostics, create_diagnostic_bundle
from zeroarm_desktop.application.session_recording import SessionRecordingBridge
from zeroarm_desktop.domain.evidence import EvidenceLog
from zeroarm_desktop.infrastructure.paths import default_data_root


class DiagnosticsPage(QWidget):
    def __init__(
        self,
        provider: object,
        *,
        recording: SessionRecordingBridge | None = None,
        evidence_log: EvidenceLog | None = None,
        performance_text: str = "",
    ) -> None:
        super().__init__()
        self.setObjectName("page_diagnostics")
        self.provider = provider
        self.recording = recording
        self.evidence_log = evidence_log
        self._performance_text = performance_text
        title = QLabel("诊断与会话数据")
        title.setObjectName("page_title")
        self.text = QLabel("等待刷新")
        self.text.setObjectName("diagnostics_text")
        self.text.setWordWrap(True)
        refresh = QPushButton("刷新诊断")
        refresh.setObjectName("refresh_diagnostics")
        refresh.clicked.connect(self.refresh)
        bundle = QPushButton("导出脱敏诊断包")
        bundle.setObjectName("export_diagnostic_bundle")
        bundle.clicked.connect(self.export)
        evidence = QPushButton("导出 OperationEvidence JSON")
        evidence.setObjectName("export_evidence_button")
        evidence.clicked.connect(self.export_evidence)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        for widget in (title, refresh, bundle, evidence, self.text):
            layout.addWidget(widget)
        layout.addStretch()

    def set_performance_text(self, text: str) -> None:
        self._performance_text = text

    def refresh(self) -> None:
        snapshot = collect_diagnostics(getattr(self.provider, "session", None))
        recorder_line = "Recorder 未绑定"
        if self.recording is not None:
            stats = self.recording.recorder.statistics
            recorder_line = (
                f"Recorder session={self.recording.session_id or '--'} "
                f"written={stats.events_written} dropped={stats.events_dropped} "
                f"batches={stats.batches_written} err={stats.last_error or 'none'}"
            )
        evidence_count = 0 if self.evidence_log is None else len(self.evidence_log.items)
        self.text.setText(
            f"Session={snapshot.session_state} Firmware={snapshot.firmware or '--'}\n"
            f"SessionStats={snapshot.session_statistics}\n"
            f"ParserStats={snapshot.parser_statistics}\n"
            f"{recorder_line}\n"
            f"Evidence count={evidence_count}\n"
            f"Performance: {self._performance_text or '--'}\n" + "\n".join(snapshot.capability_gaps)
        )

    def export(self) -> None:
        path = default_data_root() / "diagnostics" / "zeroarm-diagnostics.zip"
        create_diagnostic_bundle(
            collect_diagnostics(getattr(self.provider, "session", None)),
            path,
        )
        self.text.setText(f"诊断包已导出: {path.name}")

    def export_evidence(self) -> None:
        if self.evidence_log is None:
            self.text.setText("EvidenceLog 未注入")
            return
        path = default_data_root() / "diagnostics" / "operation_evidence.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.evidence_log.to_json(), encoding="utf-8")
        self.text.setText(f"Evidence 已导出: {path.name} | items={len(self.evidence_log.items)}")


class ProtocolConsolePage(QWidget):
    def __init__(self, provider: object) -> None:
        super().__init__()
        self.setObjectName("page_protocol_console")
        self.provider = provider
        title = QLabel("安全协议终端")
        title.setObjectName("page_title")
        self.command = QComboBox()
        self.command.setObjectName("console_command")
        self.command.addItems(
            [
                "HELLO",
                "GET_STATE",
                "GRIPPER_PING",
                "BENCH_QUERY",
                "BENCH_GET_PROTECTION",
            ]
        )
        send = QPushButton("发送只读请求")
        send.setObjectName("console_send")
        send.clicked.connect(self.send)
        self.result = QLabel("仅允许 HELLO/GET_STATE/夹爪Ping/台架Query | 不提供任意 HEX 直发")
        self.result.setObjectName("console_result")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        for widget in (title, self.command, send, self.result):
            layout.addWidget(widget)
        layout.addStretch()

    def send(self) -> None:
        session = getattr(self.provider, "session", None)
        if not isinstance(session, DeviceSession):
            self.result.setText("未连接")
            return
        name = self.command.currentText()
        try:
            if name == "GET_STATE":
                session.poll_once()
                self.result.setText("GET_STATE只读请求完成")
            elif name == "HELLO":
                identity = session.identity
                self.result.setText(f"HELLO缓存身份: {identity.hello_text if identity else '--'}")
            elif name == "GRIPPER_PING":
                response = session.send_gripper_ping(1)
                self.result.setText(
                    f"GRIPPER_PING result={response.raw_result} id={response.id} "
                    f"ok={response.is_ok}"
                )
            elif name == "BENCH_QUERY":
                state = session.send_bench_query(1)
                self.result.setText(
                    f"BENCH_QUERY motor={state.motor_id} online={state.online} "
                    f"pos={state.position_urad}"
                )
            else:
                protection = session.send_bench_get_protection(3)
                self.result.setText(
                    f"BENCH_GET_PROTECTION motor={protection.motor_id} "
                    f"temp={protection.temperature_c}C cur={protection.current_ma}mA"
                )
        except (PermissionError, RuntimeError, ValueError, TypeError) as error:
            self.result.setText(str(error))
