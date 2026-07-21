"""Converter registry: modüller @register ile rota ekler, cli.py routes_for ile okur."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .tooling import ExternalTool

ConvertFunc = Callable[[Path, Path], None]


@dataclass(frozen=True)
class ConversionRoute:
    source_ext: str
    target_ext: str
    label: str
    convert: ConvertFunc
    requires: "ExternalTool | None" = None
    # Rota tek girdiden birden çok dosya üretiyorsa (ör. pdf->png, sayfa başına)
    # True. Böyle rotalar zincirde ara adım olamaz (yalnızca son adım olabilir).
    multi_output: bool = False
    # Köprü (zincirleme) rota ise geçilen ara uzantılar; doğrudan rotalarda boş.
    via: tuple[str, ...] = field(default_factory=tuple)


_REGISTRY: list[ConversionRoute] = []


# Format kategorileri ve sırası; converts ekranı, format matrisi ve köprü
# sıralaması bu tek kaynaktan beslenir (ui.py ikonları buradan türetir).
GROUP_ORDER: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("image", (".png", ".jpg", ".jpeg", ".webp", ".svg", ".heic", ".icns", ".ico",
               ".gif", ".bmp", ".tiff", ".tif")),
    ("document", (".pdf", ".docx", ".pptx", ".epub", ".mobi", ".txt", ".html")),
    ("data", (".json", ".csv", ".yaml", ".yml", ".toml", ".xml", ".md", ".sql")),
    ("spreadsheet", (".xlsx",)),
    ("video", (".mp4", ".mov", ".mkv", ".webm", ".avi")),
    ("audio", (".mp3", ".wav", ".m4a", ".flac", ".ogg")),
)


def group_index(ext: str) -> int:
    """Uzantının kategori sırası; bilinmeyen uzantı sona düşer."""
    for i, (_key, exts) in enumerate(GROUP_ORDER):
        if ext in exts:
            return i
    return len(GROUP_ORDER)


def group_key(ext: str) -> str:
    """Uzantının kategori anahtarı ('image', 'audio' ... yoksa 'other')."""
    for key, exts in GROUP_ORDER:
        if ext in exts:
            return key
    return "other"


def register(source_ext: str, target_ext: str, label: str,
             requires: "ExternalTool | None" = None, multi_output: bool = False):
    """Dönüştürme fonksiyonunu registry'e ekleyen dekoratör. `requires`
    verilirse cli.py dönüşümden önce aracın kurulu olduğunu kontrol eder.
    `multi_output` verilirse rota zincirde ara adım olarak kullanılmaz."""
    def decorator(func: ConvertFunc) -> ConvertFunc:
        _REGISTRY.append(
            ConversionRoute(
                source_ext=source_ext.lower(),
                target_ext=target_ext.lower(),
                label=label,
                convert=func,
                requires=requires,
                multi_output=multi_output,
            )
        )
        return func
    return decorator


def routes_for(source_ext: str) -> list[ConversionRoute]:
    """Verilen kaynak uzantı için kayıtlı tüm dönüştürme rotalarını döner."""
    return [r for r in _REGISTRY if r.source_ext == source_ext.lower()]


def all_source_extensions() -> list[str]:
    """Desteklenen tüm kaynak uzantıların listesi."""
    return sorted({r.source_ext for r in _REGISTRY})


def all_routes() -> list[ConversionRoute]:
    """Kayıtlı tüm dönüştürme rotaları (converts ekranı için)."""
    return list(_REGISTRY)


def conversion_matrix() -> list[dict]:
    """Tüm rotaları kategoriye ve kaynağa göre gruplu saf-veri olarak döner.
    converts ekranı ve `--list-formats` çıktıları bu tek kaynaktan üretilir."""
    by_source: dict[str, list[ConversionRoute]] = {}
    for route in _REGISTRY:
        by_source.setdefault(route.source_ext, []).append(route)

    matrix = []
    for ext in sorted(by_source, key=lambda e: (group_index(e), e)):
        targets = [
            {
                "target": r.target_ext,
                "requires": r.requires.friendly_name if r.requires else None,
                "label": r.label,
            }
            for r in sorted(by_source[ext], key=lambda r: r.target_ext)
        ]
        matrix.append({"source": ext, "group": group_key(ext), "targets": targets})
    return matrix
