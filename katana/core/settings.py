"""Bir çalıştırmanın çıktı/akış ayarları (kalite ayarları için converters/options.py)."""

from dataclasses import dataclass
from pathlib import Path

from .naming import CONFLICT_POLICIES


@dataclass
class RunConfig:
    on_conflict: str = "rename"
    name_template: str | None = None
    dry_run: bool = False
    log_path: Path | None = None
    jobs: int = 1


_current = RunConfig()


def get() -> RunConfig:
    return _current


def configure(**updates) -> None:
    for key, value in updates.items():
        if value is None:
            continue
        if not hasattr(_current, key):
            raise KeyError(f"Bilinmeyen ayar: {key}")
        if key == "on_conflict" and value not in CONFLICT_POLICIES:
            raise ValueError(f"Geçersiz çakışma politikası: {value}")
        setattr(_current, key, value)


def reset() -> None:
    global _current
    _current = RunConfig()
