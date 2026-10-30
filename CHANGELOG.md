# Changelog

## 1.1 — 2026-10-30

### Added

- **Open in default mode** button in **Linux Status** and `launch-default` CLI:
  restores the original `AssettoCorsa.exe` and opens AC through Steam, so the
  controller can be configured in **Options → Controls**. The next server join
  re-applies the direct launch.
- **Per-car slot check** before joining: AssettoServer reserves entry-list slots
  per car model, so the app now reads `/api/details`, shows the models with free
  slots and offers another instance of the same track with a free slot, or
  another installed car that has one.
- **Full entry-list content check**: AC loads every car model in the server's
  entry list, not only the car you drive. The app blocks before launching,
  explains the missing models and can install them from the server's
  `content.cars` URLs (`Baixar carros do servidor`, `join --install-missing`).
- **No Hesi car CDN**: new **No Hesi cars (CDN)** dialog in **Install mods**
  (search, size, installed status, selection, install selected) and the
  `nohesi-cars` CLI command. The 511-file index (~45 GiB) is cached for 24 h at
  `~/.cache/acm/nohesi-cars.json`.
- **Find mods**: No Hesi cars install directly from `cdn.nohesi.gg` on click,
  and **Instalar todos os No Hesi** installs all missing No Hesi cars for that
  server at once.
- **Where to download**: the missing-mods dialog and the join dialog now show
  links advertised by the server, extracted from the `/api/details`
  `description` and from the server name (Discord, websites, Google Drive,
  MediaFire, direct files). Supported links offer **download and install**;
  Discord/Mega/Patreon/etc. open in the browser.
- **Server Google search** fallback for servers that do not publish a download
  page, plus cleaner per-car search terms (underscores become spaces).
- **ACF/Kunos servers without `/api/details`**: the join dialog falls back to
  the lobby car list, shows the server's link (e.g. its Discord) and offers
  **Tentar mesmo assim**.

### Changed

- The “server full” warning now uses live `clients`/`maxclients` from
  `/api/details` instead of only the cached lobby data.
- `join --dry-run` now reports entry-list content and the selected car's slot
  availability.
- `--install-missing` was added to `join`, and `launch-default` and
  `nohesi-cars` are new CLI commands.

### Fixed

- Missing `QApplication` import in the Servers tab.
- Checkbox indicators in dark-theme tables are now visible.

## 1.0 — 2026-10-24

- Initial public release: Linux Status checks and setup wizard, mod installation,
  track catalog, AC lobby browser, server joining with `race.ini`/CSP features,
  installed-content management, PT/EN UI, and the AppImage build workflow.
