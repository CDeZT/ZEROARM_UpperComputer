"""Navigation shell and stable global status surface."""

from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from time import monotonic, sleep

from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from zeroarm_desktop.application.device_session import DeviceSession, SessionState
from zeroarm_desktop.application.performance import PerformanceSampler
from zeroarm_desktop.application.session_recording import SessionRecordingBridge
from zeroarm_desktop.cli import LaunchOptions
from zeroarm_desktop.domain.evidence import EvidenceLog, OutcomeStatus, make_evidence
from zeroarm_desktop.domain.safety import AppMode
from zeroarm_desktop.gui.pages.calibration import CalibrationPage
from zeroarm_desktop.gui.pages.cartesian import CartesianPage
from zeroarm_desktop.gui.pages.connection import ConnectionPage
from zeroarm_desktop.gui.pages.dashboard import DashboardPage
from zeroarm_desktop.gui.pages.dataset import DatasetPage
from zeroarm_desktop.gui.pages.diagnostics import DiagnosticsPage, ProtocolConsolePage
from zeroarm_desktop.gui.pages.firmware import FirmwarePage
from zeroarm_desktop.gui.pages.gamepad_recipe import GamepadRecipePage
from zeroarm_desktop.gui.pages.gripper import GripperPage
from zeroarm_desktop.gui.pages.home import HomePage
from zeroarm_desktop.gui.pages.joint_monitor import JointMonitorPage
from zeroarm_desktop.gui.pages.manual_joint import ManualJointPage
from zeroarm_desktop.gui.pages.teach import TeachPage
from zeroarm_desktop.gui.pages.trajectory import TrajectoryPage
from zeroarm_desktop.gui.pages.workspace3d import Workspace3DPage
from zeroarm_desktop.gui.theme import DARK_THEME, LIGHT_THEME
from zeroarm_desktop.gui.viewmodels.home import HomeViewModel
from zeroarm_desktop.gui.viewmodels.idle_monitor import OperatorIdleHomeMonitor
from zeroarm_desktop.gui.viewmodels.manual_joint import ManualJointViewModel
from zeroarm_desktop.gui.viewmodels.snapshot import SnapshotViewModel, SnapshotViewState
from zeroarm_desktop.gui.viewmodels.teach import TeachViewModel
from zeroarm_desktop.gui.viewmodels.trajectory import TrajectoryViewModel
from zeroarm_desktop.gui.viewmodels.workspace3d import Workspace3DViewModel
from zeroarm_desktop.infrastructure.paths import robot_model_root
from zeroarm_desktop.model3d.fk import UrdfForwardKinematics
from zeroarm_desktop.model3d.ik import NumericalIkSolver
from zeroarm_desktop.model3d.scene import RobotSceneBuilder
from zeroarm_desktop.version import __version__

RESET_REQUIRED_MASK = 0x0E00
CONTROLLED_SHUTDOWN_HOME_TIMEOUT_S = 5.0


def _placeholder(object_name: str, title: str, detail: str) -> QWidget:
    page = QWidget()
    page.setObjectName(object_name)
    heading = QLabel(title)
    heading.setObjectName("page_title")
    description = QLabel(detail)
    description.setWordWrap(True)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(36, 32, 36, 32)
    layout.addWidget(heading)
    layout.addWidget(description)
    layout.addStretch()
    return page


