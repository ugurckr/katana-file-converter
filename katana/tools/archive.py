"""Dosyaları tek arşivde paketleme ve arşiv açma (zip/tar)."""

import tarfile
import zipfile
from pathlib import Path

ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2")


def is_archive(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(s) for s in ARCHIVE_SUFFIXES)


def bundle(paths: list[Path], dst: Path) -> int:
    """Dosyaları uzantıya göre zip ya da tar arşivine koyar, sayılarını döner."""
    files = [p for p in paths if p.is_file()]
    dst.parent.mkdir(parents=True, exist_ok=True)
    name = dst.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in files:
                zf.write(p, arcname=p.name)
    else:
        mode = "w:gz" if name.endswith((".gz", ".tgz")) else (
            "w:bz2" if name.endswith((".bz2", ".tbz2")) else "w")
        with tarfile.open(dst, mode) as tf:
            for p in files:
                tf.add(p, arcname=p.name)
    return len(files)


def extract(archive: Path, dst_dir: Path) -> list[Path]:
    """Arşivi açar ve çıkan dosya yollarını döner."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_root = dst_dir.resolve()
    name = archive.name.lower()

    def _safe(member_name: str) -> Path:
        # Zip Slip: hedef klasör dışına çıkan girdileri reddet.
        target = (dst_dir / member_name).resolve()
        if not str(target).startswith(str(dst_root)):
            raise ValueError(f"Güvensiz arşiv yolu: {member_name}")
        return target

    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                _safe(member)
            zf.extractall(dst_dir)
            names = zf.namelist()
    else:
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                _safe(member.name)
            tf.extractall(dst_dir)
            names = [m.name for m in tf.getmembers()]

    return [dst_dir / n for n in names if (dst_dir / n).is_file()]
