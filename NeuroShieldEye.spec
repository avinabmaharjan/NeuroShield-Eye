# -*- mode: python ; coding: utf-8 -*-
# NeuroShieldEye.spec — PyInstaller build specification
#
# Build command:
#   pyinstaller NeuroShieldEye.spec
#
# Output: dist/NeuroShieldEye.exe

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None
pyqtgraph_datas = collect_data_files("pyqtgraph")

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("assets", "assets"),
        ("default_config.json", "."),
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
        "logger",
        "settings_manager",
        "settings_panel",
        "database_manager",
        "tray_manager",
        "blue_light_overlay",
        "break_timer",
        "dim_engine",
        "focus_mode",
        "posture_reminder",
        "dashboard_window",
        "auth_window",
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/tray_icon.ico",
    uac_admin=False,
)
