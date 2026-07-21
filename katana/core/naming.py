"""Çıktı adı şablonları ve dosya çakışması yönetimi."""

from datetime import datetime
from pathlib import Path

TEMPLATE_FIELDS = ("stem", "ext", "parent", "index", "date")
CONFLICT_POLICIES = ("overwrite", "skip", "rename")


def render_output_name(
    source: Path,
    target_ext: str,
    template: str | None = None,
    output_dir: Path | None = None,
    index: int = 0,
) -> Path:
    """Şablon (veya varsayılan olarak kaynak adı) ile hedef yolu üretir."""
    ext = target_ext.lstrip(".").lower()
    base_dir = output_dir if output_dir is not None else source.parent

    if template:
        name = template.format(
            stem=source.stem,
            ext=ext,
            parent=source.parent.name,
            index=index + 1,
            date=datetime.now().strftime("%Y-%m-%d"),
        )
        candidate = Path(name)
        if not candidate.suffix:
            candidate = candidate.with_suffix("." + ext)
        return base_dir / candidate.name

    return (base_dir / source.name).with_suffix("." + ext)


def resolve_conflict(path: Path, policy: str) -> Path | None:
    """overwrite = aynı yol, skip = varsa None, rename = 'name (1).ext'."""
    if policy == "overwrite" or not path.exists():
        return path
    if policy == "skip":
        return None

    stem, suffix, parent = path.stem, path.suffix, path.parent
    i = 1
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1
