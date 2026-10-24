"""Constantes, VDF, utilidades e detecção Steam/AC/Proton."""

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


APP_ID = "244210"

AC_DIR_NAME = "assettocorsa"

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"

ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz"}

CSP_URL = "https://acstuff.club/patch/?get={version}"

CSP_PAGE = "https://acstuff.club/patch/"

GE_PROTON_DEFAULT = "GE-Proton9-20"

GE_API = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/tags/{tag}"

FONTS_URL = "https://files.acstuff.ru/shared/T0Zj/fonts.zip"

SERVER_LIST_URL = "http://lobby.assettocorsa.net/lobby.ashx/list?guid={guid}"

SERVER_LIST_UA = "Assetto Corsa Launcher"

SERVERS_TTL = 60  # segundos; o lobby responde "SLOW DOWN" se martelar

CACHE = Path.home() / ".cache" / "acm"

STATE = Path.home() / ".local" / "share" / "acm"

BACKUPS = STATE / "backups"

MANIFESTS = STATE / "manifests"

SERVERS_CACHE = CACHE / "servers.json"

CATALOG_URL = "https://docs.google.com/spreadsheets/d/1UcjQGfjGOAzGPf2VqraRgZsKHmZiTqWJmrnMHHh323A/export?format=xlsx"

CATALOG_PAGE = "https://docs.google.com/spreadsheets/d/1UcjQGfjGOAzGPf2VqraRgZsKHmZiTqWJmrnMHHh323A/edit"

CATALOG_CACHE = CACHE / "tracks-catalog.json"

CATALOG_TTL = 7 * 24 * 3600

__all__ = [
    "DistroInfo", "detect_distro", "distro_install_command",
    "APP_ID", "AC_DIR_NAME", "UA", "ARCHIVE_EXTS", "CSP_URL", "CSP_PAGE",
    "GE_PROTON_DEFAULT", "GE_API", "FONTS_URL", "SERVER_LIST_URL",
    "SERVER_LIST_UA", "SERVERS_TTL", "CACHE", "STATE", "BACKUPS",
    "MANIFESTS", "SERVERS_CACHE", "CATALOG_URL", "CATALOG_PAGE",
    "CATALOG_CACHE", "CATALOG_TTL", "eprint", "human", "run", "confirm",
    "sha256", "sha512_file", "is_process_running", "parse_vdf", "read_vdf",
    "SteamInstall", "AcInstall", "detect_steam", "detect_ac",
    "prefix_documents",
]

def eprint(*a, **k):
    print(*a, file=sys.stderr, **k)

