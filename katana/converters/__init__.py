"""Converter modülleri burada import edilerek kendilerini kaydettirir.
Yeni format desteği: modülü yaz, @register ile tanımla, buraya import et."""

from . import av  # noqa: F401
from . import data  # noqa: F401
from . import documents  # noqa: F401
from . import icons  # noqa: F401
from . import image_extra  # noqa: F401
from . import ocr  # noqa: F401  (opsiyonel; Tesseract yoksa rota kaydetmez)
from . import spreadsheet  # noqa: F401
from . import text  # noqa: F401
from .base import (
    GROUP_ORDER,
    ConversionRoute,
    all_routes,
    all_source_extensions,
    conversion_matrix,
    group_index,
    group_key,
    routes_for,
)
from .chain import bridged_routes_for, find_chain, make_composite

__all__ = [
    "ConversionRoute",
    "routes_for",
    "all_routes",
    "all_source_extensions",
    "conversion_matrix",
    "GROUP_ORDER",
    "group_index",
    "group_key",
    "find_chain",
    "bridged_routes_for",
    "make_composite",
]