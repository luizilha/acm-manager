#!/usr/bin/env bash
# Gera o AppImage do AC Manager (PySide6 + PyInstaller).
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

APP=acm-manager
VERSION=1.1
ARCH=x86_64
OUT="${APP}-${VERSION}-${ARCH}.AppImage"

echo "[1/5] venv + dependências"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install --no-cache-dir -q -r requirements-build.txt

echo "[2/5] PyInstaller"
rm -rf build dist
.venv/bin/pyinstaller --noconfirm --clean --windowed --name "$APP" \
    --icon acm.png --paths . acm_gui.py

echo "[3/5] AppDir"
rm -rf AppDir
mkdir -p "AppDir/usr/bin" "AppDir/usr/share/applications" \
         "AppDir/usr/share/icons/hicolor/256x256/apps"
cp -a "dist/$APP/." "AppDir/usr/bin/"
cp acm.png "AppDir/$APP.png"
cp acm.png "AppDir/usr/share/icons/hicolor/256x256/apps/$APP.png"

cat > "AppDir/$APP.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=AC Manager
Comment=Assetto Corsa no Linux sem Content Manager
Exec=$APP
Icon=$APP
Categories=Game;Utility;
Terminal=false
EOF
cp "AppDir/$APP.desktop" "AppDir/usr/share/applications/$APP.desktop"

cat > AppDir/AppRun <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
if [ -z "${QT_QPA_PLATFORM:-}" ]; then
    if [ -n "${WAYLAND_DISPLAY:-}" ]; then
        export QT_QPA_PLATFORM=wayland
    else
        export QT_QPA_PLATFORM=xcb
    fi
fi
exec "$HERE/usr/bin/acm-manager" "$@"
EOF
chmod +x AppDir/AppRun

echo "[4/5] appimagetool"
mkdir -p tools
if [ ! -x tools/appimagetool ]; then
    curl -L --fail -o tools/appimagetool \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x tools/appimagetool
fi

if ! command -v mksquashfs >/dev/null 2>&1; then
    echo "[!] mksquashfs não encontrado. Instale squashfs-tools (ex.: sudo pacman -S squashfs-tools)."
    echo "    O appimagetool pode falhar sem ele."
fi

echo "[5/5] Empacotando"
ARCH="$ARCH" APPIMAGE_EXTRACT_AND_RUN=1 \
    ./tools/appimagetool AppDir "$OUT"

ls -lh "$OUT"
echo "Pronto: $(pwd)/$OUT"
