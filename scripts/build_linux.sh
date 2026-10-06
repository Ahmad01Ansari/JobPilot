#!/usr/bin/env bash
# ==============================================================================
# JobPilot Desktop - Linux Distribution Build Script (v0.1.0-beta.1)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=== Building JobPilot Desktop (Linux x86_64) ==="

VENV_PYTHON=".venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Virtual environment not found at .venv. Please initialize .venv first."
    exit 1
fi

# Ensure pyinstaller is installed
if ! "$VENV_PYTHON" -m pip show pyinstaller > /dev/null 2>&1; then
    echo "Installing PyInstaller in virtualenv..."
    "$VENV_PYTHON" -m pip install pyinstaller
fi

# Clean prior build artifacts while keeping cached tools
echo "Cleaning old build artifacts..."
rm -rf build/JobPilot build/deb_pkg dist/AppDir
rm -f dist/*.AppImage dist/*.deb dist/*.tar.gz

# Build using JobPilot.spec
echo "Running PyInstaller build..."
"$VENV_PYTHON" -m PyInstaller --clean --noconfirm JobPilot.spec

if [ -d "dist/JobPilot" ]; then
    # --------------------------------------------------------------------------
    # 1. AppImage Generation
    # --------------------------------------------------------------------------
    echo "Creating AppDir for AppImage generation..."
    APPDIR="dist/AppDir"
    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin"
    mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

    # Copy PyInstaller distribution binaries into AppDir
    cp -r dist/JobPilot/* "$APPDIR/usr/bin/"

    # Copy icons
    cp "$PROJECT_ROOT/app/ui/assets/brand/jobpilot_256.png" "$APPDIR/jobpilot.png"
    cp "$PROJECT_ROOT/app/ui/assets/brand/jobpilot_256.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/jobpilot.png"

    # Create .desktop file in AppDir
    cat > "$APPDIR/jobpilot.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=JobPilot
GenericName=Autonomous Job Search & Application Bot
Comment=AI-powered desktop recruitment management application
Exec=JobPilot
Icon=jobpilot
Terminal=false
Categories=Utility;Office;Development;
StartupWMClass=JobPilot
EOF

    # Create AppRun entrypoint
    cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/JobPilot" "$@"
EOF
    chmod +x "$APPDIR/AppRun"

    # Build AppImage using appimagetool if available or download it
    mkdir -p build
    APPIMAGETOOL="build/appimagetool-x86_64.AppImage"
    APPIMAGE_RUNTIME="build/runtime-x86_64"
    APPIMAGE_OUT="dist/JobPilot-0.1.0-beta.1-x86_64.AppImage"

    if [ ! -f "$APPIMAGETOOL" ]; then
        echo "Fetching appimagetool..."
        curl -fsSL -o "$APPIMAGETOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage" || true
        chmod +x "$APPIMAGETOOL" 2>/dev/null || true
    fi

    if [ ! -f "$APPIMAGE_RUNTIME" ]; then
        echo "Fetching AppImage runtime..."
        curl -fsSL -o "$APPIMAGE_RUNTIME" "https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64" || true
    fi

    if [ -x "$APPIMAGETOOL" ]; then
        echo "Generating AppImage: $APPIMAGE_OUT"
        RUNTIME_FLAG=""
        if [ -f "$APPIMAGE_RUNTIME" ]; then
            RUNTIME_FLAG="--runtime-file $APPIMAGE_RUNTIME"
        fi
        ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run $RUNTIME_FLAG "$APPDIR" "$APPIMAGE_OUT" || {
            echo "Warning: Direct AppImage packaging encountered an issue; falling back."
        }
        if [ -f "$APPIMAGE_OUT" ]; then
            cp "$APPIMAGE_OUT" "dist/JobPilot-x86_64.AppImage" 2>/dev/null || true
        fi
    fi

    # --------------------------------------------------------------------------
    # 2. Debian (.deb) Package Generation
    # --------------------------------------------------------------------------
    DEB_OUT="dist/jobpilot_0.1.0-beta.1_amd64.deb"
    if command -v dpkg-deb >/dev/null 2>&1; then
        echo "Creating Debian (.deb) package structure..."
        DEB_DIR="build/deb_pkg"
        rm -rf "$DEB_DIR"
        mkdir -p "$DEB_DIR/DEBIAN"
        mkdir -p "$DEB_DIR/opt/jobpilot"
        mkdir -p "$DEB_DIR/usr/bin"
        mkdir -p "$DEB_DIR/usr/share/applications"
        mkdir -p "$DEB_DIR/usr/share/icons/hicolor/256x256/apps"
        mkdir -p "$DEB_DIR/usr/share/pixmaps"

        # Copy binaries to /opt/jobpilot
        cp -r dist/JobPilot/* "$DEB_DIR/opt/jobpilot/"
        chmod 755 "$DEB_DIR/opt/jobpilot/JobPilot"

        # Create launcher script in /usr/bin/jobpilot
        cat > "$DEB_DIR/usr/bin/jobpilot" <<'EOF'
#!/bin/sh
export PATH="/opt/jobpilot:${PATH}"
export LD_LIBRARY_PATH="/opt/jobpilot:${LD_LIBRARY_PATH}"
exec /opt/jobpilot/JobPilot "$@"
EOF
        chmod 755 "$DEB_DIR/usr/bin/jobpilot"

        # Desktop entry and icon in both hicolor and pixmaps for universal desktop visibility
        cp "$PROJECT_ROOT/app/ui/assets/brand/jobpilot_256.png" "$DEB_DIR/usr/share/icons/hicolor/256x256/apps/jobpilot.png"
        cp "$PROJECT_ROOT/app/ui/assets/brand/jobpilot_256.png" "$DEB_DIR/usr/share/pixmaps/jobpilot.png"
        cat > "$DEB_DIR/usr/share/applications/jobpilot.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=JobPilot
GenericName=Autonomous Job Search & Application Cockpit
Comment=AI-powered desktop recruitment management application
Exec=/usr/bin/jobpilot
Icon=jobpilot
Terminal=false
Categories=Utility;Office;Development;
StartupWMClass=JobPilot
EOF
        chmod 644 "$DEB_DIR/usr/share/applications/jobpilot.desktop"

        # Package metadata control file
        cat > "$DEB_DIR/DEBIAN/control" <<EOF
Package: jobpilot
Version: 0.1.0-beta.1
Section: utils
Priority: optional
Architecture: amd64
Maintainer: JobPilot Team <support@jobpilot.local>
Description: JobPilot - Autonomous Job Application Cockpit
 JobPilot is an AI-powered desktop automation platform for continuous
 job discovery, qualification scoring, and autonomous application submission
 across LinkedIn, Naukri, Indeed, Glassdoor, and Foundit.
EOF
        chmod 644 "$DEB_DIR/DEBIAN/control"

        # Post-install & Post-remove triggers to immediately refresh GNOME / KDE icon cache
        cat > "$DEB_DIR/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ -x /usr/bin/update-desktop-database ]; then
    update-desktop-database -q /usr/share/applications || true
fi
if [ -x /usr/bin/gtk-update-icon-cache ]; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
EOF
        chmod 755 "$DEB_DIR/DEBIAN/postinst"

        cat > "$DEB_DIR/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if [ -x /usr/bin/update-desktop-database ]; then
    update-desktop-database -q /usr/share/applications || true
fi
if [ -x /usr/bin/gtk-update-icon-cache ]; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
EOF
        chmod 755 "$DEB_DIR/DEBIAN/postrm"

        echo "Building Debian package: $DEB_OUT"
        dpkg-deb --build --root-owner-group "$DEB_DIR" "$DEB_OUT"
        cp "$DEB_OUT" "dist/jobpilot_latest_amd64.deb" 2>/dev/null || true
    else
        echo "Warning: dpkg-deb not found; skipping .deb creation."
    fi

    # --------------------------------------------------------------------------
    # 3. Portable Tarball Generation
    # --------------------------------------------------------------------------
    echo "Packaging portable tar.gz distribution..."
    cd dist
    tar -czf "jobpilot-v0.1.0-beta.1-linux-x86_64.tar.gz" JobPilot/
    cd "$PROJECT_ROOT"

    echo "=== Build Complete! ==="
    if [ -f "$APPIMAGE_OUT" ]; then
        echo "✓ AppImage created: $APPIMAGE_OUT"
    fi
    if [ -f "$DEB_OUT" ]; then
        echo "✓ Debian package:  $DEB_OUT"
    fi
    echo "✓ Tarball created:  dist/jobpilot-v0.1.0-beta.1-linux-x86_64.tar.gz"
else
    echo "ERROR: Build failed; dist/JobPilot directory was not created."
    exit 1
fi
