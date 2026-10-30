"""Aba Linux Status: detecção do ambiente e manutenção do runtime."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

import acm
from gui import i18n
from gui.common import card


class LinuxStatusTab(QWidget):
    """Status de Steam, AC, Proton, CSP, fontes, dwrite e protontricks."""

    def __init__(self, host):
        super().__init__()
        self.host = host
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel(i18n.tr("Ambiente Linux"))
        title.setObjectName("Section")
        head.addWidget(title)
        head.addStretch(1)
        self.badge = QLabel(i18n.tr("verificando…"))
        self.badge.setStyleSheet(
            "background:#1c2029;border:1px solid #2c3240;border-radius:14px;"
            "padding:6px 12px;color:#98a0ad;font-weight:600;"
        )
        head.addWidget(self.badge)
        layout.addLayout(head)

        self.banner = QFrame()
        self.banner.setObjectName("Banner")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(14, 10, 14, 10)
        banner_layout.setSpacing(12)
        self.banner_label = QLabel(i18n.tr(
            "Configuração pendente. O assistente instala Proton-GE 9-20, CSP, fontes e protontricks."
        ))
        self.banner_label.setWordWrap(True)
        self.banner_btn = QPushButton(i18n.tr("Configurar tudo"))
        self.banner_btn.setObjectName("Primary")
        self.banner_btn.clicked.connect(self.configure_all)
        banner_layout.addWidget(self.banner_label, 1)
        banner_layout.addWidget(self.banner_btn)
        layout.addWidget(self.banner)
        self.banner.setVisible(False)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self.c_steam = card(i18n.tr("Steam"))
        self.c_ac = card(i18n.tr("Assetto Corsa"))
        self.c_distro = card(i18n.tr("Distro"))
        self.c_proton = card(i18n.tr("Proton"))
        self.c_csp = card(i18n.tr("CSP"))
        self.c_fonts = card(i18n.tr("Fontes"))
        self.c_dwrite = card(i18n.tr("dwrite"))
        self.c_tricks = card(i18n.tr("protontricks"))
        self.c_cache = card(i18n.tr("Cache CSP"))
        cards = [
            self.c_steam, self.c_ac, self.c_distro, self.c_proton,
            self.c_csp, self.c_fonts, self.c_dwrite, self.c_tricks,
            self.c_cache,
        ]
        for i, (frame, _) in enumerate(cards):
            grid.addWidget(frame, i // 4, i % 4)
        layout.addLayout(grid)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_setup = QPushButton(i18n.tr("Configurar tudo"))
        self.btn_setup.setObjectName("Primary")
        self.btn_setup.clicked.connect(self.configure_all)
        self.btn_csp = QPushButton(i18n.tr("Instalar/atualizar CSP"))
        self.btn_csp.clicked.connect(self.install_csp)
        self.btn_proton = QPushButton(i18n.tr("Instalar Proton-GE 9-20"))
        self.btn_proton.clicked.connect(self.install_proton)
        self.btn_fonts = QPushButton(i18n.tr("Instalar fontes"))
        self.btn_fonts.clicked.connect(self.install_fonts)
        self.btn_deps = QPushButton(i18n.tr("Instalar dependências"))
        self.btn_deps.clicked.connect(self.install_deps)
        self.btn_refresh = QPushButton(i18n.tr("Atualizar status"))
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_open = QPushButton(i18n.tr("Abrir pasta do AC"))
        self.btn_open.clicked.connect(self.open_ac_folder)
        for button in (
            self.btn_setup, self.btn_csp, self.btn_proton,
            self.btn_fonts, self.btn_deps, self.btn_refresh, self.btn_open,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

        play = QHBoxLayout()
        play.setSpacing(8)
        self.btn_play = QPushButton(i18n.tr("Abrir no modo padrão"))
        self.btn_play.setObjectName("Primary")
        self.btn_play.setToolTip(i18n.tr(
            "Restaura o launcher original e abre o AC pelo Steam para configurar o controle"
        ))
        self.btn_play.clicked.connect(self.open_default_mode)
        play.addWidget(self.btn_play)
        play.addStretch(1)
        layout.addLayout(play)
        layout.addStretch(1)

    def set_busy(self, on: bool):
        for button in (
            self.btn_setup, self.btn_csp, self.btn_proton,
            self.btn_fonts, self.btn_deps, self.btn_refresh, self.btn_play,
            self.banner_btn,
        ):
            button.setEnabled(not on)

    @staticmethod
    def _set(card_tuple, value: str, ok: bool | None):
        _, label = card_tuple
        label.setText(value)
        if ok is True:
            label.setStyleSheet("color:#7ee2a8;")
        elif ok is False:
            label.setStyleSheet("color:#ff9aa2;")
        else:
            label.setStyleSheet("color:#f3f5f8;")

    def refresh(self):
        try:
            steam = acm.detect_steam()
            ac = acm.detect_ac()
        except Exception as e:
            self.host.append_log(f"[x] {e}")
            return

        self._set(self.c_ac, "—", None)
        self._set(self.c_proton, "—", None)
        self._set(self.c_csp, "—", None)
        self._set(self.c_fonts, "—", None)
        self._set(self.c_dwrite, "—", None)
        self._set(self.c_tricks, "—", None)
        self._set(self.c_cache, "—", None)
        try:
            distro = acm.detect_distro()
            self._set(self.c_distro, distro.label(), distro.family != "unknown")
        except Exception as e:
            self._set(self.c_distro, "—", None)
            self.host.append_log(f"[x] {e}")

        if not steam:
            self._set(self.c_steam, i18n.tr("não encontrada"), False)
            self.badge.setText(i18n.tr("Steam não encontrada"))
            self.badge.setStyleSheet(
                "background:#2a1518;border:1px solid #5a1f27;border-radius:14px;"
                "padding:6px 12px;color:#ff8b94;font-weight:600;"
            )
            self.banner.setVisible(False)
            return

        self._set(self.c_steam, f"{i18n.tr(steam.label())}\n{steam.root}", True)
        if not ac:
            self._set(self.c_ac, i18n.tr("não encontrado"), False)
            self.badge.setText(i18n.tr("AC não encontrado"))
            self.badge.setStyleSheet(
                "background:#2a1518;border:1px solid #5a1f27;border-radius:14px;"
                "padding:6px 12px;color:#ff8b94;font-weight:600;"
            )
            self.banner.setVisible(False)
            return

        try:
            cars = sum(1 for p in (ac.ac_root / "content/cars").iterdir() if p.is_dir())
            tracks = sum(1 for p in (ac.ac_root / "content/tracks").iterdir() if p.is_dir())
            content = i18n.tr("{cars} carros · {tracks} pistas", cars=cars, tracks=tracks)
        except Exception:
            content = ""
        self._set(self.c_ac, f"{ac.ac_root}\n{content}".strip(), True)
        self._set(
            self.c_proton, ac.proton_name or i18n.tr("não definido"),
            bool(ac.proton_name and ac.proton_name.startswith("GE-Proton9")),
        )
        self._set(self.c_csp, ac.csp_version or i18n.tr("não instalado"), bool(ac.csp_version))
        segoe_content = (ac.ac_root / "content/fonts/system/segoeui.ttf").exists()
        segoe_prefix = (ac.prefix / "drive_c/windows/Fonts/segoeui.ttf").exists()
        self._set(
            self.c_fonts,
            i18n.tr("Segoe UI OK") if (segoe_content and segoe_prefix)
            else i18n.tr("content={content}, prefixo={prefix}", content=segoe_content, prefix=segoe_prefix),
            segoe_content and segoe_prefix,
        )
        self._set(self.c_dwrite, i18n.tr("ativo") if ac.dwrite_override else i18n.tr("faltando"),
                  bool(ac.dwrite_override))
        self._set(self.c_tricks, ac.protontricks_kind or i18n.tr("não instalado"),
                  bool(ac.protontricks_kind))

        cache_off = False
        ini = ac.ac_root / "extension/config/general.ini"
        if ini.exists():
            text = ini.read_text(encoding="utf-8", errors="replace")
            cache_off = "CACHE_ACS=0" in text and "CACHING_LOADING2=0" in text
        self._set(self.c_cache, i18n.tr("desativado") if cache_off else i18n.tr("ativo/padrão"), cache_off)

        ready = bool(
            ac.csp_version and ac.dwrite_override and segoe_content and segoe_prefix
            and ac.proton_name and ac.proton_name.startswith("GE-Proton9") and cache_off
        )
        self.banner.setVisible(not ready)
        if ready:
            self.badge.setText(i18n.tr("Tudo pronto"))
            self.badge.setStyleSheet(
                "background:#10251a;border:1px solid #1f5a3a;border-radius:14px;"
                "padding:6px 12px;color:#7ee2a8;font-weight:600;"
            )
        else:
            self.badge.setText(i18n.tr("Configuração pendente"))
            self.badge.setStyleSheet(
                "background:#2a2212;border:1px solid #5a481f;border-radius:14px;"
                "padding:6px 12px;color:#ffd479;font-weight:600;"
            )

    def configure_all(self):
        note = i18n.tr(
            "Vou instalar/verificar Proton-GE 9-20, CSP, fontes e protontricks.\n\n"
            "Feche o Steam para que o Proton do AC possa ser alterado automaticamente.\n"
            "Continuar?"
        )
        self.host.run_task(
            i18n.tr("Configurar tudo"),
            lambda: acm.setup_all(acm.GE_PROTON_DEFAULT, True, False, False),
            note,
        )

    def install_csp(self):
        self.host.run_task(
            i18n.tr("Instalar/atualizar CSP"),
            lambda: acm.install_csp_version(None, False, True, False),
            i18n.tr("Baixar e instalar/atualizar o CSP? O jogo deve estar fechado."),
        )

    def install_proton(self):
        self.host.run_task(
            i18n.tr("Instalar Proton-GE"),
            lambda: acm.install_proton_ge(acm.GE_PROTON_DEFAULT, True),
            i18n.tr("Baixar e instalar {version}? (~1,3 GB)", version=acm.GE_PROTON_DEFAULT),
        )

    def install_fonts(self):
        self.host.run_task(
            i18n.tr("Instalar fontes"),
            lambda: acm.install_fonts(True),
            i18n.tr("Instalar Segoe UI/Verdana e corefonts no prefixo?"),
        )

    def install_deps(self):
        self.host.run_task(
            i18n.tr("Instalar dependências"),
            lambda: acm.install_system_deps(True),
            i18n.tr(
                "Instalar unrar, 7z, bsdtar e cabextract usando o gerenciador da sua distro?"
            ),
        )

    def open_ac_folder(self):
        ac = acm.detect_ac()
        if ac:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(ac.ac_root)))

    def open_default_mode(self):
        note = i18n.tr(
            "Isso restaura o launcher original do AC e abre o jogo pelo Steam em modo padrão.\n\n"
            "Use Options → Controls no launcher para associar os controles.\n\n"
            "O Assetto Corsa precisa estar fechado. Continuar?"
        )
        self.host.run_task(
            i18n.tr("Abrir no modo padrão"),
            acm.launch_default_mode,
            note,
        )
