import io
import json
import time
import zipfile


class FakeResponse:
    def __init__(self, data, fail_after=None):
        self._buf = io.BytesIO(data)
        self._fail_after = fail_after
        self._read = 0
        self.headers = {'Content-Length': str(len(data))}

    def read(self, n=-1):
        if self._fail_after is not None and self._read >= self._fail_after:
            raise OSError('bağlantı koptu')
        chunk = self._buf.read(n)
        self._read += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_opener(resp):
    return lambda url, timeout: resp


def zip_bytes(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def fail_run(*a, **k):
    raise AssertionError('run çağrılmamalıydı')


def wait_until(pred, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return
        time.sleep(0.01)
    raise AssertionError('koşul zamanında gerçekleşmedi')


def json_opener(obj):
    return lambda url, timeout: FakeResponse(json.dumps(obj).encode())


def raising_opener(url, timeout):
    raise OSError('erişilemedi')


def boom(*a):
    raise RuntimeError('çağrılmamalıydı')
