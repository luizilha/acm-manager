"""Infraestrutura de tarefas em segundo plano."""

from __future__ import annotations

import contextlib
import io

from PySide6.QtCore import QThread, Signal

from gui import i18n


class EmittingStream(io.TextIOBase):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        self.buffer = ""

    def write(self, text: str) -> int:
        self.buffer += text
        if "\n" in self.buffer:
            lines = self.buffer.split("\n")
            self.buffer = lines.pop()
            for line in lines:
                self.signal.emit(line)
        return len(text)

    def flush(self):
        if self.buffer:
            self.signal.emit(self.buffer)
            self.buffer = ""


class Worker(QThread):
    log = Signal(str)
    done = Signal(bool, str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        stream = EmittingStream(self.log)
        try:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                rc = self.fn()
            self.done.emit(rc == 0, i18n.tr("Concluído.") if rc == 0 else i18n.tr("Falhou (código {rc}).", rc=rc))
        except Exception as e:
            self.log.emit(f"[x] {e}")
            self.done.emit(False, str(e))
