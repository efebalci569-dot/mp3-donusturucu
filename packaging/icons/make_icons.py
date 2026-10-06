"""Uygulama logosunu üretir: koyu yuvarlak kare üzerinde yeşil çift nota.

Çıktılar (depoya eklenir, CI bu betiği çalıştırmaz):
  packaging/icons/app.ico    Windows (16–256 px)
  packaging/icons/app.icns   macOS
  packaging/icons/app.png    1024 px ana görsel
  frontend/favicon.png, site/favicon.png   tarayıcı sekmesi (128 px)

Kullanım: python packaging/icons/make_icons.py   (Pillow gerekir)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent

S = 1024
BG_TOP = (24, 24, 36)
BG_BOTTOM = (10, 10, 15)
BORDER = (42, 42, 62, 255)      # --border
GREEN_A = (0, 217, 95)          # --accent
GREEN_B = (0, 255, 136)
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _vertical_gradient(top, bottom):
    column = Image.new('RGB', (1, S))
    for y in range(S):
        t = y / (S - 1)
        column.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return column.resize((S, S))


def _diagonal_gradient(a, b):
    small = Image.new('RGB', (64, 64))
    for y in range(64):
        for x in range(64):
            t = (x + (63 - y)) / 126
            small.putpixel((x, y), tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    return small.resize((S, S), Image.BILINEAR)


def _note_mask():
    # ♫: iki eğik nota başı, iki sap ve eğimli bir kiriş
    mask = Image.new('L', (S, S), 0)
    heads = [(345, 722), (705, 650)]
    for cx, cy in heads:
        head = Image.new('L', (S, S), 0)
        ImageDraw.Draw(head).ellipse((cx - 128, cy - 92, cx + 128, cy + 92), fill=255)
        head = head.rotate(22, center=(cx, cy), resample=Image.BICUBIC)
        mask = Image.composite(Image.new('L', (S, S), 255), mask, head)
    d = ImageDraw.Draw(mask)
    stem_w, beam_h = 58, 118
    (lx, ly), (rx, ry) = heads
    l_stem, r_stem = lx + 76, rx + 76
    top_l, top_r = 262, 190
    d.rectangle((l_stem, top_l, l_stem + stem_w, ly - 20), fill=255)
    d.rectangle((r_stem, top_r, r_stem + stem_w, ry - 20), fill=255)
    d.polygon([(l_stem, top_l), (r_stem + stem_w, top_r),
               (r_stem + stem_w, top_r + beam_h), (l_stem, top_l + beam_h)], fill=255)
    return mask


def build_icon():
    radius = int(S * 0.22)
    rounded = Image.new('L', (S, S), 0)
    ImageDraw.Draw(rounded).rounded_rectangle((0, 0, S - 1, S - 1), radius=radius, fill=255)

    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    img.paste(_vertical_gradient(BG_TOP, BG_BOTTOM), (0, 0), rounded)

    mask = _note_mask()
    glow = mask.filter(ImageFilter.GaussianBlur(40)).point(lambda v: int(v * 0.45))
    glow_layer = Image.new('RGBA', (S, S), GREEN_A + (0,))
    glow_layer.putalpha(Image.composite(glow, Image.new('L', (S, S), 0), rounded))
    img = Image.alpha_composite(img, glow_layer)

    notes = _diagonal_gradient(GREEN_A, GREEN_B).convert('RGBA')
    notes.putalpha(mask)
    img = Image.alpha_composite(img, notes)

    border = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle((6, 6, S - 7, S - 7), radius=radius - 6,
                                             outline=BORDER, width=12)
    return Image.alpha_composite(img, border)


def main():
    icon = build_icon()
    icon.save(OUT / 'app.png')
    icon.save(OUT / 'app.ico', sizes=ICO_SIZES)
    icon.save(OUT / 'app.icns')
    favicon = icon.resize((128, 128), Image.LANCZOS)
    for page in ('frontend', 'site'):
        favicon.save(ROOT / page / 'favicon.png')
    print('logo dosyaları üretildi')


if __name__ == '__main__':
    main()
