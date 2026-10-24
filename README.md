# AC Manager — Assetto Corsa no Linux

Gerenciador desktop para Assetto Corsa no Linux, **sem Content Manager**: status do ambiente, Proton/CSP, instalação de mods, catálogo de pistas, servidores e inventário de conteúdo.

> Projeto independente, não afiliado à Kunos Simulazioni, ao Content Manager ou às comunidades de servidores.

## Setup em máquina nova

O script já embute todas as correções descobertas na prática:

- Steam **nativa ou Flatpak** (detecção automática)
- **Proton-GE 9-20** (CSP não funciona com Proton 11 em alguns setups)
- CSP com `CACHE_ACS=0` e `CACHING_LOADING2=0` (correção do pattern scan no Linux)
- `dwrite=native,builtin` no prefixo
- **fonts.zip** (Segoe UI/Verdana) em `content/fonts/system` e `C:\windows\Fonts`
- `protontricks` (Flatpak ou host) + `corefonts`
- manifesto e backups de tudo que altera

Fluxo recomendado:

```bash
cd acm-manager

# 1. Fecha o Steam. Instala o Proton-GE 9-20 e define ele para o AC.
python3 acm.py setup --yes

# Se o prefixo ainda não existir, o setup avisa:
#   2. Abra o AC uma vez pela Steam (cria o prefixo)
#   3. python3 acm.py setup --yes
```

Ou passo a passo:

```bash
python3 acm.py detect

python3 acm.py install-proton-ge --version GE-Proton9-20 --yes
python3 acm.py set-proton --name GE-Proton9-20 --yes   # Steam fechado

python3 acm.py install-protontricks --yes
python3 acm.py install-fonts --yes
python3 acm.py install-csp --yes
```

`set-proton` edita o `config.vdf` com backup (`config.vdf.acm-backup`). Se o Steam estiver aberto, ele mostra o caminho na UI em vez de arriscar sobrescrever.

## Interface gráfica (AppImage)

Arquivo pronto:

```bash
chmod +x acm-manager-1.0-x86_64.AppImage
./acm-manager-1.0-x86_64.AppImage
```

A janela tem quatro abas:

- **Linux Status** — Steam, AC, Proton, CSP, fontes, `dwrite`, protontricks e cache;
  botões **Configurar tudo**, CSP, Proton-GE, fontes, atualizar status e abrir pasta;
- **Instalar mods** — drag-and-drop/arquivo local e URL direta;
- **Servidores** — lobby, filtros (inclui **Só sem mods**), ping, detalhes, catálogo e **Entrar**;
- **Instalados** — inventário, tamanhos e remoção para a lixeira.

O **log** e a barra de progresso ficam no shell da janela e são compartilhados
pelas ações das quatro abas. No canto superior direito, o seletor **Português/English**
troca o idioma da interface na hora; a preferência fica em `~/.config/acm/settings.json`.

Se o AppImage não abrir por FUSE ausente:

```bash
APPIMAGE_EXTRACT_AND_RUN=1 ./acm-manager-1.0-x86_64.AppImage
```

Para reconstruir (na máquina de build):

```bash
./build_appimage.sh
```

O AppImage é gerado em `acm-manager-1.0-x86_64.AppImage` (~83 MB, Qt embutido). Ele foi compilado no CachyOS/Arch; em distros com glibc bem mais antiga pode ser necessário reconstruir em um container/VM com glibc mais antiga.

### Rodar direto do código

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python acm_gui.py
```

O núcleo também funciona pela CLI:

```bash
.venv/bin/python acm.py --help
```

Para gerar o AppImage: `./build_appimage.sh` (usa `requirements-build.txt`).

## Compatibilidade e drag-and-drop

A interface é **Qt 6 (PySide6)**, não GTK:

- roda em **GNOME, KDE, Xfce, niri** e outros, em Wayland ou X11;
- o AppImage embute Qt (`libqwayland.so` e `libqxcb.so`);
- por padrão usa **Wayland nativo** quando `WAYLAND_DISPLAY` existe; senão X11/xcb;
- em GNOME/KDE ela não usa GTK/libadwaita, então o visual é o tema escuro próprio
  (Fusion), não o tema do sistema. Funciona, mas não parece um app GTK nativo.

Se o app não abrir ou o drag-and-drop falhar, force a outra plataforma:

```bash
QT_QPA_PLATFORM=wayland ./acm-manager-1.0-x86_64.AppImage
QT_QPA_PLATFORM=xcb     ./acm-manager-1.0-x86_64.AppImage
```

O drag-and-drop agora aceita o **arquivo em qualquer lugar da janela**, não só na
área pontilhada. A área também é **clicável** (abre o seletor de arquivo), como
fallback para compositores que bloqueiam DnD.

## Uso do dia a dia

```bash
# 1. Ver o que foi detectado
python3 acm.py detect

