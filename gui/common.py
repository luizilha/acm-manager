"""Widgets e helpers compartilhados entre as abas."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QImageReader, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

import acm
from gui import i18n

_PREVIEW_CACHE: "OrderedDict[tuple, QPixmap]" = OrderedDict()
_PREVIEW_CACHE_MAX = 32


def preview_pixmap(path, width: int, height: int) -> QPixmap | None:
    """Carrega e escala um preview, com cache pequeno em memória."""
    if not path:
        return None
    try:
        source = Path(path)
        stat = source.stat()
    except OSError:
        return None
    key = (str(source), stat.st_mtime_ns, int(width), int(height))
    cached = _PREVIEW_CACHE.get(key)
    if cached is not None:
        _PREVIEW_CACHE.move_to_end(key)
        return cached
    reader = QImageReader(str(source))
    reader.setAutoTransform(True)
    source_size = reader.size()
    if source_size.isValid() and (
        source_size.width() > width or source_size.height() > height
    ):
        reader.setScaledSize(
            source_size.scaled(
                QSize(int(width), int(height)),
                Qt.AspectRatioMode.KeepAspectRatio,
            )
        )
    image = reader.read()
    if image.isNull():
        return None
    pixmap = QPixmap.fromImage(image)
    if not source_size.isValid() and (
        pixmap.width() > width or pixmap.height() > height
    ):
        pixmap = pixmap.scaled(
            int(width), int(height),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    _PREVIEW_CACHE[key] = pixmap
    while len(_PREVIEW_CACHE) > _PREVIEW_CACHE_MAX:
        _PREVIEW_CACHE.popitem(last=False)
    return pixmap


def card(title: str) -> tuple[QFrame, QLabel]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(4)
    t = QLabel(title.upper())
    t.setObjectName("CardTitle")
    v = QLabel("—")
    v.setObjectName("CardValue")
    v.setWordWrap(True)
    v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(t)
    layout.addWidget(v)
    return frame, v


def archive_paths(mime) -> list[str]:
    paths: list[str] = []
    if mime.hasUrls():
        for url in mime.urls():
            p = url.toLocalFile()
            if p:
                paths.append(p)
    if not paths:
        for line in (mime.text() or "").splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("file://"):
                url = QUrl(line)
                p = url.toLocalFile()
                if p:
                    paths.append(p)
            elif line.startswith("/"):
                paths.append(line)
    return [
        p for p in paths
        if Path(p).suffix.lower() in acm.ARCHIVE_EXTS
        or Path(p).name.lower().endswith(".tar.gz")
    ]


class DropZone(QFrame):
    fileDropped = Signal(str)
    browseRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(190)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel("⬇")
        icon.setStyleSheet("font-size: 34px; color: #e10600;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(i18n.tr("Arraste o mod aqui"))
        title.setObjectName("DropTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel(i18n.tr(
            "Aceita .zip, .rar, .7z, .tar.gz — carro, pista, app, clima, fonte ou CSP\n"
            "ou clique nesta área para escolher o arquivo"
        ))
        hint.setObjectName("DropHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        for widget in (icon, title, hint):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(hint)

    def _accepts(self, event) -> bool:
        return bool(archive_paths(event.mimeData()))

    def mousePressEvent(self, event):
        self.browseRequested.emit()
        event.accept()

    def _set_drag(self, on: bool):
        self.setProperty("drag", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self._accepts(event):
            self._set_drag(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._accepts(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drag(False)
        event.accept()

    def dropEvent(self, event: QDropEvent):
        self._set_drag(False)
        paths = archive_paths(event.mimeData())
        if paths:
            self.fileDropped.emit(paths[0])
            event.acceptProposedAction()
        else:
            event.ignore()
