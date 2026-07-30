"""Mock teach recording page."""

from PySide6.QtWidgets import QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget

from zeroarm_desktop.application.device_session import DeviceSession
from zeroarm_desktop.application.teach import TeachRecorder


class TeachPage(QWidget):
    def __init__(self, session_provider: object) -> None:
        super().__init__()
        self.setObjectName("page_teach")
        self._provider = session_provider
        self.recorder = TeachRecorder()
        title = QLabel("拖动示教 (Mock Only)")
        title.setObjectName("page_title")
        self.mask_input = QSpinBox()
        self.mask_input.setRange(1, 0x3F)
        self.mask_input.setValue(0x3F)
        self.mask_input.setObjectName("teach_joint_mask")
        self.status = QLabel("V1 device time / sample sequence: -- / 未提供")
        self.status.setObjectName("teach_status")
        start = QPushButton("开始Mock示教")
        start.setObjectName("teach_start_button")
        stop = QPushButton("停止并Review")
        stop.setObjectName("teach_stop_button")
        start.clicked.connect(self.start)
        stop.clicked.connect(self.stop)
        layout = QVBoxLayout(self)
        for widget in (title, self.mask_input, start, stop, self.status):
            layout.addWidget(widget)
        layout.addWidget(QLabel("TEACH_STOP后保持失能语义 | 不自动ENABLE。"))
        layout.addStretch()

    def start(self) -> None:
        try:
            session = self._session()
            result = session.send_teach_start(self.mask_input.value())
            if not result.is_ok:
                raise RuntimeError(f"TEACH_START result={result.raw_value}")
            self.recorder.start()
            session.subscribe_snapshots(self.recorder.append)
            if session.latest_snapshot is not None:
                self.recorder.append(session.latest_snapshot)
            self.status.setText("RECORDING | V1时间字段保持Unknown")
        except (PermissionError, RuntimeError, ValueError) as error:
            self.status.setText(str(error))

    def stop(self) -> None:
        try:
            session = self._session()
            session.send_teach_stop()
            if session.latest_snapshot is not None:
                self.recorder.append(session.latest_snapshot)
            recording = self.recorder.stop(self.mask_input.value())
            self.status.setText(
                f"REVIEW | samples={len(recording.samples)} "
                f"dropped={recording.dropped_samples} | 保持失能"
            )
        except (PermissionError, RuntimeError, ValueError) as error:
            self.status.setText(str(error))

    def _session(self) -> DeviceSession:
        session = getattr(self._provider, "session", None)
        if not isinstance(session, DeviceSession) or not session.actions_allowed:
            raise PermissionError("拖动示教仅允许Mock")
        return session
