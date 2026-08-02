"""Application theme definitions for operator console surfaces."""

DARK_THEME = """
QWidget {
    background: #111820;
    color: #dbe5ec;
    font-size: 13px;
}
QLabel { background: transparent; }
QFrame#header, QFrame#status_bar {
    background: #17232d;
    border: 1px solid #263746;
}
QFrame#navigation {
    background: #0c131a;
    border-right: 1px solid #24323d;
}
QWidget#navigation_content, QScrollArea#navigation_scroll,
QScrollArea#navigation_scroll > QWidget > QWidget {
    background: #0c131a;
}
QPushButton {
    background: #1d2c37;
    border: 1px solid #314655;
    border-radius: 6px;
    padding: 8px 12px;
    text-align: left;
}
QPushButton:hover { background: #263b49; }
QPushButton:checked {
    background: #167d72;
    color: white;
    border-color: #1fa394;
}
QPushButton[role="primary"] {
    background: #167d72;
    border-color: #1fa394;
    color: white;
    font-weight: 700;
    text-align: center;
}
QPushButton[role="primary"]:hover { background: #1b9184; }
QPushButton[role="warning"] {
    background: #4a381d;
    border-color: #8a652c;
    color: #ffe1aa;
    font-weight: 600;
    text-align: center;
}
QPushButton[role="danger"] {
    background: #542626;
    border-color: #8f3f3f;
    color: #ffd7d7;
    font-weight: 600;
    text-align: center;
}
QPushButton:disabled {
    color: #788690;
    background: #182129;
}
QPushButton:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QLineEdit:focus, QTextEdit:focus,
QPlainTextEdit:focus {
    border: 2px solid #55a7ff;
}
QPushButton#global_stop_button {
    background: #6b2a2a;
    border-color: #9a3d3d;
    color: #ffe8e8;
    font-weight: 700;
    text-align: center;
}
QPushButton#global_stop_button:hover { background: #823333; }
QFrame[class="status_card"], QFrame[class="metric_card"] {
    background: #17232d;
    border: 1px solid #2b3d4b;
    border-radius: 8px;
}
QFrame[class="status_card"][tone="ok"] { border-left: 3px solid #2aa899; }
QFrame[class="status_card"][tone="warning"] { border-left: 3px solid #d69a3a; }
QFrame[class="status_card"][tone="danger"] { border-left: 3px solid #d85b5b; }
QLabel#dashboard_card_caption {
    color: #8ea2b0;
    font-size: 12px;
    font-weight: 600;
}
QLabel[class="dashboard_card_value"] { font-size: 15px; font-weight: 600; }
QLabel#dashboard_auto_home {
    color: #ffd18a;
    background: #3b2d18;
    border-radius: 6px;
    padding: 7px 10px;
}
QLabel#dashboard_session_metrics { color: #8ea2b0; }
QLabel[class="action_lock"] {
    color: #ffd18a;
    background: #3b2d18;
    border: 1px solid #6b5128;
    border-radius: 6px;
    padding: 7px 10px;
}
QLabel[class="action_lock"][unlocked="true"] {
    color: #a7e7de;
    background: #15332f;
    border-color: #245f57;
}
QScrollBar:vertical {
    background: #0c131a;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #415362;
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QLabel#page_title {
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 0.2px;
}
QLabel#page_subtitle {
    color: #9fb0bc;
}
QLabel#profile_chip {
    color: #9fb0bc;
}
QLabel#nav_group_heading {
    color: #7f93a1;
}
QLabel#connection_error {
    background: #4a2222;
    border: 1px solid #9a3d3d;
    border-radius: 5px;
    color: #ffd9d4;
    padding: 8px 10px;
}
QLabel#badge,
QLabel#connection_badge,
QLabel#firmware_badge,
QLabel#snapshot_age_badge,
QLabel#fault_badge,
QLabel#auto_home_badge {
    background: #24343f;
    border: 1px solid #314655;
    border-radius: 12px;
    padding: 5px 10px;
}
QLabel#fault_badge { color: #ffb4a8; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QTextEdit, QPlainTextEdit {
    background: #152029;
    border: 1px solid #314655;
    border-radius: 5px;
    padding: 5px 8px;
    selection-background-color: #167d72;
}
QComboBox::drop-down { border: none; width: 22px; }
QStackedWidget { background: #111820; }
QScrollArea { border: none; }
QFormLayout, QGridLayout { spacing: 10px; }
"""

