import logging
import os
import platform
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger('mp3.tools')

FFMPEG_MISSING_MSG = (
    'FFmpeg bulunamadı; uygulama paketi bozuk olabilir. '
    'Uygulamayı yeniden indirip kur.'
)
SETUP_NETWORK_MSG = "Araçlar indirilemedi. İnternet bağlantını kontrol edip Tekrar dene'ye bas."

YTDLP_URL = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/{asset}'
DENO_URL = 'https://github.com/denoland/deno/releases/latest/download/{asset}'
MIN_DENO = (2, 3, 0)
YTDLP_UPDATE_INTERVAL = 1800

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


@dataclass(frozen=True)
class ToolPaths:
    ytdlp: Path
    deno: Path
    ffmpeg: Path


def _progress_cb(state, name):
    return lambda pct: state.set_step(name, 'downloading', pct)


def ensure_ytdlp(bin_dir, state, system, opener=urllib.request.urlopen):
    dest = Path(bin_dir) / exe_name('yt-dlp', system)
    if not (dest.exists() and dest.stat().st_size > 0):
        state.set_step('ytdlp', 'downloading', 0)
        url = YTDLP_URL.format(asset=ytdlp_asset(system))
        download(url, dest, _progress_cb(state, 'ytdlp'), opener=opener)
    state.set_step('ytdlp', 'ready', 100)
    return dest


def parse_deno_version(text):
    m = re.search(r'\bdeno (\d+)\.(\d+)\.(\d+)', text or '')
    return tuple(int(x) for x in m.groups()) if m else None


def _deno_version(path, run):
    try:
        r = run([str(path), '--version'], capture_output=True, text=True, timeout=30,
                **hidden_subprocess_kwargs())
        return parse_deno_version(r.stdout)
    except Exception as e:
        log.warning('deno sürümü okunamadı: %s', e)
        return None


def ensure_deno(bin_dir, state, system, machine, opener=urllib.request.urlopen, run=subprocess.run):
    bin_dir = Path(bin_dir)
    dest = bin_dir / exe_name('deno', system)
    if dest.exists():
        version = _deno_version(dest, run)
        if version and version >= MIN_DENO:
            state.set_step('deno', 'ready', 100)
            return dest
    state.set_step('deno', 'downloading', 0)
    archive = bin_dir / 'deno.zip'
    download(DENO_URL.format(asset=deno_asset(system, machine)), archive,
             _progress_cb(state, 'deno'), opener=opener)
    try:
        part = dest.with_name(dest.name + '.part')
        with zipfile.ZipFile(archive) as z, z.open(exe_name('deno', system)) as src, open(part, 'wb') as out:
            shutil.copyfileobj(src, out)
        os.replace(part, dest)
    finally:
        archive.unlink(missing_ok=True)
    if os.name != 'nt':
        dest.chmod(0o755)
    state.set_step('deno', 'ready', 100)
    return dest


def run_setup(state, bin_dir, system=None, machine=None,
              opener=urllib.request.urlopen, run=subprocess.run):
    system = system or platform.system()
    machine = machine or platform.machine()
    state.reset()
    try:
        ffmpeg = ensure_ffmpeg(bin_dir, state, system)
        ytdlp = ensure_ytdlp(bin_dir, state, system, opener=opener)
        deno = ensure_deno(bin_dir, state, system, machine, opener=opener, run=run)
    except ToolError as e:
        log.error('kurulum hatası: %s', e)
        state.fail(str(e))
        return None
    except (OSError, zipfile.BadZipFile) as e:
        # urllib.error.URLError de OSError'dır
        log.error('kurulum indirme hatası: %s', e)
        state.fail(SETUP_NETWORK_MSG)
        return None
    return ToolPaths(ytdlp=ytdlp, deno=deno, ffmpeg=ffmpeg)


class YtdlpUpdater:
    # YouTube sık değiştiği için yt-dlp arka planda güncellenir; en fazla
    # YTDLP_UPDATE_INTERVAL saniyede bir.
    def __init__(self, ytdlp, clock=time.monotonic, run=subprocess.run):
        self._ytdlp = Path(ytdlp)
        self._clock = clock
        self._run = run
        self._lock = threading.Lock()
        self._running = False
        self._last_start = None

    @property
    def is_running(self):
        with self._lock:
            return self._running

    def trigger(self):
        with self._lock:
            now = self._clock()
            if self._running:
                return False
            if self._last_start is not None and now - self._last_start < YTDLP_UPDATE_INTERVAL:
                return False
            self._running = True
            self._last_start = now
        threading.Thread(target=self._update, daemon=True).start()
        return True

    def _update(self):
        try:
            self._run([str(self._ytdlp), '-U'], capture_output=True, timeout=300,
                      **hidden_subprocess_kwargs())
            log.info('yt-dlp güncelleme denemesi bitti')
        except Exception as e:
            log.warning('yt-dlp güncellenemedi: %s', e)
        finally:
            with self._lock:
                self._running = False
