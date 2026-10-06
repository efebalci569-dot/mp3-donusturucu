import json
import os
import urllib.request
from pathlib import Path

from paths import APP_ID


def read_port(path):
    try:
        port = json.loads(Path(path).read_text(encoding='utf-8'))['port']
        return int(port)
    except Exception:
        return None


def write_port(path, port):
    Path(path).write_text(json.dumps({'port': port, 'pid': os.getpid()}), encoding='utf-8')


def clear(path, port):
    # Başka (daha yeni) bir kopyanın kaydını silme.
    if read_port(path) == port:
        Path(path).unlink(missing_ok=True)


def probe(port, timeout=2.0, opener=urllib.request.urlopen):
    try:
        with opener(f'http://127.0.0.1:{port}/api/health', timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8')).get('app') == APP_ID
    except Exception:
        return False


def find_running(path, probe=probe):
    port = read_port(path)
    if port is not None and probe(port):
        return port
    return None
