"""Dönüşüm geçmişi: her batch'in çıktılarını kaydeder, undo ile geri alır."""

import json
import threading
from datetime import datetime
from pathlib import Path

HISTORY_DIR = Path.home() / ".katana" / "history"

_pending: list[dict] = []
_lock = threading.Lock()


def start_batch() -> None:
    with _lock:
        _pending.clear()


def record(source: Path, output: Path) -> None:
    with _lock:
        _pending.append({"source": str(source), "output": str(output)})


def commit_batch() -> Path | None:
    """Biriken çıktıları zaman damgalı bir manifeste yazar."""
    if not _pending:
        return None
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "outputs": list(_pending),
    }
    _pending.clear()
    try:
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = HISTORY_DIR / f"{stamp}.json"
        path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
    except OSError:
        return None


def _manifests() -> list[Path]:
    if not HISTORY_DIR.is_dir():
        return []
    return sorted(HISTORY_DIR.glob("*.json"), reverse=True)


def last_batch() -> tuple[Path, list[Path]] | None:
    for manifest in _manifests():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        return manifest, [Path(o["output"]) for o in data.get("outputs", [])]
    return None


def undo_last() -> tuple[list[Path], list[Path]]:
    """Son batch'in çıktılarını siler. (silinenler, bulunamayanlar) döner."""
    batch = last_batch()
    if batch is None:
        return [], []
    manifest, outputs = batch
    deleted: list[Path] = []
    missing: list[Path] = []
    for out in outputs:
        try:
            if out.is_file():
                out.unlink()
                deleted.append(out)
            else:
                missing.append(out)
        except OSError:
            missing.append(out)
    try:
        manifest.unlink()
    except OSError:
        pass
    return deleted, missing
