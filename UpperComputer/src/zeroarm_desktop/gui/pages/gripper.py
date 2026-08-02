"""Readonly gripper and motor-bench diagnostics page."""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from zeroarm_desktop.application.device_session import DeviceSession, SessionState
from zeroarm_desktop.domain.safety import (
    AppMode,
    CommandFamily,
    CommandIntent,
    SafetyContext,
    SafetyGate,
)


class GripperPage(QWidget):
    def __init__(self, provider: object) -> None:
        super().__init__()
        self.setObjectName("page_gripper")
        self.provider = provider
        title = QLabel("夹爪 / 台架只读诊断")
        title.setObjectName("page_title")
        subtitle = QLabel(
            "仅开放 Ping/Read/Query/GetProtection | 禁止任意透传与夹爪动作 | 未标定不得 MOVE/WRITE"
        )
        subtitle.setWordWrap(True)

        self.servo_id = QSpinBox()
        self.servo_id.setObjectName("gripper_servo_id")
        self.servo_id.setRange(1, 253)
        self.servo_id.setValue(1)
        self.motor_id = QSpinBox()
        self.motor_id.setObjectName("bench_motor_id")
        self.motor_id.setRange(1, 6)
        self.motor_id.setValue(1)
        form = QFormLayout()
        form.addRow("夹爪舵机 ID", self.servo_id)
        form.addRow("台架电机 ID", self.motor_id)

        ping = QPushButton("Gripper Ping")
        ping.setObjectName("gripper_ping_button")
        ping.clicked.connect(self.ping)
        read = QPushButton("Gripper Read Pos")
        read.setObjectName("gripper_read_button")
        read.clicked.connect(self.read_pos)
        query = QPushButton("Bench Query")
        query.setObjectName("bench_query_button")
        query.clicked.connect(self.bench_query)
        protection = QPushButton("Bench GetProtection")
        protection.setObjectName("bench_protection_button")
        protection.clicked.connect(self.bench_protection)
        action_probe = QPushButton("探测夹爪动作门 (应拒绝)")
        action_probe.setObjectName("gripper_action_probe_button")
        action_probe.clicked.connect(self.probe_action_gate)
        row = QHBoxLayout()
        for button in (ping, read, query, protection):
            row.addWidget(button)

        self.status = QLabel("连接后可发送只读诊断")
        self.status.setObjectName("gripper_status")
        self.status.setWordWrap(True)
        self.audit = QLabel("命令审计: --")
        self.audit.setObjectName("gripper_audit")
        self.audit.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(form)
        layout.addLayout(row)
        layout.addWidget(action_probe)
        layout.addWidget(self.status)
        layout.addWidget(self.audit)
        layout.addStretch()

    @Slot()
    def ping(self) -> None:
        self._guard(
            lambda: self._format_gripper(self._session().send_gripper_ping(self.servo_id.value()))
        )

    @Slot()
    def read_pos(self) -> None:
        self._guard(
            lambda: self._format_gripper(
                self._session().send_gripper_read(self.servo_id.value(), 0x38, 2)
            )
        )

    @Slot()
    def bench_query(self) -> None:
        self._guard(
            lambda: self._format_bench(self._session().send_bench_query(self.motor_id.value()))
        )

    @Slot()
    def bench_protection(self) -> None:
        self._guard(
            lambda: self._format_protection(
                self._session().send_bench_get_protection(self.motor_id.value())
            )
        )

    @Slot()
    def probe_action_gate(self) -> None:
        session = getattr(self.provider, "session", None)
        snapshot = session.latest_snapshot if isinstance(session, DeviceSession) else None
        decision = SafetyGate().evaluate(
            CommandIntent(CommandFamily.GRIPPER, joint_mask=0),
            SafetyContext(
                isinstance(session, DeviceSession) and session.state is SessionState.READONLY_READY,
                AppMode.OPERATOR,
                snapshot,
                0,
                500_000_000,
                "mock-model-v1",
                True,
                True,
                False,
                True,
            ),
        )
        self.status.setText(
            "夹爪动作门拒绝: " + ", ".join(decision.denials)
            if not decision.allowed
            else "异常: 夹爪动作门放行"
        )

    def _session(self) -> DeviceSession:
        session = getattr(self.provider, "session", None)
        if not isinstance(session, DeviceSession):
            raise RuntimeError("请先连接设备")
        return session

    def _format_gripper(self, response: object) -> None:
        data = getattr(response, "data", b"")
        self.status.setText(
            f"Gripper cmd=0x{getattr(response, 'command', 0):02X} "
            f"result={getattr(response, 'raw_result', '?')} "
            f"id={getattr(response, 'id', '?')} "
            f"servo_error={getattr(response, 'servo_error', '?')} "
            f"data={data.hex() if data else '--'}"
        )
        self._refresh_audit()

    def _format_bench(self, state: object) -> None:
        self.status.setText(
            f"Bench motor={getattr(state, 'motor_id', '?')} "
            f"online={getattr(state, 'online', '?')} "
            f"pos={getattr(state, 'position_urad', '?')} urad "
            f"vel={getattr(state, 'velocity_tenths_rpm', '?')} "
            f"cur={getattr(state, 'current_ma', '?')} mA "
            f"fault={getattr(state, 'fault_flags', '?')}"
        )
        self._refresh_audit()

    def _format_protection(self, protection: object) -> None:
        self.status.setText(
            f"Protection motor={getattr(protection, 'motor_id', '?')} "
            f"temp={getattr(protection, 'temperature_c', '?')} C "
            f"limit={getattr(protection, 'current_ma', '?')} mA "
            f"time={getattr(protection, 'detection_time_ms', '?')} ms"
        )
        self._refresh_audit()

    def _refresh_audit(self) -> None:
        session = getattr(self.provider, "session", None)
        if isinstance(session, DeviceSession):
            recent = session.command_audit[-8:]
            self.audit.setText("命令审计: " + (", ".join(recent) if recent else "--"))

    def _guard(self, operation: object) -> None:
        try:
            if callable(operation):
                operation()
        except (PermissionError, RuntimeError, ValueError, TypeError) as error:
            self.status.setText(str(error))
