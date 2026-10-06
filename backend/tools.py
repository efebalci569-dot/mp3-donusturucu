import logging
import os
import shutil
import subprocess
import threading
import urllib.request
from pathlib import Path

log = logging.getLogger('mp3.tools')

FFMPEG_MISSING_MSG = (
    'FFmpeg bulunamadı; uygulama paketi bozuk olabilir. '
    'Uygulamayı yeniden indirip kur.'
)

_CHUNK = 64 * 1024

_DENO_TARGETS = {
    ('Windows', 'x86_64'): 'x86_64-pc-windows-msvc',
    ('Windows', 'aarch64'): 'aarch64-pc-windows-msvc',
    ('Darwin', 'aarch64'): 'aarch64-apple-darwin',
    ('Darwin', 'x86_64'): 'x86_64-apple-darwin',
    ('Linux', 'x86_64'): 'x86_64-unknown-linux-gnu',
    ('Linux', 'aarch64'): 'aarch64-unknown-linux-gnu',
}
_MACHINE_ALIASES = {'amd64': 'x86_64', 'x86_64': 'x86_64', 'arm64': 'aarch64', 'aarch64': 'aarch64'}


class ToolError(Exception):
    pass


class UnsupportedPlatform(ToolError):
    pass


def hidden_subprocess_kwargs():
    # Paketlenmiş (pencereli) uygulamada her alt süreç için konsol penceresi açılmasın.
    if os.name == 'nt':
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    return {}


def exe_name(name, system):
    return f'{name}.exe' if system == 'Windows' else name


def ytdlp_asset(system):
    assets = {'Windows': 'yt-dlp.exe', 'Darwin': 'yt-dlp_macos', 'Linux': 'yt-dlp_linux'}
    if system not in assets:
        raise UnsupportedPlatform(f'Desteklenmeyen işletim sistemi: {system}')
    return assets[system]


def deno_asset(system, machine):
    arch = _MACHINE_ALIASES.get((machine or '').lower())
    target = _DENO_TARGETS.get((system, arch))
    if not target:
        raise UnsupportedPlatform(f'Desteklenmeyen platform: {system} {machine}')
    return f'deno-{target}.zip'


def download(url, dest, on_progress, opener=urllib.request.urlopen):
    # Önce .part dosyasına yaz, bitince yerine koy: yarım dosya hiçbir zaman kurulu sayılmaz.
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + '.part')
    try:
        with opener(url, timeout=60) as resp, open(part, 'wb') as out:
            total = int(resp.headers.get('Content-Length') or 0)
            done = 0
            while True:
                chunk = resp.read(_CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if total:
                    on_progress(min(100, done * 100 // total))
        os.replace(part, dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    if os.name != 'nt':
        dest.chmod(0o755)
    on_progress(100)


class SetupState:
    STEPS = ('ffmpeg', 'ytdlp', 'deno')

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with self._lock:
            self._steps = {n: {'state': 'pending', 'progress': 0} for n in self.STEPS}
            self._error = None

    def set_step(self, name, state, progress=0):
        with self._lock:
            self._steps[name] = {'state': state, 'progress': int(progress)}

    def fail(self, message):
        with self._lock:
            self._error = message

    @property
    def ready(self):
        with self._lock:
            return self._error is None and all(s['state'] == 'ready' for s in self._steps.values())

    def to_dict(self):
        with self._lock:
            ready = self._error is None and all(s['state'] == 'ready' for s in self._steps.values())
            return {
                'ready': ready,
                'steps': {n: dict(s) for n, s in self._steps.items()},
                'error': self._error,
            }


def bundled_ffmpeg():
    custom = os.environ.get('FFMPEG_PATH')
    if custom and os.path.isfile(custom):
        return Path(custom)
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return Path(exe)
    except Exception:
        pass
    found = shutil.which('ffmpeg')
    return Path(found) if found else None


def ensure_ffmpeg(bin_dir, state, system):
    # Gömülü ikilinin adı standart değil (ffmpeg-win-x86_64-v7.1.exe); yt-dlp için
    # bin/ffmpeg[.exe] adıyla bir kopyası tutulur.
    src = bundled_ffmpeg()
    if src is None:
        state.set_step('ffmpeg', 'error')
        raise ToolError(FFMPEG_MISSING_MSG)
    dest = Path(bin_dir) / exe_name('ffmpeg', system)
    if not dest.exists() or dest.stat().st_size != src.stat().st_size:
        state.set_step('ffmpeg', 'downloading', 0)
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + '.part')
        shutil.copy2(src, part)
        os.replace(part, dest)
        if os.name != 'nt':
            dest.chmod(0o755)
    state.set_step('ffmpeg', 'ready', 100)
    return dest
