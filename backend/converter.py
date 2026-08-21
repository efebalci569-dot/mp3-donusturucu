import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JOBS_DIR = os.environ.get("JOBS_DIR") or os.path.join(tempfile.gettempdir(), "mp3_jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "2"))
JOB_TTL_SECONDS = int(os.environ.get("JOB_TTL_SECONDS", "1800"))
DOWNLOAD_TIMEOUT_SECONDS = int(os.environ.get("DOWNLOAD_TIMEOUT_SECONDS", "600"))

YOUTUBE_PATTERN = re.compile(
    r'^https?://(www\.|music\.|m\.)?'
    r'(youtube\.com/(watch\?.*v=[\w\-]{5,}|shorts/[\w\-]{5,})'
    r'|youtu\.be/[\w\-]{5,})'
)

FALLBACK_ARGS = [
    [],
    ['--extractor-args', 'youtube:player_client=android_vr'],
]

_lock = threading.Lock()
_jobs = {}
_executor = None


def _get_executor():
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)
    return _executor


def validate_url(url):
    return bool(url) and len(url) <= 500 and bool(YOUTUBE_PATTERN.match(url))


def sanitize_title(t):
    t = re.sub(r'[^\w\s\-]', '', t).strip()
    t = re.sub(r'\s+', ' ', t)
    return t[:80] or 'video'


def _base_args():
    args = ['yt-dlp', '--remote-components', 'ejs:github', '--no-playlist']
    if shutil.which('node'):
        args += ['--js-runtime', 'node']
    cookies_browser = os.environ.get('YTDLP_COOKIES_FROM_BROWSER')
    if cookies_browser:
        args += ['--cookies-from-browser', cookies_browser]
    cookies_file = os.environ.get('YTDLP_COOKIES_FILE')
    if cookies_file and os.path.exists(cookies_file):
        args += ['--cookies', cookies_file]
    return args


def resolve_ffmpeg():
    custom = os.environ.get('FFMPEG_PATH')
    if custom:
        if os.path.isfile(custom):
            return custom
        if os.path.isdir(custom):
            candidate = os.path.join(custom, 'ffmpeg')
            if os.path.isfile(candidate) or os.path.isfile(candidate + '.exe'):
                return candidate
            return custom
    found = shutil.which('ffmpeg')
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _extract_error(stderr_text, default):
    for line in (stderr_text or '').split('\n'):
        if 'ERROR' in line:
            return line.strip()
    return default


def _fetch_info(url):
    last_err = 'Video bilgisi alınamadı'
    for extra in FALLBACK_ARGS:
        try:
            r = subprocess.run(
                _base_args() + extra + ['--dump-json', url],
                capture_output=True, text=True, timeout=60
            )
        except subprocess.TimeoutExpired:
            continue
        if r.returncode == 0:
            try:
                return r.stdout.strip().split('\n')[0], None
            except Exception:
                pass
        last_err = _extract_error(r.stderr, last_err)
    return None, last_err


def start_job(url):
    job_id = uuid.uuid4().hex
    job_dir = os.path.join(JOBS_DIR, f'job_{job_id}')
    os.makedirs(job_dir, exist_ok=True)
    job = {
        'id': job_id,
        'dir': job_dir,
        'status': 'queued',
        'progress': 0,
        'title': None,
        'filename': None,
        'size_mb': None,
        'error': None,
        'created_at': time.time(),
    }
    with _lock:
        _jobs[job_id] = job
    _get_executor().submit(_run_job, job, url)
    return job


