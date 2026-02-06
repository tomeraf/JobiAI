# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for JobiAI Desktop Application.

Build command:
    cd c:\projects\JobiAI
    pyinstaller jobiai.spec

The output will be in dist/JobiAI.exe
"""

import sys
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(SPECPATH)
BACKEND_DIR = PROJECT_ROOT / 'backend'
FRONTEND_DIR = PROJECT_ROOT / 'frontend'
ASSETS_DIR = PROJECT_ROOT / 'assets'

block_cipher = None

# Collect all app submodules
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules('app')
hiddenimports += [
    # Async database
    'aiosqlite',
    # Uvicorn internals
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    # FastAPI/Starlette
    'starlette.routing',
    'starlette.responses',
    'starlette.staticfiles',
    # Pydantic
    'pydantic',
    'pydantic_settings',
    # System tray
    'pystray',
    'pystray._win32',
    'PIL',
    'PIL.Image',
    # Windows
    'win32api',
    'win32con',
    'win32gui',
    'win32event',
    'winerror',
    'winreg',
    # SQLAlchemy
    'sqlalchemy.dialects.sqlite',
    # Playwright stealth
    'playwright_stealth',
    'playwright_stealth.stealth',
]

# Data files to include
datas = []

# Include playwright_stealth JS files
import playwright_stealth
stealth_path = Path(playwright_stealth.__file__).parent
if (stealth_path / 'js').exists():
    datas.append((str(stealth_path / 'js'), 'playwright_stealth/js'))

# Include frontend dist if it exists
frontend_dist = FRONTEND_DIR / 'dist'
if frontend_dist.exists():
    datas.append((str(frontend_dist), 'frontend/dist'))
else:
    print("WARNING: Frontend dist not found. Run 'npm run build' in frontend/ first.")

# Include assets
if ASSETS_DIR.exists():
    datas.append((str(ASSETS_DIR), 'assets'))

a = Analysis(
    [str(BACKEND_DIR / 'app' / 'desktop.py')],
    pathex=[str(BACKEND_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused modules to reduce size
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'jupyter',
        # Don't bundle Playwright browsers (download on first run)
        'playwright.driver',
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
    name='JobiAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Temporarily enabled for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS_DIR / 'icon.ico') if (ASSETS_DIR / 'icon.ico').exists() else None,
)
