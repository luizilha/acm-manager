"""Entrada da aplicação Qt e testes rápidos."""

from __future__ import annotations

import json
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import acm
from gui.constants import APP_NAME, APP_VERSION
from gui.main_window import MainWindow


def self_test() -> int:
    ac = acm.detect_ac()
    if not ac:
        print(json.dumps({"ok": False, "error": "AC não encontrado"}))
        return 1
    print(json.dumps({"ok": True, **ac.summary()}, indent=2, ensure_ascii=False))
    return 0


def screenshot(path: str) -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    app.processEvents()
    QTimer.singleShot(700, lambda: (window.grab().save(path), app.quit()))
    app.exec()
    print(path)
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    if "--screenshot" in sys.argv:
        index = sys.argv.index("--screenshot")
        return screenshot(sys.argv[index + 1] if index + 1 < len(sys.argv) else "acm.png")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()
