"""CSP, protontricks, fontes, Proton-GE e setup."""

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
from .base import _safe_rel, _csp_version

from .downloads import download


def _set_ini_values(path: Path, values: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for key, value in values.items():
        pattern = re.compile(rf"^;?\s*{re.escape(key)}\s*=.*$", re.M)
        if pattern.search(text):
            text = pattern.sub(f"{key}={value}", text, count=1)
        else:
            m = re.search(r"^\[OPTIMIZATIONS\]\s*$", text, re.M)
            if m:
                text = text[:m.end()] + f"\n{key}={value}" + text[m.end():]
            else:
                text += f"\n[OPTIMIZATIONS]\n{key}={value}\n"
    path.write_text(text, encoding="utf-8", errors="replace")

def disable_csp_caches(ac: AcInstall) -> None:
    """Correção conhecida no Linux/Proton: cache de memória/loading quebra o CSP."""
    default = ac.ac_root / "extension" / "config" / "general.ini"
    if not default.exists():
        return
    backup = default.with_suffix(".ini.acm-backup")
    if not backup.exists():
        shutil.copy2(default, backup)
    values = {"CACHE_ACS": "0", "CACHING_LOADING2": "0"}
    _set_ini_values(default, values)

    user = prefix_documents(ac) / "cfg" / "extension" / "general.ini"
    user.parent.mkdir(parents=True, exist_ok=True)
    if user.exists():
        ub = user.with_suffix(".ini.acm-backup")
        if not ub.exists():
            shutil.copy2(user, ub)
        _set_ini_values(user, values)
    else:
        shutil.copy2(default, user)
    print("[✓] Cache do CSP desativado (CACHE_ACS=0, CACHING_LOADING2=0).")

def install_csp_version(version: str | None, dry_run: bool, assume_yes: bool, do_fonts: bool) -> int:
    ac = detect_ac()
    if not ac:
        eprint("[x] AC não encontrado.")
        return 1

    version = version or latest_csp_version()
    print(f"[i] AC: {ac.ac_root}")
    print(f"[i] Prefixo: {ac.prefix}")
    print(f"[i] CSP atual: {ac.csp_version or 'não instalado'}")
    print(f"[i] CSP alvo: {version}")

    if is_process_running("acs.exe") or is_process_running("AssettoCorsa.exe"):
        eprint("[!] O AC/CM parece estar rodando. Feche o jogo antes de instalar o CSP.")
        return 1

    if dry_run:
        print("[dry-run] Baixaria o CSP, extrairia dwrite.dll + extension/ e ajustaria o user.reg.")
        return 0

    if not confirm(f"Instalar CSP {version} em {ac.ac_root}?", assume_yes):
        print("[i] Cancelado.")
        return 0

    CACHE.mkdir(parents=True, exist_ok=True)
    zip_path = CACHE / f"lights-patch-v{version}.zip"
    if not zip_path.exists():
        print("[i] Baixando CSP…")
        zip_path = download(CSP_URL.format(version=version), CACHE)
    else:
        print(f"[i] Usando cache: {zip_path}")

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        if "dwrite.dll" not in names or not any(n.startswith("extension/") for n in names):
            eprint("[x] Zip do CSP não contém dwrite.dll/extension — abortando.")
            return 1

        print(f"[i] Extraindo {len(names)} arquivos para o AC…")
        for i, info in enumerate(zf.infolist(), 1):
            if info.is_dir() or info.filename.startswith("__MACOSX/"):
                continue
            rel = _safe_rel(info.filename)
            out = ac.ac_root / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            if i % 100 == 0:
                eprint(f"\r  {i}/{len(names)}", end="")
        eprint(f"\r  {len(names)}/{len(names)}")

    disable_csp_caches(ac)
    ensure_dwrite_override(ac.prefix)
    installed = _csp_version(ac.ac_root)
    print(f"[✓] CSP instalado. Versão no manifesto: {installed}")

    if do_fonts:
        install_fonts(assume_yes)
    return 0

def latest_csp_version() -> str:
    try:
        req = urllib.request.Request(CSP_PAGE, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode("utf-8", "replace")
        versions = re.findall(r"\b(0\.\d+\.\d+)\b", text)
        if versions:
            return max(set(versions), key=lambda v: tuple(int(x) for x in v.split(".")))
    except Exception as e:
        eprint(f"[!] Não consegui consultar a versão do CSP: {e}")
    return "0.2.11"

def ensure_dwrite_override(prefix: Path) -> bool:
    reg = prefix / "user.reg"
    if not reg.exists():
        eprint(f"[!] user.reg não encontrado em {prefix}")
        return False

    lines = reg.read_text(encoding="utf-8", errors="surrogateescape").splitlines(keepends=True)
    header = "[Software\\\\Wine\\\\DllOverrides]"
    start = next((i for i, l in enumerate(lines) if l.startswith(header)), None)
    if start is None:
        eprint("[!] Seção DllOverrides não encontrada; não vou inventar o registro.")
        return False

    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("[")), len(lines))
    key_re = re.compile(r'^"dwrite"\s*=')
    for i in range(start + 1, end):
        if key_re.match(lines[i]):
            if lines[i].strip() != '"dwrite"="native,builtin"':
                backup = reg.with_name(reg.name + ".acm-backup")
                if not backup.exists():
                    shutil.copy2(reg, backup)
                lines[i] = '"dwrite"="native,builtin"\n'
                reg.write_text("".join(lines), encoding="utf-8", errors="surrogateescape")
                print("[✓] Override dwrite atualizado.")
            else:
                print("[i] Override dwrite já está correto.")
            return True

    backup = reg.with_name(reg.name + ".acm-backup")
    if not backup.exists():
        shutil.copy2(reg, backup)
    insert_at = start + 1
    if insert_at < len(lines) and lines[insert_at].startswith("#time="):
        insert_at += 1
    lines.insert(insert_at, '"dwrite"="native,builtin"\n')
    reg.write_text("".join(lines), encoding="utf-8", errors="surrogateescape")
    print("[✓] Override dwrite adicionado (backup em user.reg.acm-backup).")
    return True

