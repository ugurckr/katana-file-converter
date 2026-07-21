"""Dönüşüm ayarları (JPEG kalitesi, çözünürlük). Converter'lar get() ile okur,
interaktif akış dönüşümden önce set_option() ile yazar; CLI modunda hep varsayılan."""

DEFAULTS = {
    "jpeg_quality": 95,
    "video_height": None,   # None = orijinal çözünürlük
    # görsel
    "resize": None,         # "800x600" | "50%"
    "watermark": None,
    # ses/video
    "audio_bitrate": None,  # "192k"
    "trim_start": None,     # "00:00:05" | "5"
    "trim_end": None,
}

_current: dict = dict(DEFAULTS)


def get(key: str):
    return _current[key]


def set_option(key: str, value) -> None:
    if key not in DEFAULTS:
        raise KeyError(f"Bilinmeyen dönüşüm ayarı: {key}")
    _current[key] = value
