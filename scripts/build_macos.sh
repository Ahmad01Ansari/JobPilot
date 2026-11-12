#!/usr/bin/env bash
# ==============================================================================
# JobPilot Desktop - macOS Distribution Build Script
# Builds native JobPilot.app bundle and .dmg / .zip packages on macOS.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

ARCH="$(uname -m)"
echo "=== Building JobPilot Desktop (macOS ${ARCH}) ==="

# Python interpreter selection
if [ -f ".venv/bin/python" ]; then
    PYTHON_EXEC=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_EXEC="python3"
else
    echo "ERROR: Python 3 not found. Please ensure Python 3.11 is installed."
    exit 1
fi

APP_VERSION="$("$PYTHON_EXEC" -c "import app.version; print(app.version.__version__)" 2>/dev/null || echo "0.4.5-beta")"
echo "Target version: ${APP_VERSION}"

# Ensure PyInstaller is installed
if ! "$PYTHON_EXEC" -m pip show pyinstaller > /dev/null 2>&1; then
    echo "Installing PyInstaller..."
    "$PYTHON_EXEC" -m pip install pyinstaller
fi

# Ensure brand assets (including macOS jobpilot.icns) are generated
echo "Generating multi-platform brand icons..."
"$PYTHON_EXEC" scripts/generate_icons.py

# Clean prior build artifacts
echo "Cleaning old build artifacts..."
rm -rf build/JobPilot dist/JobPilot dist/JobPilot.app dist/*.dmg dist/*.zip

# Build using JobPilot.spec
echo "Running PyInstaller build..."
"$PYTHON_EXEC" -m PyInstaller --clean --noconfirm JobPilot.spec

if [ ! -d "dist/JobPilot.app" ]; then
    echo "ERROR: PyInstaller failed to produce dist/JobPilot.app"
    exit 1
fi

echo "Successfully built dist/JobPilot.app"

# Ad-hoc code signing for local execution and Gatekeeper compliance
if command -v codesign >/dev/null 2>&1; then
    echo "Applying ad-hoc code signature to JobPilot.app..."
    codesign --force --deep --sign - "dist/JobPilot.app" || true
fi

# Package 1: Portable ZIP Archive (preserves symlinks and app bundle permissions)
echo "Creating macOS ZIP distribution archive..."
ZIP_NAME="JobPilot-${APP_VERSION}-macos-${ARCH}.zip"
(
    cd dist
    zip -r -y "${ZIP_NAME}" "JobPilot.app"
)
echo "Created dist/${ZIP_NAME}"

# Package 2: DMG Disk Image
DMG_NAME="JobPilot-${APP_VERSION}-macos-${ARCH}.dmg"
echo "Creating macOS DMG installer..."

# Prepare staging folder for DMG with Applications symlink
DMG_STAGE="dist/dmg_stage"
rm -rf "$DMG_STAGE"
mkdir -p "$DMG_STAGE"
cp -R "dist/JobPilot.app" "$DMG_STAGE/"
ln -s /Applications "$DMG_STAGE/Applications"

if command -v hdiutil >/dev/null 2>&1; then
    hdiutil create -volname "JobPilot" -srcfolder "$DMG_STAGE" -ov -format UDZO "dist/${DMG_NAME}"
    rm -rf "$DMG_STAGE"
    echo "Created dist/${DMG_NAME}"
else
    echo "Warning: hdiutil not found (non-macOS host). Skipping DMG creation."
fi

echo "=== macOS Build Complete ==="
ls -lh dist/JobPilot* || true

