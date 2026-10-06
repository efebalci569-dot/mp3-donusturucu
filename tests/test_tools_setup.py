import subprocess
import urllib.error
from pathlib import Path

import pytest

import tools
from helpers import FakeResponse, fake_opener, fail_run, wait_until, zip_bytes


def version_run(text):
    calls = []

    def run(args, **kw):
        calls.append((args, kw))
        return subprocess.CompletedProcess(args, 0, text, "")
    run.calls = calls
    return run


@pytest.fixture
def ffmpeg_stub(tmp_path, monkeypatch):
    src = tmp_path / "ffmpeg-src"
    src.write_bytes(b"ff")
    monkeypatch.setattr(tools, "bundled_ffmpeg", lambda: src)
    return src


def test_ensure_ytdlp_downloads_when_missing(tmp_path):
    urls = []

    def opener(url, timeout):
        urls.append(url)
        return FakeResponse(b"bin")
    p = tools.ensure_ytdlp(tmp_path, tools.SetupState(), "Linux", opener=opener)
    assert urls == ["https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux"]
    assert p == tmp_path / "yt-dlp" and p.read_bytes() == b"bin"


def test_ensure_ytdlp_skips_when_present(tmp_path):
    (tmp_path / "yt-dlp.exe").write_bytes(b"bin")

    def opener(url, timeout):
        raise AssertionError("indirmemeliydi")
    assert tools.ensure_ytdlp(tmp_path, tools.SetupState(), "Windows", opener=opener) \
        == tmp_path / "yt-dlp.exe"


def test_parse_deno_version():
    assert tools.parse_deno_version("deno 2.9.7 (stable, release, x86_64-pc-windows-msvc)\nv8 14.0") == (2, 9, 7)
    assert tools.parse_deno_version("garip çıktı") is None


def test_ensure_deno_extracts_zip(tmp_path):
    p = tools.ensure_deno(tmp_path, tools.SetupState(), "Linux", "x86_64",
                          opener=fake_opener(FakeResponse(zip_bytes({"deno": b"DENO"}))), run=fail_run)
    assert p == tmp_path / "deno" and p.read_bytes() == b"DENO"
    assert not (tmp_path / "deno.zip").exists()


def test_ensure_deno_replaces_old_version(tmp_path):
    (tmp_path / "deno").write_bytes(b"OLD")
    p = tools.ensure_deno(tmp_path, tools.SetupState(), "Linux", "x86_64",
                          opener=fake_opener(FakeResponse(zip_bytes({"deno": b"NEW"}))),
                          run=version_run("deno 2.2.0 (stable)"))
    assert p.read_bytes() == b"NEW"


def test_ensure_deno_keeps_new_enough_hidden(tmp_path):
    (tmp_path / "deno.exe").write_bytes(b"OK")
    run = version_run("deno 2.3.0 (stable)")

    def opener(url, timeout):
        raise AssertionError("indirmemeliydi")
    p = tools.ensure_deno(tmp_path, tools.SetupState(), "Windows", "AMD64", opener=opener, run=run)
    assert p.read_bytes() == b"OK"
    assert run.calls[0][0] == [str(tmp_path / "deno.exe"), "--version"]
    assert tools.hidden_subprocess_kwargs().items() <= run.calls[0][1].items()


def test_run_setup_network_error_sets_message(tmp_path, ffmpeg_stub):
    def opener(url, timeout):
        raise urllib.error.URLError("yok")
    st = tools.SetupState()
    assert tools.run_setup(st, tmp_path / "bin", "Linux", "x86_64", opener=opener, run=fail_run) is None
    assert st.to_dict()["error"] == tools.SETUP_NETWORK_MSG and st.ready is False
    # yarıda kalan adım "indiriliyor %0"da takılı görünmemeli
    assert st.to_dict()["steps"]["ytdlp"]["state"] == "error"


def test_run_setup_success_returns_paths(tmp_path, ffmpeg_stub):
    def opener(url, timeout):
        if url.endswith(".zip"):
            return FakeResponse(zip_bytes({"deno": b"DENO"}))
        return FakeResponse(b"YTDLP")
    st = tools.SetupState()
    bin_dir = tmp_path / "bin"
    tp = tools.run_setup(st, bin_dir, "Linux", "x86_64", opener=opener, run=fail_run)
    assert tp == tools.ToolPaths(bin_dir / "yt-dlp", bin_dir / "deno", bin_dir / "ffmpeg")
    assert st.ready is True


def test_updater_rate_limit_and_hidden():
    now = [1000.0]
    calls = []

    def run(args, **kw):
        calls.append((args, kw))
    u = tools.YtdlpUpdater(Path("/b/yt-dlp"), clock=lambda: now[0], run=run)
    assert u.trigger() is True
    wait_until(lambda: not u.is_running)
    now[0] += 10
    assert u.trigger() is False
    now[0] += 1800
    assert u.trigger() is True
    wait_until(lambda: not u.is_running)
    assert calls[0][0] == [str(Path("/b/yt-dlp")), "-U"]
    assert tools.hidden_subprocess_kwargs().items() <= calls[0][1].items()
    assert len(calls) == 2
