import instance
from helpers import json_opener, raising_opener


def test_instance_roundtrip_and_corrupt(tmp_path):
    f = tmp_path / "instance.json"
    instance.write_port(f, 5123)
    assert instance.read_port(f) == 5123
    f.write_text("{bozuk")
    assert instance.read_port(f) is None
    assert instance.read_port(tmp_path / "yok.json") is None


def test_clear_keeps_other_instance(tmp_path):
    f = tmp_path / "instance.json"
    instance.write_port(f, 1)
    instance.clear(f, 2)
    assert f.exists()
    instance.clear(f, 1)
    assert not f.exists()


def test_probe():
    assert instance.probe(1, opener=json_opener({"app": "mp3donusturucum"})) is True
    assert instance.probe(1, opener=json_opener({"app": "baska"})) is False
    assert instance.probe(1, opener=raising_opener) is False


def test_find_running_ignores_dead(tmp_path):
    f = tmp_path / "instance.json"
    instance.write_port(f, 5123)
    assert instance.find_running(f, probe=lambda p: False) is None
    assert instance.find_running(f, probe=lambda p: True) == 5123
    assert instance.find_running(tmp_path / "yok.json", probe=lambda p: True) is None
