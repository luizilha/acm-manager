"""Lobby de servidores, ping, race.ini e entrada."""

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

from .content import local_content, check_server_mods, _resolve_server_track


def steam_id(steam: SteamInstall | None = None) -> str:
    steam = steam or detect_steam()
    if not steam:
        raise RuntimeError("Steam não encontrada.")
    login = steam.root / "config" / "loginusers.vdf"
    if login.exists():
        data = read_vdf(login)
        users = data.get("users", data)
        if isinstance(users, dict):
            candidates = []
            for uid, info in users.items():
                if isinstance(info, dict) and uid.isdigit():
                    candidates.append((
                        1 if str(info.get("AutoLogin")) == "1" else 0,
                        int(info.get("timestamp") or 0),
                        uid,
                    ))
            if candidates:
                candidates.sort(reverse=True)
                return candidates[0][2]
    cfg = steam.root / "config" / "config.vdf"
    if cfg.exists():
        data = read_vdf(cfg)

        def walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k == "SteamID" and isinstance(v, str) and v.isdigit():
                        return v
                    r = walk(v)
                    if r:
                        return r
            return None

        sid = walk(data)
        if sid:
            return sid
    sid = os.environ.get("STEAM_ID")
    if sid:
        return sid
    raise RuntimeError("Steam ID não encontrado; defina STEAM_ID.")

def _normalize_server(s: dict) -> dict:
    out = dict(s)
    out["name"] = str(s.get("name") or "(sem nome)")
    out["ip"] = str(s.get("ip") or "")
    out["port"] = int(s.get("port") or 0)
    out["cport"] = int(s.get("cport") or 0)
    out["clients"] = int(s.get("clients") or 0)
    out["maxclients"] = int(s.get("maxclients") or 0)
    out["pass"] = bool(s.get("pass"))
    cars = s.get("cars") or []
    out["car_count"] = len(cars) if isinstance(cars, list) else 0
    track = str(s.get("track") or "")
    out["track"] = track
    short = track.rsplit("../", 1)[-1] if "../" in track else track
    out["track_short"] = short.rsplit("/", 1)[-1] if "/" in short else short
    country = s.get("country")
    out["country_name"] = country[0] if isinstance(country, list) and country else ""
    out["country_code"] = country[1] if isinstance(country, list) and len(country) > 1 else ""
    return out

