import logging
import os
import sys

import pytest

import launcher


@pytest.fixture(autouse=True)
def restore_logging():
    # launcher kök günlükçüye dosya işleyicisi ekler; testler arasında sızmasın.
    root = logging.getLogger()
    before = list(root.handlers)
    yield
    for h in list(root.handlers):
        if h not in before:
            root.removeHandler(h)
            h.close()


def test_smoke_test_passes():
    assert launcher.main(["--smoke-test"]) == 0


def test_smoke_test_with_none_streams(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert launcher.main(["--smoke-test"]) == 0


def test_second_instance_opens_browser(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(launcher.paths, "data_dir", lambda *a, **k: tmp_path)
    monkeypatch.setattr(launcher.instance, "find_running", lambda path, **k: 5123)
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)
    assert launcher.main([]) == 0 and opened == ["http://127.0.0.1:5123/"]


def test_smoke_test_fails_without_ca_bundle(monkeypatch):
    # Paketlenmiş uygulamada certifi'nin CA dosyası yoksa macOS/Linux'ta hiçbir şey inemez.
    import certifi
    monkeypatch.setattr(certifi, "where", lambda: "/yok/cacert.pem")
    assert launcher.main(["--smoke-test"]) == 1


def test_linux_frozen_restores_library_path(monkeypatch):
    # PyInstaller LD_LIBRARY_PATH'i paket klasörüne çevirir; tarayıcı/yt-dlp/deno bunu miras almamalı.
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/paket")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/asil")
    launcher._restore_linux_library_path()
    assert os.environ["LD_LIBRARY_PATH"] == "/asil"


def test_linux_frozen_drops_library_path_without_original(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/paket")
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    launcher._restore_linux_library_path()
    assert "LD_LIBRARY_PATH" not in os.environ
