import updates
from helpers import boom


def test_newer_release():
    assert updates.check_latest("1.0.0", fetch=lambda u: {"tag_name": "v1.1.0", "html_url": "H"}) \
        == {"available": True, "version": "v1.1.0", "url": "H"}


def test_same_release():
    assert updates.check_latest("1.1.0", fetch=lambda u: {"tag_name": "v1.1.0", "html_url": "H"}) is None


def test_dev_version_skips_fetch():
    assert updates.check_latest("0.0.0-dev", fetch=boom) is None


def test_fetch_error():
    assert updates.check_latest("1.0.0", fetch=boom) is None


def test_parse_version():
    assert updates.parse_version("v1.10.2") == (1, 10, 2)
    assert updates.parse_version("0.0.0-ci.5") is None
