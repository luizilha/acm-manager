# AC Manager — Technical Setup

This document covers the system requirements, runtime dependencies, Proton/CSP
setup, file locations, server joining, and troubleshooting. For the user-facing
overview, see [README.md](README.md).

## 1. Requirements

- Linux x86_64
- Steam, with **Assetto Corsa** installed and available in a Steam library
- Proton for Assetto Corsa (the app recommends **GE-Proton9-20**)
- AppImage FUSE support, or `APPIMAGE_EXTRACT_AND_RUN=1`
- Python is **not** required to run the AppImage; it is required only for
  source execution and building

The app does **not** redistribute Assetto Corsa, Content Manager, CSP, cars,
tracks, fonts, or mods.

## 2. Supported distributions

The setup detects `/etc/os-release` and picks the matching package manager:

| Family | Examples | Package manager |
|---|---|---|
| Arch | Arch, CachyOS, Manjaro, EndeavourOS, Garuda | `pacman` |
| Debian | Debian, Ubuntu, Mint, Pop!_OS, Kali | `apt-get` |
| Fedora | Fedora, Nobara, RHEL/Rocky/Alma derivatives | `dnf` or `dnf5` |

If the package manager is unknown, the app prints the commands and does not
execute them.

In a GUI without a TTY, privileged package commands try `pkexec` first. If
`pkexec` is unavailable, the command is printed for manual execution.

### Runtime packages

| Purpose | Arch | Debian/Ubuntu | Fedora |
|---|---|---|---|
| protontricks | `protontricks` | `protontricks` | `protontricks` |
| RAR extraction | `unrar` | `unrar` (may need non-free) | `unrar` (may need RPM Fusion) |
| 7z extraction | `p7zip` | `p7zip-full` | `p7zip-plugins` |
| bsdtar/libarchive | `libarchive` | `libarchive-tools` | `bsdtar` |
| corefonts support | `cabextract` | `cabextract` | `cabextract` |
| AppImage FUSE | `fuse2` | `libfuse2` | `fuse-libs` |

Install them from the app with **Linux Status → Install dependencies**, or:

```bash
python3 acm.py setup-deps --yes
python3 acm.py setup-deps --dry-run   # show the command only
```

`protontricks` can also be installed with `pipx install protontricks`, or as the
Flatpak `com.github.Matoking.protontricks` when Steam itself is Flatpak.

## 3. Running the AppImage

```bash
chmod +x acm-manager-1.1.1-x86_64.AppImage
./acm-manager-1.1.1-x86_64.AppImage
```

If FUSE is missing:

```bash
APPIMAGE_EXTRACT_AND_RUN=1 ./acm-manager-1.1.1-x86_64.AppImage
```

The AppImage is built on Ubuntu 22.04 by GitHub Actions for broader glibc
compatibility. Older systems may still require rebuilding on an older base.

## 4. Steam layouts

The app supports Flatpak and native Steam.

### Flatpak Steam

Typical paths:

```text
Steam root: ~/.var/app/com.valvesoftware.Steam/.local/share/Steam
AC prefix:  <library>/steamapps/compatdata/244210/pfx
AC root:    <library>/steamapps/common/assettocorsa
```

The app reads the Steam library folders from `libraryfolders.vdf` and the
current Steam user from `config/loginusers.vdf`/`config.vdf`.

### Native Steam

Typical paths:

```text
Steam root: ~/.local/share/Steam
AC prefix:  <library>/steamapps/compatdata/244210/pfx
AC root:    <library>/steamapps/common/assettocorsa
```

No path is assumed for the game itself; the app searches the Steam libraries.

## 5. Linux Status setup

The **Linux Status** tab checks:

- Steam installation and running state
- Assetto Corsa root and prefix
- Proton name/version
- CSP version
- Segoe UI/Verdana in `content/fonts/system` and `C:\windows\Fonts`
- `dwrite` override in the Proton prefix
- protontricks source (Flatpak or host)
- CSP cache flags
- detected distro

**Set up everything** performs the equivalent of:

1. install/select **GE-Proton9-20** (Steam must be closed);
2. install `protontricks`;
3. install fonts (`fonts.zip` + `corefonts`);
4. install/update **CSP**;
5. apply the `dwrite=native,builtin` override;
6. disable CSP caches (`CACHE_ACS=0`, `CACHING_LOADING2=0`);
7. install extraction dependencies for the current distro.

If the prefix does not exist yet, open Assetto Corsa once through Steam, then
run the setup again.

## 6. Proton and CSP details

### Proton-GE

GE-Proton9-20 is the tested default. It is installed into:

```text
<Steam root>/compatibilitytools.d/GE-Proton9-20
```

