from pathlib import Path

import pytest

import converter
from app import create_app
from lifecycle import Lifecycle
from tools import SetupState, ToolPaths

B = "http://127.0.0.1:5000"
TP = ToolPaths(Path("/b/yt-dlp"), Path("/b/deno"), Path("/b/ffmpeg"))


class Recorder:
    def __init__(self):
        self.count = 0

    def __call__(self):
        self.count += 1

    def heartbeat(self):
        self.count += 1


def make_client(setup=None, lifecycle=None, retry=None, update=lambda: None):
    app = create_app(5000, setup or SetupState(), lifecycle or Lifecycle(), retry or Recorder(), update)
    return app.test_client()


@pytest.fixture
def client():
    return make_client()


@pytest.fixture
def ready_client(tmp_path):
    st = SetupState()
    for n in st.STEPS:
        st.set_step(n, "ready", 100)
    converter.configure(TP, tmp_path)
    return make_client(setup=st)


def test_rejects_foreign_host(client):
    assert client.get("/api/health", base_url="http://evil.com:5000").status_code == 403
    assert client.get("/api/health", base_url="http://127.0.0.1:6000").status_code == 403
    assert client.get("/api/health", base_url=B).status_code == 200
    assert client.get("/api/health", base_url="http://localhost:5000").status_code == 200


def test_health_identifies_app(client):
    assert client.get("/api/health", base_url=B).json["app"] == "mp3donusturucum"


def test_index_served(client):
    assert "MP3 DÖNÜŞTÜRÜCÜM" in client.get("/", base_url=B).get_data(as_text=True)


def test_convert_while_setup_not_ready_returns_503(client):
    r = client.post("/api/convert", json={"url": "https://youtu.be/jNQXAC9IVRw"}, base_url=B)
    assert r.status_code == 503 and "hazırlanıyor" in r.json["error"]


def test_convert_rejects_non_json_body(ready_client):
    r = ready_client.post("/api/convert", data="url=https://youtu.be/jNQXAC9IVRw",
                          content_type="text/plain", base_url=B)
    assert r.status_code == 400


def test_convert_starts_job(ready_client, monkeypatch):
    monkeypatch.setattr(converter, "start_job", lambda url: {"id": "abc"})
    r = ready_client.post("/api/convert", json={"url": "https://youtu.be/jNQXAC9IVRw"}, base_url=B)
    assert r.status_code == 202 and r.json == {"success": True, "job_id": "abc"}


def test_heartbeat_calls_lifecycle():
    lc = Recorder()
    r = make_client(lifecycle=lc).post("/api/heartbeat", base_url=B)
    assert r.status_code == 204 and lc.count == 1


def test_setup_includes_update():
    upd = {"available": True, "version": "v1.1.0", "url": "H"}
    r = make_client(update=lambda: upd).get("/api/setup", base_url=B)
    assert r.json["update"]["available"] is True and r.json["ready"] is False


def test_setup_retry_calls_callback():
    retry = Recorder()
    r = make_client(retry=retry).post("/api/setup/retry", base_url=B)
    assert r.status_code == 202 and retry.count == 1


def test_download_non_ascii_filename_header(ready_client, tmp_path, monkeypatch):
    f = tmp_path / "a.mp3"
    f.write_bytes(b"ID3")
    monkeypatch.setattr(converter, "build_download_response_path", lambda j: (str(f), "Şarkı.mp3"))
    r = ready_client.get("/api/download/x", base_url=B)
    assert "filename*=UTF-8''%C5%9Eark%C4%B1.mp3" in r.headers["Content-Disposition"]
    r.close()
