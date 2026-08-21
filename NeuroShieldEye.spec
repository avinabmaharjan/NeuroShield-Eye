# -*- mode: python ; coding: utf-8 -*-
# NeuroShieldEye.spec — PyInstaller build specification
#
# Build command:
#   pyinstaller NeuroShieldEye.spec
#
# Output: dist/NeuroShieldEye.exe

from PyInstaller.utils.hooks import collect_data_files
import os

block_cipher = None

# Collect pyqtgraph data files (includes colormaps, etc.)
pyqtgraph_datas = collect_data_files("pyqtgraph")

a = Analysis(
    scripts=['main.py']
    pathex=["src"],
    binaries=[],
    datas=[
        ("assets", "assets"),
        ("config", "config"),
        *pyqtgraph_datas,
    ],
    hiddenimports=[
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "pyqtgraph",
        "sqlite3",
        "winreg",
        "winsound",
        "msvcrt",
        # All project modules
        "utils.logger",
        "settings.settings_manager",
        "settings.settings_panel",
        "database.database_manager",
        "tray.tray_manager",
        "overlay.blue_light_overlay",
        "break_system.break_timer",
        "brightness.dim_engine",
        "focus.focus_mode",
        "posture.posture_reminder",
        "dashboard.dashboard_window",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "IPython",
        "jupyter",
        "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="NeuroShieldEye",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # No console window (windowed app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/tray_icon.ico",
    uac_admin=False,         # Set to True if registry write needs elevation
    version=None,
)
