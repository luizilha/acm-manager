"""Tema visual (Qt/Fusion)."""

STYLE = """
QMainWindow, QWidget { background: #0e1015; color: #eef1f6; }
QLabel { color: #eef1f6; background: transparent; }
QLabel#Title { font-size: 26px; font-weight: 700; }
QLabel#Subtitle { color: #98a0ad; font-size: 13px; }
QLabel#Section { color: #c7ccd6; font-size: 15px; font-weight: 600; }
QFrame#Card {
    background: #171a21;
    border: 1px solid #242936;
    border-radius: 10px;
}
QFrame#Banner {
    background: #241417;
    border: 1px solid #5a1f27;
    border-radius: 10px;
}
QLabel#CardTitle { color: #8e97a6; font-size: 11px; font-weight: 600; text-transform: uppercase; }
QLabel#CardValue { color: #f3f5f8; font-size: 13px; }
QPushButton {
    background: #1c2029;
    border: 1px solid #2c3240;
    border-radius: 8px;
    padding: 8px 14px;
    color: #e9edf3;
}
QPushButton:hover { background: #252b37; border-color: #3a4252; }
QPushButton:pressed { background: #13161c; }
QPushButton#Primary {
    background: #d80b16;
    border: 1px solid #f02a33;
    color: white;
    font-weight: 600;
}
QPushButton#Primary:hover { background: #ef1a25; }
QPushButton:disabled { color: #6f7683; background: #151820; border-color: #222733; }
QPushButton#Primary:disabled { color: #a56469; background: #351418; border-color: #4a1a1f; }
QFrame#DropZone {
    background: #12151b;
    border: 2px dashed #333a48;
    border-radius: 12px;
}
QFrame#DropZone[drag="true"] {
    background: #1d1216;
    border-color: #e10600;
}
QLabel#DropTitle { font-size: 18px; font-weight: 600; color: #e8ebf1; }
QLabel#DropHint { color: #98a0ad; font-size: 12px; }
QPlainTextEdit {
    background: #0b0d11;
    border: 1px solid #242936;
    border-radius: 10px;
    color: #cfd5df;
    font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    font-size: 11px;
    padding: 6px;
}
QProgressBar {
    background: #171a21;
    border: 1px solid #242936;
    border-radius: 5px;
    max-height: 8px;
    text-align: center;
}
QProgressBar::chunk { background: #e10600; border-radius: 4px; }
QCheckBox { color: #cfd5df; }
QMessageBox { background: #171a21; }
QTabWidget::pane {
    border: 1px solid #242936;
    border-radius: 10px;
    top: -1px;
}
QTabBar::tab {
    background: #12151b;
    border: 1px solid #242936;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: #98a0ad;
}
QTabBar::tab:selected {
    background: #1c2029;
    color: #ffffff;
    border-bottom: 2px solid #e10600;
}
QLineEdit {
    background: #12151b;
    border: 1px solid #2c3240;
    border-radius: 8px;
    padding: 8px 10px;
    color: #eef1f6;
}
QTableWidget {
    background: #0f1218;
    alternate-background-color: #141822;
    border: 1px solid #242936;
    border-radius: 10px;
    gridline-color: #1f2532;
    selection-background-color: #2a1518;
    selection-color: #ffffff;
}
QHeaderView::section {
    background: #171a21;
    color: #98a0ad;
    border: 0;
    border-bottom: 1px solid #242936;
    padding: 7px;
    font-weight: 600;
}
QTableWidget::item { padding: 4px; }
QTableWidget::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #3a4150;
    border-radius: 3px;
    background: #12151b;
}
QTableWidget::indicator:hover { border-color: #e10600; }
QTableWidget::indicator:checked {
    background: #e10600;
    border-color: #e10600;
}
QTableWidget::indicator:disabled {
    background: #171a21;
    border-color: #242936;
}
QTableCornerButton::section { background: #171a21; border: 0; }
QScrollBar:vertical { background: #0f1218; width: 10px; margin: 0; border: none; }
QScrollBar::handle:vertical { background: #2c3240; min-height: 24px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0; background: #0f1218; border: none;
}
QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
    background: #0f1218; image: none; border: none;
}
QTableWidget QTableCornerButton::section { background: #171a21; border: none; }
QHeaderView::section:last { border-right: none; }
"""
