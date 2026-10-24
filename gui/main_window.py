"""Shell da janela: header, abas, log e execução de tarefas."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSignalBlocker, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QTabWidget, QVBoxLayout,
    QWidget,
)

from gui import i18n
from gui.common import archive_paths
from gui.constants import APP_NAME, APP_VERSION
from gui.tabs.installed import InstalledTab
from gui.tabs.install_mods import InstallModsTab
from gui.tabs.linux_status import LinuxStatusTab
from gui.tabs.servers import ServersTab
from gui.theme import STYLE
from gui.workers import Worker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(i18n.tr("AC Manager — Assetto Corsa no Linux"))
        self.resize(1180, 840)
        self.setMinimumSize(980, 700)
        self.setAcceptDrops(True)
        QApplication.instance().installEventFilter(self)
        self.worker: Worker | None = None
        self._build()
        self.setStyleSheet(STYLE)
        self.status_tab.refresh()

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(22, 18, 22, 16)
        outer.setSpacing(12)

        header = QHBoxLayout()
        logo = QLabel("AC")
        logo.setFixedSize(52, 52)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            "background:#d80b16;color:white;border-radius:12px;"
            "font-size:20px;font-weight:800;"
        )
        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel(APP_NAME)
        title.setObjectName("Title")
        subtitle = QLabel(i18n.tr("Assetto Corsa no Linux, sem Content Manager"))
        subtitle.setObjectName("Subtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addWidget(logo)
        header.addLayout(titles)
        header.addStretch(1)
        self.language = QComboBox()
        for code, label in i18n.LANGUAGES.items():
            self.language.addItem(label, code)
        self.language.setCurrentIndex(max(0, list(i18n.LANGUAGES).index(i18n.current_language())))
        self.language.setToolTip("Português / English")
        self.language.currentIndexChanged.connect(self._language_changed)
        header.addWidget(self.language)
        outer.addLayout(header)

        self.tabs = QTabWidget()
        self.status_tab = LinuxStatusTab(self)
        self.install_tab = InstallModsTab(self)
        self.servers_tab = ServersTab(self)
        self.installed_tab = InstalledTab(self)
        self.tabs.addTab(self.status_tab, i18n.tr("Linux Status"))
        self.tabs.addTab(self.install_tab, i18n.tr("Instalar mods"))
        self.tabs.addTab(self.servers_tab, i18n.tr("Servidores"))
        self.tabs.addTab(self.installed_tab, i18n.tr("Instalados"))
        self.tabs.currentChanged.connect(self._on_tab_changed)
        outer.addWidget(self.tabs, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        outer.addWidget(self.progress)

        log_head = QHBoxLayout()
        log_label = QLabel(i18n.tr("Log"))
        log_label.setObjectName("Section")
        log_head.addWidget(log_label)
        log_head.addStretch(1)
        clear = QPushButton(i18n.tr("Limpar log"))
        clear.clicked.connect(lambda: self.log.clear())
        log_head.addWidget(clear)
        outer.addLayout(log_head)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.log.setMinimumHeight(110)
        self.log.setMaximumHeight(180)
        outer.addWidget(self.log)

        foot = QHBoxLayout()
        foot.addWidget(QLabel(i18n.tr("Protótipo — análise local, sem Content Manager.")))
        foot.addStretch(1)
        foot.addWidget(QLabel(f"v{APP_VERSION}"))
        outer.addLayout(foot)

    def _language_changed(self, index: int):
        code = self.language.itemData(index)
        if not code or code == i18n.current_language():
            return
        if self.worker and self.worker.isRunning():
            QMessageBox.information(
                self, i18n.tr("Idioma"),
                i18n.tr("Aguarde a tarefa atual terminar para trocar o idioma."),
            )
            blocker = QSignalBlocker(self.language)
            self.language.setCurrentIndex(
                max(0, list(i18n.LANGUAGES).index(i18n.current_language()))
            )
            del blocker
            return
        i18n.set_language(code)
        self._rebuild_ui()

    def _rebuild_ui(self):
        self.servers_tab.shutdown()
        self.installed_tab.shutdown()
        old = self.centralWidget()
        if old is not None:
            old.hide()
            old.setParent(None)
            old.deleteLater()
        self._build()
        self.setStyleSheet(STYLE)
        self.setWindowTitle(i18n.tr("AC Manager — Assetto Corsa no Linux"))
        self.status_tab.refresh()

    def append_log(self, line: str):
        if line:
            self.log.appendPlainText(line)

    def mark_installed_stale(self):
        self.installed_tab.mark_stale()

    def _set_busy(self, on: bool):
        self.status_tab.set_busy(on)
        self.install_tab.set_busy(on)
        self.servers_tab.set_busy(on)
        self.installed_tab.set_busy(on)
        self.progress.setVisible(on)

    def run_task(self, title: str, fn, confirm: str | None = None):
        if self.worker and self.worker.isRunning():
            return
        if confirm:
            answer = QMessageBox.question(
                self, title, confirm,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.append_log(f"\n=== {title} ===")
        self._set_busy(True)
        self.worker = Worker(fn)
        self.worker.log.connect(self.append_log)
        self.worker.done.connect(lambda ok, msg: self._finished(title, ok, msg))
        self.worker.start()

    def _finished(self, title: str, ok: bool, msg: str):
        self._set_busy(False)
        self.worker = None
        self.append_log(f"[{'✓' if ok else 'x'}] {msg}")
        self.status_tab.refresh()
        self.servers_tab._reload_local_content()
        if self.tabs.currentIndex() == 2:
            self.servers_tab.apply_server_filter()
        if self.installed_tab._stale and self.tabs.currentIndex() == 3:
            self.installed_tab.refresh()
        if not ok:
            QMessageBox.warning(self, title, msg)
        else:
            self.statusBar().showMessage(f"{title}: {msg}", 6000)

    def _on_tab_changed(self, index: int):
        if index == 2:
            self.servers_tab.on_activated()
        elif index == 3:
            self.installed_tab.on_activated()

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            mime = getattr(event, "mimeData", lambda: None)()
            if mime is not None and archive_paths(mime):
                event.acceptProposedAction()
                return True
        elif kind == QEvent.Type.Drop:
            mime = getattr(event, "mimeData", lambda: None)()
            if mime is not None:
                paths = archive_paths(mime)
                if paths:
                    self.tabs.setCurrentIndex(1)
                    self.install_tab.accept_drop(paths[0])
                    event.acceptProposedAction()
                    return True
        return super().eventFilter(obj, event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if archive_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if archive_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        paths = archive_paths(event.mimeData())
        if paths:
            self.tabs.setCurrentIndex(1)
            self.install_tab.accept_drop(paths[0])
            event.acceptProposedAction()
        else:
            event.ignore()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            if not self.worker.wait(2500):
                self.worker.terminate()
                self.worker.wait(500)
        self.servers_tab.shutdown()
        self.installed_tab.shutdown()
        super().closeEvent(event)
