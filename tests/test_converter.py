import subprocess
from pathlib import Path

import pytest

import converter
import tools
from tools import ToolPaths

TP = ToolPaths(Path("/b/yt-dlp"), Path("/b/deno"), Path("/b/ffmpeg"))
URL = "https://youtu.be/jNQXAC9IVRw"


@pytest.fixture(autouse=True)
def fresh_jobs(monkeypatch):
    monkeypatch.setattr(converter, "_jobs", {})


def test_validate_url():
    for ok in ("https://youtu.be/jNQXAC9IVRw", "https://www.youtube.com/shorts/abcdefghijk",
               "https://music.youtube.com/watch?v=jNQXAC9IVRw"):
        assert converter.validate_url(ok)
    assert not converter.validate_url("https://vimeo.com/123456")


def test_info_cmd_uses_tool_paths():
    assert converter.info_cmd(TP, "U") == [
        str(TP.ytdlp), "--ignore-config", "--no-playlist",
        "--js-runtimes", f"deno:{TP.deno}", "--ffmpeg-location", str(TP.ffmpeg),
        "--dump-json", "U"]


def test_download_cmd_contains_mp3_flags():
    cmd = converter.download_cmd(TP, "U", "/j/%(id)s.%(ext)s")
    assert cmd[-1] == "U" and cmd[7:10] == ["-x", "--audio-format", "mp3"]
    assert cmd[cmd.index("--output") + 1] == "/j/%(id)s.%(ext)s"


def test_friendly_error():
    assert converter.friendly_error("ERROR: [youtube] x: No video formats found!") == converter.BLOCKED_MSG
    assert converter.friendly_error("ERROR: [youtube] x: HTTP Error 403: Forbidden") == converter.BLOCKED_MSG
    assert converter.friendly_error("ERROR: Private video") == "Bu video gizli (private)."
    assert converter.friendly_error("ERROR: Video unavailable") == "Video bulunamadı veya kaldırılmış."


def test_job_success_flow(tmp_path, monkeypatch):
    converter.configure(TP, tmp_path)
    monkeypatch.setattr(converter, "_run_info",
                        lambda cmd: subprocess.CompletedProcess(cmd, 0, '{"title": "Şarkı / Test"}', ""))

    def fake_dl(job, cmd):
        (Path(job["dir"]) / "abc.mp3").write_bytes(b"ID3" + b"0" * 1000)
        return True, ""
    monkeypatch.setattr(converter, "_popen_download", fake_dl)
    job = converter._new_job(URL)
    converter._run_job(job, URL)
    assert job["status"] == "done" and job["filename"] == "Şarkı Test.mp3" and job["progress"] == 100
    path, name = converter.build_download_response_path(job["id"])
    assert Path(path).read_bytes().startswith(b"ID3") and name == "Şarkı Test.mp3"


def test_job_blocked_calls_on_blocked(tmp_path, monkeypatch):
    calls = []
    converter.configure(TP, tmp_path, on_blocked=lambda: calls.append(1))
    monkeypatch.setattr(converter, "_run_info", lambda cmd: subprocess.CompletedProcess(
        cmd, 1, "", "WARNING: x\nERROR: [youtube] x: No video formats found!"))
    job = converter._new_job(URL)
    converter._run_job(job, URL)
    assert job["status"] == "error" and job["error"] == converter.BLOCKED_MSG and calls == [1]


def test_active_job_count(tmp_path):
    converter.configure(TP, tmp_path)
    a = converter._new_job(URL)
    converter._new_job(URL)
    assert converter.active_job_count() == 2
    a["status"] = "done"
    assert converter.active_job_count() == 1


class FakeProc:
    def __init__(self, lines):
        self.stdout = iter(lines)

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


def test_subprocesses_hidden(tmp_path, monkeypatch):
    converter.configure(TP, tmp_path)
    seen = []

    def fake_run(cmd, **kw):
        seen.append(kw)
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    def fake_popen(cmd, **kw):
        seen.append(kw)
        return FakeProc(["PROGRESS 50.0%\n"])
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    converter._run_info(["x"])
    job = converter._new_job(URL)
    ok, _ = converter._popen_download(job, ["x"])
    assert ok and job["progress"] == 50
    hidden = tools.hidden_subprocess_kwargs().items()
    assert len(seen) == 2 and all(hidden <= kw.items() for kw in seen)
