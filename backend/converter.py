import json
import os
import re
import shutil
import subprocess
import sys
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

# Render gibi datacenter IP'leri web istemcide anında bot-check yer.
# Mobil istemciler (android/ios/mweb) çok daha toleranslıdır.
# Sırayla dene: hangisi çalışırsa dur.
FALLBACK_ARGS = [
    ['--extractor-args', 'youtube:player_client=android'],
    ['--extractor-args', 'youtube:player_client=ios'],
    ['--extractor-args', 'youtube:player_client=mweb'],
    [],  # varsayılan web istemci (PO Token provider burada devreye girer)
    ['--extractor-args', 'youtube:player_client=android_vr'],
    # PO Token plugin kuruluysa (bgutil) web istemciyle token'lı deneme
    ['--extractor-args', 'youtube:player_client=web',
     '--extractor-args', 'youtube:po_token=auto'],
]

YT_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/131.0.0.0 Safari/537.36'
)

_lock = threading.Lock()
_jobs = {}
_executor = None

_ytdlp_version_cache = None
_impersonate_support_cache = None


def _log(msg):
    print(f'[converter] {msg}', flush=True, file=sys.stderr)


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


def _ytdlp_version():
    global _ytdlp_version_cache
    if _ytdlp_version_cache is not None:
        return _ytdlp_version_cache
    try:
        r = subprocess.run(
            ['yt-dlp', '--version'],
            capture_output=True, text=True, timeout=15
        )
        _ytdlp_version_cache = r.stdout.strip() if r.returncode == 0 else 'unknown'
    except Exception:
        _ytdlp_version_cache = 'unknown'
    return _ytdlp_version_cache


def _has_pot_provider():
    # Plugin pip paketi olarak kuruluysa yt-dlp otomatik yükler (import yolu yok).
    try:
        from importlib import metadata as md
        for d in md.distributions():
            name = ((d.metadata.get('Name') or '').lower())
            if 'bgutil' in name and 'pot' in name:
                return True
    except Exception:
        pass
    return False


def _pot_server_ok():
    import socket
    try:
        s = socket.create_connection(('127.0.0.1', 4416), timeout=3)
        s.close()
        return True
    except Exception:
        return False


def _supports_impersonate():
    global _impersonate_support_cache
    if _impersonate_support_cache is not None:
        return _impersonate_support_cache
    try:
        import curl_cffi  # noqa: F401
    except Exception:
        _impersonate_support_cache = False
        return False
    try:
        r = subprocess.run(
            ['yt-dlp', '--help'],
            capture_output=True, text=True, timeout=15
        )
        _impersonate_support_cache = 'impersonate' in (r.stdout + r.stderr).lower()
    except Exception:
        _impersonate_support_cache = False
    return _impersonate_support_cache


def _cookies_candidates():
    cands = []
    env_path = (os.environ.get('YTDLP_COOKIES_FILE') or '').strip()
    if env_path:
        cands.append(env_path)
    cands += [
        os.path.join(BASE_DIR, 'cookies.txt'),
        os.path.join(BASE_DIR, 'appcookies.txt'),
        os.path.join(os.getcwd(), 'cookies.txt'),
        os.path.join(os.getcwd(), 'appcookies.txt'),
        '/etc/secrets/cookies.txt',
        '/etc/secrets/appcookies.txt',
        '/app/cookies.txt',
    ]
    seen, out = set(), []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def resolve_cookies_file():
    for c in _cookies_candidates():
        try:
            if c and os.path.isfile(c):
                return c
        except Exception:
            pass
    return None


def _base_args():
    args = ['yt-dlp', '--remote-components', 'ejs:github', '--no-playlist']
    if shutil.which('node'):
        args += ['--js-runtime', 'node']
    # Datacenter engeline karşı temel sağlamlaştırma
    args += [
        '--retries', '3',
        '--fragment-retries', '3',
        '--socket-timeout', '15',
        '--force-ipv4',
        '--user-agent', YT_USER_AGENT,
    ]
    if _supports_impersonate():
        args += ['--impersonate', 'chrome']
    cookies_browser = os.environ.get('YTDLP_COOKIES_FROM_BROWSER')
    if cookies_browser:
        args += ['--cookies-from-browser', cookies_browser]
    cookies_file = resolve_cookies_file()
    if cookies_file:
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


