# -*- mode: python ; coding: utf-8 -*-
# Empaqueta la app en dist/MakroModManager/ (onedir).
# El JRE bundleado (carpeta runtime/) se añade como datos junto al exe.

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('runtime', 'runtime'), ('assets', 'assets')],   # JRE jlink + assets (icono, imagen broma)
    hiddenimports=['tkinter', 'tkinter.ttk'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='MakroModManager',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
    icon='assets/icon.ico',
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, upx_exclude=[], name='MakroModManager',
)
