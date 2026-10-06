import argparse
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

from werkzeug.serving import make_server

import converter
import instance
import paths
import tools
import updates
from app import create_app
from lifecycle import Lifecycle
from version import __version__

log = logging.getLogger('mp3.launcher')


def _ensure_std_streams():
    # Pencereli PyInstaller paketinde stdout/stderr None olur; yazan her şey çökmesin.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')


def _setup_logging(log_path):
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if log_path is None:
        handler = logging.StreamHandler(sys.stderr)
    else:
        handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=1, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    root.addHandler(handler)
    # Her heartbeat/poll isteğini günlüğe yazmasın.
    logging.getLogger('werkzeug').setLevel(logging.WARNING)


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _make_server(setup, lifecycle, retry_setup, update_info):
    last_error = None
    for _ in range(2):
        port = _free_port()
        app = create_app(port, setup, lifecycle, retry_setup, update_info)
        try:
            return make_server('127.0.0.1', port, app, threaded=True), port
        except OSError as e:
            last_error = e
    raise last_error


def _smoke_test():
    base = Path(tempfile.mkdtemp(prefix='mp3-smoke-'))
    try:
        setup = tools.SetupState()
        ffmpeg = tools.ensure_ffmpeg(paths.bin_dir(base), setup, platform.system())
        r = subprocess.run([str(ffmpeg), '-version'], capture_output=True, timeout=60,
                           **tools.hidden_subprocess_kwargs())
        if r.returncode != 0:
            log.error('ffmpeg çalışmadı (kod %s)', r.returncode)
            return 1
        server, port = _make_server(setup, Lifecycle(), lambda: None, lambda: None)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            ok = instance.probe(port, timeout=10)
        finally:
            server.shutdown()
            server.server_close()
        log.info('smoke test %s', 'OK' if ok else 'FAIL')
        return 0 if ok else 1
    except Exception:
        log.exception('smoke test hata')
        return 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _serve(base, inst_file, open_browser):
    setup = tools.SetupState()
    lifecycle = Lifecycle()
    bin_dir = paths.bin_dir(base)
    jobs_dir = paths.jobs_dir(base)
    update = {'info': None}
    setup_thread = {'t': None}
    setup_lock = threading.Lock()

    def run_setup():
        tp = tools.run_setup(setup, bin_dir)
        if tp:
            updater = tools.YtdlpUpdater(tp.ytdlp)
            converter.configure(tp, jobs_dir, on_blocked=updater.trigger)
            updater.trigger()
            log.info('kurulum tamam')

    def start_setup():
        with setup_lock:
            t = setup_thread['t']
            if t is not None and t.is_alive():
                return
            setup_thread['t'] = threading.Thread(target=run_setup, daemon=True)
            setup_thread['t'].start()

    def retry_setup():
        if setup.to_dict()['error']:
            start_setup()

    def check_updates():
        update['info'] = updates.check_latest(__version__)

    server, port = _make_server(setup, lifecycle, retry_setup, lambda: update['info'])
    instance.write_port(inst_file, port)
    start_setup()
    threading.Thread(target=check_updates, daemon=True).start()
    converter.start_janitor()

    def watch():
        while True:
            time.sleep(5)
            if lifecycle.should_exit(converter.active_job_count()):
                log.info('sekme kapalı ve iş yok, uygulama kapanıyor')
                server.shutdown()
                return
    threading.Thread(target=watch, daemon=True).start()

    url = f'http://127.0.0.1:{port}/'
    log.info('MP3 Dönüştürücüm %s başladı: %s', __version__, url)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception as e:
            log.warning('tarayıcı açılamadı: %s', e)
    try:
        server.serve_forever()
    finally:
        instance.clear(inst_file, port)
        server.server_close()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='MP3Donusturucum')
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)
    _ensure_std_streams()

    if args.smoke_test:
        _setup_logging(None)
        return _smoke_test()

    base = paths.data_dir()
    for d in (base, paths.bin_dir(base)):
        d.mkdir(parents=True, exist_ok=True)
    _setup_logging(paths.log_file(base))
    inst_file = paths.instance_file(base)

    running = instance.find_running(inst_file)
    if running:
        webbrowser.open(f'http://127.0.0.1:{running}/')
        return 0

    # Önceki (kapanırken yarım kalmış) oturumların geçici dosyaları
    shutil.rmtree(paths.jobs_dir(base), ignore_errors=True)
    paths.jobs_dir(base).mkdir(parents=True, exist_ok=True)
    return _serve(base, inst_file, open_browser=not args.no_browser)


if __name__ == '__main__':
    sys.exit(main())
