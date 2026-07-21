"""Görsel dönüştürücüleri: svg, webp, heic, bmp, tiff, png/jpg -> pdf.
Pillow + svglib/reportlab ile çalışır, harici araç gerekmez."""

import base64
import io
from pathlib import Path

import pillow_heif
from PIL import Image, ImageDraw, ImageFont
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

from . import options
from .base import register

pillow_heif.register_heif_opener()


def _apply_resize(img: Image.Image) -> Image.Image:
    """resize ayarına göre boyutlandırır: 'GxY', tek boyut (oran korunur) ya da 'N%'."""
    spec = options.get("resize")
    if not spec:
        return img
    spec = str(spec).strip().lower()
    w, h = img.size
    try:
        if spec.endswith("%"):
            factor = float(spec[:-1]) / 100.0
            new = (max(1, round(w * factor)), max(1, round(h * factor)))
        elif "x" in spec:
            a, _, b = spec.partition("x")
            tw = int(a) if a.strip() else 0
            th = int(b) if b.strip() else 0
            if tw and th:
                new = (tw, th)
            elif tw:                       # yalnızca genişlik
                new = (tw, max(1, round(h * tw / w)))
            else:                          # yalnızca yükseklik
                new = (max(1, round(w * th / h)), th)
        else:
            return img
    except (ValueError, ZeroDivisionError):
        return img
    return img.resize(new, Image.LANCZOS)


def _apply_watermark(img: Image.Image) -> Image.Image:
    """watermark metnini sağ-alt köşeye yarı saydam basar."""
    text = options.get("watermark")
    if not text:
        return img
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font_size = max(14, base.size[0] // 24)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), str(text), font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margin = max(8, font_size // 2)
    pos = (base.size[0] - tw - margin, base.size[1] - th - margin * 2)
    draw.text(pos, str(text), font=font, fill=(255, 255, 255, 160))
    return Image.alpha_composite(base, overlay)


def _postprocess(img: Image.Image, mode: str) -> Image.Image:
    """Kaydetmeden önce resize + watermark uygular ve renk moduna çevirir."""
    img = _apply_resize(img)
    img = _apply_watermark(img)
    return img.convert(mode)


def _convert_via_pillow(src: Path, dst: Path, mode: str, fmt: str, **save_kwargs) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        _postprocess(img, mode).save(dst, format=fmt, **save_kwargs)


def _flatten_to_jpg(src: Path, dst: Path) -> None:
    """Şeffaf pikselleri beyaz zemine bindirip JPEG'e çevirir; düz
    convert("RGB") şeffaflığı siyaha boyardı."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img = _apply_watermark(_apply_resize(img))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.getchannel("A"))
            img = background
        else:
            img = img.convert("RGB")
        img.save(dst, format="JPEG", quality=options.get("jpeg_quality"))


def _svg_to_raster(src: Path, dst: Path, fmt: str) -> None:
    drawing = svg2rlg(str(src))
    dst.parent.mkdir(parents=True, exist_ok=True)
    renderPM.drawToFile(drawing, str(dst), fmt=fmt)


def _raster_to_svg(src: Path, dst: Path) -> None:
    # Gerçek vektörleştirme yapmaz (potrace/vtracer gerektirir); PNG'yi
    # <image> etiketiyle bir SVG konteynerine gömer.
    with Image.open(src) as img:
        img = img.convert("RGBA")
        width, height = img.size
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    svg_content = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        f'  <image width="{width}" height="{height}" '
        f'href="data:image/png;base64,{b64}"/>\n'
        f"</svg>\n"
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(svg_content, encoding="utf-8")


@register(".svg", ".png", "PNG görsel")
def svg_to_png(src: Path, dst: Path) -> None:
    _svg_to_raster(src, dst, fmt="PNG")


@register(".svg", ".jpg", "JPEG görsel")
def svg_to_jpg(src: Path, dst: Path) -> None:
    _svg_to_raster(src, dst, fmt="JPG")


@register(".png", ".svg", "SVG konteyner (gömülü PNG)")
def png_to_svg(src: Path, dst: Path) -> None:
    _raster_to_svg(src, dst)


@register(".jpg", ".svg", "SVG konteyner (gömülü PNG)")
def jpg_to_svg(src: Path, dst: Path) -> None:
    _raster_to_svg(src, dst)


@register(".jpeg", ".svg", "SVG konteyner (gömülü PNG)")
def jpeg_to_svg(src: Path, dst: Path) -> None:
    _raster_to_svg(src, dst)


@register(".png", ".pdf", "PDF belge")
def png_to_pdf(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGB", fmt="PDF")


@register(".jpg", ".pdf", "PDF belge")
def jpg_to_pdf(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGB", fmt="PDF")


@register(".jpeg", ".pdf", "PDF belge")
def jpeg_to_pdf(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGB", fmt="PDF")


@register(".webp", ".png", "PNG görsel")
def webp_to_png(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGBA", fmt="PNG")


@register(".webp", ".jpg", "JPEG görsel")
def webp_to_jpg(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGB", fmt="JPEG", quality=options.get("jpeg_quality"))


@register(".png", ".webp", "WEBP görsel (web optimizasyonu)")
def png_to_webp(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGBA", fmt="WEBP")


@register(".jpg", ".webp", "WEBP görsel (web optimizasyonu)")
def jpg_to_webp(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGBA", fmt="WEBP")


@register(".jpeg", ".webp", "WEBP görsel (web optimizasyonu)")
def jpeg_to_webp(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGBA", fmt="WEBP")


@register(".heic", ".jpg", "JPEG görsel")
def heic_to_jpg(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGB", fmt="JPEG", quality=options.get("jpeg_quality"))


@register(".heic", ".png", "PNG görsel")
def heic_to_png(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGBA", fmt="PNG")


@register(".png", ".jpg", "JPEG görsel (beyaz zemin)")
def png_to_jpg(src: Path, dst: Path) -> None:
    _flatten_to_jpg(src, dst)


@register(".jpg", ".png", "PNG görsel")
def jpg_to_png(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGB", fmt="PNG")


@register(".jpeg", ".png", "PNG görsel")
def jpeg_to_png(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGB", fmt="PNG")


@register(".bmp", ".png", "PNG görsel")
def bmp_to_png(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGBA", fmt="PNG")


@register(".bmp", ".jpg", "JPEG görsel")
def bmp_to_jpg(src: Path, dst: Path) -> None:
    _flatten_to_jpg(src, dst)


@register(".tiff", ".png", "PNG görsel")
def tiff_to_png(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGBA", fmt="PNG")


@register(".tiff", ".jpg", "JPEG görsel")
def tiff_to_jpg(src: Path, dst: Path) -> None:
    _flatten_to_jpg(src, dst)


@register(".tif", ".png", "PNG görsel")
def tif_to_png(src: Path, dst: Path) -> None:
    _convert_via_pillow(src, dst, mode="RGBA", fmt="PNG")


@register(".tif", ".jpg", "JPEG görsel")
def tif_to_jpg(src: Path, dst: Path) -> None:
    _flatten_to_jpg(src, dst)


@register(".gif", ".png", "PNG görsel (ilk kare)")
def gif_to_png(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img.seek(0)
        img.convert("RGBA").save(dst, format="PNG")