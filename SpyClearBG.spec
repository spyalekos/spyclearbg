# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, copy_metadata
from PyInstaller.building.api import Splash

datas = []
if os.path.exists('assets'):
    datas.append(('assets', 'assets'))
binaries = []
hiddenimports = []

# Collect Flet
tmp_ret = collect_all('flet')
datas.extend(tmp_ret[0])
binaries.extend(tmp_ret[1])
hiddenimports.extend(tmp_ret[2])

# Collect Rembg
tmp_ret = collect_all('rembg')
datas.extend(tmp_ret[0])
binaries.extend(tmp_ret[1])
hiddenimports.extend(tmp_ret[2])

# Collect ONNX Runtime
tmp_ret = collect_all('onnxruntime')
datas.extend(tmp_ret[0])
binaries.extend(tmp_ret[1])
hiddenimports.extend(tmp_ret[2])

# Collect PyMatting metadata for rembg (fixes PackageNotFoundError)
datas.extend(copy_metadata('pymatting'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

splash = Splash(
    'assets/splash.jpg',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    text_size=12,
    minify_script=True,
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
    a.binaries,
    a.datas,
    [],
    name='SpyClearBG',
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
)
