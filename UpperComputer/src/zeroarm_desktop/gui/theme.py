"""Application theme definitions for operator console surfaces."""

DARK_THEME = """
QWidget {
    background: #111820;
    color: #dbe5ec;
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", sans-serif;
    font-size: 13px;
}
QFrame#header, QFrame#status_bar {
    background: #17232d;
    border: 1px solid #263746;
}
QFrame#navigation {
    background: #0c131a;
    border-right: 1px solid #24323d;
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
QPushButton:disabled {
    color: #788690;
    background: #182129;
}
QPushButton#global_stop_button {
    background: #6b2a2a;
    border-color: #9a3d3d;
    color: #ffe8e8;
    font-weight: 700;
    text-align: center;
}
QPushButton#global_stop_button:hover { background: #823333; }
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
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", sans-serif;
    font-size: 13px;
}
QFrame#header, QFrame#status_bar {
    background: #ffffff;
    border: 1px solid #d5dde4;
}
QFrame#navigation {
    background: #e8eef3;
    border-right: 1px solid #d5dde4;
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
QPushButton:disabled {
    color: #8a96a1;
    background: #eef1f4;
}
QPushButton#global_stop_button {
    background: #b91c1c;
    border-color: #991b1b;
    color: #ffffff;
    font-weight: 700;
    text-align: center;
}
QPushButton#global_stop_button:hover { background: #dc2626; }
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
