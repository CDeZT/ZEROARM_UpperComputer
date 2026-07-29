"""Offline application window for the engineering baseline."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from zeroarm_desktop.version import __version__


class MainWindow(QMainWindow):
    """Top-level ZeroArm Desktop window."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("main_window")
        self.setWindowTitle(f"ZeroArm Desktop {__version__}")
        self.setMinimumSize(900, 620)
        self.resize(1180, 760)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._build_workspace(), 1)

        content = QWidget()
        content.setObjectName("baseline_content")
        content.setLayout(layout)
        self.setCentralWidget(content)
        self.setStyleSheet(_STYLE_SHEET)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)

        product = QLabel("ZEROARM")
        product.setObjectName("product_mark")
        subtitle = QLabel("DESKTOP CONSOLE")
        subtitle.setObjectName("product_subtitle")

        overview = QLabel("  OVERVIEW")
        overview.setObjectName("active_navigation")
        overview.setFixedHeight(44)

        navigation = QLabel("连接与设备\n\n关节监控\n\n3D 工作区\n\n轨迹与示教\n\n诊断记录")
        navigation.setObjectName("future_navigation")

        baseline = QLabel(f"ENGINEERING BASELINE\nVERSION {__version__}")
        baseline.setObjectName("baseline_badge")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(24, 34, 24, 24)
        layout.addWidget(product)
        layout.addWidget(subtitle)
        layout.addSpacing(42)
        layout.addWidget(overview)
        layout.addSpacing(22)
        layout.addWidget(navigation)
        layout.addStretch()
        layout.addWidget(baseline)
        return sidebar

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        workspace.setObjectName("workspace")

        eyebrow = QLabel("SYSTEM OVERVIEW  /  OFFLINE MODE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("ZeroArm 控制中枢")
        title.setObjectName("application_title")
        description = QLabel("安全优先的六轴机械臂调试与操作平台")
        description.setObjectName("hero_description")

        connection = QLabel("●  尚未连接")
        connection.setObjectName("connection_status")
        connection.setAlignment(Qt.AlignmentFlag.AlignCenter)
        connection.setFixedSize(132, 38)

        heading = QHBoxLayout()
        heading.addWidget(title)
        heading.addStretch()
        heading.addWidget(connection)

        status_row = QHBoxLayout()
        status_row.setSpacing(14)
        status_row.addWidget(self._status_card("通信链路", "离线", "未启动 Transport"))
        status_row.addWidget(self._status_card("设备状态", "未知", "等待只读握手"))
        status_row.addWidget(self._status_card("运行模式", "观察者", "动作能力已锁定"))

        notice = QFrame()
        notice.setObjectName("safety_notice")
        notice_title = QLabel("安全边界已生效")
        notice_title.setObjectName("notice_title")
        notice_text = QLabel(
            "当前 Demo 不连接串口、不加载机械模型且不发送任何硬件命令。"
            "后续设备通信与动作能力将按审查单元逐步启用。"
        )
        notice_text.setObjectName("notice_text")
        notice_text.setWordWrap(True)
        notice_layout = QVBoxLayout(notice)
        notice_layout.setContentsMargins(20, 16, 20, 16)
        notice_layout.addWidget(notice_title)
        notice_layout.addWidget(notice_text)

        capability = QFrame()
        capability.setObjectName("capability_panel")
        capability_title = QLabel("工程状态")
        capability_title.setObjectName("section_title")
        capability_text = QLabel(
            "✓  Python / PySide6 工程基线\n"
            "✓  可复现依赖与静态检查\n"
            "✓  无硬件 GUI 启动与关闭测试\n"
            "○  V1 协议与 Mock 通信 (下一单元)"
        )
        capability_text.setObjectName("capability_text")
        capability_layout = QVBoxLayout(capability)
        capability_layout.setContentsMargins(24, 20, 24, 20)
        capability_layout.addWidget(capability_title)
        capability_layout.addSpacing(8)
        capability_layout.addWidget(capability_text)

        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(42, 34, 42, 34)
        layout.addWidget(eyebrow)
        layout.addSpacing(8)
        layout.addLayout(heading)
        layout.addWidget(description)
        layout.addSpacing(30)
        layout.addLayout(status_row)
        layout.addSpacing(18)
        layout.addWidget(notice)
        layout.addSpacing(18)
        layout.addWidget(capability)
        layout.addStretch()
        return workspace

    @staticmethod
    def _status_card(label: str, value: str, detail: str) -> QFrame:
        card = QFrame()
        card.setObjectName("status_card")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setFixedHeight(132)

        label_widget = QLabel(label.upper())
        label_widget.setObjectName("card_label")
        value_widget = QLabel(value)
        value_widget.setObjectName("card_value")
        detail_widget = QLabel(detail)
        detail_widget.setObjectName("card_detail")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.addWidget(label_widget)
        layout.addStretch()
        layout.addWidget(value_widget)
        layout.addWidget(detail_widget)
        return card


_STYLE_SHEET = """
QMainWindow, QWidget#baseline_content, QWidget#workspace {
    background: #f3f5f7;
    color: #17212b;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
}
QFrame#sidebar {
    background: #101923;
    border: none;
}
QLabel#product_mark {
    color: #f6f8fa;
    font-size: 26px;
    font-weight: 800;
    letter-spacing: 3px;
}
QLabel#product_subtitle, QLabel#eyebrow {
    color: #7591a9;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#active_navigation {
    color: #ffffff;
    background: #1d9b8a;
    border-radius: 5px;
    font-size: 12px;
    font-weight: 700;
}
QLabel#future_navigation {
    color: #718294;
    font-size: 13px;
    line-height: 1.5;
}
QLabel#baseline_badge {
    color: #708295;
    border-top: 1px solid #273646;
    padding-top: 16px;
    font-size: 9px;
    font-weight: 600;
}
QLabel#application_title {
    color: #17212b;
    font-size: 32px;
    font-weight: 750;
}
QLabel#hero_description {
    color: #687480;
    font-size: 14px;
}
QLabel#connection_status {
    color: #52616d;
    background: #e5e9ec;
    border: 1px solid #d4dade;
    border-radius: 19px;
    font-size: 12px;
    font-weight: 700;
}
QFrame#status_card, QFrame#capability_panel {
    background: #ffffff;
    border: 1px solid #e0e5e8;
    border-radius: 7px;
}
QLabel#card_label {
    color: #89949d;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#card_value {
    color: #1b2731;
    font-size: 22px;
    font-weight: 700;
}
QLabel#card_detail, QLabel#notice_text {
    color: #75818a;
    font-size: 11px;
}
QFrame#safety_notice {
    background: #e8f5f2;
    border-left: 4px solid #1d9b8a;
    border-radius: 4px;
}
QLabel#notice_title {
    color: #146f64;
    font-size: 13px;
    font-weight: 700;
}
QLabel#section_title {
    color: #1b2731;
    font-size: 16px;
    font-weight: 700;
}
QLabel#capability_text {
    color: #56636e;
    font-size: 13px;
    line-height: 1.5;
}
"""
