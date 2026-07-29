"""Application theme definitions."""

DARK_THEME = """
QWidget { background: #111820; color: #dbe5ec; font-family: "Segoe UI", "Microsoft YaHei UI"; }
QFrame#header, QFrame#status_bar { background: #17232d; border: 1px solid #263746; }
QFrame#navigation { background: #0c131a; }
QPushButton {
    background: #1d2c37; border: 1px solid #314655;
    border-radius: 5px; padding: 8px 12px;
}
QPushButton:hover { background: #263b49; }
QPushButton:checked { background: #167d72; color: white; }
QPushButton:disabled { color: #788690; background: #182129; }
QLabel#page_title { font-size: 25px; font-weight: 700; }
QLabel#badge { background: #24343f; border-radius: 12px; padding: 5px 10px; }
QStackedWidget { background: #111820; }
"""

LIGHT_THEME = DARK_THEME.replace("#111820", "#f3f5f7").replace("#dbe5ec", "#17212b")
