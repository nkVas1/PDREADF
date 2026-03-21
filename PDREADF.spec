# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for PDREADF – Professional PDF Reader & Editor.

Produces a single-file, windowed executable with only the Qt modules
the application actually uses (QtCore, QtGui, QtWidgets,
QtPrintSupport).  All unused Qt sub-packages (Qt3D, QtQuick, QML,
QtMultimedia, QtWebEngine, …) are excluded to keep the bundle small
and avoid missing-DLL warnings.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# ── data / binaries collection ────────────────────────────────
fitz_datas = collect_data_files("fitz")
fitz_bins = collect_dynamic_libs("fitz")
pymupdf_datas = collect_data_files("pymupdf")
pymupdf_bins = collect_dynamic_libs("pymupdf")
pikepdf_datas = collect_data_files("pikepdf")
pikepdf_bins = collect_dynamic_libs("pikepdf")

# ── icon ──────────────────────────────────────────────────────
icon_path = "icon.ico" if os.path.isfile("icon.ico") else None

# ── excludes – Qt modules NOT used by PDREADF ─────────────────
qt_excludes = [
    "PyQt6.Qt3D",
    "PyQt6.Qt3DAnimation",
    "PyQt6.Qt3DCore",
    "PyQt6.Qt3DExtras",
    "PyQt6.Qt3DInput",
    "PyQt6.Qt3DLogic",
    "PyQt6.Qt3DRender",
    "PyQt6.QtBluetooth",
    "PyQt6.QtCharts",
    "PyQt6.QtDataVisualization",
    "PyQt6.QtDesigner",
    "PyQt6.QtHelp",
    "PyQt6.QtLocation",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    "PyQt6.QtNfc",
    "PyQt6.QtOpenGL",
    "PyQt6.QtOpenGLWidgets",
    "PyQt6.QtPositioning",
    "PyQt6.QtQml",
    "PyQt6.QtQuick",
    "PyQt6.QtQuick3D",
    "PyQt6.QtQuickControls2",
    "PyQt6.QtQuickWidgets",
    "PyQt6.QtRemoteObjects",
    "PyQt6.QtSensors",
    "PyQt6.QtSerialPort",
    "PyQt6.QtSpatialAudio",
    "PyQt6.QtSql",
    "PyQt6.QtSvg",
    "PyQt6.QtSvgWidgets",
    "PyQt6.QtTest",
    "PyQt6.QtTextToSpeech",
    "PyQt6.QtWebChannel",
    "PyQt6.QtWebEngine",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebSockets",
    "PyQt6.QtXml",
]

general_excludes = [
    "tkinter",
    "unittest",
    "pydoc",
    "doctest",
    "lib2to3",
    "xmlrpc",
    "multiprocessing.popen_forkserver",
    "multiprocessing.popen_spawn_posix",
]

all_excludes = qt_excludes + general_excludes

a = Analysis(
    ["pdreadf.py"],
    pathex=[],
    binaries=fitz_bins + pymupdf_bins + pikepdf_bins,
    datas=fitz_datas + pymupdf_datas + pikepdf_datas,
    hiddenimports=[
        "fitz",
        "fitz.fitz",
        "fitz.utils",
        "pymupdf",
        "pikepdf",
        "pikepdf._core",
        "PIL",
        "PIL.Image",
        "PyQt6",
        "PyQt6.sip",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.QtPrintSupport",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=all_excludes,
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
    name="PDREADF",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                      # --windowed
    disable_windowed_traceback=False,    # show crash dialog on error
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
