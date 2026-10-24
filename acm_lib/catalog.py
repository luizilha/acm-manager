"""Catálogo de pistas (Google Sheets), links e download por host."""

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

from .downloads import download, _filename_from_headers


class UnsupportedDownload(RuntimeError):
    """O catálogo tem um link que não dá para baixar sem navegador/login."""

def _catalog_norm(value: object) -> str:
    return " ".join(str(value or "").lower().split())

def _catalog_tokens(value: str) -> set[str]:
    raw = re.findall(r"[a-z0-9]+", _catalog_norm(value))
    out: set[str] = set()
    for token in raw:
        if "24h" in token or "24hours" in token:
            out.add("24h")
        elif token not in {"extra", "layout", "layouts", "track", "pista"}:
            out.add(token)
    return out

def _xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    out = []
    for si in root.iter(f"{ns}si"):
        out.append("".join(t.text or "" for t in si.iter(f"{ns}t")))
    return out

def _xlsx_sheet_files(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rel_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rel_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rels = {r.get("Id"): r.get("Target") for r in rel_root}
    out = []
    for sh in wb.iter(f"{ns}sheet"):
        target = rels.get(sh.get(f"{rel_ns}id"))
        if not target:
            continue
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        out.append((sh.get("name") or "", target))
    return out

def _xlsx_cell_value(cell: ET.Element, shared: list[str]) -> tuple[str, str]:
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    v = cell.find(f"{ns}v")
    isel = cell.find(f"{ns}is")
    formula = cell.find(f"{ns}f")
    value = ""
    if cell.get("t") == "s" and v is not None and (v.text or "").isdigit():
        idx = int(v.text)
        if 0 <= idx < len(shared):
            value = shared[idx]
    elif cell.get("t") == "inlineStr" and isel is not None:
        value = "".join(t.text or "" for t in isel.iter(f"{ns}t"))
    elif v is not None:
        value = v.text or ""
    return value, (formula.text or "") if formula is not None else ""

def _cell_urls(value: str, formula: str) -> list[str]:
    urls = re.findall(r'HYPERLINK\(\s*"([^"]+)"', formula, re.I)
    if not urls:
        urls = re.findall(r"HYPERLINK\(\s*'([^']+)'", formula, re.I)
    if not urls and value.startswith(("http://", "https://")):
        urls = [value.strip()]
    return [html_lib.unescape(url).strip() for url in urls]

def parse_track_catalog(data: bytes) -> list[dict]:
    """Lê o .xlsx exportado do Google Sheets e extrai as pistas com link."""
    zf = zipfile.ZipFile(io.BytesIO(data))
    shared = _xlsx_shared_strings(zf)
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    entries: list[dict] = []
    for sheet_name, sheet_file in _xlsx_sheet_files(zf):
        if sheet_name.lower() in {"readme", "various links"}:
            continue
        try:
            root = ET.fromstring(zf.read(sheet_file))
        except Exception:
            continue
        rows = list(root.iter(f"{ns}row"))
        header_row = None
        columns: dict[str, int] = {}
        for row in rows[:12]:
            found: dict[str, int] = {}
            for cell in row.iter(f"{ns}c"):
                value, _ = _xlsx_cell_value(cell, shared)
                low = value.lower().strip()
                if not low:
                    continue
                col = re.match(r"([A-Z]+)", cell.get("r") or "")
                if not col:
                    continue
                idx = 0
                for ch in col.group(1):
                    idx = idx * 26 + ord(ch) - 64
                if "folder" in low and "name" in low:
                    found["folder"] = idx
                elif low in {"track name", "name"}:
                    found["name"] = idx
                elif "author" in low:
                    found["author"] = idx
                elif low in {"ver", "version", "versão"}:
                    found["version"] = idx
            if "folder" in found:
                header_row = row
                columns = found
                break
        if header_row is None or "folder" not in columns:
            continue
        start = False
        for row in rows:
            if row is header_row:
                start = True
                continue
            if not start:
                continue
            cells: dict[int, tuple[str, str]] = {}
            for cell in row.iter(f"{ns}c"):
                ref = cell.get("r") or ""
                m = re.match(r"([A-Z]+)", ref)
                if not m:
                    continue
                idx = 0
                for ch in m.group(1):
                    idx = idx * 26 + ord(ch) - 64
                cells[idx] = _xlsx_cell_value(cell, shared)
            folder_val, _ = cells.get(columns["folder"], ("", ""))
            folder = " ".join(folder_val.split())
            if not folder or folder in {"-", "?"} or folder.startswith(("http://", "https://")):
                continue
            name_val, _ = cells.get(columns.get("name", 1), ("", ""))
            author_val, _ = cells.get(columns.get("author", 0), ("", ""))
            version_val, _ = cells.get(columns.get("version", 0), ("", ""))
            b_value, b_formula = cells.get(2, ("", ""))
            urls = _cell_urls(b_value, b_formula)
            entry = {
                "name": " ".join((name_val or folder).split()),
                "folder": folder,
                "author": " ".join(author_val.split()),
                "version": " ".join(version_val.split()),
                "link": urls[0] if urls else "",
                "sheet": sheet_name,
            }
            entries.append(entry)

    # Para entradas sem link (ex.: N24H do seeker), tenta o site/loja do mesmo autor.
    def author_link_score(link: str) -> int:
        low = link.lower()
        if "/shop" in low:
            return 2
        if "patreon.com" in low or "ko-fi.com" in low:
            return 1
        return 0

    by_author: dict[str, str] = {}
    for entry in entries:
        author = _catalog_norm(entry.get("author"))
        link = str(entry.get("link") or "")
        if not author or not link:
            continue
        if author not in by_author or author_link_score(link) > author_link_score(by_author[author]):
            by_author[author] = link
    for entry in entries:
        if entry.get("link"):
            continue
        author = _catalog_norm(entry.get("author"))
        if author in by_author:
            entry["author_link"] = by_author[author]
    return entries

def fetch_track_catalog(force: bool = False, ttl: int = CATALOG_TTL) -> list[dict]:
    """Baixa/carrega o catálogo local com cache de 7 dias."""
    cached: list[dict] | None = None
    fetched_at = 0.0
    if CATALOG_CACHE.exists():
        try:
            data = json.loads(CATALOG_CACHE.read_text(encoding="utf-8"))
            cached = data.get("entries") or []
            fetched_at = float(data.get("fetched_at") or 0)
        except Exception:
            cached = None
    if cached and not force and time.time() - fetched_at < ttl:
        return cached
    try:
        req = urllib.request.Request(CATALOG_URL, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read(32 * 1024 * 1024)
        entries = parse_track_catalog(raw)
        if not entries:
            raise RuntimeError("catálogo vazio")
        CATALOG_CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CATALOG_CACHE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"fetched_at": time.time(), "entries": entries}, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(CATALOG_CACHE)
        print(f"[i] Catálogo de pistas atualizado: {len(entries)} entradas.")
        return entries
    except Exception as e:
        if cached:
            eprint(f"[!] Não atualizei o catálogo ({e}); usando cache de {len(cached)} entradas.")
            return cached
        raise

def catalog_layout_score(layout: str, folder: str) -> int:
    lt = _catalog_tokens(layout)
    ft = _catalog_tokens(folder)
    if not lt:
        return 0
    score = len(lt & ft) * 3
    if "24h" in lt and "24h" in ft:
        score += 4
    return score

def catalog_lookup(track: str, base: str = "", layout: str = "",
                    entries: list[dict] | None = None, limit: int = 8) -> list[dict]:
    entries = entries if entries is not None else fetch_track_catalog()
    track_n = _catalog_norm(track)
    exact = [e for e in entries if _catalog_norm(e.get("folder")) == track_n]
    if exact:
        return exact[:limit]

    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(entry: dict, score: int, why: str):
        key = (_catalog_norm(entry.get("folder")), str(entry.get("link") or ""))
        if key in seen:
            return
        seen.add(key)
        item = dict(entry)
        item["_score"] = score
        item["_match"] = why
        out.append(item)

    base_n = _catalog_norm(base)
    layout_n = _catalog_norm(layout)
    if base_n:
        base_entries: list[dict] = []
        layout_entries: list[dict] = []
        for entry in entries:
            folder_n = _catalog_norm(entry.get("folder"))
            if folder_n == base_n:
                base_entries.append(entry)
            elif folder_n.startswith(base_n + " (") and layout_n:
                score = catalog_layout_score(layout_n, folder_n)
                if score > 0:
                    item = dict(entry)
                    item["_score"] = score
                    item["_match"] = "layout"
                    layout_entries.append(item)
        if layout_n and layout_entries:
            for entry in layout_entries:
                add(entry, int(entry.get("_score") or 0), "layout")
        else:
            for entry in base_entries:
                add(entry, 10, "base")
    if not out and track_n:
        # IDs compostos sem base/layout explícitos: tenta achar a base pelo prefixo.
        for entry in entries:
            folder_n = _catalog_norm(entry.get("folder"))
            if folder_n and (track_n.startswith(folder_n + "-") or track_n == folder_n):
                add(entry, 1, "prefix")
    out.sort(key=lambda e: (-int(e.get("_score") or 0), not bool(e.get("link")),
                            _catalog_norm(e.get("folder"))))
    return out[:limit]

def catalog_url_support(url: str) -> tuple[bool, str]:
    """Retorna (automático, nome do host) para um link do catálogo."""
    if not url.startswith(("http://", "https://")):
        return False, "link inválido"
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    if host in {"drive.google.com", "docs.google.com", "drive.usercontent.google.com"}:
        if "/file/d/" in parsed.path or parsed.path in {"/open", "/uc"}:
            return True, "Google Drive"
        return False, "Google Drive (pasta)"
    if host.endswith("mediafire.com"):
        return (True, "MediaFire") if "/file/" in path else (False, "MediaFire (pasta)")
    if host.endswith("sharemods.com"):
        return False, "Sharemods (Cloudflare)"
    if host == "acstuff.ru" and path.startswith("/s/"):
        return True, "acstuff.ru"
    if host.endswith("mega.nz"):
        return False, "Mega (baixe manualmente)"
    if host.endswith("patreon.com") or host.endswith("ko-fi.com"):
        return False, "conteúdo pago/login"
    if host.endswith("racedepartment.com") or host.endswith("overtake.gg"):
        return False, "login necessário"
    if host.endswith("steampowered.com") or host.endswith("steamcommunity.com"):
        return False, "conteúdo oficial/Steam"
    if Path(path).suffix.lower() in ARCHIVE_EXTS:
        return True, host
    return False, host

def _sniff_archive_ext(path: Path) -> str:
    try:
        with path.open("rb") as f:
            head = f.read(512)
    except OSError:
        return ""
    if head.startswith(b"PK\x03\x04"):
        return ".zip"
    if head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return ".7z"
    if head.startswith(b"Rar!"):
        return ".rar"
    if head.startswith(b"\x1f\x8b"):
        return ".tar.gz"
    if head.startswith(b"BZh"):
        return ".tar.bz2"
    if head.startswith(b"\xfd7zXZ\x00"):
        return ".tar.xz"
    if len(head) > 262 and head[257:262] == b"ustar":
        return ".tar"
    return ""

def _ensure_archive_suffix(path: Path) -> Path:
    if path.suffix.lower() in ARCHIVE_EXTS:
        return path
    ext = _sniff_archive_ext(path)
    if not ext:
        raise RuntimeError(f"O download não é um arquivo de mod reconhecido: {path.name}")
    target = path.with_name(path.name + ext)
    path.replace(target)
    return target

def _save_stream(r, dest_dir: Path, fallback_name: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = Path(_filename_from_headers(r.headers, r.geturl() or "")).name or fallback_name
    if not name or name in {".", ".."}:
        name = fallback_name
    dest = dest_dir / name
    total = int(r.headers.get("Content-Length") or 0)
    done = 0
    last = 0.0
    tmp = dest.with_suffix(dest.suffix + ".part")
    with tmp.open("wb") as f:
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            now = time.time()
            if now - last > 0.3:
                last = now
                pct = f" {done * 100 / total:5.1f}%" if total else ""
                eprint(f"\r  {human(done)}{pct}  {name}", end="")
    eprint()
    if done < 1024:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Download vazio/curto: {name}")
    tmp.replace(dest)
    return dest

def _google_drive_id(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    m = re.search(r"/file/d/([^/]+)", parsed.path)
    if m:
        return m.group(1)
    qs = urllib.parse.parse_qs(parsed.query)
    return (qs.get("id") or [""])[0]

def download_google_drive(url: str, dest_dir: Path) -> Path:
    file_id = _google_drive_id(url)
    if not file_id:
        raise UnsupportedDownload("Não encontrei o ID do arquivo do Google Drive.")
    base = "https://drive.usercontent.google.com/download"
    params = {"id": file_id, "export": "download", "confirm": "t"}
    req = urllib.request.Request(base + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        ctype = (r.headers.get("Content-Type") or "").lower()
        data = r.read(512 * 1024) if "html" in ctype else b""
        if "html" in ctype:
            page = data.decode("utf-8", "replace")
            m = re.search(r'name="uuid"\s+value="([^"]+)"', page)
            if not m:
                raise RuntimeError("O Google Drive não liberou o download (link privado ou pasta).")
            params["uuid"] = m.group(1)
            req = urllib.request.Request(base + "?" + urllib.parse.urlencode(params),
                                         headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=60) as r2:
                return _ensure_archive_suffix(_save_stream(r2, dest_dir, f"gdrive-{file_id}.zip"))
        # Content-Type binário: o corpo já começou a ser lido; junta o restante.
        dest_dir.mkdir(parents=True, exist_ok=True)
        name = Path(_filename_from_headers(r.headers, r.geturl() or "")).name or f"gdrive-{file_id}.zip"
        dest = dest_dir / name
        tmp = dest.with_suffix(dest.suffix + ".part")
        total = int(r.headers.get("Content-Length") or 0)
        done = len(data)
        with tmp.open("wb") as f:
            f.write(data)
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    eprint(f"\r  {human(done)} {done * 100 / total:5.1f}%  {name}", end="")
        eprint()
        if done < 1024:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("Download vazio do Google Drive.")
        tmp.replace(dest)
        return _ensure_archive_suffix(dest)

def download_mediafire(url: str, dest_dir: Path) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        page = r.read(8 * 1024 * 1024).decode("utf-8", "replace")
    candidates = re.findall(r'href=["\'](https?://download[^"\']+)["\']', page, re.I)
    if not candidates:
        candidates = re.findall(r'(https?://[^"\']+\.(?:zip|rar|7z|tar\.gz))', page, re.I)
    if not candidates:
        raise UnsupportedDownload("O MediaFire não retornou um link direto (proteção/JS).")
    direct = html_lib.unescape(candidates[0])
    path = download(direct, dest_dir)
    return _ensure_archive_suffix(path)

def download_catalog_entry(entry: dict, dest_dir: Path | None = None) -> Path:
    url = str(entry.get("link") or "")
    auto, label = catalog_url_support(url)
    if not auto:
        raise UnsupportedDownload(f"{label}: download automático não disponível.")
    dest_dir = dest_dir or (CACHE / "downloads")
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    print(f"[i] Baixando do catálogo ({label}): {entry.get('name') or entry.get('folder')}")
    if host in {"drive.google.com", "docs.google.com", "drive.usercontent.google.com"}:
        archive = download_google_drive(url, dest_dir)
    elif host.endswith("mediafire.com"):
        archive = download_mediafire(url, dest_dir)
    else:
        archive = download(url, dest_dir)
    return _ensure_archive_suffix(archive)
