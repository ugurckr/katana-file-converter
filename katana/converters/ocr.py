"""OCR ile görsel→metin (opsiyonel; pytesseract + Tesseract kuruluysa etkin)."""

import shutil
from pathlib import Path

from .base import register

_AVAILABLE: bool | None = None


def ocr_available() -> bool:
    global _AVAILABLE
    if _AVAILABLE is not None:
        return _AVAILABLE
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        _AVAILABLE = False
        return False
    _AVAILABLE = shutil.which("tesseract") is not None
    return _AVAILABLE


def _image_to_txt(src: Path, dst: Path) -> None:
    import pytesseract
    from PIL import Image

    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        text = pytesseract.image_to_string(img)
    dst.write_text(text, encoding="utf-8")


if ocr_available():
    for _ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"):
        register(_ext, ".txt", "Metin (OCR ile)")(_image_to_txt)