def _cookies_diag():
    # İçeriği sızdırmadan sadece sayaçlar: dosya boş mu, youtube satırı var mı?
    path = resolve_cookies_file()
    if not path:
        return {'exists': False}
    try:
        size = os.path.getsize(path)
    except Exception:
        size = -1
    lines, yt = 0, 0
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                lines += 1
                if 'youtube.com' in s or 'google.com' in s:
                    yt += 1
    except Exception:
        pass
    return {'exists': True, 'bytes': size, 'entries': lines, 'youtube_entries': yt}


def _installed_yt_pkgs():
    try:
        from importlib import metadata as md
        out = []
        for d in md.distributions():
            name = (d.metadata.get('Name') or '')
            low = name.lower()
            if any(k in low for k in ('yt-dlp', 'bgutil', 'pot', 'curl_cffi', 'curl-cffi')):
                out.append(f'{name} {d.version}')
        return sorted(out)
    except Exception as e:
        return [f'hata: {e}']


def debug_info():
    resolved = resolve_cookies_file()
    return {
        'yt_dlp_version': _ytdlp_version(),
        'ffmpeg': bool(resolve_ffmpeg()),
        'pot_provider': _has_pot_provider(),
        'pot_server': _pot_server_ok(),
        'impersonate': _supports_impersonate(),
        'node': bool(shutil.which('node')),
        'cookies_file_env': os.environ.get('YTDLP_COOKIES_FILE', ''),
        'cookies_file_resolved': resolved or '',
        'cookies_file_exists': bool(resolved),
        'cookies': _cookies_diag(),
        'packages': _installed_yt_pkgs(),
        'max_jobs': MAX_CONCURRENT_JOBS,
    }


def _extract_error(stderr_text, default):
    for line in (stderr_text or '').split('\n'):
        if 'ERROR' in line:
            return line.strip()
    return default


def _is_bot_check(text):
    low = (text or '').lower()
    markers = (
        'sign in to confirm',
        "confirm you're not a bot",
        'confirm you are not a bot',
        'server verification',
        'sunucu do',
        'po token',
        'po_token',
        'nsig',
        'did not get video data',
        'unable to extract player',
        'player response',
    )
    return any(m in low for m in markers)


def _should_try_next_client(text):
    low = (text or '').lower()
    if '403' in low or 'forbidden' in low:
        return True
    return _is_bot_check(text)


def _friendly_error(raw):
    raw = (raw or '').strip()
    low = raw.lower()
    if not raw:
        return 'Video bilgisi alınamadı'
    # 1. Bot doğrulaması -> kullanıcının gördüğü ana hata
    if _is_bot_check(raw):
        return (
            'YouTube bu video için sunucu doğrulaması istiyor. '
            'Başka bir herkese açık video deneyin. '
            '(Sunucu IP’si YouTube tarafından engellendi — cookies dosyası eklenirse düzelir.)'
        )
    if 'private' in low:
        return 'Bu video gizli (private).'
    if 'unavailable' in low or 'not available' in low:
        return 'Video bulunamadı veya kaldırılmış.'
    if 'age' in low and ('confirm' in low or 'sign' in low):
        return 'Bu video yaş doğrulaması istiyor, dönüştürülemez.'
    if 'sign in' in low or 'login required' in low or 'log in' in low:
        return 'Bu video giriş yapmayı gerektiriyor.'
    if '403' in low or 'forbidden' in low:
        return 'YouTube indirmeyi engelledi (403). Lütfen tekrar deneyin.'
    # ham mesajı kısaltıp döndür (logda tamamı var)
    return raw[:300]