class MainWindow(QMainWindow):
    """Application shell with deterministic routing and safe global controls."""

    page_changed = Signal(str)

    def __init__(
        self,
        *,
        shutdown: Callable[[], None] | None = None,
        confirm_fault_exit: Callable[[str, str], bool] | None = None,
        session_database_path: Path | None = None,
        launch_options: LaunchOptions | None = None,
    ) -> None:
        super().__init__()
        self._shutdown = shutdown
        self._confirm_fault_exit = (
            confirm_fault_exit
            if confirm_fault_exit is not None
            else self._default_fault_exit_confirm
        )
        self.launch_options = launch_options or LaunchOptions()
        self._theme_name = "dark"
        self._pages: dict[str, int] = {}
        self._buttons: dict[str, QPushButton] = {}
        self.evidence_log = EvidenceLog()
        self.recording = SessionRecordingBridge(session_database_path)
        self.performance_sampler = PerformanceSampler()
        self.setObjectName("main_window")
        self.setWindowTitle(f"ZeroArm Desktop {__version__}")
        self.setMinimumSize(1280, 720)
        self.resize(1440, 900)
        if self.launch_options.reset_layout:
            self.setGeometry(80, 60, 1440, 900)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self._build_navigation())
        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("page_stack")
        body.addWidget(self.page_stack, 1)
        root_layout.addLayout(body, 1)
        root_layout.addWidget(self._build_status_bar())
        self.setCentralWidget(root)

        self.connection_page = ConnectionPage(prefer_mock=True)
        self.connection_page.connection_text_changed.connect(self.set_connection_text)
        self.snapshot_view_model = SnapshotViewModel()
        self.snapshot_view_model.state_changed.connect(self._apply_snapshot_state)
        self.connection_page.session_changed.connect(self.snapshot_view_model.bind_session)
        self.connection_page.session_changed.connect(self._on_session_changed)
        asset_root = robot_model_root()
        urdf = asset_root / "URDF_XG_Robot_Arm_Urdf_V1_1/urdf" / "URDF_XG_Robot_Arm_Urdf_V1_1.urdf"
        kinematics = UrdfForwardKinematics(urdf)
        self.workspace_view_model = Workspace3DViewModel(RobotSceneBuilder(kinematics))
        self.connection_page.session_changed.connect(self.workspace_view_model.bind_session)
        self.manual_view_model = ManualJointViewModel(self.connection_page)
        self.manual_view_model.ghost_target_changed.connect(
            self.workspace_view_model.set_ghost_target
        )
        self.connection_page.session_changed.connect(
            lambda session: self.manual_view_model.stop_hold("connection_changed")
        )
        self.trajectory_view_model = TrajectoryViewModel(self.connection_page)
        self.trajectory_view_model.ghost_changed.connect(self.workspace_view_model.set_ghost_target)
        self.dashboard_page = DashboardPage(self.snapshot_view_model)
        self.register_page("connection", self.connection_page)
        self.register_page("dashboard", self.dashboard_page)
        self.register_page("joint_monitor", JointMonitorPage(self.snapshot_view_model))
        if self.launch_options.safe_mode:
            self.register_page(
                "workspace_3d",
                _placeholder(
                    "page_workspace_3d",
                    "3D 工作区 (Safe Mode)",
                    "safe-mode 已禁用 3D / OpenGL 重型页面，便于排查启动与资源问题。",
                ),
            )
        else:
            self.register_page(
                "workspace_3d", Workspace3DPage(self.workspace_view_model, asset_root)
            )
        self.register_page("manual_joint", ManualJointPage(self.manual_view_model))
        self.register_page("trajectory", TrajectoryPage(self.trajectory_view_model))
        self.teach_view_model = TeachViewModel(self.connection_page)
        self.teach_view_model.trajectory_saved.connect(self._on_teach_trajectory_saved)
        self.teach_page = TeachPage(self.teach_view_model)
        self.register_page("teach", self.teach_page)
        self.register_page(
            "cartesian",
            CartesianPage(
                NumericalIkSolver(kinematics),
                self.connection_page,
                self.workspace_view_model.set_ghost_target,
            ),
        )
        self.home_view_model = HomeViewModel(self.connection_page)
        self.register_page("calibration", CalibrationPage(self.home_view_model))
        self.register_page("home", HomePage(self.home_view_model))
        self.connection_page.session_changed.connect(
            lambda session: self.home_view_model.set_mode(
                AppMode.OPERATOR
                if self.mode_selector.currentText() == "Operator"
                else AppMode.OBSERVER
            )
        )
        self.idle_monitor = OperatorIdleHomeMonitor(self.connection_page, self.home_view_model)
        self.idle_monitor.countdown_changed.connect(self._apply_idle_countdown)
        self.idle_monitor.home_triggered.connect(
            lambda text: self.notification_center.setText(text)
        )
        self.connection_page.session_changed.connect(
            lambda session: self.idle_monitor.start()
            if session is not None
            else self.idle_monitor.stop()
        )
        self.manual_view_model.status_changed.connect(self.idle_monitor.note_activity)
        self.teach_view_model.status_changed.connect(self.idle_monitor.note_activity)
        self.page_changed.connect(lambda route: self.idle_monitor.note_activity())
        self.diagnostics_page = DiagnosticsPage(
            self.connection_page,
            recording=self.recording,
            evidence_log=self.evidence_log,
        )
        self.register_page("diagnostics", self.diagnostics_page)
        self.register_page("protocol_console", ProtocolConsolePage(self.connection_page))
        self.register_page("gripper", GripperPage(self.connection_page))
        self.register_page("gamepad_recipe", GamepadRecipePage(self.trajectory_view_model))
        self.register_page("dataset", DatasetPage(self.teach_view_model))
        self.register_page("firmware", FirmwarePage())
        self._metrics_timer = QTimer(self)
        self._metrics_timer.setInterval(1000)
        self._metrics_timer.timeout.connect(self._refresh_performance)
        self._metrics_timer.start()
        self.navigate("connection")
        self.apply_theme("dark")
        if self.launch_options.safe_mode:
            self.notification_center.setText("Safe Mode | 3D 已降级 | Serial 动作仍禁用")
        shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        shortcut.activated.connect(lambda: self.navigate("connection"))
        diagnostics_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        diagnostics_shortcut.activated.connect(lambda: self.navigate("diagnostics"))
        self.stop_shortcut = QShortcut(QKeySequence("Space"), self)
        self.stop_shortcut.activated.connect(self._global_stop)

    def register_page(self, route: str, page: QWidget) -> None:
        if route in self._pages:
            old = self.page_stack.widget(self._pages[route])
            self.page_stack.removeWidget(old)
            old.deleteLater()
        self._pages[route] = self.page_stack.addWidget(page)

    def navigate(self, route: str) -> None:
        if self.page_stack.currentWidget() is not None and route != "manual_joint":
            self.manual_view_model.stop_hold("navigation")
        index = self._pages[route]
        self.page_stack.setCurrentIndex(index)
        for name, button in self._buttons.items():
            button.setChecked(name == route)
        self.page_changed.emit(route)

    def apply_theme(self, theme: str) -> None:
        if theme not in {"dark", "light"}:
            raise ValueError("theme must be dark or light")
        self._theme_name = theme
        self.setStyleSheet(DARK_THEME if theme == "dark" else LIGHT_THEME)

    def set_connection_text(self, text: str) -> None:
        self.connection_badge.setText(text)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 10, 16, 10)
        product = QLabel(f"ZEROARM DESKTOP  {__version__}")
        product.setObjectName("product_title")
        product.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(product)
        profile = QLabel("V1 · profile 0x1D · Serial 默认只读")
        profile.setObjectName("profile_chip")
        layout.addWidget(profile)
        layout.addStretch()
        self.connection_badge = QLabel("未连接")
        self.connection_badge.setObjectName("connection_badge")
        self.firmware_badge = QLabel("固件未知")
        self.firmware_badge.setObjectName("firmware_badge")
        self.snapshot_age_badge = QLabel("状态 --")
        self.snapshot_age_badge.setObjectName("snapshot_age_badge")
        self.fault_badge = QLabel("FAULT --")
        self.fault_badge.setObjectName("fault_badge")
        for badge in (
            self.connection_badge,
            self.firmware_badge,
            self.snapshot_age_badge,
            self.fault_badge,
        ):
            badge.setProperty("class", "badge")
            layout.addWidget(badge)
        self.mode_selector = QComboBox()
        self.mode_selector.setObjectName("mode_selector")
        self.mode_selector.addItems(["Observer", "Operator"])
        self.mode_selector.currentTextChanged.connect(self._mode_changed)
        layout.addWidget(self.mode_selector)
        self.stop_button = QPushButton("软件停止 · 非急停")
        self.stop_button.setObjectName("global_stop_button")
        self.stop_button.setToolTip("仅停止 Mock 点动/回放等软件动作，不是物理急停")
        self.stop_button.clicked.connect(self._global_stop)
        layout.addWidget(self.stop_button)
        return header

    def _build_navigation(self) -> QFrame:
        navigation = QFrame()
        navigation.setObjectName("navigation")
        navigation.setFixedWidth(236)
        layout = QVBoxLayout(navigation)
        layout.setContentsMargins(14, 18, 14, 18)
        layout.setSpacing(6)
        groups = (
            (
                "设备",
                (
                    ("connection", "连接与设备"),
                    ("dashboard", "系统总览"),
                    ("joint_monitor", "六轴监控"),
                    ("workspace_3d", "3D 工作区"),
                ),
            ),
            (
                "操作 (Mock)",
                (
                    ("manual_joint", "手动关节"),
                    ("trajectory", "轨迹编辑器"),
                    ("teach", "拖动示教"),
                    ("home", "回零向导"),
                    ("calibration", "标定"),
                    ("cartesian", "Cartesian 离线 IK"),
                ),
            ),
            (
                "诊断与数据",
                (
                    ("diagnostics", "诊断"),
                    ("protocol_console", "安全协议终端"),
                    ("gripper", "夹爪/台架只读"),
                    ("gamepad_recipe", "手柄 / Recipe"),
                    ("dataset", "数据集"),
                    ("firmware", "固件升级"),
                ),
            ),
        )
        for group_title, items in groups:
            heading = QLabel(group_title)
            heading.setObjectName("nav_group_heading")
            layout.addWidget(heading)
            for route, text in items:
                button = QPushButton(text)
                button.setObjectName(f"nav_{route}")
                button.setCheckable(True)
                button.clicked.connect(lambda checked=False, name=route: self.navigate(name))
                self._buttons[route] = button
                layout.addWidget(button)
        layout.addStretch()
        theme = QPushButton("切换深浅主题")
        theme.setObjectName("theme_toggle_button")
        theme.clicked.connect(self._toggle_theme)
        layout.addWidget(theme)
        return navigation

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("status_bar")
        self.status_bar_layout = QHBoxLayout(bar)
        layout = self.status_bar_layout
        layout.setContentsMargins(16, 8, 16, 8)
        self.link_status = QLabel("RX 0 B  |  TX 0 B  |  Snapshot 0 Hz")
        self.link_status.setObjectName("link_status")
        self.notification_center = QLabel("Observer 模式 | 动作能力锁定")
        self.notification_center.setObjectName("notification_center")
        self.auto_home_badge = QLabel("自动回零 --")
        self.auto_home_badge.setObjectName("auto_home_badge")
        self.auto_home_badge.setProperty("class", "badge")
        layout.addWidget(self.link_status)
        layout.addStretch()
        layout.addWidget(self.auto_home_badge)
        layout.addWidget(self.notification_center)
        return bar

    def _toggle_theme(self) -> None:
        self.apply_theme("light" if self._theme_name == "dark" else "dark")

    def _global_stop(self) -> None:
        self.manual_view_model.stop_hold("global_stop")
        self.trajectory_view_model.abort_playback("global_stop")
        with suppress(PermissionError, RuntimeError, ValueError):
            if self.teach_view_model.state.value == "recording":
                self.teach_view_model.stop()
        self.notification_center.setText("软件 STOP | 非急停 | 点动/回放已停止")

    def _mode_changed(self, text: str) -> None:
        self.trajectory_view_model.abort_playback("mode_changed")
        mode = AppMode.OPERATOR if text == "Operator" else AppMode.OBSERVER
        self.manual_view_model.set_mode(mode)
        self.home_view_model.set_mode(mode)
        self.trajectory_view_model.set_mode(mode)
        self.teach_view_model.set_mode(mode)
        self.notification_center.setText(f"{text} 模式 | Serial动作始终禁用")

    def _apply_idle_countdown(self, remaining_s: int) -> None:
        if remaining_s > 0:
            self.auto_home_badge.setText(f"自动回零 {remaining_s}s")
        else:
            self.auto_home_badge.setText("自动回零 触发中")

    def _apply_snapshot_state(self, state: SnapshotViewState) -> None:
        generation = "--" if state.generation is None else str(state.generation)
        self.snapshot_age_badge.setText(f"Snapshot #{generation}")
        fault = "--" if state.fault_flags_raw is None else f"0x{state.fault_flags_raw:08X}"
        self.fault_badge.setText(f"FAULT {fault}")
        session = self.connection_page.session
        if session is not None:
            statistics = session.statistics
            identity = session.identity
            if identity is not None:
                self.firmware_badge.setText(identity.hello_text)
            self.link_status.setText(
                f"Requests {statistics.requests_sent} | "
                f"Responses {statistics.responses_received} | "
                f"Snapshots {statistics.snapshots_published}"
            )

    def _on_session_changed(self, session: object) -> None:
        device = session if isinstance(session, DeviceSession) else None
        self.recording.bind_session(device)
        if device is None:
            self.firmware_badge.setText("固件未知")

    def _on_teach_trajectory_saved(self, trajectory: object) -> None:
        from zeroarm_desktop.domain.trajectory import Trajectory

        if isinstance(trajectory, Trajectory):
            self.trajectory_view_model.load_trajectory(trajectory)
            self.evidence_log.append(
                make_evidence(
                    command_name="TEACH_SAVE_TRAJECTORY",
                    outcome=OutcomeStatus.COMPLETED,
                    notes=(f"points={len(trajectory.points)}", trajectory.name),
                )
            )
            self.recording.note(
                "teach_trajectory_saved",
                {"name": trajectory.name, "points": len(trajectory.points)},
            )
            self.notification_center.setText(f"示教轨迹已加载到编辑器: {trajectory.name}")

    def _refresh_performance(self) -> None:
        sample = self.performance_sampler.sample(
            self.connection_page.session,
            self.recording.recorder.statistics,
        )
        text = (
            f"Hz≈{sample.snapshot_hz:.1f} | poll_coalesced={sample.poll_coalesced} | "
            f"rec_w={sample.recorder_written} drop={sample.recorder_dropped}"
        )
        if sample.notes:
            text += " | " + ",".join(sample.notes)
        self.dashboard_page.set_session_metrics(text)
        self.diagnostics_page.set_performance_text(text)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._metrics_timer.stop()
        self.idle_monitor.stop()
        self.snapshot_view_model.close()
        self.workspace_view_model.close()
        self.manual_view_model.stop_hold("shutdown")
        self.trajectory_view_model.abort_playback("shutdown")
        with suppress(PermissionError, RuntimeError, ValueError):
            if self.teach_view_model.state.value == "recording":
                self.teach_view_model.stop()
        session = self.connection_page.session
        if (
            session is not None
            and session.state is SessionState.READONLY_READY
            and not self._controlled_shutdown(session, event)
        ):
            return
        self.connection_page.close_session()
        self.recording.unbind()
        if self._shutdown is not None:
            self._shutdown()
        event.accept()

    def _controlled_shutdown(self, session: DeviceSession, event: QCloseEvent) -> bool:
        snapshot = session.latest_snapshot
        fault = snapshot.fault_flags_raw if snapshot is not None else 0
        if fault & RESET_REQUIRED_MASK:
            confirmed = self._confirm_fault_exit(
                "无法安全归零退出",
                f"检测到 RESET-REQUIRED 故障 (0x{fault:08X}), 无法自动回零。\n"
                "请断电复位 MCU 并确认机械状态后再退出。是否仍然退出?",
            )
            if not confirmed:
                event.ignore()
                return False
            return True
        if not session.actions_allowed:
            return True
        if (
            snapshot is not None
            and snapshot.run_state_raw == 1
            and fault == 0
            and (snapshot.homed_mask or 0) != 0x1D
        ):
            self.notification_center.setText("受控退出: 请求回零 0x1D")
            session.pause_polling()
            session.send_home(0x1D)
            deadline = monotonic() + CONTROLLED_SHUTDOWN_HOME_TIMEOUT_S
            while monotonic() < deadline:
                QCoreApplication.processEvents()
                sleep(0.01)
                session.poll_once()
                latest = session.latest_snapshot
                if latest is not None and (latest.homed_mask or 0) == 0x1D:
                    self.notification_center.setText("受控退出: 回零完成证据已记录")
                    return True
        return True

    def _default_fault_exit_confirm(self, title: str, text: str) -> bool:
        answer = QMessageBox.warning(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer is QMessageBox.StandardButton.Yes

    def event(self, event: QEvent) -> bool:
        if event.type() in {
            QEvent.Type.WindowDeactivate,
            QEvent.Type.ApplicationDeactivate,
        } and hasattr(self, "manual_view_model"):
            self.manual_view_model.stop_hold("focus_loss")
            self.trajectory_view_model.abort_playback("focus_loss")
        return super().event(event)