def _run_package_command(command: list[str]) -> int:
    """Executa sudo no terminal ou usa pkexec quando a GUI não tem TTY."""
    command = list(command)
    if command and command[0] == "sudo" and hasattr(os, "geteuid") and os.geteuid() != 0:
        if shutil.which("pkexec"):
            command = ["pkexec", *command[1:]]
        elif not sys.stdin or not sys.stdin.isatty():
            eprint("[!] Sem terminal e sem pkexec; execute o comando manualmente:")
            eprint("    " + " ".join(command))
            return 1
    return subprocess.run(command).returncode


def _missing_system_tools() -> list[str]:
    missing = []
    if not shutil.which("unrar") and not shutil.which("unar"):
        missing.append("unrar")
    if not shutil.which("7z") and not shutil.which("7zz"):
        missing.append("7z")
    if not shutil.which("bsdtar"):
        missing.append("bsdtar")
    if not shutil.which("cabextract"):
        missing.append("cabextract")
    return missing


def _dependency_packages(distro: DistroInfo, tools: list[str]) -> list[str]:
    mapping = {
        "arch": {
            "unrar": "unrar", "7z": "p7zip",
            "bsdtar": "libarchive", "cabextract": "cabextract",
        },
        "debian": {
            "unrar": "unrar", "7z": "p7zip-full",
            "bsdtar": "libarchive-tools", "cabextract": "cabextract",
        },
        "fedora": {
            "unrar": "unrar", "7z": "p7zip-plugins",
            "bsdtar": "bsdtar", "cabextract": "cabextract",
        },
    }.get(distro.family, {})
    return [mapping[tool] for tool in tools if tool in mapping]


