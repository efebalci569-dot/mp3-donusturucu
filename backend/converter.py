import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import tools

log = logging.getLogger('mp3.converter')

MAX_CONCURRENT_JOBS = 2
JOB_TTL_SECONDS = 1800
DOWNLOAD_TIMEOUT_SECONDS = 600

BLOCKED_MSG = 'YouTube indirmeyi engelledi. yt-dlp güncelleniyor; birkaç dakika sonra tekrar dene.'

YOUTUBE_PATTERN = re.compile(
    r'^https?://(www\.|music\.|m\.)?'
    r'(youtube\.com/(watch\?.*v=[\w\-]{5,}|shorts/[\w\-]{5,})'
    r'|youtu\.be/[\w\-]{5,})'
)

_lock = threading.Lock()
_jobs = {}
_executor = None
_tools = None
_jobs_dir = None
_on_blocked = lambda: None  # noqa: E731


def configure(tool_paths, jobs_dir, on_blocked=lambda: None):
    global _tools, _jobs_dir, _on_blocked
    _tools = tool_paths
    _jobs_dir = Path(jobs_dir)
    _jobs_dir.mkdir(parents=True, exist_ok=True)
    _on_blocked = on_blocked


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


def base_args(tp):
    return [str(tp.ytdlp), '--ignore-config', '--no-playlist',
            '--js-runtimes', f'deno:{tp.deno}',
            '--ffmpeg-location', str(tp.ffmpeg)]


def info_cmd(tp, url):
    return base_args(tp) + ['--dump-json', url]


def download_cmd(tp, url, output_tpl):
    return base_args(tp) + [
        '-x', '--audio-format', 'mp3', '--audio-quality', '0',
        '--newline',
        '--progress-template', 'download:PROGRESS %(progress._percent_str)s',
        '--output', output_tpl,
        url,
    ]


def is_blocked(raw):
    low = (raw or '').lower()
    return any(m in low for m in ('403', 'forbidden', 'no video formats', 'sign in to confirm'))


def friendly_error(raw):
    raw = (raw or '').strip()
    low = raw.lower()
    if not raw:
        return 'Video bilgisi alınamadı'
    if is_blocked(raw):
        return BLOCKED_MSG
    if 'private' in low:
        return 'Bu video gizli (private).'
    if 'unavailable' in low or 'not available' in low:
        return 'Video bulunamadı veya kaldırılmış.'
    if 'age' in low and ('confirm' in low or 'sign' in low):
        return 'Bu video yaş doğrulaması istiyor, dönüştürülemez.'
    return raw[:300]


def _extract_error(text, default):
    for line in (text or '').split('\n'):
        if 'ERROR' in line:
            return line.strip()
    return default


def _run_info(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=60, **tools.hidden_subprocess_kwargs())


def _popen_download(job, cmd):
    last_err = 'İndirme başarısız'
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='replace',
        **tools.hidden_subprocess_kwargs()
    )
    started = time.time()
    failed = False
    for line in proc.stdout:
        if time.time() - started > DOWNLOAD_TIMEOUT_SECONDS:
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
            last_err = line
            log.warning('job %s ERROR: %s', job['id'], last_err[:300])
    code = proc.wait(timeout=30)
    return (code == 0 and not failed), last_err


def _new_job(url):
    job_id = uuid.uuid4().hex
    job_dir = _jobs_dir / f'job_{job_id}'
    job_dir.mkdir(parents=True, exist_ok=True)
    job = {
        'id': job_id,
        'dir': str(job_dir),
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
    return job


def start_job(url):
    job = _new_job(url)
    _get_executor().submit(_run_job, job, url)
    return job


def _fail_with(raw):
    if is_blocked(raw):
        _on_blocked()
    raise RuntimeError(friendly_error(raw))


def _run_job(job, url):
    job['status'] = 'processing'
    try:
        r = _run_info(info_cmd(_tools, url))
        if r.returncode != 0:
            _fail_with(_extract_error(r.stderr, 'Video bilgisi alınamadı'))
        try:
            info = json.loads(r.stdout.strip().split('\n')[0])
        except Exception:
            raise RuntimeError('Video bilgisi çözümlenemedi')
        title = info.get('title') or 'Bilinmeyen Video'
        job['title'] = title

        output_tpl = os.path.join(job['dir'], '%(id)s.%(ext)s')
        ok, last_err = _popen_download(job, download_cmd(_tools, url, output_tpl))
        mp3_files = [f for f in os.listdir(job['dir']) if f.endswith('.mp3')]
        if not ok or not mp3_files:
            _fail_with(last_err)

        size_mb = os.path.getsize(os.path.join(job['dir'], mp3_files[0])) / (1024 * 1024)
        job['filename'] = f'{sanitize_title(title)}.mp3'
        job['size_mb'] = round(size_mb, 2)
        job['progress'] = 100
        job['status'] = 'done'
    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e) or 'Dönüştürme başarısız'
        log.warning('job %s FAILED: %s', job['id'], job['error'][:300])
        _cleanup_job_dir(job)


def get_job(job_id):
    with _lock:
        return _jobs.get(job_id)


def active_job_count():
    with _lock:
        return sum(1 for j in _jobs.values() if j['status'] in ('queued', 'processing'))


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
    shutil.rmtree(job['dir'], ignore_errors=True)


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
    threading.Thread(target=_janitor_loop, daemon=True).start()
