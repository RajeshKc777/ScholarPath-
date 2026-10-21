# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for ScholarPath AI (G207 / G138).

Build (from the repository root, in the project venv):

    .venv\\Scripts\\python.exe -m PyInstaller packaging\\scholarpath.spec --noconfirm

Output: dist\\ScholarPathAI\\ScholarPathAI.exe plus its _internal folder.

Notes:
- The app is a windowed (GUI) program: no console window is opened.
- **No user data is bundled**: config, database and logs stay in the per-user
  application folder (%APPDATA%\\ScholarPath), never inside the build.
- The optional OCR extra (winsdk) is bundled only when it is installed.
"""

import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

ROOT = Path(SPECPATH).parent
SRC = ROOT / "src"

hiddenimports = [
    # the app's own optional/indirect imports
    "scholarpath.gateway.opencode",
    "scholarpath.gateway.openai_compat",
    "scholarpath.gateway.chain",
    "scholarpath.gateway.failover",
    "scholarpath.gateway.credentials",
    "scholarpath.gateway.factory",
    "scholarpath.gateway.registry",
    "scholarpath.gateway.stub",
    "scholarpath.mcp.client",
    # voice: neural TTS (aiohttp), MP3 decoding, the offline Windows voice
    "edge_tts",
    "aiohttp",
    "miniaudio",
    "_miniaudio",
    "pyttsx3",
    "comtypes",
    "comtypes.client",
    # voice input: capture (PyAudio) + the recognition library and its data
    "speech_recognition",
    "pyaudio",
    "winsound",
    # standard library bits that are imported lazily
    "sqlite3",
    "email",
    "http.client",
    "xml.etree.ElementTree",
]

datas = collect_data_files("speech_recognition")
binaries = collect_dynamic_libs("pyaudio")

# TLS roots for the live connections (search + speech services).
if importlib.util.find_spec("certifi"):
    datas += collect_data_files("certifi")
    hiddenimports.append("certifi")

# OCR is an optional extra: bundle it when the user installed it.
if importlib.util.find_spec("winsdk"):
    hiddenimports += collect_submodules("winsdk")
    datas += collect_data_files("winsdk")

block_cipher = None

analysis = Analysis(
    [str(SRC / "scholarpath" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "pytest",
        "_pytest",
        "IPython",
        "notebook",
        "sqlalchemy",
        "setuptools",
        "pip",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="ScholarPathAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # a desktop app: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ScholarPathAI",
)
