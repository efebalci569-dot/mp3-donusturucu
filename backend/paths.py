import os
import platform
import sys
from pathlib import Path

APP_ID = 'mp3donusturucum'
APP_NAME = 'MP3Donusturucum'


def data_dir(system=None, env=None, home=None):
    # Kullanıcıya özel veri klasörü; burada klasör oluşturulmaz (launcher oluşturur).
    system = system or platform.system()
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    if system == 'Windows':
        base = env.get('LOCALAPPDATA') or str(home / 'AppData' / 'Local')
        return Path(base) / APP_NAME
    if system == 'Darwin':
        return home / 'Library' / 'Application Support' / APP_NAME
    xdg = env.get('XDG_DATA_HOME')
    return (Path(xdg) if xdg else home / '.local' / 'share') / APP_ID


def resource_dir():
    # PyInstaller paketinde gömülü dosyalar _MEIPASS altında; geliştirmede depo kökü.
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def bin_dir(base):
    return Path(base) / 'bin'


def jobs_dir(base):
    return Path(base) / 'jobs'


def instance_file(base):
    return Path(base) / 'instance.json'


def log_file(base):
    return Path(base) / 'log.txt'