# 2. Instalar um mod local
python3 acm.py install-mod /caminho/para/mod.zip --dry-run
python3 acm.py install-mod /caminho/para/mod.zip --yes

# 3. Mod por URL direta
python3 acm.py install-mod 'https://exemplo.com/mod.zip' --yes

# 4. Sites com JavaScript/verificação (ex.: assettoworld)
python3 acm.py install-mod 'https://www.assettoworld.com/car/bmw-m4-gt3-5' --browser
```

Opções importantes do `install-mod`:

- `--dry-run`: mostra o que seria instalado, sem copiar.
- `--force`: substitui o destino, movendo o antigo para `~/.local/share/acm/backups/`.
- `--merge`: mescla com o que já existe.
- `--browser`: abre a página no navegador e espera um novo `.zip/.rar/.7z` em `~/Downloads`.
- `--yes`: não pergunta.

## Conteúdo instalado (tamanho e exclusão)

Aba **Instalados**:

- por padrão mostra **somente mods de terceiros**; base + DLC ficam ocultos;
- usa a lista oficial do CSP (`extension/config/data_standard_content.ini`) para
  reconhecer carros/pistas base e DLC;
- checkbox **Mostrar oficiais (base/DLC)** para ver tudo;
- mostra o **tamanho de cada item** e o total (na sua instalação: 3 mods de
  terceiros · 895,5 MiB · 372 oficiais ocultos);
- filtro por tipo/nome;
- seleção múltipla + **Excluir selecionado**;
- exclusão **move para `~/.local/share/acm/trash`**, não apaga de vez;
- conteúdo oficial (base/DLC) é protegido.

CLI:

```bash
python3 acm.py installed
python3 acm.py installed --filter interlagos
python3 acm.py installed --json
python3 acm.py remove "/caminho/do/content/cars/meu_mod" --yes
```

O detector agora entende **pistas multi-layout** (`ui/gp/ui_track.json`,
`ui/norm/ui_track.json`, `models_gp.ini`, `models_norm.ini`). Era por isso que o
RAR `vhe_interlagos` não era reconhecido; ele já foi instalado e aparece na lista
com ~590 MiB.

## Arquitetura

O núcleo não depende da interface. A GUI conversa com o núcleo pela fachada
`acm.py`, e cada aba tem seu próprio arquivo, widgets, workers e ações.

```text
acm.py                  fachada compatível + entrada da CLI
acm_lib/
  base.py               constantes, utilidades, VDF e detecção Steam/AC/Proton
  downloads.py          HTTP, resolução de URL e download
  catalog.py            catálogo de pistas e download por host
  content.py            inventário, checagem de mods e lixeira
  servers.py            lobby, ping, race.ini e entrada
  installer.py          extração, detecção e instalação de mods
  setup.py              CSP, protontricks, fontes e Proton-GE
  cli.py                parser e comandos

acm_gui.py              entrada da GUI
gui/
  app.py                QApplication, self-test e screenshot
  main_window.py        shell: header, abas, log e tarefas
  theme.py              tema Qt
  constants.py          nome/versão
  common.py             cards, drag-and-drop e helpers
  workers.py            Worker/EmittingStream genéricos
  tabs/
    linux_status.py     aba Linux Status
    install_mods.py     aba Instalar mods
    servers.py          aba Servidores
    catalog_dialog.py   diálogo de mods faltando + catálogo
    installed.py        aba Instalados
