import sys
from pathlib import Path

import paths


def test_data_dir_windows():
    assert paths.data_dir("Windows", {"LOCALAPPDATA": r"C:\U\AppData\Local"}, Path("/h")) \
        == Path(r"C:\U\AppData\Local") / "MP3Donusturucum"


def test_data_dir_mac():
    assert paths.data_dir("Darwin", {}, Path("/h")) == Path("/h/Library/Application Support/MP3Donusturucum")


def test_data_dir_linux_xdg():
    assert paths.data_dir("Linux", {"XDG_DATA_HOME": "/x"}, Path("/h")) == Path("/x/mp3donusturucum")


def test_data_dir_linux_default():
    assert paths.data_dir("Linux", {}, Path("/h")) == Path("/h/.local/share/mp3donusturucum")


def test_resource_dir_dev():
    assert (paths.resource_dir() / "frontend" / "index.html").is_file()


def test_resource_dir_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/m", raising=False)
    assert paths.resource_dir() == Path("/m")