def install_system_deps(assume_yes: bool, dry_run: bool = False) -> int:
    """Instala ferramentas externas de extração/fontes para a distro atual."""
    distro = detect_distro()
    print(f"[i] Distro: {distro.label()}")
    missing = _missing_system_tools()
    if not missing:
        print("[✓] Dependências de sistema já instaladas (unrar/7z/bsdtar/cabextract).")
        return 0
    packages = _dependency_packages(distro, missing)
    if not packages:
        eprint(f"[!] Não sei instalar {', '.join(missing)} em {distro.name}.")
        eprint("    Instale manualmente: unrar, 7z (p7zip/7zip), bsdtar (libarchive) e cabextract.")
        return 1
    command = distro_install_command(distro, packages)
    print(f"[i] Faltando: {', '.join(missing)}")
    print("    " + " ".join(command))
    if dry_run:
        return 0
    if not confirm(f"Instalar {', '.join(packages)} com {distro.package_manager}?", assume_yes):
        return 0
    rc = _run_package_command(command)
    if rc != 0:
        eprint(f"[x] O gerenciador retornou {rc}. Instale manualmente: {', '.join(packages)}")
        return rc
    print("[✓] Dependências de sistema instaladas.")
    return 0


def install_protontricks(assume_yes: bool) -> int:
    ac = detect_ac()
    if not ac:
        eprint("[x] AC não encontrado.")
        return 1

    if ac.protontricks_kind:
        ensure_protontricks_access(ac)
        print(f"[i] protontricks já disponível ({ac.protontricks_kind}); acesso à biblioteca ajustado.")
        return 0

    if ac.steam.kind == "flatpak":
        print("[i] Steam é Flatpak: instalando protontricks via Flatpak (flathub).")
        if not confirm("Instalar com.github.Matoking.protontricks?", assume_yes):
            return 0
        subprocess.run(["flatpak", "remote-add", "--user", "--if-not-exists", "flathub",
                        "https://flathub.org/repo/flathub.flatpakrepo"], check=False)
        rc = subprocess.run(["flatpak", "install", "--user", "-y", "flathub",
                             "com.github.Matoking.protontricks"]).returncode
        if rc != 0:
            eprint("[x] Falha ao instalar o protontricks Flatpak.")
            return rc
        print("[✓] protontricks instalado.")
        return 0

    distro = detect_distro()
    print(f"[i] Steam nativa + {distro.label()}")
    command = distro_install_command(distro, ["protontricks"])
    if command:
        print("    " + " ".join(command))
        if confirm(f"Instalar protontricks com {distro.package_manager}?", assume_yes):
            rc = _run_package_command(command)
            if rc == 0:
                print("[✓] protontricks instalado.")
                return 0
            eprint(f"[!] {distro.package_manager} retornou {rc}; tentando pipx.")

    if shutil.which("pipx"):
        print("    pipx install protontricks")
        if confirm("Instalar protontricks com pipx?", assume_yes):
            rc = subprocess.run(["pipx", "install", "protontricks"]).returncode
            if rc == 0:
                print("[✓] protontricks instalado via pipx.")
                return 0
    eprint("[!] protontricks não instalado.")
    eprint("    Instale com o gerenciador da sua distro ou: pipx install protontricks")
    return 0

def ensure_protontricks_access(ac: AcInstall) -> None:
    """O protontricks Flatpak precisa de acesso à biblioteca fora do sandbox."""
    if ac.protontricks_kind != "flatpak":
        return
    paths = {str(ac.library), str(ac.steam.root)}
    for path in paths:
        subprocess.run(
            ["flatpak", "override", "--user", f"--filesystem={path}",
             "com.github.Matoking.protontricks"],
            check=False,
        )

def protontricks_cmd(ac: AcInstall) -> list[str] | None:
    if ac.protontricks_kind == "flatpak":
        return ["flatpak", "run", "com.github.Matoking.protontricks", APP_ID]
    if ac.protontricks_kind == "host":
        return ["protontricks", APP_ID]
    return None

