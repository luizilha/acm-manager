"""Diálogo de conteúdo faltante e catálogo de pistas."""

from __future__ import annotations

import html

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTextBrowser, QVBoxLayout,
)

import acm
from gui import i18n


class MissingModsDialog(QDialog):
    """Mostra pista/carros faltando e permite baixar/instalar do catálogo."""

    def __init__(self, host, server: dict, status: dict, parent=None):
        super().__init__(parent)
        self.host = host
        self.server = server
        self.status = status
        self._catalog: list[dict] | None = None
        self._nohesi_index: list[dict] = []
        self._nohesi_missing: list[dict] = []
        self._nohesi_position: dict[str, int] = {}
        self._server_links: list[dict] = []
        self.matches: list[dict] = []
        self.setWindowTitle(i18n.tr("Buscar mods faltando"))
        self.resize(760, 560)
        self._build()

    def _build(self):
        server = self.server
        status = self.status
        self._load_nohesi()
        self._load_server_links()
        parts = [f"<h3>{html.escape(server['name'])}</h3>"]
        base = status.get("track_base") or ""
        layout = status.get("track_layout") or ""
        if status["missing_track"]:
            if base:
                label = f"<code>{html.escape(base)}</code>"
                if layout:
                    label += f" / layout <code>{html.escape(layout)}</code>"
                title = i18n.tr("Layout faltando") if layout else i18n.tr("Pista faltando")
                query = base + (f" {layout.replace('_', ' ')}" if layout else "")
            else:
                label = html.escape(server["track_short"])
                title = i18n.tr("Pista faltando")
                query = server["track_short"]
            parts.append(
                f"<p><b>{title}:</b> "
                f"<a href='{html.escape(acm.mod_search_url('track', query))}'>{label}</a></p>"
            )

        if status["missing_track"]:
            entries = self._load_catalog()
            if entries:
                self.matches = acm.catalog_lookup(
                    str(server.get("track") or ""), base, layout, entries=entries
                )
                if self.matches:
                    parts.append("<p><b>" + i18n.tr("Catálogo de pistas (Breathe):") + "</b></p><ul>")
                    for index, entry in enumerate(self.matches):
                        parts.append(self._catalog_line(index, entry))
                    parts.append("</ul>")
                else:
                    parts.append(
                        i18n.tr("<p style='color:#98a0ad'>Não encontrei essa pista no catálogo.</p>")
                    )
            else:
                parts.append(i18n.tr("<p style='color:#98a0ad'>Catálogo não disponível agora.</p>"))

        if not status["csp_ok"]:
            parts.append(
                i18n.tr("<p><b>CSP:</b> precisa build {required}; instalado {installed}.</p>", required=status["required_csp"], installed=status["csp_build"] or i18n.tr("nenhum"))
            )
        if status["missing_cars"]:
            parts.append(
                i18n.tr("<p style='color:#98a0ad'>Só contam carros cujo ID de pasta em <code>content/cars</code> é exatamente o ID pedido pelo servidor. Variantes com outro prefixo ou sufixo (ex.: <code>_sprint</code>) continuam aparecendo como faltando.</p>")
            )
            if self._nohesi_missing:
                parts.append(
                    i18n.tr("<p style='color:#98a0ad'>Carros No Hesi instalam direto do CDN ao clicar; use o botão abaixo para instalar todos.</p>")
                )
            parts.append(i18n.tr("<p><b>Carros faltando ({n}):</b></p><ul>", n=len(status["missing_cars"])))
            for car in status["missing_cars"][:40]:
                position = self._nohesi_position.get(car.lower())
                if position is not None:
                    item = self._nohesi_missing[position]
                    parts.append(
                        f"<li><a href='acm-car:{position}'>{html.escape(car)}</a>"
                        f" <span style='color:#98a0ad'>({acm.human(item['size'])})</span></li>"
                    )
                else:
                    url = acm.mod_search_url("car", car)
                    parts.append(f"<li><a href='{html.escape(url)}'>{html.escape(car)}</a></li>")
            parts.append("</ul>")
        if not (status["missing_track"] or status["missing_cars"] or not status["csp_ok"]):
            parts.append(i18n.tr("<p>Você tem todo o conteúdo necessário para este servidor.</p>"))
        parts.append(i18n.tr("<p><b>Onde baixar (indicado pelo servidor):</b></p>"))
        if self._server_links:
            parts.append("<ul>")
            for index, link in enumerate(self._server_links):
                auto, host = acm.catalog_url_support(link["url"])
                label = html.escape(link["label"])
                if auto:
                    parts.append(
                        f"<li><a href='acm-link:{index}'>{label}</a> — "
                        + i18n.tr("baixar e instalar")
                        + f" <span style='color:#98a0ad'>({html.escape(host)})</span></li>"
                    )
                else:
                    parts.append(
                        f"<li><a href='{html.escape(link['url'])}'>{label}</a>"
                        f" <span style='color:#98a0ad'>({html.escape(host)})</span></li>"
                    )
            parts.append("</ul>")
        else:
            parts.append(i18n.tr("<p style='color:#98a0ad'>O servidor não informou links de download.</p>"))
        parts.append(
            f"<p><a href='{html.escape(acm.server_mod_search_url(server))}'>"
            + i18n.tr("Buscar o servidor no Google")
            + "</a></p>"
        )
        parts.append(
            "<p style='color:#98a0ad'>"
            + i18n.tr("Links de Google Drive, MediaFire e arquivos diretos são baixados e instalados ao clicar. Sharemods (Cloudflare), Mega, Patreon, RaceDepartment/Overtake (login) e Ko-fi abrem no navegador para você baixar manualmente. O catálogo cobre pistas; carros No Hesi vêm do CDN e os demais usam o Google.")
            + "</p><p style='color:#6f7683'>"
            + i18n.tr("Fonte do catálogo:")
            + f" <a href='{html.escape(acm.CATALOG_PAGE)}'>AC Tracks Listing by Breathe</a>.</p>"
        )

        layout = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.setHtml("".join(parts))
        self.browser.anchorClicked.connect(self._anchor_clicked)
        layout.addWidget(self.browser)
        buttons = QHBoxLayout()
        refresh = QPushButton(i18n.tr("Atualizar catálogo"))
        refresh.clicked.connect(self._refresh_catalog)
        close = QPushButton(i18n.tr("Fechar"))
        close.clicked.connect(self.accept)
        buttons.addWidget(refresh)
        buttons.addStretch(1)
        if self._nohesi_missing:
            total = sum(int(item.get("size") or 0) for item in self._nohesi_missing)
            self.btn_nohesi_all = QPushButton(i18n.tr(
                "Instalar todos os No Hesi ({n} · {size})",
                n=len(self._nohesi_missing), size=acm.human(total),
            ))
            self.btn_nohesi_all.setObjectName("Primary")
            self.btn_nohesi_all.clicked.connect(self._install_all_nohesi)
            buttons.addWidget(self.btn_nohesi_all)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    @staticmethod
    def _catalog_line(index: int, entry: dict) -> str:
        name = html.escape(entry.get("name") or entry.get("folder") or "?")
        folder = html.escape(entry.get("folder") or "")
        author = html.escape(entry.get("author") or "")
        version = html.escape(entry.get("version") or "")
        meta = []
        if folder:
            meta.append(f"<code>{folder}</code>")
        if author:
            meta.append(author)
        if version:
            meta.append(version)
        line = f"<li><b>{name}</b>"
        if meta:
            line += " — " + " · ".join(meta)
        link = str(entry.get("link") or "")
        if link:
            auto, host = acm.catalog_url_support(link)
            if auto:
                line += (
                    f" — <a href='acm-install:{index}'>" + i18n.tr("Baixar e instalar") + "</a>"
                    f" <span style='color:#98a0ad'>({html.escape(i18n.tr(host))})</span>"
                )
            else:
                line += (
                    f" — <a href='{html.escape(link)}'>" + i18n.tr("Abrir link") + "</a>"
                    f" <span style='color:#ffd479'>({html.escape(i18n.tr(host))})</span>"
                )
        elif entry.get("author_link"):
            line += (
                f" — <a href='{html.escape(str(entry['author_link']))}'>" + i18n.tr("site/loja do autor") + "</a>"
                + " <span style='color:#98a0ad'>(" + i18n.tr("sem link direto do mod") + ")</span>"
            )
        else:
            line += " — <span style='color:#98a0ad'>" + i18n.tr("sem link de download") + "</span>"
        return line + "</li>"

    def _load_catalog(self) -> list[dict]:
        if self._catalog is not None:
            return self._catalog
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._catalog = acm.fetch_track_catalog()
        except Exception as e:
            self._catalog = []
            self.host.append_log(f"[!] Catálogo indisponível: {e}")
        finally:
            QApplication.restoreOverrideCursor()
        return self._catalog

    def _refresh_catalog(self):
        self._catalog = None
        self.accept()
        QTimer.singleShot(0, self._reopen)

    def _reopen(self):
        MissingModsDialog(self.host, self.server, self.status, self.parent()).exec()

    def _anchor_clicked(self, url: QUrl):
        if url.scheme() == "acm-install":
            raw = url.path().lstrip("/") or url.host()
            try:
                entry = self.matches[int(raw)]
            except (ValueError, IndexError):
                return
            self.accept()
            self._install_catalog_entry(entry)
            return
        if url.scheme() == "acm-car":
            raw = url.path().lstrip("/") or url.host()
            try:
                item = self._nohesi_missing[int(raw)]
            except (ValueError, IndexError):
                return
            self._install_nohesi_item(item)
            return
        if url.scheme() == "acm-link":
            raw = url.path().lstrip("/") or url.host()
            try:
                link = self._server_links[int(raw)]
            except (ValueError, IndexError):
                return
            self._install_server_link(link)
            return
        QDesktopServices.openUrl(url)

    def _install_catalog_entry(self, entry: dict):
        ac = acm.detect_ac()
        if not ac:
            QMessageBox.warning(self, i18n.tr("Catálogo"), i18n.tr("AC não encontrado."))
            return
        name = entry.get("name") or entry.get("folder") or "mod"
        link = str(entry.get("link") or "")
        auto, host = acm.catalog_url_support(link)
        if not auto:
            QMessageBox.information(
                self, i18n.tr("Catálogo"),
                i18n.tr("Esse link precisa de navegador/login:\n\n{host}\n{link}", host=host, link=link),
            )
            QDesktopServices.openUrl(QUrl(link))
            return
        answer = QMessageBox.question(
            self, i18n.tr("Baixar e instalar"),
            i18n.tr("Baixar e instalar automaticamente?\n\n{name}\nPasta: {folder}\nFonte: {host}\n\nO arquivo será baixado e instalado em {root}.", name=name, folder=entry.get("folder"), host=host, root=ac.ac_root),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        def do_install() -> int:
            archive = acm.download_catalog_entry(entry)
            return acm.install_archive(archive, ac.ac_root, source=link, assume_yes=True)

        self.host.mark_installed_stale()
        self.host.run_task(i18n.tr("Baixar e instalar do catálogo"), do_install)

    def _load_server_links(self):
        details = self.server.get("_details")
        if details is None:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                details = acm.fetch_server_details(self.server, timeout=4)
            except Exception as e:
                details = None
                self.host.append_log(f"[!] Detalhes do servidor indisponíveis: {e}")
            finally:
                QApplication.restoreOverrideCursor()
            if details is not None:
                self.server["_details"] = details
        self._server_links = acm.server_download_links(self.server, details)

    def _install_server_link(self, link: dict):
        auto, host = acm.catalog_url_support(link["url"])
        if not auto:
            QDesktopServices.openUrl(QUrl(link["url"]))
            return
        answer = QMessageBox.question(
            self, i18n.tr("Baixar e instalar"),
            i18n.tr(
                "Baixar e instalar este link indicado pelo servidor?\n\n{label}\n{url}\n\nFonte: {host}",
                label=link["label"], url=link["url"], host=host,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        url = link["url"]
        self.accept()
        self.host.mark_installed_stale()
        self.host.append_log(i18n.tr("Baixando do link do servidor: {url}", url=url))
        self.host.run_task(
            i18n.tr("Baixar e instalar do servidor"),
            lambda: acm.install_mod(url, False, False, False, False, True),
        )

    def _load_nohesi(self):
        if not self.status.get("missing_cars"):
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._nohesi_index = acm.fetch_nohesi_car_index()
        except Exception as e:
            self._nohesi_index = []
            self.host.append_log(f"[!] CDN No Hesi indisponível: {e}")
        finally:
            QApplication.restoreOverrideCursor()
        by_model = {item["model"].lower(): item for item in self._nohesi_index}
        for car in self.status["missing_cars"]:
            item = by_model.get(str(car).lower())
            if item is not None:
                self._nohesi_position[str(car).lower()] = len(self._nohesi_missing)
                self._nohesi_missing.append(item)

    def _install_nohesi_item(self, item: dict):
        name = item["model"]
        self.accept()
        self.host.mark_installed_stale()
        self.host.append_log(i18n.tr("Instalando {car} do CDN No Hesi…", car=name))
        self.host.run_task(
            i18n.tr("Instalar {car}", car=name),
            lambda: acm.install_nohesi_cars([name], True, self._nohesi_index),
        )

    def _install_all_nohesi(self):
        items = list(self._nohesi_missing)
        if not items:
            return
        total = sum(int(item.get("size") or 0) for item in items)
        answer = QMessageBox.question(
            self, i18n.tr("Instalar carros No Hesi"),
            i18n.tr(
                "Baixar e instalar {n} carro(s) No Hesi deste servidor?\n\nTotal: {size}.",
                n=len(items), size=acm.human(total),
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        models = [item["model"] for item in items]
        index = self._nohesi_index
        self.accept()
        self.host.mark_installed_stale()
        self.host.append_log(i18n.tr("Instalando {n} carro(s) do CDN No Hesi…", n=len(models)))
        self.host.run_task(
            i18n.tr("Instalar carros No Hesi"),
            lambda: acm.install_nohesi_cars(models, True, index),
        )
