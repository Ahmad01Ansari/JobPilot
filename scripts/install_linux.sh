#!/usr/bin/env bash
# ==============================================================================
# JobPilot Desktop - Linux Launcher & Icon Installer
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Installing JobPilot Desktop Launcher & Icon ==="

APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"

mkdir -p "$APP_DIR"
mkdir -p "$ICON_DIR"

# Copy brand icon
cp "$PROJECT_ROOT/app/ui/assets/brand/jobpilot_256.png" "$ICON_DIR/jobpilot.png"

# Generate .desktop launcher with absolute paths
DESKTOP_FILE="$APP_DIR/jobpilot.desktop"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=JobPilot
GenericName=Autonomous Job Search & Application Bot
Comment=AI-powered desktop recruitment management application
Exec=$PROJECT_ROOT/.venv/bin/python $PROJECT_ROOT/run_desktop.py
Icon=$ICON_DIR/jobpilot.png
Terminal=false
Categories=Utility;Office;Development;
StartupWMClass=JobPilot
EOF

chmod +x "$DESKTOP_FILE"
echo "JobPilot desktop entry installed at: $DESKTOP_FILE"

# Refresh desktop database if utility exists
if command -v update-desktop-database > /dev/null 2>&1; then
    update-desktop-database "$APP_DIR" || true
fi

echo "=== Installation complete. JobPilot is now available in your application launcher. ==="
