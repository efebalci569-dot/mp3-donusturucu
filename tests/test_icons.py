from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "packaging" / "icons"


def test_ico_has_all_windows_sizes():
    with Image.open(ICONS / "app.ico") as im:
        sizes = im.info["sizes"]
    assert {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)} <= set(sizes)


def test_icns_is_valid_macos_icon():
    with Image.open(ICONS / "app.icns") as im:
        assert im.format == "ICNS" and im.size[0] >= 512


def test_favicons_exist_for_app_and_site():
    for page in ("frontend", "site"):
        with Image.open(ROOT / page / "favicon.png") as im:
            assert im.size == (128, 128) and im.mode == "RGBA"
        html = (ROOT / page / "index.html").read_text(encoding="utf-8")
        assert '<link rel="icon" type="image/png" href="/favicon.png">' in html


def test_packaging_uses_icons():
    spec = (ROOT / "packaging" / "mp3donusturucum.spec").read_text(encoding="utf-8")
    assert "app.ico" in spec and "app.icns" in spec
    iss = (ROOT / "packaging" / "windows" / "installer.iss").read_text(encoding="utf-8-sig")
    assert r"SetupIconFile=..\icons\app.ico" in iss