def _fetch_info(url, job=None):
    last_err = 'Video bilgisi alınamadı'
    cookies_file = resolve_cookies_file()
    _log(
        f'info start yt-dlp={_ytdlp_version()} '
        f'pot={_has_pot_provider()} impersonate={_supports_impersonate()} '
        f'cookies={cookies_file or "yok"}'
    )
    for i, extra in enumerate(FALLBACK_ARGS):
        label = ' '.join(extra) if extra else 'default-web'
        try:
            r = subprocess.run(
                _base_args() + extra + ['--dump-json', url],
                capture_output=True, text=True, timeout=60
            )
        except subprocess.TimeoutExpired:
            _log(f'info deneme {i} [{label}] timeout')
            continue
        if r.returncode == 0:
            try:
                line = r.stdout.strip().split('\n')[0]
                _log(f'info deneme {i} [{label}] OK')
                _note(job, f'info {label}: OK')
                return line, None
            except Exception:
                pass
        last_err = _extract_error(r.stderr, last_err)
        _log(f'info deneme {i} [{label}] FAIL: {last_err[:200]}')
        _note(job, f'info {label}: {last_err[:150]}')
        if not _should_try_next_client(last_err):
            break
    return None, _friendly_error(last_err)


def _note(job, msg):
    if job is not None:
        try:
            job.setdefault('log', []).append(msg[:200])
        except Exception:
            pass


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
        'log': [],
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

        info_json, err = _fetch_info(url, job)
        if err:
            raise RuntimeError(err)

        try:
            info = json.loads(info_json)
        except Exception:
            raise RuntimeError('Video bilgisi çözümlenemedi')

        title = info.get('title') or 'Bilinmeyen Video'
        job['title'] = title
        _log(f'job {job["id"]} title="{title[:60]}"')

        output_tpl = os.path.join(job['dir'], '%(id)s.%(ext)s')
        last_err = 'İndirme başarısız'

        for i, extra in enumerate(FALLBACK_ARGS):
            label = ' '.join(extra) if extra else 'default-web'
            cmd = (
                _base_args() + extra +
                ['-x', '--audio-format', 'mp3', '--audio-quality', '0',
                 '--newline',
                 '--progress-template', 'download:PROGRESS %(progress._percent_str)s',
                 '--ffmpeg-location', str(ffmpeg),
                 '--output', output_tpl,
                 url]
            )
            _log(f'job {job["id"]} indirme deneme {i} [{label}]')
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
                    _log(f'job {job["id"]} ERROR: {last_err[:300]}')
            code = proc.wait(timeout=30)

            if code == 0 and not failed:
                _log(f'job {job["id"]} indirme OK (deneme {i})')
                _note(job, f'dl {label}: OK')
                break

            if not _should_try_next_client(last_err):
                _log(f'job {job["id"]} tekrar denenemez hata, duruluyor')
                _note(job, f'dl {label}: DUR ({last_err[:120]})')
                break
            _log(f'job {job["id"]} deneme {i} başarısız, sonraki istemci deneniyor')
            _note(job, f'dl {label}: {last_err[:150]}')

        mp3_files = [f for f in os.listdir(job['dir']) if f.endswith('.mp3')]
        if not mp3_files:
            raise RuntimeError(_friendly_error(last_err))

        filename = f"{sanitize_title(title)}.mp3"
        size_mb = os.path.getsize(os.path.join(job['dir'], mp3_files[0])) / (1024 * 1024)

        job['filename'] = filename
        job['size_mb'] = round(size_mb, 2)
        job['progress'] = 100
        job['status'] = 'done'

    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e) or 'Dönüştürme başarısız'
        _log(f'job {job["id"]} FAILED: {job["error"][:300]}')
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
    # Sadece dosyaları sil; kayıt dursun ki /api/status gerçek hatayı gösterebilsin.
    # Kayıt temizliğini sweep_expired (TTL) yapar.
    try:
        if os.path.exists(job['dir']):
            shutil.rmtree(job['dir'], ignore_errors=True)
    except Exception:
        pass


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
