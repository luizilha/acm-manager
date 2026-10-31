"""Aba Servidores: lobby, filtros, ping, catálogo de pistas e entrada."""

from __future__ import annotations

import html
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

import acm
from gui import i18n
from gui.tabs.car_picker import pick_car
from gui.tabs.catalog_dialog import MissingModsDialog

SERVER_DISPLAY_LIMIT = 500


class ServerWorker(QThread):
    data = Signal(object, float, bool)
    failed = Signal(str)

    def __init__(self, force: bool = False):
        super().__init__()
        self.force = force

    def run(self):
        try:
            servers, fetched, cached = acm.fetch_server_list(force=self.force)
            self.data.emit(servers, fetched, cached)
        except Exception as e:
            self.failed.emit(str(e))


class PingWorker(QThread):
    row = Signal(int, str)
    done = Signal()

    def __init__(self, rows):
        super().__init__()
        self.rows = rows

    def run(self):
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = {
                pool.submit(acm.ping_server, s["ip"], s["port"]): (r, s)
                for r, s in self.rows
            }
            for future in as_completed(futures):
                r, _ = futures[future]
                try:
                    result = future.result()
                except Exception:
                    result = None
                self.row.emit(r, f"{result[1]}ms" if result else "—")
        self.done.emit()


class ServersTab(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self._servers: list[dict] = []
        self._servers_fetched: float = 0.0
        self._servers_cached: bool = True
        self._server_worker: ServerWorker | None = None
        self._ping_worker: PingWorker | None = None
        self._local_content: dict | None = None
        self._official: dict | None = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self.server_filter = QLineEdit()
        self.server_filter.setPlaceholderText(i18n.tr("Filtrar por nome, pista ou país…"))
        self.server_filter.textChanged.connect(self.apply_server_filter)
        self.server_only_ok = QCheckBox(i18n.tr("Só mods OK"))
        self.server_only_ok.stateChanged.connect(lambda _: self.apply_server_filter())
        self.server_no_mods = QCheckBox(i18n.tr("Só sem mods"))
        self.server_no_mods.setToolTip(i18n.tr(
            "Mostra somente servidores cuja pista e carros são oficiais (base/DLC). "
            "Não considera CSP como mod de conteúdo. Não garante acesso livre "
            "(licença/password)."
        ))
        self.server_no_mods.stateChanged.connect(lambda _: self.apply_server_filter())
        self.server_refresh = QPushButton(i18n.tr("Atualizar lista"))
        self.server_refresh.clicked.connect(lambda: self.refresh_servers(True))
        self.server_join = QPushButton(i18n.tr("Entrar"))
        self.server_join.setObjectName("Primary")
        self.server_join.setEnabled(False)
        self.server_join.clicked.connect(self.join_selected)
        self.server_search = QPushButton(i18n.tr("Buscar mods"))
        self.server_search.setEnabled(False)
        self.server_search.clicked.connect(self.search_missing_mods)
        self.server_ping = QPushButton(i18n.tr("Pingar top 50"))
        self.server_ping.setEnabled(False)
        self.server_ping.clicked.connect(self.ping_servers)
        top.addWidget(self.server_filter, 1)
        top.addWidget(self.server_no_mods)
        top.addWidget(self.server_only_ok)
        top.addWidget(self.server_refresh)
        top.addWidget(self.server_join)
        top.addWidget(self.server_search)
        top.addWidget(self.server_ping)
        layout.addLayout(top)

        self.server_status = QLabel(i18n.tr("Clique em Atualizar lista para carregar o lobby."))
        self.server_status.setObjectName("DropHint")
        self.server_status.setWordWrap(True)
        layout.addWidget(self.server_status)

        self.server_table = QTableWidget(0, 6)
        self.server_table.setHorizontalHeaderLabels(
            [i18n.tr("Nome"), i18n.tr("Players"), i18n.tr("Pista"), i18n.tr("Mods"), i18n.tr("Ping"), i18n.tr("Senha")]
        )
        self.server_table.verticalHeader().setVisible(False)
        self.server_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.server_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.server_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.server_table.setAlternatingRowColors(True)
        self.server_table.setCornerButtonEnabled(False)
        header = self.server_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.server_table.cellDoubleClicked.connect(self.show_server_details)
        self.server_table.itemSelectionChanged.connect(self._server_selection_changed)
        layout.addWidget(self.server_table, 1)

    def on_activated(self):
        self._reload_local_content()
        if not self._servers and not (
            self._server_worker and self._server_worker.isRunning()
        ):
            self.refresh_servers(False)
        else:
            self.apply_server_filter()

    def set_busy(self, on: bool):
        self.server_refresh.setEnabled(not on)
        self.server_join.setEnabled(not on and self.server_table.currentRow() >= 0)
        self.server_search.setEnabled(not on and self.server_table.currentRow() >= 0)
        self.server_ping.setEnabled(not on and self.server_table.rowCount() > 0)

    def shutdown(self):
        for worker in (self._server_worker, self._ping_worker):
            if worker and worker.isRunning():
                worker.requestInterruption()
                if not worker.wait(2500):
                    worker.terminate()
                    worker.wait(500)

    def refresh_servers(self, force: bool = True):
        if self._server_worker and self._server_worker.isRunning():
            return
        self.server_refresh.setEnabled(False)
        self.server_ping.setEnabled(False)
        self.server_status.setText(i18n.tr("Carregando lista do lobby do Assetto Corsa…"))
        self._server_worker = ServerWorker(force=force)
        self._server_worker.data.connect(self._servers_loaded)
        self._server_worker.failed.connect(self._servers_failed)
        self._server_worker.start()

    def _servers_loaded(self, servers, fetched, cached):
        self._servers = servers
        self._servers_fetched = fetched
        self._servers_cached = cached
        self.server_refresh.setEnabled(True)
        self.server_ping.setEnabled(bool(servers))
        self.apply_server_filter()

    def _servers_failed(self, msg: str):
        self.server_refresh.setEnabled(True)
        self.server_status.setText(i18n.tr("Falha ao carregar servidores: {msg}", msg=msg))
        self.host.append_log(f"[x] Servidores: {msg}")

    def apply_server_filter(self):
        text = self.server_filter.text().lower().strip()
        only_ok = self.server_only_ok.isChecked()
        only_official = self.server_no_mods.isChecked()
        official = self._official
        if official is None:
            official = acm.official_content()
            self._official = official
        matched: list[tuple[dict, dict | None]] = []
        for server in self._servers:
            if text and not (
                text in server["name"].lower()
                or text in server["track"].lower()
                or text in server["country_name"].lower()
            ):
                continue
            if only_official and acm.server_requires_mods(server, official):
                continue
            status = acm.check_server_mods(server, self._local_content) if self._local_content else None
            if only_ok and not (status and status["ok"]):
                continue
            matched.append((server, status))
        matched.sort(key=lambda pair: (-pair[0]["clients"], pair[0]["name"].lower()))
        rows = matched[:SERVER_DISPLAY_LIMIT]
        self.server_table.setRowCount(0)
        self.server_table.setRowCount(len(rows))
        for row, (server, status) in enumerate(rows):
            name = QTableWidgetItem(server["name"])
            name.setData(Qt.ItemDataRole.UserRole, server)
            players = QTableWidgetItem(f'{server["clients"]}/{server["maxclients"]}')
            players.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            track = QTableWidgetItem(server["track_short"])

            if status is None:
                mods_text, mods_color = "?", "#98a0ad"
            elif status["missing_track"]:
                mods_text = i18n.tr("layout") if status.get("track_base") else i18n.tr("pista")
                mods_color = "#ff9aa2"
            elif not status["csp_ok"]:
                mods_text, mods_color = f"CSP {status['required_csp']}", "#ff9aa2"
            elif status["missing_cars"] and not status["installed_cars"]:
                mods_text, mods_color = i18n.tr("sem carro"), "#ff9aa2"
            elif status["missing_cars"]:
                mods_text, mods_color = i18n.tr("faltam {n}", n=len(status["missing_cars"])), "#ffd479"
            else:
                mods_text, mods_color = "OK", "#7ee2a8"
            mods = QTableWidgetItem(mods_text)
            mods.setForeground(QColor(mods_color))
            mods.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if status and status["missing_cars"]:
                mods.setToolTip(i18n.tr("Faltando: {items}", items=", ".join(status["missing_cars"][:30])))
            elif status and status["missing_track"]:
                base = status.get("track_base") or ""
                layout = status.get("track_layout") or ""
                if base and layout:
                    mods.setToolTip(i18n.tr("Falta o layout {layout} da pista {base}.", layout=layout, base=base))
                else:
                    mods.setToolTip(i18n.tr("Falta a pista {track}.", track=server["track"]))

            ping = QTableWidgetItem("—")
            ping.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            password = QTableWidgetItem("🔒" if server["pass"] else "")
            password.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            for column, item in enumerate([name, players, track, mods, ping, password]):
                self.server_table.setItem(row, column, item)
        self._server_selection_changed()
        when = (
            time.strftime("%H:%M:%S", time.localtime(self._servers_fetched))
            if self._servers_fetched else "—"
        )
        self.server_status.setText(i18n.tr(
            "{n} servidores · mostrando {shown} · {source} {when}",
            n=len(matched), shown=len(rows),
            source=i18n.tr("cache") if self._servers_cached else i18n.tr("atualizado"),
            when=when,
        ))
        self.server_ping.setEnabled(bool(rows))

    def ping_servers(self):
        if self._ping_worker and self._ping_worker.isRunning():
            return
        rows = []
        for row in range(min(50, self.server_table.rowCount())):
            item = self.server_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole):
                rows.append((row, item.data(Qt.ItemDataRole.UserRole)))
        if not rows:
            return
        self.server_ping.setEnabled(False)
        self.server_refresh.setEnabled(False)
        self.server_filter.setEnabled(False)
        self.server_status.setText(i18n.tr("Pingando {n} servidores…", n=len(rows)))
        self._ping_worker = PingWorker(rows)
        self._ping_worker.row.connect(self._ping_row)
        self._ping_worker.done.connect(self._ping_done)
        self._ping_worker.start()

    def _ping_row(self, row: int, text: str):
        item = self.server_table.item(row, 4)
        if item:
            item.setText(text)

    def _ping_done(self):
        self.server_ping.setEnabled(True)
        self.server_refresh.setEnabled(True)
        self.server_filter.setEnabled(True)
        self.server_status.setText(i18n.tr("Ping concluído para os servidores visíveis."))

    def _server_selection_changed(self):
        has = self.server_table.currentRow() >= 0 and bool(self._servers)
        self.server_join.setEnabled(has)
        self.server_search.setEnabled(has)

    def _reload_local_content(self):
        try:
            ac = acm.detect_ac()
            self._local_content = acm.local_content(ac) if ac else None
            self._official = None
        except Exception as e:
            self.host.append_log(f"[x] {e}")

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

    def search_missing_mods(self):
        row = self.server_table.currentRow()
        if row < 0:
            return
        item = self.server_table.item(row, 0)
        server = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not server:
            return
        self._reload_local_content()
        status = acm.check_server_mods(server, self._local_content) if self._local_content else None
        if status is None:
            QMessageBox.warning(self, i18n.tr("Buscar mods"), i18n.tr("Não consegui verificar o conteúdo instalado."))
            return
        MissingModsDialog(self.host, server, status, self).exec()

    def join_selected(self):
        row = self.server_table.currentRow()
        if row < 0:
            return
        item = self.server_table.item(row, 0)
        server = item.data(Qt.ItemDataRole.UserRole) if item else None
        if server:
            self._join_flow(server)

    def _join_flow(self, server: dict, car_hint: str | None = None, depth: int = 0):
        self._reload_local_content()
        if acm.is_process_running("acs.exe") or acm.is_process_running("AssettoCorsa.exe"):
            QMessageBox.warning(
                self, i18n.tr("Entrar no servidor"),
                i18n.tr("Feche o Assetto Corsa antes de entrar. O jogo precisa iniciar com o race.ini novo."),
            )
            return
        status = acm.check_server_mods(server, self._local_content) if self._local_content else None
        if status is None:
            QMessageBox.warning(self, i18n.tr("Entrar no servidor"), i18n.tr("Não consegui verificar o conteúdo instalado."))
            return
        if status["missing_track"]:
            base = status.get("track_base") or ""
            layout = status.get("track_layout") or ""
            if base and layout:
                detail = i18n.tr("Falta o layout {layout} da pista {base}:", layout=layout, base=base)
            else:
                detail = i18n.tr("Você não tem a pista deste servidor:")
            QMessageBox.warning(
                self, i18n.tr("Pista/layout faltando"),
                f"{detail}\n\n{html.escape(server['track'])}",
            )
            return
        if not status["csp_ok"]:
            QMessageBox.warning(
                self, i18n.tr("CSP necessário"),
                i18n.tr("Este servidor pede CSP build {required}; você tem {installed}.", required=status["required_csp"], installed=status["csp_build"] or i18n.tr("nenhum")),
            )
            return
        details = server.get("_details") if depth > 0 else None
        if not details:
            details = acm.fetch_server_details(server, timeout=5)
        if details:
            server["_details"] = details
        access_note = acm.server_access_note(details)
        if access_note:
            answer = QMessageBox.warning(
                self,
                i18n.tr("Acesso ao servidor"),
                i18n.tr(
                    "Este servidor parece exigir licença/password, entry list ou doação.\n\n{note}\n\nSe você já tem a licença, pode continuar. Caso contrário, obtenha no Discord/site do servidor.\n\nContinuar?",
                    note=access_note,
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        missing_entry = acm.missing_entry_cars(details, self._local_content)
        has_entry = bool(
            isinstance(details, dict)
            and isinstance(details.get("players"), dict)
            and details["players"].get("Cars")
        )
        if not has_entry:
            missing_entry = list(status.get("missing_cars") or [])
        if missing_entry:
            if not self._handle_missing_entry(server, missing_entry, details, status):
                return
        installed = status["installed_cars"]
        if not installed:
            QMessageBox.warning(
                self, i18n.tr("Carros faltando"),
                i18n.tr("Nenhum carro do servidor está instalado.\n\nFaltando:\n{items}", items="\n".join(status["missing_cars"][:20])),
            )
            return
        if car_hint and any(c.lower() == car_hint.lower() for c in installed):
            car = next(c for c in installed if c.lower() == car_hint.lower())
        elif len(installed) == 1:
            car = installed[0]
        else:
            car = pick_car(self, installed)
            if not car:
                return
        slot_ok, slots = acm.check_car_slot(server, car, server.get("_details"))
        if slot_ok is False:
            resolved = self._resolve_no_slot(server, car, installed, slots, depth)
            if resolved is None:
                return
            new_server, new_car = resolved
            if new_server is not server:
                return self._join_flow(new_server, new_car, depth + 1)
            car = new_car
        password = ""
        if server["pass"]:
            password, ok = QInputDialog.getText(
                self, i18n.tr("Senha do servidor"), i18n.tr("Senha")+":",
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return
        clients = slots.get("clients", server["clients"]) if slots else server["clients"]
        maxclients = slots.get("maxclients", server["maxclients"]) if slots else server["maxclients"]
        if clients >= maxclients:
            answer = QMessageBox.question(
                self, i18n.tr("Servidor cheio"),
                i18n.tr("O servidor está cheio. Tentar entrar mesmo assim?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        ac = acm.detect_ac()
        if not ac:
            QMessageBox.warning(self, i18n.tr("Entrar no servidor"), i18n.tr("AC não encontrado."))
            return
        launcher = ac.ac_root / "AssettoCorsa.exe"
        acs = ac.ac_root / "acs.exe"
        if launcher.exists() and acs.exists() and launcher.stat().st_size != acs.stat().st_size:
            answer = QMessageBox.question(
                self, i18n.tr("Lançamento direto"),
                i18n.tr("Para entrar direto no servidor, o app substitui o AssettoCorsa.exe pelo acs.exe.\n\nO launcher original é preservado como AssettoCorsa_original.exe.\n\nContinuar?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.host.append_log(i18n.tr("Entrando em {name} com {car}", name=server["name"], car=car))
        self.host.run_task(
            i18n.tr("Entrar no servidor"),
            lambda: acm.join_server(server, car, password, True, True),
        )

    def _resolve_no_slot(self, server: dict, car: str, installed: list[str],
                         slots: dict, depth: int) -> tuple[dict, str] | None:
        """Mostra as alternativas quando o carro escolhido está sem vaga."""
        free = sorted(slots.get("free", {}).items(), key=lambda item: (-item[1], item[0]))
        free_text = ", ".join(f"{model} x{count}" for model, count in free) or i18n.tr("nenhuma")
        lines = [
            i18n.tr("Não há vaga livre para {car} neste servidor.", car=car),
            i18n.tr("Jogadores: {current}/{max}", current=slots.get("clients", server["clients"]), max=slots.get("maxclients", server["maxclients"])),
            i18n.tr("Vagas livres agora: {slots}", slots=free_text),
            i18n.tr("O servidor usa entry list: cada modelo de carro tem um número fixo de vagas."),
        ]
        self.host.append_log(i18n.tr("Sem vaga para {car} em {name}", car=car, name=server["name"]))
        alt_cars = [
            c for c in installed
            if any(model.lower() == c.lower() and count > 0 for model, count in slots.get("free", {}).items())
        ]
        alt_servers: list[dict] = []
        if depth < 2:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                alt_servers = acm.find_slot_alternatives(self._servers, car, server["track"], server)
            except Exception as e:
                self.host.append_log(f"[!] {e}")
            finally:
                QApplication.restoreOverrideCursor()
        info = []
        if alt_servers:
            info.append(i18n.tr("Outras instâncias com vaga para {car}:", car=car))
            for item in alt_servers:
                s = item["server"]
                info.append(f"· {s['name']} — {s['ip']}:{s['port']} ({s['clients']}/{s['maxclients']})")
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(i18n.tr("Sem vaga"))
        box.setText("\n".join(lines))
        if info:
            box.setInformativeText("\n".join(info))
        btn_server = None
        btn_car = None
        if alt_servers:
            btn_server = box.addButton(i18n.tr("Entrar em outra instância"), QMessageBox.ButtonRole.AcceptRole)
        if alt_cars:
            btn_car = box.addButton(i18n.tr("Escolher outro carro"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is btn_server:
            labels = [
                f"{item['server']['name']} — {item['server']['ip']}:{item['server']['port']} "
                f"({item['server']['clients']}/{item['server']['maxclients']})"
                for item in alt_servers
            ]
            choice, ok = QInputDialog.getItem(
                self, i18n.tr("Outra instância"),
                i18n.tr("Escolha a instância:"),
                labels, 0, False,
            )
            if not ok or not choice:
                return None
            return alt_servers[labels.index(choice)]["server"], car
        if clicked is btn_car:
            choice = pick_car(self, alt_cars)
            if not choice:
                return None
            return server, choice
        return None

    def show_server_details(self, row: int, _column: int):
        item = self.server_table.item(row, 0)
        server = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not server:
            return
        lines = [
            f"<b>{html.escape(server['name'])}</b>",
            i18n.tr("Endereço: {address} (HTTP {http})", address=html.escape(f"{server['ip']}:{server['port']}"), http=server['cport']),
            i18n.tr("Jogadores: {current}/{max}", current=server['clients'], max=server['maxclients']),
            i18n.tr("Pista: {track}", track=html.escape(server['track_short'])),
            i18n.tr("País: {country}", country=html.escape(server['country_name'] or '—')),
            i18n.tr("Carros permitidos: {n}", n=server['car_count']),
            i18n.tr("Senha: {value}", value=i18n.tr("sim") if server['pass'] else i18n.tr("não")),
        ]
        status = acm.check_server_mods(server, self._local_content) if self._local_content else None
        if status:
            if status["ok"]:
                lines.append(i18n.tr("Mods: {value}", value="<span style='color:#7ee2a8'>OK</span>"))
            elif status["missing_track"]:
                base = status.get("track_base") or ""
                layout = status.get("track_layout") or ""
                if base and layout:
                    lines.append(i18n.tr(
                        "Mods: {value} (<code>{base}</code> / <code>{layout}</code>)",
                        value="<span style='color:#ff9aa2'>" + i18n.tr("layout faltando") + "</span>",
                        base=html.escape(base), layout=html.escape(layout),
                    ))
                else:
                    lines.append(i18n.tr("Mods: {value}", value="<span style='color:#ff9aa2'>" + i18n.tr("pista faltando") + "</span>"))
            elif not status["csp_ok"]:
                lines.append(i18n.tr(
                    "Mods: {value}",
                    value="<span style='color:#ff9aa2'>" + i18n.tr(
                        "CSP build {required} (instalado {installed})",
                        required=status['required_csp'],
                        installed=status['csp_build'] or i18n.tr("nenhum"),
                    ) + "</span>",
                ))
            else:
                lines.append(i18n.tr("Mods: {value}", value="<span style='color:#ffd479'>" + i18n.tr("faltam {n} carro(s)", n=len(status['missing_cars'])) + "</span>"))
            if status["missing_cars"]:
                lines.append(i18n.tr("Faltando: {items}", items=html.escape(", ".join(status["missing_cars"][:20]))))
            if status["installed_cars"]:
                lines.append(i18n.tr("Instalados: {items}", items=html.escape(", ".join(status["installed_cars"][:10]))))
        QMessageBox.information(self, i18n.tr("Servidor"), "<br>".join(lines))

    def _handle_missing_entry(self, server: dict, missing: list[str],
                              details: dict, status: dict) -> bool:
        """Explica o conteúdo faltante e oferece baixar do servidor.

        Retorna ``True`` para continuar o join mesmo assim (quando a entry list
        não pôde ser lida) ou ``False`` para parar.
        """
        has_entry = bool(
            isinstance(details, dict)
            and isinstance(details.get("players"), dict)
            and details["players"].get("Cars")
        )
        shown = "\n".join(f"· {model}" for model in missing[:12])
        if len(missing) > 12:
            shown += "\n" + i18n.tr("… +{n}", n=len(missing) - 12)
        if has_entry:
            text = i18n.tr(
                "O Assetto Corsa carrega todos os carros da entry list do servidor, não só o seu.\n\n"
                "Faltam {n} carro(s):\n{models}\n\n"
                "Sem eles o jogo falha com “car … is missing”.",
                n=len(missing), models=shown,
            )
        else:
            text = i18n.tr(
                "Você não tem {n} carro(s) que este servidor usa:\n{models}\n\n"
                "O AC pode exigir todos ao entrar. Se não tiver certeza, tente mesmo assim.",
                n=len(missing), models=shown,
            )
        urls = acm.server_car_downloads(details, missing)
        links = acm.server_download_links(server, details)
        auto_links = [link for link in links if acm.catalog_url_support(link["url"])[0]]
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(i18n.tr("Conteúdo do servidor incompleto"))
        box.setText(text)
        info = []
        if urls and len(urls) < len(missing):
            info.append(i18n.tr(
                "{have} de {n} têm link de download no servidor; o resto precisa ser manual.",
                have=len(urls), n=len(missing),
            ))
        if links:
            info.append(i18n.tr(
                "O servidor indica: {links}",
                links=", ".join(f"{link['label']} ({link['host']})" for link in links[:4]),
            ))
        if info:
            box.setInformativeText("\n".join(info))
        btn_install = None
        if urls:
            btn_install = box.addButton(
                i18n.tr("Baixar carros do servidor"), QMessageBox.ButtonRole.AcceptRole
            )
        btn_link = None
        if auto_links:
            btn_link = box.addButton(
                i18n.tr("Baixar do link do servidor"), QMessageBox.ButtonRole.AcceptRole
            )
        elif links:
            btn_link = box.addButton(
                i18n.tr("Abrir link do servidor"), QMessageBox.ButtonRole.ActionRole
            )
        btn_skip = None
        if not has_entry:
            btn_skip = box.addButton(
                i18n.tr("Tentar mesmo assim"), QMessageBox.ButtonRole.ActionRole
            )
        btn_search = box.addButton(i18n.tr("Buscar mods"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is btn_install:
            self.host.append_log(i18n.tr("Instalando {n} carro(s) do servidor…", n=len(urls)))
            self.host.run_task(
                i18n.tr("Instalar carros do servidor"),
                lambda: acm.install_server_cars(server, missing, True),
                i18n.tr(
                    "Baixar e instalar {n} carro(s) do próprio servidor?\n\n"
                    "Pode baixar vários GB e demorar bastante. O jogo deve estar fechado.",
                    n=len(urls),
                ),
            )
        elif clicked is btn_link:
            link = auto_links[0] if auto_links else links[0]
            auto, host = acm.catalog_url_support(link["url"])
            if not auto:
                QDesktopServices.openUrl(QUrl(link["url"]))
                return False
            answer = QMessageBox.question(
                self, i18n.tr("Baixar e instalar"),
                i18n.tr(
                    "Baixar e instalar este link indicado pelo servidor?\n\n{label}\n{url}\n\nFonte: {host}\n\nO arquivo é extraído e instalado em AC.",
                    label=link["label"], url=link["url"], host=host,
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
            url = link["url"]
            self.host.mark_installed_stale()
            self.host.append_log(i18n.tr("Baixando do link do servidor: {url}", url=url))
            self.host.run_task(
                i18n.tr("Baixar e instalar do servidor"),
                lambda: acm.install_mod(url, False, False, False, False, True),
            )
        elif clicked is btn_search:
            MissingModsDialog(self.host, server, status, self).exec()
        elif clicked is btn_skip:
            return True
        return False
