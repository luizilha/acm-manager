"""Extração, detecção e instalação de mods."""

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
from .base import _safe_rel

from .downloads import download, browser_download, _is_assettoworld


def extract_archive(archive: Path, staging: Path) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    suffix = archive.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                if info.is_dir() or info.filename.startswith("__MACOSX/"):
                    continue
                rel = _safe_rel(info.filename)
                out = staging / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, out.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        return
    if suffix in (".tar", ".gz", ".tgz", ".bz2", ".xz"):
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                rel = _safe_rel(member.name)
                out = staging / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                src = tf.extractfile(member)
                if src:
                    with src, out.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
        return

    # Antes de entregar RAR/7z a um extrator externo, valida os nomes.
    names: list[str] | None = None
    if suffix == ".rar" and shutil.which("unrar"):
        listing = subprocess.run(["unrar", "lb", str(archive)], capture_output=True, text=True)
        if listing.returncode == 0:
            names = listing.stdout.splitlines()
    elif suffix == ".7z" and shutil.which("bsdtar"):
        listing = subprocess.run(["bsdtar", "-tf", str(archive)], capture_output=True, text=True)
        if listing.returncode == 0:
            names = listing.stdout.splitlines()
    if names:
        for name in names:
            if name.strip():
                _safe_rel(name)

    # RAR: bsdtar não cobre alguns filtros VM; prefira unrar quando existir.
    if suffix == ".rar" and shutil.which("unrar"):
        subprocess.run(["unrar", "x", "-o+", "-y", "-p-", str(archive), str(staging) + os.sep],
                       check=True)
        return

    # 7z nativo quando disponível; bsdtar como fallback.
    if suffix == ".7z":
        for seven in ("7z", "7zz"):
            if shutil.which(seven):
                subprocess.run([seven, "x", "-y", f"-o{staging}", str(archive)], check=True)
                return

    # outros formatos via bsdtar (libarchive)
    if shutil.which("bsdtar"):
        subprocess.run(["bsdtar", "-xf", str(archive), "-C", str(staging)], check=True)
        return
    raise RuntimeError(f"Formato não suportado: {archive.suffix}. Instale bsdtar (libarchive), unrar ou 7z.")

@dataclass
class ContentItem:
    kind: str
    src: Path
    dest_rel: PurePosixPath
    name: str
    merge: bool = False

def _rel_parts(path: Path, root: Path) -> tuple[str, ...]:
    try:
        return path.relative_to(root).parts
    except ValueError:
        return path.parts

def detect_items(staging: Path) -> list[ContentItem]:
    items: list[ContentItem] = []
    seen: set[str] = set()

    def add(kind: str, src: Path, dest: PurePosixPath, name: str, merge: bool = False):
        key = str(dest)
        if key in seen:
            return
        seen.add(key)
        items.append(ContentItem(kind, src, dest, name, merge))

    # CSP
    if (staging / "dwrite.dll").exists() and (staging / "extension" / "config" / "data_manifest.ini").exists():
        add("csp", staging, PurePosixPath("."), "Custom Shaders Patch")

    # Carros
    for ui in staging.rglob("ui_car.json"):
        if ui.parent.name.lower() != "ui":
            continue
        car_dir = ui.parent.parent
        parts = _rel_parts(car_dir, staging)
        if "content" in parts and "cars" in parts:
            idx = parts.index("content")
            dest = PurePosixPath(*parts[idx:])
            name = parts[idx + 2] if len(parts) > idx + 2 else car_dir.name
        else:
            dest = PurePosixPath("content", "cars", car_dir.name)
            name = car_dir.name
        add("car", car_dir, dest, name)

    # Pistas (inclui multi-layout e layout packs dentro de uma pista existente)
    for ui in staging.rglob("ui_track.json"):
        parent = ui.parent
        is_layout = parent.parent.name.lower() == "ui"
        if parent.name.lower() == "ui":
            track_dir = parent.parent
        elif is_layout:
            track_dir = parent.parent.parent
        else:
            continue
        parts = _rel_parts(track_dir, staging)
        if "content" in parts and "tracks" in parts:
            idx = parts.index("content")
            dest = PurePosixPath(*parts[idx:])
            base_name = parts[idx + 2] if len(parts) > idx + 2 else track_dir.name
            if is_layout:
                # Layout pack: mescla dentro da pista base existente
                add("track-layout", track_dir, dest, f"{base_name} (layout pack)", merge=True)
                continue
            name = base_name
        else:
            dest = PurePosixPath("content", "tracks", track_dir.name)
            name = track_dir.name
        add("track", track_dir, dest, name)

    # Texturas compartilhadas (merge dentro de content/texture)
    texture = staging / "content" / "texture"
    if texture.is_dir():
        add("texture", texture, PurePosixPath("content/texture"), "texture", merge=True)

    # Apps Python/Lua
    for kind_dir in ("python", "lua"):
        base = staging / "apps" / kind_dir
        if base.is_dir():
            for child in base.iterdir():
                if child.is_dir():
                    add(f"app-{kind_dir}", child, PurePosixPath("apps", kind_dir, child.name), child.name)

    # Clima
    weather = staging / "content" / "weather"
    if weather.is_dir():
        for child in weather.iterdir():
            if child.is_dir():
                add("weather", child, PurePosixPath("content", "weather", child.name), child.name)

    # Fontes
    fonts = staging / "content" / "fonts"
    if fonts.is_dir():
        for f in fonts.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".ttf", ".otf"):
                rel = f.relative_to(staging)
                add("font", f, PurePosixPath(*rel.parts), f.name)

    # PP filters
    pp = staging / "system" / "cfg" / "ppfilters"
    if pp.is_dir():
        for f in pp.rglob("*"):
            if f.is_file():
                rel = f.relative_to(staging)
                add("ppfilter", f, PurePosixPath(*rel.parts), f.name)

    # Showroom / driver models
    for sub, kind in (("showroom", "showroom"), ("driver", "driver")):
        base = staging / "content" / sub
        if base.is_dir():
            for child in base.iterdir():
                if child.is_dir():
                    add(kind, child, PurePosixPath("content", sub, child.name), child.name)

    # Um layout de pista já vem dentro do item pai; não instalar duas vezes.
    car_track = [it for it in items if it.kind in ("car", "track")]
    filtered: list[ContentItem] = []
    for it in items:
        nested = any(
            it is not parent and it.kind in ("car", "track")
            and str(it.dest_rel).startswith(str(parent.dest_rel) + "/")
            for parent in car_track
            if it.dest_rel != parent.dest_rel
        )
        if not nested:
            filtered.append(it)
    items = filtered

    # Estrutura genérica (content/apps/system/extension na raiz)
    if not items:
        for top in ("content", "apps", "system", "extension"):
            base = staging / top
            if base.is_dir():
                add("generic", base, PurePosixPath(top), top)

    # Se só há uma pasta no topo, desce nela e tenta de novo
    if not items:
        tops = [p for p in staging.iterdir() if not p.name.startswith(".")]
        if len(tops) == 1 and tops[0].is_dir():
            nested = detect_items(tops[0])
            # ajusta os caminhos: já são relativos à pasta interna, então mantém
            return nested

    return items

