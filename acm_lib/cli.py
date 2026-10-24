"""Parser e comandos da CLI."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html as html_lib
import io
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable

from .base import *

from .downloads import *
from .catalog import *
from .content import *
from .servers import *
from .installer import *
from .setup import *


def cmd_detect(_args) -> int:
    steam = detect_steam()
    distro = detect_distro()
    print(f"Distro: {distro.label()}")
    if not steam:
        print("[x] Steam não encontrada (nem Flatpak, nem nativa).")
        return 1
    ac = detect_ac()
    print(f"Steam: {steam.label()}{' (rodando)' if steam.running else ''}")
    print(f"  root: {steam.root}")
    for lib in steam.libraries:
        print(f"  library: {lib}")
    if not ac:
        print("[x] Assetto Corsa não encontrado nas bibliotecas.")
        return 1
    print(f"\nAC: {ac.ac_root}")
    print(f"  library: {ac.library}")
    print(f"  prefixo: {ac.prefix}")
    print(f"  Proton: {ac.proton_name or 'não definido'}")
    if ac.proton_path:
        print(f"  Proton path: {ac.proton_path}")
    print(f"  CSP: {ac.csp_version or 'não instalado'}")
    print(f"  dwrite override: {ac.dwrite_override!r}")
    print(f"  protontricks: {ac.protontricks_kind or 'não instalado'}")
    print(f"  compatdata existe: {ac.prefix.exists()}")
    print(f"  Segoe UI (content): {(ac.ac_root / 'content/fonts/system/segoeui.ttf').exists()}")
    print(f"  Segoe UI (prefixo): {(ac.prefix / 'drive_c/windows/Fonts/segoeui.ttf').exists()}")
    cache_ini = ac.ac_root / "extension/config/general.ini"
    if cache_ini.exists():
        cache_text = cache_ini.read_text(encoding="utf-8", errors="replace")
        print(f"  CSP cache off: {'CACHE_ACS=0' in cache_text and 'CACHING_LOADING2=0' in cache_text}")
    return 0

def cmd_status(_args) -> int:
    return cmd_detect(_args)

def cmd_setup_deps(args) -> int:
    return install_system_deps(args.yes, args.dry_run)


def cmd_install_csp(args) -> int:
    return install_csp_version(args.version, args.dry_run, args.yes, not args.no_fonts)

def cmd_servers(args) -> int:
    servers, fetched, cached = fetch_server_list(force=args.force)
    text = (args.filter or "").lower()
    rows = [
        s for s in servers
        if not text or text in s["name"].lower() or text in s["track"].lower()
        or text in s["country_name"].lower()
    ]
    rows.sort(key=lambda s: (-s["clients"], s["name"].lower()))
    rows = rows[:args.limit]
    if args.ping:
        for s in rows:
            result = ping_server(s["ip"], s["port"])
            s["ping_ms"] = result[1] if result else None
            if result:
                s["cport"] = result[0]
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(fetched))
    print(f"{len(servers)} servidores · {'cache' if cached else 'atualizado'} em {when}")
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    print(f"{'Players':>8}  {'Ping':>6}  {'P':2}  {'Nome':42}  {'Pista':28}  Endereço")
    for s in rows:
        ping = f"{s['ping_ms']}ms" if s.get("ping_ms") is not None else "-"
        name = s["name"][:42]
        track = s["track_short"][:28]
        flag = "🔒" if s["pass"] else " "
        print(f"{s['clients']:>3}/{s['maxclients']:<4} {ping:>6}  {flag:2}  {name:42}  {track:28}  {s['ip']}:{s['port']}")
    return 0

def cmd_catalog(args) -> int:
    entries = fetch_track_catalog(force=args.refresh)
    text = (args.search or "").lower().strip()
    matches = [
        e for e in entries
        if not text
        or text in (e.get("name") or "").lower()
        or text in (e.get("folder") or "").lower()
        or text in (e.get("author") or "").lower()
    ]
    if args.link:
        matches = [e for e in matches if e.get("link")]
    if args.auto:
        matches = [e for e in matches if e.get("link") and catalog_url_support(e["link"])[0]]
    if not matches:
        print("Nenhuma pista encontrada no catálogo.")
        return 1
    matches = matches[:args.limit]
    for i, e in enumerate(matches):
        auto, host = catalog_url_support(e.get("link") or "")
        status = "AUTO " + host if auto else (host if e.get("link") else "sem link")
        if not e.get("link") and e.get("author_link"):
            status += " (loja do autor)"
        print(f"[{i}] {e.get('name')} | {e.get('folder')} | {e.get('author') or '-'} "
              f"| {e.get('version') or '-'} | {status}")
        if e.get("link"):
            print(f"    {e['link']}")
    if args.download or args.install:
        if args.index < 0 or args.index >= len(matches):
            eprint(f"[x] Índice inválido; use 0..{len(matches) - 1}.")
            return 1
        entry = matches[args.index]
        if not entry.get("link"):
            eprint("[x] Essa entrada não tem link de download.")
            return 1
        try:
            archive = download_catalog_entry(entry, Path(args.dest).expanduser())
            print(f"[✓] Baixado: {archive}")
        except UnsupportedDownload as e:
            eprint(f"[x] {e}")
            return 1
        if args.install:
            ac_root = Path(args.ac_root).expanduser() if args.ac_root else None
            if not ac_root:
                ac = detect_ac()
                if not ac:
                    eprint("[x] AC não encontrado.")
                    return 1
                ac_root = ac.ac_root
            return install_archive(archive, ac_root, source=entry.get("link", ""),
                                   assume_yes=args.yes)
    return 0

def cmd_installed(args) -> int:
    ac = detect_ac()
    if not ac:
        eprint("[x] AC não encontrado.")
        return 1
    all_items = installed_content(ac)
    items = all_items if args.official else [x for x in all_items if not x.get("official")]
    text = (args.filter or "").lower()
    if text:
        items = [x for x in items if text in x["name"].lower() or text in x["kind"]]
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=1))
        return 0
    total = sum(x["size"] for x in items)
    hidden = len(all_items) - len([x for x in all_items if not x.get("official")])
    print(f"{len(items)} itens · {human(total)}" + (f" · {hidden} oficiais ocultos (use --official)" if not args.official else ""))
    print(f"{'Tipo':12} {'Tamanho':>10}  Nome")
    for x in items:
        print(f"{x['kind']:12} {human(x['size']):>10}  {x['name']}")
    return 0

def cmd_remove(args) -> int:
    if not confirm(f"Mover para a lixeira: {args.path}?", args.yes):
        return 0
    delete_content(args.path)
    return 0

def cmd_join(args) -> int:
    ac = detect_ac()
    if not ac:
        eprint("[x] AC não encontrado.")
        return 1
    servers, _, _ = fetch_server_list(force=False)
    server = next((s for s in servers if s["ip"] == args.ip and int(s["port"]) == args.port), None)
    if not server:
        eprint(f"[x] Servidor {args.ip}:{args.port} não encontrado na lista.")
        return 1
    local = local_content(ac)
    status = check_server_mods(server, local)
    if status["missing_track"]:
        eprint(f"[!] Pista possivelmente faltando: {server.get('track')}")
    if status["missing_cars"]:
        eprint(f"[!] Carros faltando ({len(status['missing_cars'])}): "
               + ", ".join(status["missing_cars"][:10]))
    if not status["csp_ok"]:
        eprint(f"[!] CSP build {status['required_csp']} necessário; instalado {status['csp_build']}")
    car = args.car or (status["installed_cars"][0] if status["installed_cars"] else "")
    if not car:
        eprint("[x] Nenhum carro instalado para este servidor.")
        return 1
    if args.dry_run:
        print(f"[dry-run] Servidor: {server['name']}")
        print(f"  carro: {car}")
        print(f"  instalados: {', '.join(status['installed_cars'][:10])}")
        print(f"  faltando: {', '.join(status['missing_cars'][:10]) or 'nenhum'}")
        write_remote_ini(server, car, args.password or "", ac, dry_run=True)
        return 0
    return join_server(server, car, args.password or "", not args.no_launch, args.yes)

def cmd_restore_launcher(_args) -> int:
    return restore_launcher()

def cmd_install_mod(args) -> int:
    return install_mod(args.source, args.dry_run, args.force, args.merge, args.browser, args.yes)

def cmd_install_protontricks(args) -> int:
    return install_protontricks(args.yes)

def cmd_install_fonts(args) -> int:
    return install_fonts(args.yes)

def cmd_install_proton_ge(args) -> int:
    return install_proton_ge(args.version, args.yes, args.force)

def cmd_set_proton(args) -> int:
    return set_proton_compat(args.name, args.yes, args.force)

def cmd_setup(args) -> int:
    return setup_all(args.proton_version, args.yes, args.skip_proton, args.skip_csp)

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="acm", description="Assetto Corsa Linux Manager (protótipo)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("detect", help="Detecta Steam/AC/prefixo/Proton/CSP").set_defaults(func=cmd_detect)
    sub.add_parser("status", help="Alias de detect").set_defaults(func=cmd_status)

    q = sub.add_parser("setup-deps", help="Instala unrar/7z/bsdtar/cabextract conforme a distro")
    q.add_argument("--yes", action="store_true")
    q.add_argument("--dry-run", action="store_true")
    q.set_defaults(func=cmd_setup_deps)

    q = sub.add_parser("install-csp", help="Baixa e instala o Custom Shaders Patch")
    q.add_argument("--version", help="Versão do CSP (padrão: última)")
    q.add_argument("--dry-run", action="store_true")
    q.add_argument("--yes", action="store_true")
    q.add_argument("--no-fonts", action="store_true", help="Não rodar corefonts")
    q.set_defaults(func=cmd_install_csp)

    q = sub.add_parser("install-protontricks", help="Instala o protontricks")
    q.add_argument("--yes", action="store_true")
    q.set_defaults(func=cmd_install_protontricks)

    q = sub.add_parser("install-fonts", help="Instala Segoe/Verdana + corefonts")
    q.add_argument("--yes", action="store_true")
    q.set_defaults(func=cmd_install_fonts)

    q = sub.add_parser("install-proton-ge", help="Baixa e instala uma versão do Proton-GE")
    q.add_argument("--version", default=GE_PROTON_DEFAULT)
    q.add_argument("--yes", action="store_true")
    q.add_argument("--force", action="store_true")
    q.set_defaults(func=cmd_install_proton_ge)

    q = sub.add_parser("set-proton", help="Define o Proton do AC no config.vdf")
    q.add_argument("--name", default=GE_PROTON_DEFAULT)
    q.add_argument("--yes", action="store_true")
    q.add_argument("--force", action="store_true", help="Editar mesmo com o Steam aberto")
    q.set_defaults(func=cmd_set_proton)

    q = sub.add_parser("setup", help="Instala Proton-GE, CSP, fontes e protontricks")
    q.add_argument("--proton-version", default=GE_PROTON_DEFAULT)
    q.add_argument("--yes", action="store_true")
    q.add_argument("--skip-proton", action="store_true")
    q.add_argument("--skip-csp", action="store_true")
    q.set_defaults(func=cmd_setup)

    q = sub.add_parser("servers", help="Lista os servidores online do AC")
    q.add_argument("--filter", help="Filtra por nome, pista ou país")
    q.add_argument("--limit", type=int, default=30)
    q.add_argument("--json", action="store_true")
    q.add_argument("--force", action="store_true", help="Ignora o cache de 60s")
    q.add_argument("--ping", action="store_true", help="Ping UDP + players atualizados")
    q.set_defaults(func=cmd_servers)

    q = sub.add_parser("catalog", help="Consulta o catálogo de pistas e opcionalmente baixa/instala")
    q.add_argument("--search", help="Nome, pasta ou autor")
    q.add_argument("--refresh", action="store_true", help="Ignora o cache de 7 dias")
    q.add_argument("--link", action="store_true", help="Só entradas com link")
    q.add_argument("--auto", action="store_true", help="Só links com download automático")
    q.add_argument("--limit", type=int, default=20)
    q.add_argument("--download", action="store_true", help="Baixa a entrada escolhida")
    q.add_argument("--install", action="store_true", help="Baixa e instala a entrada escolhida")
    q.add_argument("--index", type=int, default=0)
    q.add_argument("--dest", default=str(CACHE / "downloads"))
    q.add_argument("--ac-root", help="Raiz AC de teste (padrão: detectar)")
    q.add_argument("--yes", action="store_true")
    q.set_defaults(func=cmd_catalog)

    q = sub.add_parser("installed", help="Lista o conteúdo instalado com tamanho")
    q.add_argument("--filter")
    q.add_argument("--json", action="store_true")
    q.add_argument("--official", action="store_true", help="Inclui conteúdo oficial (base/DLC)")
    q.set_defaults(func=cmd_installed)

    q = sub.add_parser("remove", help="Move um conteúdo instalado para a lixeira")
    q.add_argument("path")
    q.add_argument("--yes", action="store_true")
    q.set_defaults(func=cmd_remove)

    q = sub.add_parser("join", help="Entra em um servidor da lista (grava race.ini e abre o AC)")
    q.add_argument("--ip", required=True)
    q.add_argument("--port", type=int, required=True)
    q.add_argument("--car", help="ID do carro (padrão: primeiro instalado do servidor)")
    q.add_argument("--password")
    q.add_argument("--no-launch", action="store_true", help="Só grava o race.ini, sem abrir o AC")
    q.add_argument("--dry-run", action="store_true")
    q.add_argument("--yes", action="store_true")
    q.set_defaults(func=cmd_join)

    q = sub.add_parser("restore-launcher", help="Restaura o AssettoCorsa.exe original")
    q.set_defaults(func=cmd_restore_launcher)

    q = sub.add_parser("install-mod", help="Baixa/instala um mod")
    q.add_argument("source", help="Arquivo local ou URL")
    q.add_argument("--dry-run", action="store_true")
    q.add_argument("--force", action="store_true", help="Substitui o que já existe (com backup)")
    q.add_argument("--merge", action="store_true", help="Mescla com o que já existe")
    q.add_argument("--browser", action="store_true", help="Abre no navegador e espera o download")
    q.add_argument("--yes", action="store_true")
    q.set_defaults(func=cmd_install_mod)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        eprint("\n[i] Cancelado.")
        return 130
    except Exception as e:
        eprint(f"[x] {e}")
        return 1
