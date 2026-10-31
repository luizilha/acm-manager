"""Inventário de conteúdo, checagem de mods e remoção."""

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

from .base import _csp_build


NO_HESI_CARS_URL = "https://cdn.nohesi.gg/cars/"
NO_HESI_CARS_CACHE = CACHE / "nohesi-cars.json"
NO_HESI_CARS_TTL = 24 * 3600

_NO_HESI_ROW = re.compile(r'<a href="([^"]+?\.7z)"[^>]*>.*?</a></td><td class="size">([^<]+)</td>')


def local_content(ac: AcInstall) -> dict:
    def folders(path: Path) -> set[str]:
        try:
            return {p.name.lower() for p in path.iterdir() if p.is_dir()}
        except Exception:
            return set()
    tracks_root = ac.ac_root / "content" / "tracks"
    track_layouts: set[str] = set()
    if tracks_root.is_dir():
        for base in tracks_root.iterdir():
            if not base.is_dir():
                continue
            for sub in base.iterdir():
                if not sub.is_dir():
                    continue
                if sub.name.lower() in {"ui", "data", "ai", "sfx", "skins", "extension", "texture"}:
                    continue
                if (sub / "data").is_dir() or (sub / "ai").is_dir():
                    track_layouts.add(f"{base.name}/{sub.name}".lower())
    return {
        "cars": folders(ac.ac_root / "content" / "cars"),
        "tracks": folders(tracks_root),
        "track_layouts": track_layouts,
        "csp_build": _csp_build(ac),
    }

def _first_file(*paths: Path) -> Path | None:
    for path in paths:
        try:
            if path.is_file():
                return path
        except OSError:
            continue
    return None


def default_car_skin(car_dir: Path, skin: str | None = None) -> str | None:
    """Skin usada no race.ini (a primeira pasta de skin, salvo escolha explícita)."""
    skins = Path(car_dir) / "skins"
    if not skins.is_dir():
        return None
    if skin:
        wanted = str(skin).lower()
        match = next(
            (p for p in skins.iterdir() if p.is_dir() and p.name.lower() == wanted),
            None,
        )
        if match is not None:
            return match.name
    first = next((p for p in skins.iterdir() if p.is_dir()), None)
    return first.name if first is not None else None


def car_preview_path(car_dir: Path, skin: str | None = None) -> Path | None:
    """Imagem de showroom do carro (preview.jpg), com fallbacks."""
    car_dir = Path(car_dir)
    skins = car_dir / "skins"
    candidates: list[Path] = []
    chosen = default_car_skin(car_dir, skin)
    if chosen:
        folder = skins / chosen
        candidates += [
            folder / "preview.jpg",
            folder / "preview_original.jpg",
            folder / "preview.png",
        ]
    if skins.is_dir():
        for pattern in ("*/preview.jpg", "*/preview.png", "*/preview_original.jpg"):
            candidates += sorted(skins.glob(pattern))
    ui = car_dir / "ui"
    candidates += [ui / "preview.png", ui / "preview.jpg", car_dir / "logo.png"]
    return _first_file(*candidates)


def car_metadata(car_dir: Path) -> dict:
    """Nome, marca, classe e specs de ``ui/ui_car.json``."""
    car_dir = Path(car_dir)
    data: dict = {}
    ui = car_dir / "ui" / "ui_car.json"
    if ui.is_file():
        text = ""
        try:
            text = ui.read_text(encoding="utf-8-sig", errors="replace")
            # Kunos ui_car.json costuma ter quebras de linha literais na descrição.
            loaded = json.loads(text, strict=False)
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}
            for key in ("name", "brand", "class", "year", "author"):
                match = re.search(rf'"{key}"\s*:\s*"([^"]*)"', text)
                if match:
                    data[key] = match.group(1)
    specs = data.get("specs")
    return {
        "id": car_dir.name,
        "name": str(data.get("name") or car_dir.name),
        "brand": str(data.get("brand") or ""),
        "class": str(data.get("class") or ""),
        "year": str(data.get("year") or ""),
        "author": str(data.get("author") or ""),
        "specs": specs if isinstance(specs, dict) else {},
    }


