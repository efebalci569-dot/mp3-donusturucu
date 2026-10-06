import os
import subprocess

import pytest

import tools
from helpers import FakeResponse, fake_opener


def test_ytdlp_asset():
    assert [tools.ytdlp_asset(s) for s in ("Windows", "Darwin", "Linux")] \
        == ["yt-dlp.exe", "yt-dlp_macos", "yt-dlp_linux"]


@pytest.mark.parametrize("system,machine,asset", [
    ("Windows", "AMD64", "deno-x86_64-pc-windows-msvc.zip"),
    ("Windows", "ARM64", "deno-aarch64-pc-windows-msvc.zip"),
    ("Darwin", "arm64", "deno-aarch64-apple-darwin.zip"),
    ("Darwin", "x86_64", "deno-x86_64-apple-darwin.zip"),
    ("Linux", "x86_64", "deno-x86_64-unknown-linux-gnu.zip"),
    ("Linux", "aarch64", "deno-aarch64-unknown-linux-gnu.zip"),
])
def test_deno_asset(system, machine, asset):
    assert tools.deno_asset(system, machine) == asset


def test_deno_asset_unsupported():
    with pytest.raises(tools.UnsupportedPlatform):
        tools.deno_asset("Linux", "armv7l")


def test_download_writes_file_and_reports_progress(tmp_path):
    dest = tmp_path / "ş ğ ü klasör" / "yt-dlp"
    seen = []
    tools.download("u", dest, seen.append, opener=fake_opener(FakeResponse(b"x" * 200_000)))
    assert dest.read_bytes() == b"x" * 200_000 and seen[-1] == 100
    assert not dest.with_name("yt-dlp.part").exists()
    if os.name != "nt":
        assert os.access(dest, os.X_OK)


def test_download_failure_leaves_no_file(tmp_path):
    dest = tmp_path / "yt-dlp"
    with pytest.raises(OSError):
        tools.download("u", dest, lambda p: None,
                       opener=fake_opener(FakeResponse(b"x" * 200_000, fail_after=65_536)))
    assert not dest.exists() and not dest.with_name("yt-dlp.part").exists()


def test_setup_state_ready_and_dict():
    s = tools.SetupState()
    assert s.ready is False
    for n in s.STEPS:
        s.set_step(n, "ready", 100)
    assert s.ready is True and s.to_dict()["steps"]["deno"] == {"state": "ready", "progress": 100}
    s.fail("hata")
    assert s.ready is False and s.to_dict()["error"] == "hata"


def test_ensure_ffmpeg_copies_bundled(tmp_path, monkeypatch):
    src = tmp_path / "ffmpeg-win-x86_64-v7.1.exe"
    src.write_bytes(b"ff")
    monkeypatch.setattr(tools, "bundled_ffmpeg", lambda: src)
    out = tools.ensure_ffmpeg(tmp_path / "bin", tools.SetupState(), "Windows")
    assert out == tmp_path / "bin" / "ffmpeg.exe" and out.read_bytes() == b"ff"


def test_ensure_ffmpeg_missing_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "bundled_ffmpeg", lambda: None)
    with pytest.raises(tools.ToolError, match="FFmpeg bulunamadı"):
        tools.ensure_ffmpeg(tmp_path, tools.SetupState(), "Linux")


def test_hidden_kwargs():
    expected = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    assert tools.hidden_subprocess_kwargs() == expected
