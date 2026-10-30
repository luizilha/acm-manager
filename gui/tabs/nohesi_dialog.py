"""Diálogo para listar e instalar carros do CDN do No Hesi."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

import acm
from gui import i18n


class NoHesiCarsDialog(QDialog):
    """Tabela de carros de cdn.nohesi.gg, com seleção por tamanho."""

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.host = host
        self._index: list[dict] = []
        self._installed: set[str] = set()
        self.setWindowTitle(i18n.tr("Carros No Hesi (CDN)"))
        self.resize(840, 640)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(i18n.tr("Filtrar por nome do carro…"))
        self.search.textChanged.connect(self._filter)
        self.btn_missing = QPushButton(i18n.tr("Selecionar faltantes"))
        self.btn_missing.clicked.connect(self._select_missing)
        self.btn_clear = QPushButton(i18n.tr("Limpar seleção"))
        self.btn_clear.clicked.connect(self._clear)
        self.btn_refresh = QPushButton(i18n.tr("Atualizar lista"))
        self.btn_refresh.clicked.connect(lambda: self._load(force=True))
        top.addWidget(self.search, 1)
        top.addWidget(self.btn_missing)
        top.addWidget(self.btn_clear)
        top.addWidget(self.btn_refresh)
        layout.addLayout(top)

        hint = QLabel(i18n.tr(
            "Os arquivos vêm de cdn.nohesi.gg. A lista completa tem vários GB; "
            "marque só os carros que você precisa."
        ))
        hint.setObjectName("DropHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.summary = QLabel(i18n.tr("Carregando lista do CDN…"))
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([i18n.tr("Carro"), i18n.tr("Tamanho"), i18n.tr("Status")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemChanged.connect(self._update_summary)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        close = QPushButton(i18n.tr("Fechar"))
        close.clicked.connect(self.accept)
        self.btn_install = QPushButton(i18n.tr("Instalar selecionados"))
        self.btn_install.setObjectName("Primary")
        self.btn_install.setEnabled(False)
        self.btn_install.clicked.connect(self._install)
        buttons.addWidget(close)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_install)
        layout.addLayout(buttons)

    def _load(self, force: bool = False):
        self.btn_refresh.setEnabled(False)
        self.btn_install.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._index = acm.fetch_nohesi_car_index(force=force)
            ac = acm.detect_ac()
            local = acm.local_content(ac) if ac else {"cars": set()}
            self._installed = {str(car).lower() for car in (local.get("cars") or set())}
        except Exception as e:
            self._index = []
            self.host.append_log(f"[!] Lista No Hesi indisponível: {e}")
            QMessageBox.warning(
                self, i18n.tr("Carros No Hesi"),
                i18n.tr("Não consegui carregar a lista do CDN: {msg}", msg=str(e)),
            )
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_refresh.setEnabled(True)
        self._fill()

    def _fill(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._index))
        for row, item in enumerate(self._index):
            installed = item["model"].lower() in self._installed
            name = QTableWidgetItem(item["model"])
            flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            if not installed:
                flags |= Qt.ItemFlag.ItemIsUserCheckable
            name.setFlags(flags)
            name.setCheckState(Qt.CheckState.Unchecked)
            name.setData(Qt.ItemDataRole.UserRole, item)
            size = QTableWidgetItem(acm.human(item["size"]))
            size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            size.setFlags(Qt.ItemFlag.ItemIsEnabled)
            status = QTableWidgetItem(
                i18n.tr("instalado") if installed else i18n.tr("faltando")
            )
            status.setFlags(Qt.ItemFlag.ItemIsEnabled)
            status.setForeground(QColor("#7ee2a8" if installed else "#ffd479"))
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, size)
            self.table.setItem(row, 2, status)
        self.table.blockSignals(False)
        self._filter(self.search.text())
        self._update_summary()

    def _filter(self, text: str):
        needle = text.strip().lower()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            model = item.text().lower() if item else ""
            self.table.setRowHidden(row, bool(needle) and needle not in model)

    def _set_checked(self, rows, checked: bool):
        self.table.blockSignals(True)
        for row in rows:
            item = self.table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.table.blockSignals(False)
        self._update_summary()

    def _select_missing(self):
        rows = [
            row for row in range(self.table.rowCount())
            if (item := self.table.item(row, 0)) is not None
            and item.flags() & Qt.ItemFlag.ItemIsUserCheckable
            and not self.table.isRowHidden(row)
        ]
        self._set_checked(rows, True)

    def _clear(self):
        self._set_checked(range(self.table.rowCount()), False)

    def _selected(self) -> list[dict]:
        selected: list[dict] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, dict):
                    selected.append(data)
        return selected

    def _update_summary(self):
        selected = self._selected()
        total = sum(int(item.get("size") or 0) for item in selected)
        missing = sum(1 for item in self._index if item["model"].lower() not in self._installed)
        all_size = sum(int(item.get("size") or 0) for item in self._index)
        self.summary.setText(
            i18n.tr(
                "Lista: {n} carros · {size} no total · {missing} faltando. "
                "Selecionados: {sel} · {sel_size}.",
                n=len(self._index), size=acm.human(all_size), missing=missing,
                sel=len(selected), sel_size=acm.human(total),
            )
        )
        self.btn_install.setEnabled(bool(selected))

    def _install(self):
        selected = self._selected()
        if not selected:
            QMessageBox.information(self, i18n.tr("Carros No Hesi"), i18n.tr("Nenhum carro selecionado."))
            return
        total = sum(int(item.get("size") or 0) for item in selected)
        answer = QMessageBox.question(
            self, i18n.tr("Instalar carros No Hesi"),
            i18n.tr(
                "Baixar e instalar {n} carro(s) de cdn.nohesi.gg?\n\nTotal: {size}.",
                n=len(selected), size=acm.human(total),
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        models = [item["model"] for item in selected]
        index = self._index
        self.host.mark_installed_stale()
        self.accept()
        self.host.append_log(i18n.tr("Instalando {n} carro(s) do CDN No Hesi…", n=len(models)))
        self.host.run_task(
            i18n.tr("Instalar carros No Hesi"),
            lambda: acm.install_nohesi_cars(models, True, index),
        )
