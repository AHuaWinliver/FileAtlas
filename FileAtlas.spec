# -*- mode: python ; coding: utf-8 -*-


from pathlib import Path
import importlib.util
root = Path(SPECPATH)

a = Analysis(
    [str(root / 'app.py')],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml', 'PySide6.QtQuick'],
    noarchive=False,
    optimize=0,
)
# Qt uses the Windows 11 system ICU API. A PATH-provided ICU with versioned
# symbols can be incorrectly collected and prevents QtCore from loading.
a.binaries = [item for item in a.binaries if Path(item[0]).name.lower() not in ('icuuc.dll', 'icudt78.dll')]
runtime_dir = Path(importlib.util.find_spec('shiboken6').origin).parent
for i, item in enumerate(a.binaries):
    name = Path(item[0]).name.lower()
    if name in ('vcruntime140.dll', 'vcruntime140_1.dll'):
        runtime = runtime_dir / name
        if runtime.exists():
            a.binaries[i] = (item[0], str(runtime.resolve()), item[2])
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FileAtlas',
    icon=str(root / 'assets' / 'app-icon.ico'),
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FileAtlas',
)
