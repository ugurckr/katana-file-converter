"""İkon/görsel format dönüştürücüleri: icns, ico, png.

Tamamı Pillow ile yapılır, ek bir dış bağımlılık gerekmez.
"""

from pathlib import Path

from PIL import Image

from .base import register

# ICO formatı için yaygın kullanılan standart çözünürlükler.
STANDARD_ICO_SIZES = [256, 128, 64, 48, 32, 16]


def _save_png(img: Image.Image, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGBA").save(dst, format="PNG")


def _save_ico(img: Image.Image, dst: Path) -> None:
    img = img.convert("RGBA")
    sizes = [(s, s) for s in STANDARD_ICO_SIZES if s <= max(img.size)]
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, format="ICO", sizes=sizes or [(256, 256)])


def _save_icns(img: Image.Image, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGBA").save(dst, format="ICNS")


@register(".icns", ".png", "PNG görsel (en yüksek çözünürlük)")
def icns_to_png(src: Path, dst: Path) -> None:
    with Image.open(src) as img:
        _save_png(img, dst)


@register(".icns", ".ico", "Windows ICO ikonu")
def icns_to_ico(src: Path, dst: Path) -> None:
    with Image.open(src) as img:
        _save_ico(img, dst)


@register(".png", ".icns", "macOS ICNS ikonu")
def png_to_icns(src: Path, dst: Path) -> None:
    with Image.open(src) as img:
        _save_icns(img, dst)


@register(".png", ".ico", "Windows ICO ikonu")
def png_to_ico(src: Path, dst: Path) -> None:
    with Image.open(src) as img:
        _save_ico(img, dst)


@register(".ico", ".png", "PNG görsel")
def ico_to_png(src: Path, dst: Path) -> None:
    with Image.open(src) as img:
        _save_png(img, dst)


@register(".ico", ".icns", "macOS ICNS ikonu")
def ico_to_icns(src: Path, dst: Path) -> None:
    with Image.open(src) as img:
        _save_icns(img, dst)