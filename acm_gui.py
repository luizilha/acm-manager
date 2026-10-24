#!/usr/bin/env python3
"""Entrada do AC Manager; a implementação fica no pacote ``gui``."""

from __future__ import annotations

from gui.app import main, screenshot, self_test
from gui.common import DropZone, archive_paths, card
from gui.constants import APP_NAME, APP_VERSION
from gui.main_window import MainWindow
from gui.theme import STYLE
from gui.tabs.servers import SERVER_DISPLAY_LIMIT
from gui.workers import EmittingStream, Worker

__all__ = [
    "main", "screenshot", "self_test", "MainWindow", "STYLE",
    "APP_NAME", "APP_VERSION", "SERVER_DISPLAY_LIMIT",
    "DropZone", "archive_paths", "card", "EmittingStream", "Worker",
]

if __name__ == "__main__":
    raise SystemExit(main())