The selected Proton version for app `244210` is written to Steam's
`config/config.vdf`, with `config.vdf.acm-backup` created before the change.

### CSP

CSP is downloaded from `acstuff.club` and installed into the AC root:

```text
dwrite.dll
extension/
```

The app checks `extension/config/data_manifest.ini` for the installed build. It
also writes the Proton registry override and the cache settings.

### Fonts

- `fonts.zip` provides Segoe UI/Verdana into:
  - `content/fonts/system`
  - `<prefix>/drive_c/windows/Fonts`
- `corefonts` (Arial, Times, etc.) is installed through protontricks.
- `cabextract` is required by the corefonts step.

## 7. Mod installation

Supported archives: `.zip`, `.rar`, `.7z`, `.tar`, `.tar.gz`, `.tar.bz2`,
`.tar.xz` and other formats supported by `bsdtar`.

Extraction order:

1. ZIP/TAR → Python `zipfile`/`tarfile`, with path traversal checks.
2. RAR → `unrar`; names are validated before extraction.
3. 7z → `7z`/`7zz`; fallback `bsdtar`.

Recognized content:

- cars: `ui/ui_car.json`
- tracks: `ui/ui_track.json`
- layouts: `ui/<layout>/ui_track.json` and `models_<layout>.ini`
- layout packs: merged into an existing base track
- texture packs: `content/texture` merged
- weather: `content/weather/<id>`
- apps: `apps/python`, `apps/lua`
- fonts, PP filters, showrooms, driver models
- CSP: `dwrite.dll` + `extension/config/data_manifest.ini`

A failed install exits non-zero. If every item already exists, the app reports
that nothing was installed instead of printing “Done”.

Car previews come from the content itself: `content/cars/<car>/skins/<skin>/
preview.jpg` for the join car picker and the Installed tab, and
`content/tracks/<track>/ui/preview.*` or `<layout>/map.png` for tracks. The
picker also reads `ui_car.json` for name, brand, class, year and specs.

### No Hesi car CDN

`https://cdn.nohesi.gg/cars/` exposes an index of car archives (511 files,
~45 GiB). The **Install mods** tab has **No Hesi cars (CDN)**, a table with
search, size, installed status and checkboxes, so you can install a subset.
The same list is available from the CLI:

```bash
python3 acm.py nohesi-cars                      # missing cars
python3 acm.py nohesi-cars --filter mustang     # search
python3 acm.py nohesi-cars --filter mustang --install --yes
python3 acm.py nohesi-cars --all --limit 20     # includes installed
```

The index is cached for 24 h at `~/.cache/acm/nohesi-cars.json`; use
`--refresh` (CLI) or **Refresh list** to update it.

## 8. Track catalog and downloads

The app uses the public **AC Tracks Listing by Breathe** Google Sheet and caches
the parsed catalog for 7 days at:

```text
~/.cache/acm/tracks-catalog.json
```

Automatic download support:

- Google Drive public files
- MediaFire
- direct file URLs
- `acstuff.ru/s/...`

Manual/browser support:

- Sharemods (Cloudflare)
- Mega
- Patreon/Ko-fi
- RaceDepartment/Overtake (login)

Link support is checked before the click; unsupported hosts open in the
browser. The catalog is for tracks only. Car links still use web search.

## 9. Server joining

The app uses the official AC lobby:

```http
GET http://lobby.assettocorsa.net/lobby.ashx/list?guid=<SteamID64>
User-Agent: Assetto Corsa Launcher
```

It resolves combined IDs such as:

```text
ks_nordschleife-ae nordtouristbtg
```

into a base track + layout and checks official content, installed content, CSP
build, and missing cars.

Before launch it writes to `race.ini`:

```ini
[RACE]
TRACK=<base>
CONFIG_TRACK=<layout>
MODEL=<car>
SKIN=<valid local skin>

[CAR_0]
MODEL=-
SKIN=<valid local skin>

[SESSION_0]
NAME=Nothing
TYPE=1
DURATION_MINUTES=0

[REMOTE]
ACTIVE=1
SERVER_IP=...
SERVER_PORT=<tport>
SERVER_HTTP_PORT=<cport>
SERVER_NAME=...
REQUESTED_CAR=...
GUID=<SteamID64>
PASSWORD=...
__CM_EXTENDED=1
__FEATURES=<comma-separated CSP features>
```

The CSP features and `__CM_EXTENDED` come from the server's `/api/details`.
They are required by servers that check CSP feature support.

Typical `race.ini` location:

```text
<prefix>/drive_c/users/<user>/Documents/Assetto Corsa/cfg/race.ini
```

The app also reads the server description to warn about license/password,
entry-list, or donation requirements. It does not bypass access restrictions.