def content_preview_path(kind: str, path: Path) -> Path | None:
    """Preview para um item da aba Instalados."""
    path = Path(path)
    if kind == "car":
        return car_preview_path(path)
    if kind == "track":
        direct = _first_file(
            path / "ui" / "preview.png",
            path / "ui" / "preview.jpg",
            path / "map.png",
            path / "ui" / "logo.png",
        )
        if direct is not None:
            return direct
        if path.is_dir():
            for child in sorted(path.iterdir()):
                if child.is_dir() and (child / "map.png").is_file():
                    return child / "map.png"
        return None
    if kind == "track-layout":
        return _first_file(
            path / "map.png",
            path.parent / "ui" / "preview.png",
            path.parent / "ui" / "preview.jpg",
            path.parent / "map.png",
        )
    if path.is_dir():
        return _first_file(
            path / "logo.png",
            path / "icon.png",
            path / "preview.png",
            path / "preview.jpg",
        )
    return None


def _dir_sizes(paths: list[Path]) -> dict[str, int]:
    if not paths:
        return {}
    try:
        out = subprocess.run(["du", "-sb", *map(str, paths)], capture_output=True, text=True, timeout=180)
        sizes = {}
        for line in out.stdout.splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2:
                try:
                    sizes[parts[1]] = int(parts[0])
                except ValueError:
                    pass
        if sizes:
            return sizes
    except Exception:
        pass
    sizes = {}
    for p in paths:
        total = 0
        for root, _dirs, files in os.walk(p):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        sizes[str(p)] = total
    return sizes

def official_content(ac: AcInstall | None = None) -> dict:
    """Lista de conteúdo oficial (base + DLC) do CSP; fallback para ks_*."""
    ac = ac or detect_ac()
    cars: set[str] = set()
    tracks: set[str] = set()
    layouts: set[str] = set()
    if ac:
        path = ac.ac_root / "extension/config/data_standard_content.ini"
        if path.exists():
            section = ""
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if not s or s.startswith(";"):
                    continue
                if s.startswith("[") and s.endswith("]"):
                    section = s[1:-1].upper()
                    continue
                if "=" not in s:
                    continue
                key = s.split("=", 1)[0].strip().lower()
                if section == "CARS":
                    cars.add(key)
                elif section == "TRACKS":
                    tracks.add(key.split("/", 1)[0])
                    layouts.add(key)
    return {"cars": cars, "tracks": tracks, "layouts": layouts}

