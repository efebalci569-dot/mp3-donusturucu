import logging
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