def install_fonts(assume_yes: bool) -> int:
    ac = detect_ac()
    if not ac:
        eprint("[x] AC não encontrado.")
        return 1

    # 1) Segoe UI / Verdana do pacote usado pelo setup do AC no Linux.
    CACHE.mkdir(parents=True, exist_ok=True)
    fonts_zip = CACHE / "fonts.zip"
    try:
        if not fonts_zip.exists():
            print("[i] Baixando fonts.zip (Segoe UI/Verdana)…")
            fonts_zip = download(FONTS_URL, CACHE)
        content_fonts = ac.ac_root / "content" / "fonts" / "system"
        win_fonts = ac.prefix / "drive_c" / "windows" / "Fonts"
        content_fonts.mkdir(parents=True, exist_ok=True)
        win_fonts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="acm-fonts-") as tmp:
            with zipfile.ZipFile(fonts_zip) as zf:
                for info in zf.infolist():
                    if not info.filename.lower().endswith((".ttf", ".otf")):
                        continue
                    name = Path(info.filename).name
                    data = zf.read(info)
                    (Path(tmp) / name).write_bytes(data)
                    (content_fonts / name).write_bytes(data)
                    (win_fonts / name).write_bytes(data)
                    print(f"  + {name}")
        print(f"[✓] Fontes instaladas em {content_fonts} e {win_fonts}")
    except Exception as e:
        eprint(f"[!] Falha ao instalar fonts.zip: {e}")

    # 2) corefonts via protontricks (Arial/Times/etc.)
    cmd = protontricks_cmd(ac)
    if not cmd:
        distro = detect_distro()
        command = distro_install_command(distro, ["protontricks"])
        if command:
            print("[i] protontricks ausente; corefonts pulado (Segoe/Verdana já instaladas).")
            print("    Para instalar: " + " ".join(command))
        else:
            print("[i] protontricks ausente; corefonts pulado (Segoe/Verdana já instaladas).")
        return 0
    if not shutil.which("cabextract"):
        distro = detect_distro()
        command = distro_install_command(distro, ["cabextract"])
        if command:
            print("[i] cabextract ausente; o corefonts pode falhar.")
            print("    Para instalar: " + " ".join(command))
    ensure_protontricks_access(ac)
    print("[i] Instalando corefonts no prefixo (pode demorar)…")
    env = os.environ.copy()
    if ac.steam.kind == "flatpak" and ac.protontricks_kind == "host":
        env["STEAM_DIR"] = str(ac.steam.root)
    rc = subprocess.run(cmd + ["corefonts"], env=env).returncode
    if rc == 0:
        print("[✓] corefonts instalado.")
    else:
        eprint(f"[x] protontricks retornou {rc} (as fontes do CSP já estão no lugar).")
    return 0