def human(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TiB"

def run(cmd: list[str], check: bool = False, capture: bool = False, env: dict | None = None):
    if capture:
        return subprocess.run(cmd, text=True, capture_output=True, env=env)
    return subprocess.run(cmd, check=check, env=env)

def confirm(question: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        eprint(f"[!] {question} — use --yes para confirmar em modo não interativo.")
        return False
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes", "s", "sim")

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def sha512_file(path: Path) -> str:
    h = hashlib.sha512()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def is_process_running(pattern: str) -> bool:
    try:
        out = subprocess.run(["pgrep", "-af", pattern], text=True, capture_output=True)
        return out.returncode == 0 and bool(out.stdout.strip())
    except FileNotFoundError:
        return False

def parse_vdf(text: str) -> dict:
    """Parser simples para libraryfolders.vdf / config.vdf."""
    tokens: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            i = text.find("\n", i)
            if i == -1:
                break
            continue
        if c in "{}":
            tokens.append(c)
            i += 1
            continue
        if c == '"':
            i += 1
            buf = []
            while i < n:
                if text[i] == "\\" and i + 1 < n:
                    buf.append(text[i + 1])
                    i += 2
                elif text[i] == '"':
                    i += 1
                    break
                else:
                    buf.append(text[i])
                    i += 1
            tokens.append("".join(buf))
            continue
        j = i
        while j < n and text[j] not in ' \t\r\n{}"':
            j += 1
        tokens.append(text[i:j])
        i = j

    pos = 0

    def parse_block() -> dict:
        nonlocal pos
        out: dict = {}
        while pos < len(tokens):
            t = tokens[pos]
            if t == "}":
                pos += 1
                return out
            if t == "{":
                pos += 1
                continue
            key = t
            pos += 1
            if pos >= len(tokens):
                out[key] = ""
                break
            if tokens[pos] == "{":
                pos += 1
                out[key] = parse_block()
            else:
                out[key] = tokens[pos]
                pos += 1
        return out

    result = parse_block()
    # Alguns arquivos têm uma raiz sem nome.
    if len(result) == 1 and isinstance(next(iter(result.values())), dict):
        return next(iter(result.values()))
    return result

def read_vdf(path: Path) -> dict:
    try:
        return parse_vdf(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        eprint(f"[!] Falha ao ler {path}: {e}")
        return {}

@dataclass
class SteamInstall:
    kind: str                      # "flatpak" | "native"
    root: Path                     # raiz do Steam
    libraries: list[Path]          # steamapps parents
    running: bool
    flatpak_app: str | None = None

    def label(self) -> str:
        return "Flatpak" if self.kind == "flatpak" else "nativa"

@dataclass
class AcInstall:
    steam: SteamInstall
    library: Path
    ac_root: Path
    prefix: Path
    manifest: Path | None
    proton_name: str | None
    proton_path: Path | None
    csp_version: str | None
    dwrite_override: bool | None
    protontricks_kind: str | None

    def summary(self) -> dict:
        return {
            "steam": self.steam.label(),
            "steam_root": str(self.steam.root),
            "library": str(self.library),
            "ac_root": str(self.ac_root),
            "prefix": str(self.prefix),
            "proton": self.proton_name,
            "csp": self.csp_version,
            "dwrite_override": self.dwrite_override,
            "protontricks": self.protontricks_kind,
        }

@dataclass
class DistroInfo:
    id: str
    name: str
    family: str  # arch | debian | fedora | unknown
    package_manager: str | None

    def label(self) -> str:
        if self.package_manager:
            return f"{self.name} ({self.package_manager})"
        return self.name


def detect_distro() -> DistroInfo:
    """Detecta a família da distro para adaptar pacotes de sistema."""
    data: dict[str, str] = {}
    os_release = Path("/etc/os-release")
    if os_release.exists():
        for line in os_release.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    raw_id = (data.get("ID") or "").lower()
    like = (data.get("ID_LIKE") or "").lower().split()
    name = data.get("PRETTY_NAME") or data.get("NAME") or raw_id or "Linux"

    arch_ids = {"arch", "archlinux", "cachyos", "manjaro", "endeavouros", "garuda", "artix"}
    debian_ids = {"debian", "ubuntu", "linuxmint", "pop", "elementary", "zorin", "kali"}
    fedora_ids = {"fedora", "rhel", "centos", "rocky", "almalinux", "nobara", "bazzite"}

    if raw_id in arch_ids or any(item in arch_ids or item == "arch" for item in like):
        family = "arch"
    elif raw_id in debian_ids or any(item in debian_ids or item == "debian" for item in like):
        family = "debian"
    elif raw_id in fedora_ids or any(item in fedora_ids or item in {"fedora", "rhel"} for item in like):
        family = "fedora"
    else:
        family = "unknown"

    package_manager = None
    for candidate, candidate_family in (("pacman", "arch"), ("apt-get", "debian"), ("dnf", "fedora"), ("dnf5", "fedora")):
        if family == candidate_family and shutil.which(candidate):
            package_manager = candidate
            break
    if package_manager is None:
        for candidate in ("pacman", "apt-get", "dnf", "dnf5"):
            if shutil.which(candidate):
                package_manager = candidate
                family = {"pacman": "arch", "apt-get": "debian", "dnf": "fedora", "dnf5": "fedora"}[candidate]
                break
    return DistroInfo(raw_id or "unknown", name, family, package_manager)


def distro_install_command(distro: DistroInfo, packages: list[str]) -> list[str]:
    if distro.family == "arch" and distro.package_manager == "pacman":
        return ["sudo", "pacman", "-S", "--needed", *packages]
    if distro.family == "debian" and distro.package_manager == "apt-get":
        return ["sudo", "apt-get", "install", "-y", *packages]
    if distro.family == "fedora" and distro.package_manager in {"dnf", "dnf5"}:
        return ["sudo", distro.package_manager, "install", "-y", *packages]
    return []


def _flatpak_steam_roots() -> list[Path]:
    base = Path.home() / ".var" / "app" / "com.valvesoftware.Steam"
    return [base / ".local/share/Steam", base / "data/Steam"]

def _native_steam_roots() -> list[Path]:
    h = Path.home()
    return [h / ".local/share/Steam", h / ".steam/steam", h / ".steam/root"]

def _flatpak_running() -> bool:
    return is_process_running("com.valvesoftware.Steam") or is_process_running("flatpak.*Steam")

def _steam_config_mapping(root: Path, app_id: str) -> str | None:
    cfg = root / "config" / "config.vdf"
    if not cfg.exists():
        return None
    data = read_vdf(cfg)
    # procura recursivamente por CompatToolMapping -> <app_id> -> name
    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "CompatToolMapping" and isinstance(v, dict):
                    entry = v.get(app_id)
                    if isinstance(entry, dict) and entry.get("name"):
                        return entry["name"]
                found = walk(v)
                if found:
                    return found
        return None
    return walk(data)

def _proton_versions(steam: SteamInstall) -> list[tuple[str, Path]]:
    found: dict[str, Path] = {}
    dirs = [steam.root / "compatibilitytools.d"]
    for lib in steam.libraries:
        dirs.append(lib / "steamapps" / "common")
    for base in dirs:
        if not base.is_dir():
            continue
        for child in base.iterdir():
            if not child.is_dir():
                continue
            proton = child / "proton"
            if proton.exists():
                version_file = child / "version"
                name = version_file.read_text(errors="replace").strip() if version_file.exists() else child.name
                found[name] = child
    return sorted(found.items(), key=lambda x: x[0].lower(), reverse=True)

def _csp_version(ac_root: Path) -> str | None:
    manifest = ac_root / "extension" / "config" / "data_manifest.ini"
    if not manifest.exists():
        return None
    text = manifest.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^\s*SHADERS_PATCH\s*=\s*(\S+)", text, re.M)
    return m.group(1) if m else "unknown"

def _dwrite_override(prefix: Path) -> bool | None:
    reg = prefix / "user.reg"
    if not reg.exists():
        return None
    text = reg.read_text(encoding="utf-8", errors="replace")
    return bool(re.search(r'^"dwrite"\s*=\s*"native,builtin"', text, re.M))

def _protontricks_kind() -> str | None:
    if shutil.which("protontricks"):
        return "host"
    out = subprocess.run(["flatpak", "info", "com.github.Matoking.protontricks"], capture_output=True, text=True)
    if out.returncode == 0:
        return "flatpak"
    return None

def detect_steam() -> SteamInstall | None:
    flatpak_roots = [p for p in _flatpak_steam_roots() if (p / "steamapps" / "libraryfolders.vdf").exists()]
    native_roots = [p for p in _native_steam_roots() if (p / "steamapps" / "libraryfolders.vdf").exists()]

    flatpak_running = _flatpak_running()
    native_running = is_process_running("ubuntu12_32/steam") and not flatpak_running

    if flatpak_running and flatpak_roots:
        kind, root = "flatpak", flatpak_roots[0]
    elif native_running and native_roots:
        kind, root = "native", native_roots[0]
    elif flatpak_roots:
        kind, root = "flatpak", flatpak_roots[0]
    elif native_roots:
        kind, root = "native", native_roots[0]
    else:
        return None

    libraries: list[Path] = []
    seen: set[str] = set()

    def add_lib(p: Path):
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key)
            libraries.append(p)

    add_lib(root)
    data = read_vdf(root / "steamapps" / "libraryfolders.vdf")
    folder_map = data.get("libraryfolders", data)
    if isinstance(folder_map, dict):
        for k, v in folder_map.items():
            if k.isdigit() and isinstance(v, dict) and v.get("path"):
                add_lib(Path(v["path"]))

    return SteamInstall(
        kind=kind,
        root=root,
        libraries=libraries,
        running=flatpak_running or native_running,
        flatpak_app="com.valvesoftware.Steam" if kind == "flatpak" else None,
    )

def detect_ac() -> AcInstall | None:
    steam = detect_steam()
    if not steam:
        return None

    for lib in steam.libraries:
        manifest = lib / "steamapps" / f"appmanifest_{APP_ID}.acf"
        candidate = lib / "steamapps" / "common" / AC_DIR_NAME
        if candidate.is_dir() and (candidate / "acs.exe").exists():
            ac_root = candidate
        elif manifest.exists():
            text = manifest.read_text(encoding="utf-8", errors="replace")
            m = re.search(r'"installdir"\s+"([^"]+)"', text)
            if not m:
                continue
            ac_root = lib / "steamapps" / "common" / m.group(1)
            if not (ac_root / "acs.exe").exists():
                continue
        else:
            continue

        prefix = lib / "steamapps" / "compatdata" / APP_ID / "pfx"
        proton_name = _steam_config_mapping(steam.root, APP_ID)
        proton_path = None
        for name, path in _proton_versions(steam):
            if proton_name and name == proton_name:
                proton_path = path
                break
        if proton_name is None:
            # mostra o que existe, sem escolher
            versions = _proton_versions(steam)
            proton_name = versions[0][0] if versions else None
            proton_path = versions[0][1] if versions else None

        return AcInstall(
            steam=steam,
            library=lib,
            ac_root=ac_root,
            prefix=prefix,
            manifest=manifest if manifest.exists() else None,
            proton_name=proton_name,
            proton_path=proton_path,
            csp_version=_csp_version(ac_root),
            dwrite_override=_dwrite_override(prefix),
            protontricks_kind=_protontricks_kind(),
        )
    return None

def _csp_build(ac: AcInstall) -> int | None:
    manifest = ac.ac_root / "extension" / "config" / "data_manifest.ini"
    if not manifest.exists():
        return None
    m = re.search(r"^\s*SHADERS_PATCH_BUILD\s*=\s*(\d+)", manifest.read_text(errors="replace"), re.M)
    return int(m.group(1)) if m else None

def prefix_documents(ac: AcInstall) -> Path:
    """Documents/Assetto Corsa dentro do prefixo Proton (usuário pode não ser steamuser)."""
    users = ac.prefix / "drive_c" / "users"
    if users.is_dir():
        for child in users.iterdir():
            docs = child / "Documents" / "Assetto Corsa"
            if docs.exists():
                return docs
    return users / "steamuser" / "Documents" / "Assetto Corsa"


def _safe_rel(name: str) -> PurePosixPath:
    p = PurePosixPath(name.replace("\\", "/"))
    if p.is_absolute() or any(part == ".." for part in p.parts):
        raise RuntimeError(f"Caminho inseguro no arquivo: {name}")
    return p
