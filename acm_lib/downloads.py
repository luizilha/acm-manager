"""Download HTTP e resolução de URLs."""

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


def _filename_from_headers(headers, url: str) -> str:
    cd = headers.get("Content-Disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8''|\")?([^\";]+)", cd, re.I)
    if m:
        return urllib.parse.unquote(m.group(1))
    path = urllib.parse.urlparse(url).path
    return Path(path).name or "download.bin"

def _is_assettoworld(url: str) -> bool:
    return "assettoworld.com" in urllib.parse.urlparse(url).netloc.lower()

def _is_html_error(path: Path) -> bool:
    try:
        head = path.read_bytes()[:2048].lower()
    except Exception:
        return False
    return b"<html" in head or b"security check" in head

def resolve_url(url: str) -> str:
    """Resolve links suportados pelo CM (subconjunto)."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")

    if host == "acstuff.ru" and parsed.path.startswith("/s/"):
        json_url = url + ("&" if "?" in url else "?") + "json"
        with urllib.request.urlopen(urllib.request.Request(json_url, headers={"User-Agent": UA})) as r:
            data = json.loads(r.read().decode("utf-8"))
        request = data.get("request")
        if not request:
            raise RuntimeError(f"acstuff.ru não retornou 'request': {data}")
        return request

    if _is_assettoworld(url):
        raise RuntimeError(
            "assettoworld.com exige JavaScript/verificação. Use --browser para abrir a página "
            "e aguardar o download em ~/Downloads, ou passe o arquivo já baixado."
        )

    return url

def download(url: str, dest_dir: Path) -> Path:
    url = resolve_url(url)
    dest_dir.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            final_url = r.geturl()
            name = Path(_filename_from_headers(r.headers, final_url)).name or "download.bin"
            if not Path(name).suffix:
                name += ".zip"
            dest = dest_dir / name
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            last = 0.0
            tmp = dest.with_suffix(dest.suffix + ".part")
            with tmp.open("wb") as f:
                while True:
                    chunk = r.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    now = time.time()
                    if now - last > 0.2:
                        last = now
                        pct = f" {done * 100 / total:5.1f}%" if total else ""
                        eprint(f"\r  {human(done)}{pct}  {name}", end="")
            eprint()
            tmp.replace(dest)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} ao baixar {url}") from e

    if _is_html_error(dest):
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"O servidor retornou HTML (proteção/erro) em vez de arquivo: {url}")
    return dest

def browser_download(url: str, timeout: int = 900) -> Path:
    """Abre a página no navegador e espera um novo arquivo em ~/Downloads."""
    downloads = Path.home() / "Downloads"
    downloads.mkdir(exist_ok=True)
    before = {p.resolve() for p in downloads.iterdir() if p.is_file()}
    print(f"[i] Abrindo no navegador: {url}")
    subprocess.run(["xdg-open", url], check=False)
    print(f"[i] Aguardando um novo arquivo em {downloads} (Ctrl-C para cancelar)…")
    deadline = time.time() + timeout
    while time.time() < deadline:
        for p in downloads.iterdir():
            if p.is_file() and p.suffix.lower() in ARCHIVE_EXTS and p.resolve() not in before:
                s1 = p.stat().st_size
                time.sleep(2)
                if p.exists() and p.stat().st_size == s1 and s1 > 1024:
                    print(f"[✓] Download detectado: {p} ({human(s1)})")
                    return p
        time.sleep(2)
    raise TimeoutError("Nenhum arquivo de mod apareceu em ~/Downloads.")