```

As quatro abas são independentes entre si; `MainWindow` só monta o shell e
oferece `run_task`, `append_log` e o controle de tarefa em segundo plano.

## Baixar mods

Na aba **Servidores**, o botão **Buscar mods** consulta o catálogo público
[AC Tracks Listing by Breathe](https://docs.google.com/spreadsheets/d/1UcjQGfjGOAzGPf2VqraRgZsKHmZiTqWJmrnMHHh323A/edit)
(cache local de 7 dias, sem enviar dados seus).

- **Google Drive, MediaFire e URLs diretas**: o link **Baixar e instalar**
  baixa o arquivo e instala o conteúdo automaticamente.
- **Sharemods, Mega, Patreon, RaceDepartment/Overtake e Ko-fi**: abrem no
  navegador porque exigem Cloudflare, login ou conteúdo pago.
- O catálogo é de **pistas**. Carros continuam como links de busca no Google.
- Links antigos podem estar mortos; o app avisa se o download falhar.
- Para RAR, o app usa `unrar`; para 7z, tenta `7z`/`7zz` e depois `bsdtar`.
  ZIP/TAR são extraídos pelo próprio Python.

Na aba **Instalar mods**, há o campo **Baixar da URL**: cole um link direto
(`.zip/.rar/.7z`) e o app baixa e instala. Links `acstuff.ru/s/...` também são
resolvidos.

O catálogo também pode ser usado pela CLI:

```bash
python3 acm.py catalog --search nordschleife --link
python3 acm.py catalog --search abbeville --download
python3 acm.py catalog --search adelaide_1988 --download --install --yes
```

## Servidores online

A aba **Servidores** lista o lobby oficial do Assetto Corsa sem Content Manager.

O que foi descoberto/capturado:

```http
GET http://lobby.assettocorsa.net/lobby.ashx/list?guid=<SteamID64>
User-Agent: Assetto Corsa Launcher
Accept: application/json
```

- O `guid` é o **SteamID64**, lido de `config/loginusers.vdf` (ou `config.vdf`).
- A resposta é um JSON grande (~1,6 MB, ~9.000 servidores) com nome, IP, porta UDP,
  porta HTTP, players, pista, senha, país e carros.
- O lobby tem rate limit: se martelar, responde
  `ERROR,SLOW DOWN,TOO MANY CONCURRENT REQUESTS`. O app usa cache de 60s em
  `~/.cache/acm/servers.json` e cai para o cache quando isso acontece.
- **Ping**: UDP para a porta do jogo enviando `0xC8 0x00`. A resposta tem 3 bytes:
  `[200, http_port_lo, http_port_hi]`; os dois últimos são a **porta HTTP** do
  servidor, e o tempo de resposta é o ping. Players vêm da lista do lobby.

Na GUI:

- aba **Servidores** carrega o cache ao abrir (ou busca se estiver velho);
- **Atualizar lista** força uma nova consulta;
- **Filtrar** procura em todos os ~9.000 servidores e mostra os 500 melhores;
- **Pingar top 50** mede o ping dos servidores visíveis;
- duplo clique mostra detalhes (IP, porta, pista, país, senha, carros).

CLI:

```bash
python3 acm.py servers --limit 20
python3 acm.py servers --filter "nordschleife" --limit 10
python3 acm.py servers --limit 5 --ping
python3 acm.py servers --limit 50 --json
```

### Entrar e checar mods

A coluna **Mods** compara os `cars` e o `track` do servidor com o que existe em
`content/cars` e `content/tracks`:

| Valor | Significado |
|---|---|
| `OK` | você tem a pista e todos os carros |
| `faltam N` | a pista existe, mas faltam N carros (os instalados ainda aparecem para escolher) |
| `pista` | a pista base do servidor não está instalada |
| `layout` | a pista base existe, mas falta o layout (ex.: N24H 2023) |
| `CSP N` | o servidor pede um CSP mais novo |
| `sem carro` | nenhum carro do servidor está instalado |

Use **Só mods OK** para listar apenas servidores em que você tem tudo. Use **Só sem mods** para listar servidores cuja pista/layout e carros são oficiais (base/DLC). Isso não garante acesso livre: ao entrar, o app consulta `/api/details`, grava `__FEATURES`/`__CM_EXTENDED` do CSP e avisa se a descrição indicar licença/password, entry list ou doação.
O duplo clique mostra a lista de carros faltando.

**Entrar**:

1. exige o AC fechado;
2. escolhe um carro instalado do servidor (e a senha, se houver);
3. grava `[RACE]`, `[CAR_0]`, `[SESSION_0]` e `[REMOTE]` no `race.ini`, incluindo build do CSP e `__FEATURES`/`__CM_EXTENDED` anunciados pelo servidor;
4. na primeira vez, substitui `AssettoCorsa.exe` pelo `acs.exe` e guarda o
   launcher original como `AssettoCorsa_original.exe`;
5. pede ao Steam para iniciar o app 244210 e o jogo conecta.

Para voltar ao launcher oficial:

```bash
python3 acm.py restore-launcher
```

O botão **Entrar** não baixa mods sozinho; use **Buscar mods** para instalar a
pista que falta. Ele bloqueia quando a pista/CSP/carro não estão disponíveis.

CLI de entrada (para teste ou script):

```bash
python3 acm.py join --ip 195.114.14.84 --port 9103 --car mclaren_mp412c_gt3 --dry-run
python3 acm.py join --ip 195.114.14.84 --port 9103 --car mclaren_mp412c_gt3 --no-launch
python3 acm.py join --ip 195.114.14.84 --port 9103 --car mclaren_mp412c_gt3 --yes
```

## Correções Linux que o setup aplica

| Sintoma | Causa | Correção automática |
|---|---|---|
| `Failed to patch Assetto Corsa` / `Can't find CarLabel::render` | CSP + Proton 11/cache no Linux | `GE-Proton9-20` + `CACHE_ACS=0` + `CACHING_LOADING2=0` |
| CSP não carrega | `dwrite.dll` não é usado | override `"dwrite"="native,builtin"` no `user.reg` |
| `Font C:\windows\Fonts\segoeui.ttf is missing` | `corefonts` não tem Segoe UI | `fonts.zip` → `content/fonts/system` e `C:\windows\Fonts` |
| Fontes gerais faltando | prefixo sem corefonts | `protontricks 244210 corefonts` |
| protontricks não vê o AC (Flatpak) | sandbox sem acesso à library | `flatpak override --filesystem=<library>` |

