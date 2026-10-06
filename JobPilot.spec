# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for building JobPilot Desktop (Windows & Linux)."""

import os
import sys
from pathlib import Path

block_cipher = None

project_root = Path.cwd().resolve()
icon_path = str(project_root / "app" / "ui" / "assets" / "brand" / "jobpilot.ico")
if not os.path.exists(icon_path):
    icon_path = str(project_root / "app" / "ui" / "assets" / "brand" / "jobpilot_256.png")

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

added_data = [
    (str(project_root / "app" / "ui" / "assets"), os.path.join("app", "ui", "assets")),
    (str(project_root / "config"), "config"),
] + collect_data_files("stagehand") + collect_data_files("certifi")

hidden_imports = [
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "sqlalchemy",
    "sqlalchemy.sql.default_comparator",
    "cryptography",
    "cryptography.fernet",
    "selenium",
    "selenium.webdriver",
    "webdriver_manager",
    "sqlite3",
    "app.version",
    "app.db",
    "app.models",
    "app.services",
    "app.ui",
    "modules",
    "platforms",
] + collect_submodules("stagehand") + collect_submodules("app") + collect_submodules("platforms") + collect_submodules("modules") + collect_submodules("config")

a = Analysis(
    ["run_desktop.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=added_data,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JobPilot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="JobPilot",
)
