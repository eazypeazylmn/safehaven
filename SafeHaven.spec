# -*- mode: python ; coding: utf-8 -*-
#
# SafeHaven.spec – PyInstaller Build-Konfiguration
#
# Erstellt eine einzelne SafeHaven.exe (onefile, kein Konsolenfenster).
# Einstiegspunkt ist harbor.py (GUI-Modus).
#
# Build-Befehl:
#   pyinstaller SafeHaven.spec
#
# Output: dist/SafeHaven.exe

a = Analysis(
    ['harbor.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'cv2',
        'mss',
        'mss.windows',
        'pyautogui',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SafeHaven',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # Kein schwarzes Terminal-Fenster
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