O `setup` é idempotente: se algo já estiver instalado, ele detecta e pula.

## Como o Content Manager baixa mods (referência)

O CM usa `FlexibleLoader` + `ContentScanner` + installators:

1. A URL vem de arrastar-e-soltar, do botão "Install" ou de um link
   `acmanager://install?url=...`.
2. `FlexibleLoader` escolhe um loader pelo domínio:
   Direct, AcStuff Shared (`acstuff.ru/s/...`), Google Drive, Yandex Disk,
   MediaFire, Dropbox, OneDrive, AdFly, Mega e encurtadores.
3. O arquivo é baixado para o diretório temporário
   (`Settings.Content.TemporaryFilesLocation`, por padrão `%TEMP%`), com
   progresso e retomada quando suportado.
4. O tipo é detectado e extraído por `ZipContentInstallator`,
   `SharpCompressContentInstallator` (RAR/7z), `SevenZipContentInstallator`
   ou `DirectoryContentInstallator` (pasta).
5. `ContentScanner` monta a árvore e detecta o conteúdo:
   `ui/ui_car.json` (carro), `ui/ui_track.json` (pista),
   `apps/python`/`apps/lua`, `content/weather`, `content/fonts`,
   `system/cfg/ppfilters`, `dwrite.dll` + `extension/` (CSP).
6. `ContentEntryBase` copia para o destino com opções de atualização
   (manter previews/UI/skins). O download em si não fica guardado por padrão.

Este protótipo implementa o subconjunto mais útil: URL direta, `acstuff.ru/s/`,
download para cache, extração segura, detecção e cópia para os destinos.
Para assettoworld (JS/verificação), use `--browser` ou passe o arquivo baixado.

## Destinos

| Conteúdo | Destino |
|---|---|
| Carro | `content/cars/<id>/` |
| Pista | `content/tracks/<id>/` |
| App Python | `apps/python/<id>/` |
| App Lua | `apps/lua/<id>/` |
| Clima | `content/weather/<id>/` |
| Fonte | `content/fonts/` |
| PP filter | `system/cfg/ppfilters/` |
| Showroom | `content/showroom/<id>/` |
| Modelo de piloto | `content/driver/<id>/` |
| CSP | raiz do AC (`dwrite.dll` + `extension/`) |

## Segurança / backups

- `user.reg` é salvo como `user.reg.acm-backup` antes de qualquer edição.
- Conteúdo substituído com `--force` vai para `~/.local/share/acm/backups/<data>/`.
- Manifestos em `~/.local/share/acm/manifests/`.
- O script recusa rodar como root.
- Feche o AC antes de instalar CSP/mods.

## Limitações conhecidas

- O catálogo baixa automaticamente Google Drive, MediaFire e URLs diretas.
  Sharemods, Mega, Patreon, RaceDepartment/Overtake e Ko-fi exigem navegador/login.
- O catálogo cobre pistas; carros continuam via busca no Google.
- Links antigos do catálogo podem estar mortos.
- Servidores podem exigir licença/password, entry list ou CSP features; o app avisa e
  preenche o que o servidor anuncia, mas não contorna licenças.
- RAR depende de `unrar`; 7z usa `7z`/`7zz` ou `bsdtar`.
- O filtro **Só sem mods** considera apenas conteúdo oficial, não acesso livre.

## Licença

MIT — veja [LICENSE](LICENSE). Avisos de componentes de terceiros estão em
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Assetto Corsa é marca da Kunos Simulazioni. Este projeto não distribui o jogo,
CSP, Content Manager, carros, pistas, fontes ou mods de terceiros.
