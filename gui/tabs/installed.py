"""Aba Instalados: inventário, tamanhos e remoção para a lixeira."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

import acm
from gui import i18n
from gui.common import preview_pixmap


class InstalledWorker(QThread):
    data = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            ac = acm.detect_ac()
            if not ac:
                self.failed.emit(i18n.tr("AC não encontrado."))
                return
            self.data.emit(acm.installed_content(ac))
        except Exception as e:
            self.failed.emit(str(e))


class InstalledTab(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self._installed: list[dict] = []
        self._worker: InstalledWorker | None = None
        self._stale = True
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        top = QHBoxLayout()
        self.installed_filter = QLineEdit()
        self.installed_filter.setPlaceholderText(i18n.tr("Filtrar por tipo ou nome…"))
        self.installed_filter.textChanged.connect(self.apply_filter)
        self.installed_show_official = QCheckBox(i18n.tr("Mostrar oficiais (base/DLC)"))
        self.installed_show_official.stateChanged.connect(lambda _: self.apply_filter())
        self.installed_refresh = QPushButton(i18n.tr("Atualizar tamanhos"))
        self.installed_refresh.clicked.connect(self.refresh)
        self.installed_delete = QPushButton(i18n.tr("Excluir selecionado"))
        self.installed_delete.setEnabled(False)
        self.installed_delete.clicked.connect(self.delete_selected)
        top.addWidget(self.installed_filter, 1)
        top.addWidget(self.installed_show_official)
        top.addWidget(self.installed_refresh)
        top.addWidget(self.installed_delete)
        layout.addLayout(top)

        self.installed_status = QLabel(i18n.tr("Abra esta aba para calcular os tamanhos."))
        self.installed_status.setObjectName("DropHint")
        self.installed_status.setWordWrap(True)
        layout.addWidget(self.installed_status)

        self.installed_table = QTableWidget(0, 4)
        self.installed_table.setHorizontalHeaderLabels([i18n.tr("Tipo"), i18n.tr("Nome"), i18n.tr("Tamanho"), i18n.tr("Caminho")])
        self.installed_table.verticalHeader().setVisible(False)
        self.installed_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.installed_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.installed_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.installed_table.setAlternatingRowColors(True)
        self.installed_table.setCornerButtonEnabled(False)
        header = self.installed_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.installed_table.itemSelectionChanged.connect(self._selection_changed)

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self.installed_table, 1)
        body.addWidget(self._build_preview_panel())
        layout.addLayout(body, 1)

        note = QLabel(i18n.tr(
            "Excluir move o item para ~/.local/share/acm/trash (não apaga de vez). "
            "Conteúdo oficial (base/DLC) é protegido."
        ))
        note.setObjectName("DropHint")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _build_preview_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Card")
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(340)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        panel_layout.setSpacing(5)

        self.preview = QLabel(i18n.tr("Selecione um item"))
        self.preview.setObjectName("Preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(300, 130)
        panel_layout.addWidget(self.preview)

        self.preview_title = QLabel("—")
        self.preview_title.setWordWrap(True)
        self.preview_title.setMaximumHeight(42)
        self.preview_title.setStyleSheet("font-size:15px;font-weight:700;")
        panel_layout.addWidget(self.preview_title)

        self.preview_meta = QLabel("")
        self.preview_meta.setObjectName("DropHint")
        self.preview_meta.setWordWrap(True)
        self.preview_meta.setMaximumHeight(36)
        panel_layout.addWidget(self.preview_meta)
        panel_layout.addStretch(1)
        return panel

    def on_activated(self):
        if (not self._installed or self._stale) and not (
            self._worker and self._worker.isRunning()
        ):
            self.refresh()

    def set_busy(self, on: bool):
        self.installed_refresh.setEnabled(not on)
        self.installed_delete.setEnabled(not on and bool(self.installed_table.selectedItems()))

    def shutdown(self):
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            if not self._worker.wait(2500):
                self._worker.terminate()
                self._worker.wait(500)

    def mark_stale(self):
        self._stale = True

    def refresh(self):
        if self._worker and self._worker.isRunning():
            return
        self.installed_refresh.setEnabled(False)
        self.installed_status.setText(i18n.tr("Calculando tamanhos…"))
        self._worker = InstalledWorker()
        self._worker.data.connect(self._loaded)
        self._worker.failed.connect(self._failed)
        self._worker.start()

    def _loaded(self, items):
        self._installed = items
        self._stale = False
        self.installed_refresh.setEnabled(True)
        self.apply_filter()

    def _failed(self, msg: str):
        self.installed_refresh.setEnabled(True)
        self.installed_status.setText(i18n.tr("Falha ao calcular: {msg}", msg=msg))
        self.host.append_log(f"[x] Instalados: {msg}")

    def apply_filter(self):
        text = self.installed_filter.text().lower().strip()
        matched = [
            item for item in self._installed
            if text in item["name"].lower()
            or text in item["kind"].lower()
            or text in item["path"].lower()
        ]
        if not self.installed_show_official.isChecked():
            rows = [item for item in matched if not item.get("base")]
        else:
            rows = matched
        hidden = len(matched) - len(rows)
        self.installed_table.setRowCount(0)
        self.installed_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            kind = QTableWidgetItem(i18n.tr(item["kind"]))
            name = QTableWidgetItem(item["name"])
            name.setData(Qt.ItemDataRole.UserRole, item)
            size = QTableWidgetItem(acm.human(item["size"]))
            size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            path = QTableWidgetItem(item["path"])
            if item.get("base"):
                kind.setForeground(QColor("#98a0ad"))
            for column, cell in enumerate([kind, name, size, path]):
                self.installed_table.setItem(row, column, cell)
        total = sum(item["size"] for item in rows)
        label = i18n.tr("itens") if self.installed_show_official.isChecked() else i18n.tr("mods de terceiros")
        extra = (
            i18n.tr(" · {n} oficiais ocultos", n=hidden)
            if hidden and not self.installed_show_official.isChecked() else ""
        )
        self.installed_status.setText(i18n.tr("{n} {label} · {size}{extra}", n=len(rows), label=label, size=acm.human(total), extra=extra))
        self._selection_changed()

    def _selection_changed(self):
        rows = sorted({item.row() for item in self.installed_table.selectedItems()})
        self.installed_delete.setEnabled(bool(rows))
        if len(rows) != 1:
            self._show_preview(None, len(rows))
            return
        cell = self.installed_table.item(rows[0], 1)
        item = cell.data(Qt.ItemDataRole.UserRole) if cell else None
        self._show_preview(item, 1)

    def _show_preview(self, item: dict | None, count: int):
        if not item:
            self.preview.clear()
            self.preview.setToolTip("")
            self.preview.setText(
                i18n.tr("{n} itens selecionados", n=count)
                if count > 1 else i18n.tr("Selecione um item")
            )
            self.preview_title.setText("—")
            self.preview_title.setToolTip("")
            self.preview_meta.setText("")
            return
        path = Path(item["path"])
        image = acm.content_preview_path(item["kind"], path)
        pixmap = preview_pixmap(image, 300, 130)
        if pixmap is not None and not pixmap.isNull():
            self.preview.setPixmap(pixmap)
            self.preview.setText("")
        else:
            self.preview.clear()
            self.preview.setText(i18n.tr("Sem preview"))
        self.preview.setToolTip(item["path"])

        title = item["name"]
        meta = [f"{i18n.tr(item['kind'])} · {acm.human(item['size'])}"]
        specs_tip = ""
        if item["kind"] == "car":
            info = acm.car_metadata(path)
            title = info["name"] or title
            extra = [
                value for value in (info.get("brand"), info.get("class"), info.get("year"))
                if value
            ]
            if extra:
                meta.append(" · ".join(extra))
            specs = info.get("specs") or {}
            specs_tip = " · ".join(
                str(specs[key]) for key in ("bhp", "weight", "topspeed", "pwratio")
                if specs.get(key)
            )
        self.preview_title.setText(title)
        self.preview_title.setToolTip(item["path"])
        self.preview_meta.setText("\n".join(meta))
        self.preview_meta.setToolTip(specs_tip)

    def delete_selected(self):
        rows = sorted({item.row() for item in self.installed_table.selectedItems()})
        if not rows:
            return
        items = []
        for row in rows:
            item = self.installed_table.item(row, 1)
            if item and item.data(Qt.ItemDataRole.UserRole):
                items.append(item.data(Qt.ItemDataRole.UserRole))
        if not items:
            return
        names = "\n".join(
            f"- {i18n.tr(item['kind'])}: {item['name']} ({acm.human(item['size'])})"
            for item in items[:15]
        )
        answer = QMessageBox.question(
            self, i18n.tr("Excluir conteúdo"),
            i18n.tr("Mover {n} item(ns) para a lixeira?\n\n{names}", n=len(items), names=names),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        def do_delete() -> int:
            errors = []
            for item in items:
                try:
                    acm.delete_content(item["path"])
                except Exception as e:
                    errors.append(f"{item['name']}: {e}")
            if errors:
                for error in errors:
                    acm.eprint(f"[x] {error}")
                return 1
            return 0

        self.mark_stale()
        self.host.run_task(i18n.tr("Excluir conteúdo"), do_delete)