LIGHT_THEME = """
QWidget {
    background: #f3f5f7;
    color: #17212b;
    font-size: 13px;
}
QLabel { background: transparent; }
QFrame#header, QFrame#status_bar {
    background: #ffffff;
    border: 1px solid #d5dde4;
}
QFrame#navigation {
    background: #e8eef3;
    border-right: 1px solid #d5dde4;
}
QWidget#navigation_content, QScrollArea#navigation_scroll,
QScrollArea#navigation_scroll > QWidget > QWidget {
    background: #e8eef3;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #c8d2db;
    border-radius: 6px;
    padding: 8px 12px;
    text-align: left;
}
QPushButton:hover { background: #eef3f7; }
QPushButton:checked {
    background: #0f766e;
    color: white;
    border-color: #0f766e;
}
QPushButton[role="primary"] {
    background: #0f766e;
    border-color: #0f766e;
    color: white;
    font-weight: 700;
    text-align: center;
}
QPushButton[role="primary"]:hover { background: #0d8b80; }
QPushButton[role="warning"] {
    background: #fff4d6;
    border-color: #d8b45b;
    color: #7a4d0e;
    font-weight: 600;
    text-align: center;
}
QPushButton[role="danger"] {
    background: #fde8e8;
    border-color: #dc8b8b;
    color: #991b1b;
    font-weight: 600;
    text-align: center;
}
QPushButton:disabled {
    color: #8a96a1;
    background: #eef1f4;
}
QPushButton:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QLineEdit:focus, QTextEdit:focus,
QPlainTextEdit:focus {
    border: 2px solid #2563eb;
}
QPushButton#global_stop_button {
    background: #b91c1c;
    border-color: #991b1b;
    color: #ffffff;
    font-weight: 700;
    text-align: center;
}
QPushButton#global_stop_button:hover { background: #dc2626; }
QFrame[class="status_card"], QFrame[class="metric_card"] {
    background: #ffffff;
    border: 1px solid #d5dde4;
    border-radius: 8px;
}
QFrame[class="status_card"][tone="ok"] { border-left: 3px solid #0f766e; }
QFrame[class="status_card"][tone="warning"] { border-left: 3px solid #b7791f; }
QFrame[class="status_card"][tone="danger"] { border-left: 3px solid #b91c1c; }
QLabel#dashboard_card_caption {
    color: #647482;
    font-size: 12px;
    font-weight: 600;
}
QLabel[class="dashboard_card_value"] { font-size: 15px; font-weight: 600; }
QLabel#dashboard_auto_home {
    color: #8a5a12;
    background: #fff4d6;
    border-radius: 6px;
    padding: 7px 10px;
}
QLabel#dashboard_session_metrics { color: #647482; }
QLabel[class="action_lock"] {
    color: #8a5a12;
    background: #fff4d6;
    border: 1px solid #e6c978;
    border-radius: 6px;
    padding: 7px 10px;
}
QLabel[class="action_lock"][unlocked="true"] {
    color: #0f5f58;
    background: #e1f5f1;
    border-color: #89cfc4;
}
QScrollBar:vertical {
    background: #e8eef3;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #9aa8b4;
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QLabel#page_title {
    font-size: 24px;
    font-weight: 700;
}
QLabel#page_subtitle {
    color: #5b6b78;
}
QLabel#profile_chip {
    color: #5b6b78;
}
QLabel#nav_group_heading {
    color: #6b7b88;
}
QLabel#connection_error {
    background: #fde8e8;
    border: 1px solid #dc2626;
    border-radius: 5px;
    color: #991b1b;
    padding: 8px 10px;
}
QLabel#badge,
QLabel#connection_badge,
QLabel#firmware_badge,
QLabel#snapshot_age_badge,
QLabel#fault_badge,
QLabel#auto_home_badge {
    background: #e8eef3;
    border: 1px solid #c8d2db;
    border-radius: 12px;
    padding: 5px 10px;
}
QLabel#fault_badge { color: #b91c1c; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QTextEdit, QPlainTextEdit {
    background: #ffffff;
    border: 1px solid #c8d2db;
    border-radius: 5px;
    padding: 5px 8px;
    selection-background-color: #0f766e;
}
QComboBox::drop-down { border: none; width: 22px; }
QStackedWidget { background: #f3f5f7; }
QScrollArea { border: none; }
"""