def fetch_server_list(force: bool = False, ttl: int = SERVERS_TTL):
    """Retorna (servers, fetched_at, from_cache). Usa cache para respeitar o rate limit."""
    now = time.time()
    cached = None
    if SERVERS_CACHE.exists():
        try:
            cached = json.loads(SERVERS_CACHE.read_text(encoding="utf-8"))
            if not force and now - float(cached.get("fetched_at", 0)) < ttl:
                return [_normalize_server(s) for s in cached.get("servers", [])], float(cached.get("fetched_at", 0)), True
        except Exception:
            cached = None

    sid = steam_id()
    url = SERVER_LIST_URL.format(guid=sid)
    req = urllib.request.Request(url, headers={
        "User-Agent": SERVER_LIST_UA,
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read()
            encoding = r.headers.get("Content-Encoding", "")
    except urllib.error.HTTPError as e:
        raw = e.read()
        encoding = e.headers.get("Content-Encoding", "") if e.headers else ""

    if encoding.lower() == "gzip":
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8", "replace").strip()
    if text.startswith("ERROR"):
        if cached:
            return [_normalize_server(s) for s in cached.get("servers", [])], float(cached.get("fetched_at", 0)), True
        raise RuntimeError(f"Lobby do AC respondeu: {text}")
    try:
        data = json.loads(text)
    except Exception as e:
        raise RuntimeError(f"Resposta inválida do lobby: {text[:160]}") from e

    servers = [_normalize_server(s) for s in data if isinstance(s, dict)]
    SERVERS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    SERVERS_CACHE.write_text(json.dumps({
        "fetched_at": now,
        "guid": sid,
        "servers": servers,
    }, ensure_ascii=False), encoding="utf-8")
    return servers, now, False

def ping_server(ip: str, port: int, timeout: float = 1.5):
    """Ping do AC: envia 0xC8 0x00 e recebe [200, http_port_lo, http_port_hi]."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            start = time.perf_counter()
            sock.sendto(b"\xc8\x00", (ip, int(port)))
            data, _ = sock.recvfrom(3)
            ms = (time.perf_counter() - start) * 1000
            if len(data) >= 3 and data[0] == 200:
                return struct.unpack("<H", data[1:3])[0], int(ms)
    except Exception:
        pass
    return None

def _set_ini_section(text: str, section: str, values: dict[str, str]) -> str:
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip().lower() == f"[{section.lower()}]"), None)
    if start is None:
        lines += ["", f"[{section}]"] + [f"{k}={v}" for k, v in values.items()]
        return "\n".join(lines) + "\n"
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
    seen: set[str] = set()
    for i in range(start + 1, end):
        m = re.match(r"^\s*([^=;#]+?)\s*=", lines[i])
        if not m:
            continue
        key = m.group(1).strip()
        for k, v in values.items():
            if key.lower() == k.lower():
                lines[i] = f"{k}={v}"
                seen.add(k)
    insert = end
    for k, v in values.items():
        if k not in seen:
            lines.insert(insert, f"{k}={v}")
            insert += 1
    return "\n".join(lines) + "\n"

def fetch_server_details(server: dict, timeout: float = 5.0) -> dict | None:
    """Consulta /api/details para detectar restrições que o lobby não mostra."""
    if not server:
        return None
    ip = str(server.get("ip") or "").strip()
    port = server.get("cport") or server.get("tport") or server.get("port")
    if not ip or not port:
        return None
    url = f"http://{ip}:{port}/api/details"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(2 * 1024 * 1024)
        parsed = json.loads(data.decode("utf-8", "replace"))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def server_access_note(details: dict | None) -> str | None:
    """Detecta licença/password/whitelist na descrição estendida do servidor."""
    if not details:
        return None
    raw = str(details.get("description") or "")
    text = re.sub(r"\[/?[^\]]+\]", " ", raw)
    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", text))
    low = text.lower()
    words = (
        "licence", "license", "licença", "licenca", "password", "senha",
        "whitelist", "entry list", "lista de entrada", "get licence",
        "get license", "donate", "doação", "doacao", "patreon",
    )
    if not any(word in low for word in words):
        return None
    clean = " ".join(text.split())
    return clean[:320]


def _remove_ini_keys(text: str, section: str, keys: list[str]) -> str:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().lower() == f"[{section.lower()}]"), None)
    if start is None:
        return text
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
    wanted = {key.lower() for key in keys}
    kept = []
    for i, line in enumerate(lines):
        if start < i < end:
            match = re.match(r"^\s*([^=;#]+?)\s*=", line)
            if match and match.group(1).strip().lower() in wanted:
                continue
        kept.append(line)
    return "\n".join(kept) + "\n"


def _server_track_ids(server: dict, ac: AcInstall) -> tuple[str, str]:
    """Resolve o ID do servidor para TRACK/CONFIG_TRACK com o case local."""
    raw = str(server.get("track") or "")
    local = local_content(ac)
    base, layout, _ = _resolve_server_track(raw, local)
    if not base:
        base = raw.split("/")[-1]
    base_dir = None
    tracks_root = ac.ac_root / "content" / "tracks"
    if tracks_root.is_dir():
        base_dir = next(
            (p for p in tracks_root.iterdir() if p.is_dir() and p.name.lower() == base.lower()),
            None,
        )
    if base_dir is not None:
        base = base_dir.name
        if layout:
            sub = next(
                (p for p in base_dir.iterdir() if p.is_dir() and p.name.lower() == layout.lower()),
                None,
            )
            if sub is not None:
                layout = sub.name
    return base, layout


def write_remote_ini(server: dict, car_id: str, password: str, ac: AcInstall | None = None,
                     dry_run: bool = False) -> Path:
    ac = ac or detect_ac()
    if not ac:
        raise RuntimeError("AC não encontrado.")
    cfg = prefix_documents(ac) / "cfg"
    cfg.mkdir(parents=True, exist_ok=True)
    race = cfg / "race.ini"
    text = race.read_text(encoding="utf-8", errors="replace") if race.exists() else ""
    track_id, layout_id = _server_track_ids(server, ac)
    server_name = re.sub(r"[\x00-\x1f\x7f]", "", str(server.get("name") or "")).strip()
    details = server.get("_details")
    if details is None:
        details = fetch_server_details(server)
    features: list[str] = []
    if isinstance(details, dict):
        raw_features = details.get("features")
        if isinstance(raw_features, list):
            features = [str(feature) for feature in raw_features if feature]
    skin_id = ""
    cars_root = ac.ac_root / "content" / "cars"
    if cars_root.is_dir():
        car_dir = next(
            (p for p in cars_root.iterdir() if p.is_dir() and p.name.lower() == car_id.lower()),
            None,
        )
        if car_dir is not None:
            skins = car_dir / "skins"
            if skins.is_dir():
                skin_dir = next((p for p in skins.iterdir() if p.is_dir()), None)
                if skin_dir is not None:
                    skin_id = skin_dir.name
    values = {
        "ACTIVE": "1",
        "SERVER_IP": str(server.get("ip") or ""),
        "SERVER_PORT": str(server.get("tport") or server.get("port") or ""),
        "SERVER_HTTP_PORT": str(server.get("cport") or ""),
        "SERVER_NAME": server_name,
        "REQUESTED_CAR": car_id,
        "GUID": steam_id(ac.steam),
        "PASSWORD": password or "",
    }
    if isinstance(details, dict):
        values["__CM_EXTENDED"] = "1" if details.get("currentWeatherId") is not None else "0"
    if features:
        values["__FEATURES"] = ",".join(features)
    new_text = _set_ini_section(text, "REMOTE", values)
    if not features:
        new_text = _remove_ini_keys(new_text, "REMOTE", ["__FEATURES"])
    if not isinstance(details, dict):
        new_text = _remove_ini_keys(new_text, "REMOTE", ["__CM_EXTENDED"])
    # Online usa o conteúdo local para montar o carro/pista antes do handshake.
    new_text = _set_ini_section(new_text, "RACE", {
        "TRACK": track_id,
        "CONFIG_TRACK": layout_id,
        "MODEL": car_id,
        "MODEL_CONFIG": "",
        "SKIN": skin_id,
        "CARS": "1",
    })
    new_text = _set_ini_section(new_text, "CAR_0", {
        "MODEL": "-",
        "MODEL_CONFIG": "",
        "SKIN": skin_id,
        "SETUP": "",
    })
    new_text = _set_ini_section(new_text, "SESSION_0", {
        "NAME": "Nothing",
        "TYPE": "1",
        "DURATION_MINUTES": "0",
    })
    if dry_run:
        print(f"[dry-run] Escreveria {race}:")
        for k, v in values.items():
            print(f"  {k}={v}")
        return race
    backup = race.with_name("race.ini.acm-backup")
    if race.exists() and not backup.exists():
        shutil.copy2(race, backup)
    race.write_text(new_text, encoding="utf-8")
    return race

def ensure_direct_launch(ac: AcInstall) -> bool:
    """Substitui AssettoCorsa.exe pelo acs.exe para o Steam abrir o jogo direto."""
    launcher = ac.ac_root / "AssettoCorsa.exe"
    acs = ac.ac_root / "acs.exe"
    backup = ac.ac_root / "AssettoCorsa_original.exe"
    if not launcher.exists() or not acs.exists():
        raise RuntimeError("AssettoCorsa.exe ou acs.exe não encontrado.")
    if launcher.stat().st_size == acs.stat().st_size:
        return False
    if is_process_running("acs.exe") or is_process_running("AssettoCorsa.exe"):
        raise RuntimeError("Feche o AC antes de preparar o lançamento direto.")
    if not backup.exists():
        shutil.copy2(launcher, backup)
        print(f"[✓] Launcher original salvo em {backup}")
    shutil.copy2(acs, launcher)
    print("[✓] AssettoCorsa.exe agora aponta para acs.exe (lançamento direto).")
    return True

def restore_launcher(ac: AcInstall | None = None) -> int:
    ac = ac or detect_ac()
    if not ac:
        eprint("[x] AC não encontrado.")
        return 1
    launcher = ac.ac_root / "AssettoCorsa.exe"
    backup = ac.ac_root / "AssettoCorsa_original.exe"
    if not backup.exists():
        eprint("[!] AssettoCorsa_original.exe não existe; nada a restaurar.")
        return 1
    shutil.copy2(backup, launcher)
    print("[✓] Launcher original restaurado.")
    return 0

def launch_ac(ac: AcInstall | None = None) -> None:
    """Pede ao Steam para iniciar o app 244210 (o launcher direto já está no lugar)."""
    ac = ac or detect_ac()
    if not ac:
        raise RuntimeError("AC não encontrado.")
    if shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", "steam://rungameid/244210"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["steam", "-applaunch", "244210"])
    print("[i] Pedindo ao Steam para iniciar o Assetto Corsa…")

def join_server(server: dict, car_id: str, password: str = "", launch: bool = True,
                assume_yes: bool = False) -> int:
    ac = detect_ac()
    if not ac:
        eprint("[x] AC não encontrado.")
        return 1
    if is_process_running("acs.exe") or is_process_running("AssettoCorsa.exe"):
        eprint("[!] Feche o Assetto Corsa antes de entrar em um servidor.")
        return 1
    local = local_content(ac)
    status = check_server_mods(server, local)
    if not status["join_ok"]:
        eprint("[x] Conteúdo incompatível:")
        if status["missing_track"]:
            eprint(f"    pista: {server.get('track')}")
        if not status["csp_ok"]:
            eprint(f"    CSP build {status['required_csp']} necessário; instalado {status['csp_build']}")
        if status["missing_cars"]:
            eprint("    carros faltando: " + ", ".join(status["missing_cars"][:20]))
        return 1
    if car_id:
        match = next((c for c in status["installed_cars"] if c.lower() == car_id.lower()), None)
        if not match:
            eprint(f"[x] Carro escolhido não está instalado/na lista: {car_id}")
            return 1
        car_id = match
    if not car_id:
        car_id = status["installed_cars"][0] if status["installed_cars"] else ""
    if not car_id:
        eprint("[x] Nenhum carro instalado para este servidor.")
        return 1
    if not confirm(f"Entrar em {server.get('name')} com {car_id}?", assume_yes):
        return 0
    write_remote_ini(server, car_id, password, ac)
    if launch:
        ensure_direct_launch(ac)
        launch_ac(ac)
    print(f"[✓] race.ini configurado para {server.get('ip')}:{server.get('port')}.")
    return 0
