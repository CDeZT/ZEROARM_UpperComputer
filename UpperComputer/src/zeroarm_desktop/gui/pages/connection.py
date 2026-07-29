"""Mock and Serial connection page backed by DeviceSession."""

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from zeroarm_desktop.application.device_session import DeviceSession, SessionEvent, SessionState
from zeroarm_desktop.transport.discovery import discover_serial_ports
from zeroarm_desktop.transport.mock import MockSettings, MockTransport
from zeroarm_desktop.transport.serial_transport import SerialSettings, SerialTransport


class ConnectionPage(QWidget):
    """Create and operate a read-only Session without exposing protocol details."""

    session_changed = Signal(object)
    connection_text_changed = Signal(str)
    _session_event_received = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page_connection")
        self.session: DeviceSession | None = None
        self._session_event_received.connect(self._apply_session_event)

        title = QLabel("连接与设备")
        title.setObjectName("page_title")
        subtitle = QLabel("通过相同的 V1 Session 链路连接确定性 Mock 或 Serial 设备")
        self.transport_selector = QComboBox()
        self.transport_selector.setObjectName("transport_selector")
        self.transport_selector.addItems(["Mock", "Serial"])
        self.transport_selector.currentTextChanged.connect(self._transport_changed)
        self.port_selector = QComboBox()
        self.port_selector.setObjectName("port_selector")
        self.refresh_button = QPushButton("刷新端口")
        self.refresh_button.setObjectName("refresh_ports_button")
        self.refresh_button.clicked.connect(self.refresh_ports)
        port_row = QHBoxLayout()
        port_row.addWidget(self.port_selector, 1)
        port_row.addWidget(self.refresh_button)
        self.seed = QSpinBox()
        self.seed.setObjectName("mock_seed")
        self.seed.setRange(0, 2**31 - 1)
        self.seed.setValue(7)
        self.poll_rate = QComboBox()
        self.poll_rate.setObjectName("poll_rate")
        self.poll_rate.addItems(["20 Hz", "50 Hz", "100 Hz"])

        form = QFormLayout()
        form.addRow("Transport", self.transport_selector)
        form.addRow("Serial 端口", port_row)
        form.addRow("Mock 随机种子", self.seed)
        form.addRow("状态轮询", self.poll_rate)
        self.connect_button = QPushButton("连接")
        self.connect_button.setObjectName("connect_button")
        self.connect_button.clicked.connect(self.toggle_connection)
        self.timeline = QLabel("等待连接")
        self.timeline.setObjectName("handshake_timeline")
        self.timeline.setWordWrap(True)
        self.identity = QLabel("固件: 未知 | 协议: 未知 | 能力: V1 未提供")
        self.identity.setObjectName("identity_summary")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(24)
        layout.addLayout(form)
        layout.addWidget(self.connect_button)
        layout.addSpacing(20)
        layout.addWidget(QLabel("握手时间线"))
        layout.addWidget(self.timeline)
        layout.addWidget(self.identity)
        layout.addStretch()
        self._transport_changed("Mock")

    @Slot()
    def refresh_ports(self) -> None:
        self.port_selector.clear()
        ports = discover_serial_ports()
        for port in ports:
            self.port_selector.addItem(
                f"{port.device} | {port.description or '无描述'}",
                port.device,
            )
        if not ports:
            self.port_selector.addItem("未发现串口", None)

    @Slot()
    def toggle_connection(self) -> None:
        if self.session is not None and self.session.state is not SessionState.DISCONNECTED:
            self.session.disconnect()
            self.session = None
            self.connect_button.setText("连接")
            self.identity.setText("固件: 未知 | 协议: 未知 | 能力: V1 未提供")
            self.connection_text_changed.emit("未连接")
            self.session_changed.emit(None)
            return
        try:
            session = DeviceSession(self._make_transport(), poll_rate_hz=self._selected_poll_rate())
            session.subscribe_events(self._session_event_received.emit)
            self.session = session
            self.session_changed.emit(session)
            self.timeline.setText("OPENING -> HANDSHAKING")
            session.connect()
        except Exception as error:
            self.timeline.setText(f"连接失败: {error}")
            self.connection_text_changed.emit("连接失败")
            return
        if session.state is SessionState.READONLY_READY:
            self.connect_button.setText("断开")
            self.connection_text_changed.emit("只读已连接")
            identity = session.identity
            if identity is not None:
                self.identity.setText(
                    f"固件: {identity.hello_text} | 协议: V{identity.protocol_generation} | "
                    "能力: V1 未提供"
                )

    def close_session(self) -> None:
        if self.session is not None:
            self.session.disconnect()
            self.session = None

    def _make_transport(self) -> MockTransport | SerialTransport:
        if self.transport_selector.currentText() == "Mock":
            return MockTransport(MockSettings(seed=self.seed.value()))
        port = self.port_selector.currentData()
        if not isinstance(port, str):
            raise ValueError("请选择有效串口")
        return SerialTransport(SerialSettings(port))

    def _selected_poll_rate(self) -> int:
        return int(self.poll_rate.currentText().split()[0])

    @Slot(str)
    def _transport_changed(self, transport: str) -> None:
        serial_selected = transport == "Serial"
        self.port_selector.setEnabled(serial_selected)
        self.refresh_button.setEnabled(serial_selected)
        self.seed.setEnabled(not serial_selected)
        if serial_selected:
            self.refresh_ports()

    @Slot(object)
    def _apply_session_event(self, event: SessionEvent) -> None:
        self.timeline.setText(f"{self.timeline.text()} -> {event.state.value}: {event.detail}")
