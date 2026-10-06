# -*- mode: python ; coding: utf-8 -*-
# Derleme: pyinstaller packaging/mp3donusturucum.spec --noconfirm
# ffmpeg, pyinstaller-hooks-contrib'teki imageio_ffmpeg kancasıyla pakete girer.
import re
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
BACKEND = ROOT / 'backend'
ICONS = ROOT / 'packaging' / 'icons'
# Logo: python packaging/icons/make_icons.py ile üretilir.
EXE_ICON = {'win32': ICONS / 'app.ico', 'darwin': ICONS / 'app.icns'}.get(sys.platform)
VERSION = re.search(r"__version__ = '([^']+)'", (BACKEND / 'version.py').read_text(encoding='utf-8')).group(1)

a = Analysis(
    [str(BACKEND / 'launcher.py')],
    pathex=[str(BACKEND)],
    datas=[(str(ROOT / 'frontend'), 'frontend')],
    excludes=['tkinter'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MP3Donusturucum',
    console=False,
    upx=False,
    icon=str(EXE_ICON) if EXE_ICON else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name='MP3Donusturucum', upx=False)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='MP3Donusturucum.app',
        icon=str(ICONS / 'app.icns'),
        bundle_identifier='io.github.efebalci569.mp3donusturucum',
        info_plist={
            # Penceresi olmayan uygulama: Dock'ta "yanıt vermiyor" görünmesin.
            'LSUIElement': True,
            'CFBundleShortVersionString': VERSION,
            'CFBundleVersion': VERSION,
        },
    )