AssettoServer reserves entry-list slots **per car model**, so a server with free
player slots can still refuse the chosen car with
`Can't join the server: no available slots`. Before launching, the app reads
`/api/details` and checks whether the selected car has a free slot. When it does
not, it shows the models that currently have slots and offers another instance
of the same track with a free slot for that car, or another installed car that
has one.

The AC client also loads **every car model in the server's entry list**, not
only the car you drive. A missing model aborts the join with
`Can't join this server: car "…" is missing`. The app lists the missing models
and, when the server exposes `content.cars` URLs, can download and install them
directly from the server (button **Baixar carros do servidor** in the dialog, or
`python3 acm.py join ... --install-missing`).

In **Buscar mods**, missing cars that exist in the No Hesi CDN are matched
against `cdn.nohesi.gg/cars/` and install on click; the **Instalar todos os No
Hesi** button downloads all missing No Hesi cars for that server at once.

The dialog also shows **Onde baixar (indicado pelo servidor)**: links found in
the server's `/api/details` description (AssettoServer) or in the server name
(Kunos servers). Direct archives, Google Drive, MediaFire and `acstuff.ru` links
offer **baixar e instalar**; other hosts (Discord, Mega, Patreon, …) open in the
browser. When the entry list is not exposed (e.g. `ACF #2 GTE LEGENDS`), the
join dialog falls back to the lobby car list, shows the server's Discord/website
link and lets you continue anyway.

## 10. Direct launch

To make Steam start `acs.exe` directly, the first join copies:

```text
acs.exe -> AssettoCorsa.exe
```

The original launcher is preserved as `AssettoCorsa_original.exe`. Restore it
with:

```bash
python3 acm.py restore-launcher
```

To restore it **and** open the game through Steam in the normal launcher (for
example to bind controller inputs in **Options → Controls**), use **Open in
default mode** in the Linux Status tab or:

```bash
python3 acm.py launch-default
```

The next server join applies the direct launch again.

## 11. Files and state

```text
~/.cache/acm/
  servers.json             lobby cache
  tracks-catalog.json      track catalog cache
  nohesi-cars.json         No Hesi CDN car index cache (24 h)
  downloads/               downloaded archives
  fonts.zip                font archive

~/.local/share/acm/
  manifests/               installation manifests
  backups/                 replaced content backups
  trash/                   content removed by the Installed tab

~/.config/acm/settings.json  language (pt/en)
```

Manifest files record the archive SHA-256, destination, timestamp, and installed
items. Official base/DLC content is protected from deletion.

## 12. Logs and troubleshooting

Main AC log:

```text
<prefix>/drive_c/users/<user>/Documents/Assetto Corsa/logs/log.txt
```

Common failures:

| Symptom | Check |
|---|---|
| `Failed to patch Assetto Corsa` | GE-Proton9-20 selected; CSP cache flags off |
| CSP doesn't load | `dwrite=native,builtin`; CSP `dwrite.dll` exists |
| `segoeui.ttf is missing` | fonts.zip + corefonts |
| AppImage won't start | install FUSE2 or use `APPIMAGE_EXTRACT_AND_RUN=1` |
| RAR fails | install `unrar`; 7z can fall back to `bsdtar` |
| `Handshake FAILED` | server license/password/entry list, wrong ports, or missing CSP features |
| `Can't join the server: no available slots` | the car model has no free entry-list slot; pick another car or another instance (the app checks this before launching) |
| `Can't join this server: car "…" is missing` | AC requires every model in the entry list; use **Baixar carros do servidor** or `join --install-missing` |
| `Missing CSP features` | update CSP; the app writes `__FEATURES` from `/api/details` |
| Server shows `layout` missing | install the specific layout pack; base track alone is not enough |

The **Log** panel at the bottom of the app shows install, download, and setup
output.

## 13. Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python acm_gui.py
```

Core-only checks:

```bash
python3 -m py_compile acm.py acm_gui.py acm_lib/*.py gui/*.py gui/tabs/*.py
python3 acm.py --help
```

Build:

```bash
.venv/bin/pip install -r requirements-build.txt
./build_appimage.sh
```

The bundled GitHub Actions workflow runs the same checks and builds the
AppImage on Ubuntu 22.04.

## 14. Privacy and security

- The app is local-first; it does not upload local content.
- Network access is used for the AC lobby, CSP/GitHub/Google Sheet downloads,
  server details, and mod URLs.
- The SteamID64 is sent to the official AC lobby to fetch the server list and is written to the local `race.ini`; other local paths and content are not uploaded.
- Downloaded archives are validated as archives before extraction.
- Replaced content is backed up; deletions go to the local trash.
