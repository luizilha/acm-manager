"""Aba Instalar mods: arquivo local, drag-and-drop e URL direta."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

import acm
from gui import i18n
from gui.common import DropZone


class InstallModsTab(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self._selected_file: str | None = None
        self._build()

    def _build(self):
        body = QHBoxLayout(self)
        body.setContentsMargins(12, 12, 12, 12)
        body.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(10)

        self.drop = DropZone()
        self.drop.fileDropped.connect(self.accept_drop)
        self.drop.browseRequested.connect(self.pick_file)
        left.addWidget(self.drop)

        self.file_label = QLabel(i18n.tr("Nenhum arquivo selecionado"))
        self.file_label.setObjectName("DropHint")
        self.file_label.setWordWrap(True)
        left.addWidget(self.file_label)

        row = QHBoxLayout()
        self.force = QCheckBox(i18n.tr("Substituir existentes"))
        self.btn_install_mod = QPushButton(i18n.tr("Instalar mod selecionado"))
        self.btn_install_mod.setObjectName("Primary")
        self.btn_install_mod.setEnabled(False)
        self.btn_install_mod.clicked.connect(self.install_mod)
        self.btn_pick = QPushButton(i18n.tr("Escolher arquivo…"))
        self.btn_pick.clicked.connect(self.pick_file)
        row.addWidget(self.btn_pick)
        row.addWidget(self.force)
        row.addStretch(1)
        row.addWidget(self.btn_install_mod)
        left.addLayout(row)

        url_row = QHBoxLayout()
        self.mod_url = QLineEdit()
        self.mod_url.setPlaceholderText(i18n.tr("Cole uma URL direta .zip/.rar/.7z para baixar e instalar…"))
        self.btn_url = QPushButton(i18n.tr("Baixar da URL"))
        self.btn_url.clicked.connect(self.download_mod_url)
        url_row.addWidget(self.mod_url, 1)
        url_row.addWidget(self.btn_url)
        left.addLayout(url_row)

        hint = QLabel(i18n.tr(
            "O arquivo é extraído em staging, o conteúdo é detectado e copiado para o AC. "
            "RAR usa unrar; 7z usa 7z/7zz ou bsdtar."
        ))
        hint.setObjectName("DropHint")
        hint.setWordWrap(True)
        left.addWidget(hint)
        left.addStretch(1)
        body.addLayout(left, 1)

    def set_busy(self, on: bool):
        self.btn_pick.setEnabled(not on)
        self.btn_url.setEnabled(not on)
        self.force.setEnabled(not on)
        self.btn_install_mod.setEnabled(not on and bool(self._selected_file))

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, i18n.tr("Escolher mod"), str(Path.home() / "Downloads"),
            i18n.tr("Mods (*.zip *.rar *.7z *.tar *.gz *.tgz *.bz2 *.xz);;Todos os arquivos (*)"),
        )
        if path:
            self.accept_drop(path)

    def accept_drop(self, path: str):
        self._selected_file = path
        self.file_label.setText(i18n.tr("Arquivo selecionado: {path}", path=path))
        self.btn_install_mod.setEnabled(True)
        self.host.append_log(i18n.tr("[i] Arquivo selecionado: {path}", path=path))

    def install_mod(self):
        if not self._selected_file:
            return
        force = self.force.isChecked()
        self.host.mark_installed_stale()
        self.host.run_task(
            i18n.tr("Instalar mod"),
            lambda: acm.install_mod(self._selected_file, False, force, False, False, True),
            i18n.tr("Instalar o mod?\n\n{name}\n\n{replace}", name=Path(self._selected_file).name, replace=i18n.tr("Substituindo o que já existe (com backup).") if force else i18n.tr("Itens existentes serão mantidos."))
        )

    def download_mod_url(self):
        url = self.mod_url.text().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, i18n.tr("Baixar da URL"), i18n.tr("A URL precisa começar com http:// ou https://."))
            return
        force = self.force.isChecked()
        self.host.mark_installed_stale()
        self.host.run_task(
            i18n.tr("Baixar mod da URL"),
            lambda: acm.install_mod(url, False, force, False, False, True),
            i18n.tr("Baixar e instalar esse mod?\n\n{url}", url=url),
        )
