# -*- mode: python ; coding: utf-8 -*-
# Сборка ONEDIR — папка dist\SheldonPaws\ с SheldonPaws.exe и _internal\.
# Отличие от SheldonPaws.spec (onefile) только в EXE(..., exclude_binaries=True)
# и наличии COLLECT. Блок Analysis держи зеркальным основному спеку:
# новый .py в agent/ -> hiddenimports в ОБА спека.

a = Analysis(
    ['main.py'],
    pathex=['agent'],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=['skills.skill_writer'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SheldonPaws',
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
    icon=['assets\\doberman.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='SheldonPaws',
)
