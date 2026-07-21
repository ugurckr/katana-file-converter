"""Klasör izleme: düşen/değişen dosyaları otomatik dönüştürür (watchdog ya da polling)."""

import time
from pathlib import Path

from katana import ui
from katana.core import history
from katana.converters import routes_for
from katana.i18n import t


def _convert_new(path: Path, target: str, seen: set) -> None:
    # Döngüsel import'u önlemek için cli fonksiyonları burada import edilir.
    from katana.cli import convert_one, ensure_route_ready, resolve_route

    ext = path.suffix.lower()
    if not routes_for(ext):
        return
    key = (str(path), path.stat().st_mtime if path.exists() else 0)
    if key in seen:
        return
    seen.add(key)

    try:
        route = resolve_route(ext, target)
    except SystemExit:
        return
    if not ensure_route_ready(route):
        return
    try:
        history.start_batch()
        out = convert_one(path, route)
        if out is not None:
            ui.console.print(t("watch.converted", src=path.name, dst=out.name))
            history.commit_batch()
    except Exception as exc:
        ui.print_error(t("watch.failed", src=path.name, err=exc))


def _watch_with_watchdog(directory: Path, target: str, seen: set) -> bool:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        return False

    class Handler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory:
                _convert_new(Path(event.src_path), target, seen)

        def on_modified(self, event):
            if not event.is_directory:
                _convert_new(Path(event.src_path), target, seen)

    observer = Observer()
    observer.schedule(Handler(), str(directory), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    return True


def _watch_with_polling(directory: Path, target: str, seen: set) -> None:
    ui.console.print(f"[dim]{t('watch.polling')}[/dim]")
    # Mevcut dosyaları görülmüş say; yalnızca sonradan gelenler dönüştürülsün.
    for f in directory.iterdir():
        if f.is_file():
            seen.add((str(f), f.stat().st_mtime))
    try:
        while True:
            for f in sorted(directory.iterdir()):
                if f.is_file():
                    _convert_new(f, target, seen)
            time.sleep(2)
    except KeyboardInterrupt:
        pass


def watch(directory: Path, target: str) -> None:
    seen: set = set()
    ui.console.print(f"[bold {ui.ACCENT}]{t('watch.start', dir=directory, to=target)}[/bold {ui.ACCENT}]")
    if not _watch_with_watchdog(directory, target, seen):
        _watch_with_polling(directory, target, seen)
    ui.console.print(f"\n[dim]{t('watch.stopped')}[/dim]")
