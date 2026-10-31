"""Seletor de carro com preview de showroom e dados do ui_car.json."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout,
)

import acm
from gui import i18n
from gui.common import preview_pixmap

PREVIEW_WIDTH = 360
PREVIEW_HEIGHT = 200


class CarPickerDialog(QDialog):
    """Lista pesquisável com preview e specs do carro selecionado."""

    def __init__(self, car_ids, parent=None, current: str | None = None):
        super().__init__(parent)
        self._cars = sorted(dict.fromkeys(str(car) for car in car_ids), key=str.lower)
        ac = acm.detect_ac()
        self._cars_root = ac.ac_root / "content/cars" if ac else None
        self._meta: dict[str, dict] = {}
        self.setWindowTitle(i18n.tr("Escolher carro"))
        self.resize(860, 470)
        self._build()
        self._populate(current)

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 12)
        outer.setSpacing(12)

        body = QHBoxLayout()
        body.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText(i18n.tr("Filtrar por nome ou ID…"))
        self.search.textChanged.connect(self._filter)
        left.addWidget(self.search)

        self.list = QListWidget()
        self.list.setMinimumWidth(330)
        self.list.currentItemChanged.connect(self._selection_changed)
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())
        left.addWidget(self.list, 1)
        body.addLayout(left, 1)

        panel = QFrame()
        panel.setObjectName("Card")
        panel.setMinimumWidth(PREVIEW_WIDTH + 24)
        panel.setMaximumWidth(PREVIEW_WIDTH + 40)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(8)

        self.preview = QLabel(i18n.tr("Selecione um carro"))
        self.preview.setObjectName("Preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
        panel_layout.addWidget(self.preview)

        self.title = QLabel("—")
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-size:16px;font-weight:700;")
        panel_layout.addWidget(self.title)

        self.subtitle = QLabel("")
        self.subtitle.setObjectName("DropHint")
        self.subtitle.setWordWrap(True)
        panel_layout.addWidget(self.subtitle)

        self.specs = QLabel("")
        self.specs.setObjectName("DropHint")
        self.specs.setWordWrap(True)
        panel_layout.addWidget(self.specs)

        self.car_id = QLabel("")
        self.car_id.setObjectName("DropHint")
        self.car_id.setWordWrap(True)
        self.car_id.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        panel_layout.addWidget(self.car_id)
        panel_layout.addStretch(1)
        body.addWidget(panel)
        outer.addLayout(body, 1)

        buttons = QHBoxLayout()
        cancel = QPushButton(i18n.tr("Cancelar"))
        cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton(i18n.tr("Entrar"))
        self.btn_ok.setObjectName("Primary")
        self.btn_ok.setEnabled(False)
        self.btn_ok.clicked.connect(self.accept)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.btn_ok)
        outer.addLayout(buttons)

    def _metadata(self, car: str) -> dict:
        if car in self._meta:
            return self._meta[car]
        if self._cars_root is not None:
            meta = acm.car_metadata(self._cars_root / car)
        else:
            meta = {
                "id": car, "name": car, "brand": "", "class": "",
                "year": "", "author": "", "specs": {},
            }
        self._meta[car] = meta
        return meta

    def _populate(self, current: str | None):
        self.list.blockSignals(True)
        self.list.clear()
        selected_row = 0
        ordered = sorted(
            self._cars,
            key=lambda car: (self._metadata(car)["name"].lower(), car.lower()),
        )
        for row, car in enumerate(ordered):
            item = QListWidgetItem(self._metadata(car)["name"])
            item.setData(Qt.ItemDataRole.UserRole, car)
            item.setToolTip(car)
            self.list.addItem(item)
            if current and car.lower() == current.lower():
                selected_row = row
        self.list.blockSignals(False)
        if self._cars:
            self.list.setCurrentRow(selected_row)
        self._filter(self.search.text())
        self._selection_changed()

    def _filter(self, text: str):
        needle = text.strip().lower()
        first_visible = None
        for row in range(self.list.count()):
            item = self.list.item(row)
            car = str(item.data(Qt.ItemDataRole.UserRole) or "")
            name = self._metadata(car)["name"]
            hidden = bool(needle) and needle not in name.lower() and needle not in car.lower()
            item.setHidden(hidden)
            if not hidden and first_visible is None:
                first_visible = item
        current = self.list.currentItem()
        if current is None or current.isHidden():
            self.list.setCurrentItem(first_visible)

    def _selection_changed(self, current=None, _previous=None):
        item = current if current is not None else self.list.currentItem()
        if item is None:
            self.title.setText("—")
            self.subtitle.setText("")
            self.specs.setText("")
            self.car_id.setText("")
            self.preview.clear()
            self.preview.setText(i18n.tr("Selecione um carro"))
            self.btn_ok.setEnabled(False)
            return
        car = str(item.data(Qt.ItemDataRole.UserRole) or "")
        meta = self._metadata(car)
        self.title.setText(meta["name"])
        subtitle = " · ".join(
            value for value in (meta.get("brand"), meta.get("class"), meta.get("year")) if value
        )
        self.subtitle.setText(subtitle)
        specs = meta.get("specs") or {}
        spec_parts = [
            str(specs.get(key)) for key in ("bhp", "weight", "topspeed", "pwratio")
            if specs.get(key)
        ]
        self.specs.setText(" · ".join(spec_parts))
        self.car_id.setText(i18n.tr("ID: {car}", car=car))

        preview_path = None
        if self._cars_root is not None:
            preview_path = acm.car_preview_path(self._cars_root / car)
        pixmap = preview_pixmap(preview_path, PREVIEW_WIDTH, PREVIEW_HEIGHT)
        if pixmap is not None and not pixmap.isNull():
            self.preview.setPixmap(pixmap)
            self.preview.setText("")
        else:
            self.preview.clear()
            self.preview.setText(i18n.tr("Sem preview"))
        self.btn_ok.setEnabled(True)

    def selected_car(self) -> str | None:
        item = self.list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else None


def pick_car(parent, car_ids, current: str | None = None) -> str | None:
    dialog = CarPickerDialog(car_ids, parent, current)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.selected_car()
    return None