def installed_content(ac: AcInstall | None = None) -> list[dict]:
    ac = ac or detect_ac()
    if not ac:
        return []
    roots = [
        ("car", ac.ac_root / "content/cars", True),
        ("track", ac.ac_root / "content/tracks", True),
        ("app-python", ac.ac_root / "apps/python", True),
        ("app-lua", ac.ac_root / "apps/lua", True),
        ("weather", ac.ac_root / "content/weather", True),
        ("showroom", ac.ac_root / "content/showroom", True),
        ("driver", ac.ac_root / "content/driver", True),
        ("font", ac.ac_root / "content/fonts", False),
        ("ppfilter", ac.ac_root / "system/cfg/ppfilters", False),
    ]
    entries: list[tuple[str, Path]] = []
    for kind, root, dirs_only in roots:
        if not root.is_dir():
            continue
        try:
            children = list(root.iterdir())
        except OSError:
            continue
        for child in children:
            if child.name.startswith("."):
                continue
            if dirs_only and not child.is_dir():
                continue
            entries.append((kind, child))

    official = official_content(ac)
    tracks_root = ac.ac_root / "content" / "tracks"
    layout_entries: list[tuple[str, Path]] = []
    if tracks_root.is_dir():
        for base in tracks_root.iterdir():
            if not base.is_dir():
                continue
            base_low = base.name.lower()
            if base_low not in official["tracks"] and not base_low.startswith("ks_"):
                continue
            for sub in base.iterdir():
                if not sub.is_dir():
                    continue
                if sub.name.lower() in {"ui", "data", "ai", "sfx", "skins", "extension", "texture"}:
                    continue
                if (sub / "data").is_dir() or (sub / "ai").is_dir():
                    layout_entries.append(("track-layout", sub))

    # du deduplica inodes: layouts dentro de uma pista já listada sairiam com 0.
    sizes = _dir_sizes([p for _, p in entries])
    if layout_entries:
        sizes.update(_dir_sizes([p for _, p in layout_entries]))
        entries.extend(layout_entries)
    base_weather = {"1_heavy_fog", "2_light_fog", "3_clear", "4_mid_clear", "5_light_clouds", "6_mid_clouds", "7_heavy_clouds"}
    items = []
    for kind, p in entries:
        size = sizes.get(str(p), 0)
        name = p.name
        low = name.lower()
        is_official = low.startswith("ks_")
        if kind == "car":
            is_official = is_official or low in official["cars"]
        elif kind == "track":
            is_official = is_official or low in official["tracks"]
        elif kind == "track-layout":
            name = f"{p.parent.name}/{p.name}"
            is_official = f"{p.parent.name}/{p.name}".lower() in official["layouts"]
        elif kind == "weather":
            is_official = is_official or low in base_weather
        elif kind == "app-python":
            is_official = is_official or low in {"system", "gmeter", "chat"}
        elif kind == "app-lua":
            is_official = is_official or low in {"system"}
        elif kind in ("font", "ppfilter"):
            # fontes e filtros base/CSP não são "mods" para a lista de conteúdo
            is_official = True
        elif kind == "showroom":
            is_official = is_official or low in {"showroom", "hangar", "beach", "industrial"}
        elif kind == "driver":
            is_official = is_official or low in {"driver_skins", "drivers_oculus"}
        items.append({
            "kind": kind,
            "name": name,
            "path": str(p),
            "size": size,
            "base": is_official,
            "official": is_official,
        })
    items.sort(key=lambda x: x["size"], reverse=True)
    return items

def delete_content(path: str, ac: AcInstall | None = None) -> Path:
    ac = ac or detect_ac()
    if not ac:
        raise RuntimeError("AC não encontrado.")
    p = Path(path).expanduser().resolve()
    roots = [
        ac.ac_root / "content/cars",
        ac.ac_root / "content/tracks",
        ac.ac_root / "apps/python",
        ac.ac_root / "apps/lua",
        ac.ac_root / "content/weather",
        ac.ac_root / "content/showroom",
        ac.ac_root / "content/driver",
        ac.ac_root / "content/fonts",
        ac.ac_root / "system/cfg/ppfilters",
    ]
    layout_path = p.parent.parent.resolve() == (ac.ac_root / "content" / "tracks").resolve()
    allowed = any(p.parent.resolve() == r.resolve() for r in roots) or layout_path
    if not allowed:
        raise RuntimeError("Caminho fora das pastas de conteúdo do AC.")
    official = official_content(ac)
    low = p.name.lower()
    layout_key = f"{p.parent.name}/{p.name}".lower()
    is_official = (
        (p.parent.name == "cars" and (low.startswith("ks_") or low in official["cars"]))
        or (p.parent.name == "tracks" and (low.startswith("ks_") or low in official["tracks"]))
        or (layout_path and layout_key in official["layouts"])
        or (p.parent.name == "weather" and low in {"1_heavy_fog", "2_light_fog", "3_clear", "4_mid_clear", "5_light_clouds", "6_mid_clouds", "7_heavy_clouds"})
        or (p.parent.name == "python" and low in {"system", "gmeter", "chat"})
        or p.parent.name in ("fonts", "ppfilters")
        or (p.parent.name == "showroom" and low in {"showroom", "hangar", "beach", "industrial"})
        or (p.parent.name == "driver" and low in {"driver_skins", "drivers_oculus"})
    )
    if is_official:
        raise RuntimeError("Conteúdo oficial (base/DLC); não vou mover para a lixeira.")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = STATE / "trash" / stamp / p.parent.name / p.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(p), str(dest))
    print(f"[✓] Movido para a lixeira: {dest}")
    return dest