def install_archive(archive: Path, ac_root: Path, source: str = "", dry_run: bool = False,
                    force: bool = False, merge: bool = False, assume_yes: bool = True) -> int:
    """Extrai e instala um arquivo local; não depende de uma instalação AC real."""
    archive = archive.expanduser()
    if not archive.exists():
        eprint(f"[x] Arquivo não encontrado: {archive}")
        return 1
    print(f"[i] Arquivo: {archive} ({human(archive.stat().st_size)})")
    with tempfile.TemporaryDirectory(prefix="acm-staging-") as tmp:
        staging = Path(tmp)
        print("[i] Extraindo…")
        extract_archive(archive, staging)
        items = detect_items(staging)
        if not items:
            eprint("[x] Não reconheci conteúdo instalável (carro/pista/app/clima/fontes/CSP).")
            eprint("    Estrutura vista:", ", ".join(sorted(p.name for p in staging.iterdir())[:20]))
            return 1

        print("\nConteúdo detectado:")
        for it in items:
            print(f"  - {it.kind:10} {it.name:40} -> {it.dest_rel}")

        if dry_run:
            print("\n[dry-run] Nada foi copiado.")
            return 0

        if not confirm(f"Instalar {len(items)} item(ns) em {ac_root}?", assume_yes):
            print("[i] Cancelado.")
            return 0

        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_dir = BACKUPS / stamp
        manifest_items = []
        installed_count = 0

        for it in items:
            dest = ac_root / it.dest_rel
            if dest.exists() and not it.merge and not (force or merge):
                print(f"[!] Já existe: {it.dest_rel} — use --force (substituir) ou --merge (mesclar). Pulando.")
                continue
            if dest.exists() and force and not it.merge:
                backup_dir.mkdir(parents=True, exist_ok=True)
                b = backup_dir / it.dest_rel
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest), str(b))
                print(f"[i] Backup: {it.dest_rel} -> {b}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            if it.src.is_dir():
                shutil.copytree(it.src, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(it.src, dest)
            installed_count += 1
            manifest_items.append({"kind": it.kind, "name": it.name, "dest": str(it.dest_rel), "merge": it.merge})
            print(f"[✓] {it.kind}: {it.name}" + (" (merge)" if it.merge else ""))

        if installed_count == 0:
            eprint("[!] Nada foi instalado: todos os itens já existiam.")
            eprint("    Use --force (substituir) ou --merge (mesclar) se quiser atualizar.")
            return 1

        MANIFESTS.mkdir(parents=True, exist_ok=True)
        manifest = MANIFESTS / f"{stamp}-{archive.stem}.json"
        manifest.write_text(json.dumps({
            "source": source or str(archive),
            "archive": str(archive),
            "archive_sha256": sha256(archive),
            "installed_at": stamp,
            "ac_root": str(ac_root),
            "items": manifest_items,
        }, indent=2), encoding="utf-8")
        print(f"[i] Manifesto: {manifest}")
        return 0

def install_mod(source: str, dry_run: bool, force: bool, merge: bool, browser: bool, assume_yes: bool) -> int:
    ac = detect_ac()
    if not ac:
        eprint("[x] AC não encontrado.")
        return 1

    archive: Path
    if source.startswith(("http://", "https://")):
        if browser or _is_assettoworld(source):
            if not browser:
                raise RuntimeError("assettoworld exige --browser (ou baixe o arquivo manualmente).")
            archive = browser_download(source)
        else:
            CACHE.mkdir(parents=True, exist_ok=True)
            archive = download(source, CACHE / "downloads")
    else:
        archive = Path(source).expanduser()

    return install_archive(archive, ac.ac_root, source=source, dry_run=dry_run,
                           force=force, merge=merge, assume_yes=assume_yes)
