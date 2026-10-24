"""Tradução simples PT/EN para a interface.

As strings fonte são em português; ``tr`` devolve inglês quando selecionado.
A preferência fica em ``~/.config/acm/settings.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

SETTINGS = Path.home() / ".config" / "acm" / "settings.json"
LANGUAGES = {"pt": "Português", "en": "English"}

_EN: dict[str, str] = {
    # shell
    "Idioma": "Language",
    "AC Manager — Assetto Corsa no Linux": "AC Manager — Assetto Corsa on Linux",
    "Assetto Corsa no Linux, sem Content Manager": "Assetto Corsa on Linux, without Content Manager",
    "Linux Status": "Linux Status",
    "Instalar mods": "Install mods",
    "Servidores": "Servers",
    "Instalados": "Installed",
    "Log": "Log",
    "Limpar log": "Clear log",
    "Protótipo — análise local, sem Content Manager.": "Prototype — local analysis, no Content Manager.",
    "Aguarde a tarefa atual terminar para trocar o idioma.": "Wait for the current task to finish before changing language.",
    # status
    "Ambiente Linux": "Linux environment",
    "verificando…": "checking…",
    "Steam": "Steam",
    "Assetto Corsa": "Assetto Corsa",
    "Proton": "Proton",
    "CSP": "CSP",
    "Distro": "Distro",
    "Fontes": "Fonts",
    "dwrite": "dwrite",
    "protontricks": "protontricks",
    "Cache CSP": "CSP cache",
    "Configurar tudo": "Set up everything",
    "Instalar/atualizar CSP": "Install/update CSP",
    "Instalar Proton-GE 9-20": "Install Proton-GE 9-20",
    "Instalar fontes": "Install fonts",
    "Instalar dependências": "Install dependencies",
    "Instalar unrar, 7z, bsdtar e cabextract usando o gerenciador da sua distro?":
        "Install unrar, 7z, bsdtar and cabextract using your distro package manager?",
    "Atualizar status": "Refresh status",
    "Abrir pasta do AC": "Open AC folder",
    "Configuração pendente. O assistente instala Proton-GE 9-20, CSP, fontes e protontricks.":
        "Configuration pending. The wizard installs Proton-GE 9-20, CSP, fonts and protontricks.",
    "Tudo pronto": "Everything ready",
    "Configuração pendente": "Configuration pending",
    "Steam não encontrada": "Steam not found",
    "nativa": "native",
    "AC não encontrado": "AC not found",
    "não encontrada": "not found",
    "não encontrado": "not found",
    "não definido": "not set",
    "não instalado": "not installed",
    "ativo": "enabled",
    "faltando": "missing",
    "desativado": "disabled",
    "ativo/padrão": "enabled/default",
    "Segoe UI OK": "Segoe UI OK",
    "{cars} carros · {tracks} pistas": "{cars} cars · {tracks} tracks",
    "content={content}, prefixo={prefix}": "content={content}, prefix={prefix}",
    "Vou instalar/verificar Proton-GE 9-20, CSP, fontes e protontricks.\n\nFeche o Steam para que o Proton do AC possa ser alterado automaticamente.\nContinuar?":
        "I will install/check Proton-GE 9-20, CSP, fonts and protontricks.\n\nClose Steam so the AC Proton can be changed automatically.\nContinue?",
    "Baixar e instalar/atualizar o CSP? O jogo deve estar fechado.":
        "Download and install/update CSP? The game must be closed.",
    "Baixar e instalar {version}? (~1,3 GB)": "Download and install {version}? (~1.3 GB)",
    "Instalar Segoe UI/Verdana e corefonts no prefixo?":
        "Install Segoe UI/Verdana and corefonts in the prefix?",
    "Feche o Assetto Corsa antes de entrar. O jogo precisa iniciar com o race.ini novo.":
        "Close Assetto Corsa before joining. The game must start with the new race.ini.",
    "CSP necessário": "CSP required",
    "Carros faltando": "Missing cars",
    "Nenhum carro do servidor está instalado.\n\nFaltando:\n{items}":
        "No server car is installed.\n\nMissing:\n{items}",
    "nenhum": "none",
    "Pista/layout faltando": "Track/layout missing",
    "Endereço: {address} (HTTP {http})": "Address: {address} (HTTP {http})",
    "Jogadores: {current}/{max}": "Players: {current}/{max}",
    "Pista: {track}": "Track: {track}",
    "País: {country}": "Country: {country}",
    "Carros permitidos: {n}": "Allowed cars: {n}",
    "Senha: {value}": "Password: {value}",
    "Mods: {value}": "Mods: {value}",
    "Mods: {value} (<code>{base}</code> / <code>{layout}</code>)":
        "Mods: {value} (<code>{base}</code> / <code>{layout}</code>)",
    "CSP build {required} (instalado {installed})":
        "CSP build {required} (installed {installed})",
    "faltam {n} carro(s)": "missing {n} car(s)",
    "Instalados: {items}": "Installed: {items}",
    "Escolher mod": "Choose mod",
    "Todos os arquivos (*)": "All files (*)",
    "Mods (*.zip *.rar *.7z *.tar *.gz *.tgz *.bz2 *.xz);;Todos os arquivos (*)":
        "Mods (*.zip *.rar *.7z *.tar *.gz *.tgz *.bz2 *.xz);;All files (*)",
    "[i] Arquivo selecionado: {path}": "[i] Selected file: {path}",
    # install tab
    "Nenhum arquivo selecionado": "No file selected",
    "Substituir existentes": "Replace existing",
    "Instalar mod selecionado": "Install selected mod",
    "Escolher arquivo…": "Choose file…",
    "Cole uma URL direta .zip/.rar/.7z para baixar e instalar…":
        "Paste a direct .zip/.rar/.7z URL to download and install…",
    "Baixar da URL": "Download from URL",
    "O arquivo é extraído em staging, o conteúdo é detectado e copiado para o AC. RAR usa unrar; 7z usa 7z/7zz ou bsdtar.":
        "The file is extracted to staging, content is detected and copied into AC. RAR uses unrar; 7z uses 7z/7zz or bsdtar.",
    "Arraste o mod aqui": "Drag the mod here",
    "Aceita .zip, .rar, .7z, .tar.gz — carro, pista, app, clima, fonte ou CSP\nou clique nesta área para escolher o arquivo":
        "Accepts .zip, .rar, .7z, .tar.gz — car, track, app, weather, font or CSP\nor click this area to choose the file",
    "Arquivo selecionado: {path}": "Selected file: {path}",
    "Instalar o mod?\n\n{name}\n\n{replace}": "Install the mod?\n\n{name}\n\n{replace}",
    "Substituindo o que já existe (com backup).": "Replacing existing content (with backup).",
    "Itens existentes serão mantidos.": "Existing items will be kept.",
    "A URL precisa começar com http:// ou https://.": "The URL must start with http:// or https://.",
    "Baixar e instalar esse mod?\n\n{url}": "Download and install this mod?\n\n{url}",
    "Acesso ao servidor": "Server access",
    "Este servidor parece exigir licença/password, entry list ou doação.\n\n{note}\n\nSe você já tem a licença, pode continuar. Caso contrário, obtenha no Discord/site do servidor.\n\nContinuar?":
        "This server appears to require a license/password, entry list or donation.\n\n{note}\n\nIf you already have the license, you can continue. Otherwise, get it from the server's Discord/site.\n\nContinue?",
    # servers
    "Filtrar por nome, pista ou país…": "Filter by name, track or country…",
    "Só sem mods": "No mods required",
    "Mostra somente servidores cuja pista e carros são oficiais (base/DLC). Não considera CSP como mod de conteúdo. Não garante acesso livre (licença/password).":
        "Show only servers whose track and cars are official (base/DLC). CSP is not counted as a content mod. It does not guarantee open access (license/password).",
    "Só mods OK": "Only mods OK",
    "Atualizar lista": "Refresh list",
    "Entrar": "Join",
    "Buscar mods": "Find mods",
    "Pingar top 50": "Ping top 50",
    "Clique em Atualizar lista para carregar o lobby.":
        "Click Refresh list to load the lobby.",
    "Carregando lista do lobby do Assetto Corsa…":
        "Loading the Assetto Corsa lobby…",
    "Falha ao carregar servidores: {msg}": "Failed to load servers: {msg}",
    "Pingando {n} servidores…": "Pinging {n} servers…",
    "Ping concluído para os servidores visíveis.":
        "Ping finished for visible servers.",
    "Nome": "Name",
    "Players": "Players",
    "Pista": "Track",
    "Mods": "Mods",
    "Ping": "Ping",
    "Senha": "Password",
    "layout": "layout",
    "pista": "track",
    "sem carro": "no car",
    "faltam {n}": "missing {n}",
    "Falta o layout {layout} da pista {base}.":
        "Missing layout {layout} for track {base}.",
    "Falta a pista {track}.": "Missing track {track}.",
    "Faltando: {items}": "Missing: {items}",
    "{n} servidores · mostrando {shown} · {source} {when}":
        "{n} servers · showing {shown} · {source} {when}",
    "cache": "cache",
    "atualizado": "updated",
    "Nenhum carro do servidor está instalado.\n\nFaltando:\n{items}":
        "No server car is installed.\n\nMissing:\n{items}",
    "Este servidor pede CSP build {required}; você tem {installed}.":
        "This server requires CSP build {required}; you have {installed}.",
    "Pista/layout faltando": "Track/layout missing",
    "Falta o layout {layout} da pista {base}:": "Missing layout {layout} for track {base}:",
    "Você não tem a pista deste servidor:": "You do not have this server's track:",
    "Escolher carro": "Choose car",
    "Carros instalados neste servidor:": "Cars installed for this server:",
    "Senha do servidor": "Server password",
    "Servidor cheio": "Server full",
    "O servidor está cheio. Tentar entrar mesmo assim?":
        "The server is full. Try to join anyway?",
    "Lançamento direto": "Direct launch",
    "Para entrar direto no servidor, o app substitui o AssettoCorsa.exe pelo acs.exe.\n\nO launcher original é preservado como AssettoCorsa_original.exe.\n\nContinuar?":
        "To join directly, the app replaces AssettoCorsa.exe with acs.exe.\n\nThe original launcher is kept as AssettoCorsa_original.exe.\n\nContinue?",
    "Entrando em {name} com {car}": "Joining {name} with {car}",
    "Servidor": "Server",
    "Endereço": "Address",
    "Jogadores": "Players",
    "País": "Country",
    "Carros permitidos": "Allowed cars",
    "sim": "yes",
    "não": "no",
    "OK": "OK",
    "layout faltando": "layout missing",
    "pista faltando": "track missing",
    "faltam {n} carro(s)": "missing {n} car(s)",
    "Faltando": "Missing",
    "Instalados": "Installed",
    # catalog / missing mods dialog
    "Buscar mods faltando": "Find missing mods",
    "Layout faltando": "Layout missing",
    "Pista faltando": "Track missing",
    "Catálogo de pistas (Breathe):": "Track catalog (Breathe):",
    "Não encontrei essa pista no catálogo.": "I did not find this track in the catalog.",
    "Catálogo não disponível agora.": "Catalog not available now.",
    "Só contam carros cujo ID de pasta em content/cars é exatamente o ID pedido pelo servidor. Variantes com outro prefixo ou sufixo (ex.: _sprint) continuam aparecendo como faltando.":
        "Only cars whose folder ID in content/cars exactly matches the server ID count. Variants with another prefix or suffix (e.g. _sprint) still appear as missing.",
    "Carros faltando ({n}):": "Missing cars ({n}):",
    "Você tem todo o conteúdo necessário para este servidor.":
        "You have all content required by this server.",
    "Links de Google Drive, MediaFire e arquivos diretos são baixados e instalados ao clicar. Sharemods (Cloudflare), Mega, Patreon, RaceDepartment/Overtake (login) e Ko-fi abrem no navegador para você baixar manualmente. O catálogo cobre pistas; carros continuam no Google.":
        "Google Drive, MediaFire and direct-file links are downloaded and installed on click. Sharemods (Cloudflare), Mega, Patreon, RaceDepartment/Overtake (login) and Ko-fi open in the browser for manual download. The catalog covers tracks; cars still use Google.",
    "Fonte do catálogo: AC Tracks Listing by Breathe":
        "Catalog source: AC Tracks Listing by Breathe",
    "Atualizar catálogo": "Refresh catalog",
    "Fechar": "Close",
    "Baixar e instalar": "Download and install",
    "Abrir link": "Open link",
    "site/loja do autor": "author site/shop",
    "sem link direto do mod": "no direct mod link",
    "sem link de download": "no download link",
    "Esse link precisa de navegador/login:\n\n{host}\n{link}":
        "This link needs a browser/login:\n\n{host}\n{link}",
    "Baixar e instalar automaticamente?\n\n{name}\nPasta: {folder}\nFonte: {host}\n\nO arquivo será baixado e instalado em {root}.":
        "Download and install automatically?\n\n{name}\nFolder: {folder}\nSource: {host}\n\nThe file will be downloaded and installed into {root}.",
    "Baixar e instalar do catálogo": "Download and install from catalog",
    "Catálogo": "Catalog",
    "Não consegui verificar o conteúdo instalado.":
        "Could not check installed content.",
    "Catálogo de pistas (Breathe):": "Track catalog (Breathe):",
    "Fonte do catálogo:": "Catalog source:",
    "sem link direto do mod": "no direct mod link",
    "conteúdo pago/login": "paid content/login",
    "login necessário": "login required",
    "conteúdo oficial/Steam": "official/Steam content",
    "Mega (baixe manualmente)": "Mega (download manually)",
    "Google Drive (pasta)": "Google Drive (folder)",
    "MediaFire (pasta)": "MediaFire (folder)",
    "link inválido": "invalid link",
    "Cloudflare": "Cloudflare",
    "AC não encontrado.": "AC not found.",
    "<p><b>CSP:</b> precisa build {required}; instalado {installed}.</p>":
        "<p><b>CSP:</b> requires build {required}; installed {installed}.</p>",
    "<p style='color:#98a0ad'>Só contam carros cujo ID de pasta em <code>content/cars</code> é exatamente o ID pedido pelo servidor. Variantes com outro prefixo ou sufixo (ex.: <code>_sprint</code>) continuam aparecendo como faltando.</p>":
        "<p style='color:#98a0ad'>Only cars whose folder ID in <code>content/cars</code> exactly matches the server ID count. Variants with another prefix or suffix (e.g. <code>_sprint</code>) still appear as missing.</p>",
    "<p><b>Carros faltando ({n}):</b></p><ul>":
        "<p><b>Missing cars ({n}):</b></p><ul>",
    "<p>Você tem todo o conteúdo necessário para este servidor.</p>":
        "<p>You have all content required by this server.</p>",
    "<p style='color:#98a0ad'>Catálogo não disponível agora.</p>":
        "<p style='color:#98a0ad'>Catalog not available now.</p>",
    "<p style='color:#98a0ad'>Não encontrei essa pista no catálogo.</p>":
        "<p style='color:#98a0ad'>I did not find this track in the catalog.</p>",
    # installed
    "Filtrar por tipo ou nome…": "Filter by type or name…",
    "Mostrar oficiais (base/DLC)": "Show official (base/DLC)",
    "Atualizar tamanhos": "Refresh sizes",
    "Excluir selecionado": "Delete selected",
    "Abra esta aba para calcular os tamanhos.":
        "Open this tab to calculate sizes.",
    "Calculando tamanhos…": "Calculating sizes…",
    "Falha ao calcular: {msg}": "Failed to calculate: {msg}",
    "Tipo": "Type",
    "Tamanho": "Size",
    "Caminho": "Path",
    "Excluir conteúdo": "Delete content",
    "Mover {n} item(ns) para a lixeira?\n\n{names}":
        "Move {n} item(s) to trash?\n\n{names}",
    "Excluir move o item para ~/.local/share/acm/trash (não apaga de vez). Conteúdo oficial (base/DLC) é protegido.":
        "Delete moves the item to ~/.local/share/acm/trash (it is not permanently erased). Official content (base/DLC) is protected.",
    "itens": "items",
    "mods de terceiros": "third-party mods",
    "{n} {label} · {size}{extra}": "{n} {label} · {size}{extra}",
    " · {n} oficiais ocultos": " · {n} official hidden",
    # content kinds
    "car": "car",
    "track": "track",
    "track-layout": "track layout",
    "weather": "weather",
    "app-python": "Python app",
    "app-lua": "Lua app",
    "font": "font",
    "ppfilter": "PP filter",
    "showroom": "showroom",
    "driver": "driver",
    # workers
    "Concluído.": "Done.",
    "Falhou (código {rc}).": "Failed (code {rc}).",
    "Baixar e instalar do catálogo": "Download and install from catalog",
    "Entrar no servidor": "Join server",
    "Instalar mod": "Install mod",
    "Baixar mod da URL": "Download mod from URL",
    "Excluir conteúdo": "Delete content",
    "Configurar tudo": "Set up everything",
    "Instalar/atualizar CSP": "Install/update CSP",
    "Instalar Proton-GE": "Install Proton-GE",
    "Instalar fontes": "Install fonts",
    "Instalar dependências": "Install dependencies",
    "Instalar unrar, 7z, bsdtar e cabextract usando o gerenciador da sua distro?":
        "Install unrar, 7z, bsdtar and cabextract using your distro package manager?",
}

_language = "pt"


def _load() -> str:
    global _language
    try:
        data = json.loads(SETTINGS.read_text(encoding="utf-8"))
        value = str(data.get("language") or "pt")
        _language = value if value in LANGUAGES else "pt"
    except Exception:
        _language = "pt"
    return _language


def current_language() -> str:
    return _language


def set_language(language: str) -> None:
    global _language
    if language not in LANGUAGES:
        language = "pt"
    _language = language
    try:
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if SETTINGS.exists():
            try:
                data = json.loads(SETTINGS.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data["language"] = language
        SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass


def tr(text: str, **values) -> str:
    result = _EN.get(text, text) if _language == "en" else text
    if values:
        try:
            result = result.format(**values)
        except Exception:
            pass
    return result


_load()