def mod_search_url(kind: str, mod_id: str) -> str:
    term = mod_id.replace("_", " ") if kind == "car" else mod_id
    query = urllib.parse.quote_plus(f"Assetto Corsa {term} {kind} mod download")
    return f"https://www.google.com/search?q={query}"


def _nohesi_size_bytes(text: str) -> int:
    match = re.match(r"\s*([\d.,]+)\s*(B|KiB|MiB|GiB|TiB)", text.replace("\xa0", " "))
    if not match:
        return 0
    value = float(match.group(1).replace(",", ""))
    units = {"B": 1, "KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3, "TiB": 1024 ** 4}
    return int(value * units[match.group(2)])


def fetch_nohesi_car_index(force: bool = False, ttl: int = NO_HESI_CARS_TTL) -> list[dict]:
    """Lista os carros publicados em cdn.nohesi.gg/cars (modelo, URL e tamanho)."""
    now = time.time()
    if not force and NO_HESI_CARS_CACHE.exists():
        try:
            cached = json.loads(NO_HESI_CARS_CACHE.read_text(encoding="utf-8"))
            if now - float(cached.get("fetched_at", 0)) < ttl:
                cars = cached.get("cars")
                if isinstance(cars, list) and cars:
                    return cars
        except Exception:
            pass
    req = urllib.request.Request(NO_HESI_CARS_URL, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=60) as response:
        page = response.read().decode("utf-8", "replace")
    cars: list[dict] = []
    seen: set[str] = set()
    for href, size in _NO_HESI_ROW.findall(page):
        name = urllib.parse.unquote(html_lib.unescape(href))
        model = name[:-3] if name.lower().endswith(".7z") else name
        key = model.lower()
        if not model or key in seen:
            continue
        seen.add(key)
        cars.append({
            "model": model,
            "url": urllib.parse.urljoin(NO_HESI_CARS_URL, href),
            "size": _nohesi_size_bytes(size),
        })
    if not cars:
        raise RuntimeError("A listagem de carros do CDN No Hesi veio vazia.")
    cars.sort(key=lambda item: item["model"].lower())
    try:
        NO_HESI_CARS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        NO_HESI_CARS_CACHE.write_text(
            json.dumps({"fetched_at": now, "url": NO_HESI_CARS_URL, "cars": cars}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass
    return cars


def nohesi_missing_cars(index: list[dict], local: dict | None) -> list[dict]:
    installed = {str(car).lower() for car in ((local or {}).get("cars") or set())}
    return [item for item in index if item["model"].lower() not in installed]


def install_nohesi_cars(models: Iterable[str], assume_yes: bool = True,
                        index: list[dict] | None = None) -> int:
    """Baixa e instala carros do CDN No Hesi, ignorando os já instalados."""
    ac = detect_ac()
    if not ac:
        eprint("[x] AC não encontrado.")
        return 1
    index = index or fetch_nohesi_car_index()
    by_model = {item["model"].lower(): item for item in index}
    installed = {str(car).lower() for car in (local_content(ac).get("cars") or set())}
    todo: list[dict] = []
    unknown: list[str] = []
    for model in dict.fromkeys(str(model) for model in models if model):
        item = by_model.get(model.lower())
        if item is None:
            unknown.append(model)
            continue
        if item["model"].lower() in installed:
            continue
        todo.append(item)
    if unknown:
        eprint("[!] Fora da lista do CDN: " + ", ".join(unknown[:20]))
    if not todo:
        print("[i] Nada a instalar: os carros já estão instalados.")
        return 0 if not unknown else 1
    total = sum(item["size"] for item in todo)
    print(f"[i] {len(todo)} carro(s) do CDN No Hesi ({human(total)})…")
    from .installer import install_mod
    failed: list[str] = []
    for position, item in enumerate(todo, 1):
        print(f"\n=== [{position}/{len(todo)}] {item['model']} ({human(item['size'])}) ===")
        try:
            rc = install_mod(item["url"], False, False, False, False, assume_yes)
        except Exception as e:
            eprint(f"[x] {item['model']}: {e}")
            rc = 1
        if rc != 0:
            failed.append(item["model"])
    if failed:
        eprint("[x] Falhou: " + ", ".join(failed[:20]))
        return 1
    print(f"[✓] {len(todo)} carro(s) instalado(s) do CDN No Hesi.")
    return 0

def _track_candidates(server: dict) -> set[str]:
    raw = str(server.get("track") or "")
    if raw.startswith("csp/"):
        raw = raw[4:]
    parts = [p for p in raw.replace("\\", "/").split("/") if p and p != ".." and not p.isdigit()]
    return {p.lower() for p in parts}

def _resolve_server_track(raw: str, local: dict) -> tuple[str, str, bool]:
    """Resolve o ID de pista do lobby para pasta base + layout local.

    O lobby usa tanto ``base/layout`` quanto ``base-layout`` (ex.:
    ``ks_nordschleife-ae nordtouristbtg``). Pastas locais exatas têm prioridade.
    """
    raw = str(raw or "")
    if raw.startswith("csp/"):
        raw = raw[4:]
    parts = [p for p in raw.replace("\\", "/").split("/") if p and p != ".." and not p.isdigit()]
    tracks = local.get("tracks", set())
    layouts = local.get("track_layouts", set())

    for idx, part in enumerate(parts):
        base_low = part.lower()
        if base_low not in tracks:
            continue
        layout = "/".join(parts[idx + 1:]).lower()
        if not layout:
            return part, "", True
        return part, layout, f"{base_low}/{layout}" in layouts

    for token in reversed(parts):
        low = token.lower()
        split_candidates = []
        for i, ch in enumerate(token):
            if ch != "-":
                continue
            base, layout = low[:i], low[i + 1:]
            if base in tracks:
                split_candidates.append((base, layout))
        if split_candidates:
            base, layout = max(split_candidates, key=lambda pair: len(pair[0]))
            return base, layout, f"{base}/{layout}" in layouts
    return "", "", False

def check_server_mods(server: dict, local: dict) -> dict:
    cars = [str(c) for c in (server.get("cars") or []) if c]
    missing_cars = [c for c in cars if c.lower() not in local["cars"]]
    installed_cars = [c for c in cars if c.lower() in local["cars"]]
    raw_track = str(server.get("track") or "")
    if raw_track.startswith("csp/"):
        raw_track = raw_track[4:]
    parts = [p for p in raw_track.replace("\\", "/").split("/") if p and p != ".." and not p.isdigit()]
    _base, _layout, track_ok = _resolve_server_track(raw_track, local)
    candidates = set(parts)
    required_csp = 0
    m = re.match(r"^csp/(\d+)/", str(server.get("track") or ""))
    if m:
        required_csp = int(m.group(1))
    csp_build = local.get("csp_build")
    csp_ok = required_csp <= 0 or (csp_build is not None and csp_build >= required_csp)
    join_ok = track_ok and csp_ok and (not cars or bool(installed_cars))
    return {
        "ok": not missing_cars and track_ok and csp_ok,
        "join_ok": join_ok,
        "missing_cars": missing_cars,
        "installed_cars": installed_cars,
        "missing_track": not track_ok,
        "track_base": _base,
        "track_layout": _layout,
        "track_candidates": sorted(candidates),
        "required_csp": required_csp,
        "csp_build": csp_build,
        "csp_ok": csp_ok,
    }


def server_requires_mods(server: dict, official: dict | None = None) -> bool:
    """True when track or at least one car is not official base/DLC.

    A pista é checada como base/layout no conjunto oficial. Carros usam os IDs
    exatos do ``data_standard_content.ini``; CSP não conta como mod de conteúdo.
    """
    official = official or official_content()
    raw = str(server.get("track") or "")
    official_tracks = {
        "tracks": official.get("tracks", set()),
        "track_layouts": official.get("layouts", set()),
    }
    base, layout, layout_ok = _resolve_server_track(raw, official_tracks)
    if not base:
        return True
    if layout and not layout_ok:
        return True

    official_cars = official.get("cars", set())
    cars = [str(car) for car in (server.get("cars") or []) if car]
    if official_cars:
        return any(car.lower() not in official_cars for car in cars)
    # Fallback antigo quando o manifesto do CSP não existe.
    return any(not car.lower().startswith("ks_") for car in cars)