def install_proton_ge(tag: str, assume_yes: bool, force: bool = False) -> int:
    steam = detect_steam()
    if not steam:
        eprint("[x] Steam não encontrada.")
        return 1
    dest = steam.root / "compatibilitytools.d"
    target = dest / tag
    if target.exists() and not force:
        print(f"[i] {tag} já instalado em {target}")
        return 0
    if not confirm(f"Baixar e instalar {tag}?", assume_yes):
        return 0

    req = urllib.request.Request(
        GE_API.format(tag=tag),
        headers={"User-Agent": UA, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        release = json.loads(r.read().decode("utf-8"))
    assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
    tar_name, sha_name = f"{tag}.tar.gz", f"{tag}.sha512sum"
    if tar_name not in assets:
        eprint(f"[x] Release {tag} não tem {tar_name}.")
        return 1

    CACHE.mkdir(parents=True, exist_ok=True)
    tar_path = CACHE / tar_name
    if not tar_path.exists():
        print(f"[i] Baixando {tar_name} (~1.3 GB)…")
        tar_path = download(assets[tar_name], CACHE)
    if sha_name in assets:
        sha_path = CACHE / sha_name
        if not sha_path.exists():
            sha_path = download(assets[sha_name], CACHE)
        expected = sha_path.read_text().split()[0].lower()
        actual = sha512_file(tar_path)
        if expected != actual:
            eprint(f"[x] SHA-512 não confere para {tar_name}.")
            return 1
        print("[✓] SHA-512 verificado.")

    dest.mkdir(parents=True, exist_ok=True)
    print(f"[i] Extraindo {tar_name}…")
    with tarfile.open(tar_path) as tf:
        try:
            tf.extractall(dest, filter="data")
        except TypeError:
            tf.extractall(dest)
    print(f"[✓] {tag} instalado em {dest}")
    return 0

def _vdf_block_end(text: str, brace_start: int) -> int:
    depth = 0
    i = brace_start
    in_quote = False
    while i < len(text):
        c = text[i]
        if c == '"' and (i == 0 or text[i - 1] != "\\"):
            in_quote = not in_quote
        elif not in_quote:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return len(text)

def set_proton_compat(tag: str, assume_yes: bool, force: bool = False) -> int:
    steam = detect_steam()
    if not steam:
        eprint("[x] Steam não encontrada.")
        return 1
    if steam.running and not force:
        print("[!] Feche o Steam para eu editar o config.vdf com segurança.")
        print("    Alternativa: Steam → AC → Propriedades → Compatibilidade →", tag)
        return 1
    cfg = steam.root / "config" / "config.vdf"
    if not cfg.exists():
        eprint(f"[x] config.vdf não encontrado em {cfg}")
        return 1
    text = cfg.read_text(encoding="utf-8", errors="replace")
    if not confirm(f"Definir {tag} como Proton do AC ({APP_ID})?", assume_yes):
        return 0

    m = re.search(r'"CompatToolMapping"\s*\{', text)
    if not m:
        eprint("[x] CompatToolMapping não encontrado no config.vdf.")
        return 1
    start = text.index("{", m.start())
    end = _vdf_block_end(text, start)
    block = text[start:end]

    m2 = re.search(r'"244210"\s*\{', block)
    if m2:
        s2 = block.index("{", m2.start())
        e2 = _vdf_block_end(block, s2)
        sub = block[s2:e2]
        current = re.search(r'"name"\s*"([^"]*)"', sub)
        if current and current.group(1) == tag:
            print(f"[i] AC já está configurado para {tag}.")
            return 0
        if current:
            sub = re.sub(r'("name"\s*")[^"]*(")', rf"\1{tag}\2", sub, count=1)
        else:
            sub = sub[:1] + f'\n\t\t\t\t\t\t"name"\t\t"{tag}"\n\t\t\t\t\t\t"config"\t\t""\n\t\t\t\t\t\t"priority"\t\t"250"\n' + sub[1:]
        block = block[:s2] + sub + block[e2:]
    else:
        insert = (f'\n\t\t\t\t\t"244210"\n\t\t\t\t\t{{\n'
                  f'\t\t\t\t\t\t"name"\t\t"{tag}"\n'
                  f'\t\t\t\t\t\t"config"\t\t""\n'
                  f'\t\t\t\t\t\t"priority"\t\t"250"\n'
                  f'\t\t\t\t\t}}\n')
        block = block[:-1] + insert + block[-1:]

    backup = cfg.with_name(cfg.name + ".acm-backup")
    if not backup.exists():
        shutil.copy2(cfg, backup)
    cfg.write_text(text[:start] + block + text[end:], encoding="utf-8")
    print(f"[✓] {tag} definido para o AC. Reinicie o Steam.")
    return 0

def setup_all(proton_tag: str, assume_yes: bool, skip_proton: bool, skip_csp: bool) -> int:
    ac = detect_ac()
    if not ac:
        eprint("[x] AC não encontrado.")
        return 1
    print("[i] Plano de setup:")
    print(f"  Steam: {ac.steam.label()} — {ac.steam.root}")
    print(f"  AC: {ac.ac_root}")
    print(f"  Prefixo: {ac.prefix}")
    print(f"  Proton alvo: {proton_tag}")
    print(f"  CSP: instalar/atualizar")
    print(f"  Fontes: fonts.zip + corefonts")
    if not assume_yes and not confirm("Aplicar esse plano?", assume_yes):
        return 0

    distro = detect_distro()
    print(f"[i] Distro detectada: {distro.label()}")
    install_system_deps(assume_yes)

    if not skip_proton:
        install_proton_ge(proton_tag, assume_yes)
        set_proton_compat(proton_tag, assume_yes)

    if not ac.prefix.exists():
        print("\n[!] O prefixo Proton ainda não existe.")
        print("    1. Abra o AC uma vez pela Steam com o Proton selecionado.")
        print("    2. Rode `python3 acm.py setup` de novo.")
        return 0

    install_protontricks(assume_yes)
    install_fonts(assume_yes)
    if not skip_csp:
        install_csp_version(None, False, True, False)
    print("\n[✓] Setup concluído. Abra o AC pela Steam e escolha o carro/pista.")
    return 0