def _run_job(job, url):
    job['status'] = 'processing'
    try:
        ffmpeg = resolve_ffmpeg()
        if not ffmpeg:
            raise RuntimeError('FFmpeg bulunamadı. FFMPEG_PATH ayarlayın.')

        info_json, err = _fetch_info(url)
        if err:
            low = err.lower()
            if 'private' in low:
                raise RuntimeError('Bu video gizli (private).')
            if 'unavailable' in low or 'not available' in low:
                raise RuntimeError('Video bulunamadı veya kaldırılmış.')
            if 'sign in' in low or 'age' in low:
                raise RuntimeError('Bu video giriş yapmayı gerektiriyor.')
            raise RuntimeError(err)

        try:
            info = json.loads(info_json)
        except Exception:
            raise RuntimeError('Video bilgisi çözümlenemedi')

        title = info.get('title') or 'Bilinmeyen Video'
        video_id = info.get('id') or uuid.uuid4().hex[:11]
        job['title'] = title

        output_tpl = os.path.join(job['dir'], '%(id)s.%(ext)s')
        last_err = 'İndirme başarısız'

        for extra in FALLBACK_ARGS:
            cmd = (
                _base_args() + extra +
                ['-x', '--audio-format', 'mp3', '--audio-quality', '0',
                 '--newline',
                 '--progress-template', 'download:PROGRESS %(progress._percent_str)s',
                 '--ffmpeg-location', str(ffmpeg),
                 '--output', output_tpl,
                 url]
            )
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace',
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            started = time.time()
            failed = False
            for line in proc.stdout:
                if DOWNLOAD_TIMEOUT_SECONDS and time.time() - started > DOWNLOAD_TIMEOUT_SECONDS:
                    proc.kill()
                    raise RuntimeError(f'İşlem zaman aşımı ({DOWNLOAD_TIMEOUT_SECONDS // 60} dk)')
                line = line.strip()
                if line.startswith('PROGRESS'):
                    try:
                        pct = float(line.replace('%', '').split()[1])
                        job['progress'] = max(job['progress'], min(int(pct), 95))
                    except Exception:
                        pass
                elif 'ExtractAudio' in line:
                    job['progress'] = max(job['progress'], 96)
                elif 'ERROR' in line:
                    failed = True
                    last_err = line.strip()
            code = proc.wait(timeout=30)

            if code == 0 and not failed:
                break

            low = last_err.lower()
            if not any(k in low for k in ('403', 'forbidden')):
                break

        mp3_files = [f for f in os.listdir(job['dir']) if f.endswith('.mp3')]
        if not mp3_files:
            low = last_err.lower()
            if '403' in low or 'forbidden' in low:
                raise RuntimeError('YouTube indirmeyi engelledi (403). Lütfen tekrar deneyin.')
            if 'sign in' in low:
                raise RuntimeError('Bu video giriş yapmayı gerektiriyor.')
            raise RuntimeError(last_err)

        filename = f"{sanitize_title(title)}.mp3"
        size_mb = os.path.getsize(os.path.join(job['dir'], mp3_files[0])) / (1024 * 1024)

        job['filename'] = filename
        job['size_mb'] = round(size_mb, 2)
        job['progress'] = 100
        job['status'] = 'done'

    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e) or 'Dönüştürme başarısız'
        _cleanup_job_dir(job)


def get_job(job_id):
    with _lock:
        return _jobs.get(job_id)


def build_download_response_path(job_id):
    job = get_job(job_id)
    if not job or job['status'] != 'done':
        return None, None
    files = [f for f in os.listdir(job['dir']) if f.endswith('.mp3')]
    if not files:
        return None, None
    return os.path.join(job['dir'], files[0]), job['filename']


def _cleanup_job_dir(job):
    try:
        if os.path.exists(job['dir']):
            shutil.rmtree(job['dir'], ignore_errors=True)
    except Exception:
        pass
    if job['status'] == 'error':
        with _lock:
            _jobs.pop(job['id'], None)


def sweep_expired():
    now = time.time()
    removed = []
    with _lock:
        snapshot = list(_jobs.values())
    for job in snapshot:
        if now - job['created_at'] > JOB_TTL_SECONDS:
            _cleanup_job_dir(job)
            with _lock:
                _jobs.pop(job['id'], None)
            removed.append(job['id'])
    return removed


def _janitor_loop():
    while True:
        try:
            sweep_expired()
        except Exception:
            pass
        time.sleep(60)


def start_janitor():
    t = threading.Thread(target=_janitor_loop, daemon=True)
    t.start()
