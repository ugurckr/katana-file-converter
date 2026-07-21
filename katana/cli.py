"""Katana File Converter — ana akış (interaktif + komut satırı)."""

import argparse
import json
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from katana import preview, ui
from katana.core import config, history, naming, settings
from katana.tools import archive, pdf_tools
from katana.tools import watch as watch_mod
from katana.converters import (
    all_source_extensions,
    bridged_routes_for,
    conversion_matrix,
    find_chain,
    make_composite,
    routes_for,
)
from katana.converters import options
from katana.converters.tooling import (
    auto_installable,
    find_tool,
    install_command,
    install_tool,
    installer_name,
)
from katana.i18n import t


def ensure_route_ready(route) -> bool:
    """Route'un gerektirdiği harici araç kuruluysa True; değilse kurulum önerir."""
    tool = route.requires
    if tool is None or find_tool(tool) is not None:
        return True

    # Otomatik kurulum yoksa (Linux vb.) yalnızca komutu göster.
    if not auto_installable(tool):
        cmd = install_command(tool)
        if cmd:
            ui.print_error(t("cli.tool_manual_cmd", tool=tool.friendly_name, cmd=cmd, url=tool.manual_url))
        else:
            ui.print_error(t("cli.tool_declined", tool=tool.friendly_name, url=tool.manual_url))
        return False

    if not ui.prompt_install_tool(tool):
        ui.print_error(t("cli.tool_declined", tool=tool.friendly_name, url=tool.manual_url))
        return False

    ui.console.print(
        f"[bold {ui.ACCENT}]"
        f"{t('cli.tool_installing', tool=tool.friendly_name, installer=installer_name(tool))}"
        f"[/bold {ui.ACCENT}]"
    )
    if not install_tool(tool):
        ui.print_error(t("cli.tool_failed", tool=tool.friendly_name, url=tool.manual_url))
        return False

    ui.console.print(f"[bold green]{t('cli.tool_installed', tool=tool.friendly_name)}[/bold green]\n")
    return True


def plan_output(path: Path, route, output_dir: Path | None = None,
                index: int = 0, explicit: Path | None = None) -> Path | None:
    """Adlandırma + çakışma politikasına göre hedef yolu; skip'te None döner."""
    cfg = settings.get()
    target = explicit if explicit is not None else naming.render_output_name(
        path, route.target_ext, cfg.name_template, output_dir, index
    )
    return naming.resolve_conflict(target, cfg.on_conflict)


def convert_one(path: Path, route, output_dir: Path | None = None,
                index: int = 0, explicit: Path | None = None) -> Path | None:
    """Dosyayı dönüştürür; çıktı yolunu (atlandıysa None) döner."""
    output_path = plan_output(path, route, output_dir, index, explicit)
    if output_path is None:
        return None
    route.convert(path, output_path)
    ui.record_output(output_path)
    history.record(path, output_path)
    return output_path


def group_by_extension(files: list[Path]) -> dict[str, list[Path]]:
    """Verilen dosyaları, destekli olan uzantılarına göre gruplar."""
    groups: dict[str, list[Path]] = {}
    for file in files:
        ext = file.suffix.lower()
        if routes_for(ext):
            groups.setdefault(ext, []).append(file)
    return groups


def find_convertible_files(root: Path) -> dict[str, list[Path]]:
    """Klasördeki dosyaları, destekli olan uzantılarına göre gruplar."""
    return group_by_extension(sorted(f for f in root.rglob("*") if f.is_file()))


# --log ve özet için biriken sonuçlar (status: ok | skipped | error).
_results: list[dict] = []
_results_lock = threading.Lock()


def _record_result(source: Path, target: Path | None, status: str, error: str = "") -> None:
    with _results_lock:
        _results.append({
            "time": datetime.now().isoformat(timespec="seconds"),
            "source": str(source),
            "target": str(target) if target else "",
            "status": status,
            "error": error,
        })


def _run_conversions(route, files: list[Path], output_dir: Path | None, jobs: int, on_result) -> None:
    """Dosyaları jobs iş parçacığıyla dönüştürür, her sonuç için on_result çağırır.

    Thread havuzu yeterli: Pillow/ffmpeg/PyMuPDF GIL'i bırakır ve zincir rotalarında
    process havuzunun pickle sorunu yaşanmaz.
    """
    def task(item):
        i, f = item
        try:
            return f, convert_one(f, route, output_dir, index=i), None
        except Exception as exc:
            return f, None, exc

    items = list(enumerate(files))
    if jobs <= 1:
        for item in items:
            on_result(*task(item))
        return
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = [executor.submit(task, item) for item in items]
        for future in as_completed(futures):
            on_result(*future.result())


def _flush_log() -> None:
    """Toplanan sonuçları --log ile verilen dosyaya JSONL olarak yazar."""
    cfg = settings.get()
    if not cfg.log_path or not _results:
        return
    try:
        cfg.log_path.parent.mkdir(parents=True, exist_ok=True)
        with cfg.log_path.open("a", encoding="utf-8") as fh:
            for row in _results:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:
        ui.print_error(t("log.write_failed", path=cfg.log_path, err=exc))


def _dry_run_group(route, files: list[Path], output_dir: Path | None) -> None:
    """Dönüştürmeden, her dosya için planlanan çıktı yolunu ve durumunu yazar."""
    for i, file in enumerate(files):
        planned = plan_output(file, route, output_dir, i)
        if planned is None:
            ui.console.print(
                f"  [yellow]○[/yellow] {file.name} [dim]—[/dim] {t('dryrun.skip')}"
            )
        else:
            note = f" [dim]({t('dryrun.overwrite')})[/dim]" if planned.exists() else ""
            ui.console.print(f"  [cyan]→[/cyan] {file.name} [dim]→[/dim] {planned}{note}")


def convert_group(ext: str, files: list[Path], output_dir: Path | None = None) -> tuple[int, int]:
    """Aynı uzantıdaki dosyalar için hedef formatı bir kez sorup hepsini dönüştürür."""
    route = ui.select_route(routes_for(ext))
    if route is None:
        ui.console.print(f"[dim]{t('cli.skipped')}[/dim]\n")
        return 0, 0

    if settings.get().dry_run:
        _dry_run_group(route, files, output_dir)
        ui.console.print()
        return 0, 0

    if not ensure_route_ready(route):
        return len(files), 0

    ui.prompt_route_options(route)

    success = 0
    with ui.batch_progress() as progress:
        task = progress.add_task("convert", filename=files[0].name, total=len(files))

        def on_result(file: Path, out_path: Path | None, exc: Exception | None) -> None:
            nonlocal success
            progress.update(task, filename=file.name)
            if exc is not None:
                progress.console.print(
                    f"  [bold red]✗[/bold red] {file.name} [dim]—[/dim] [red]{exc}[/red]"
                )
                _record_result(file, None, "error", str(exc))
            elif out_path is None:
                progress.console.print(
                    f"  [yellow]○[/yellow] {file.name} [dim]—[/dim] {t('conflict.skipped')}"
                )
                _record_result(file, None, "skipped")
            else:
                progress.console.print(
                    f"  [bold green]✓[/bold green] {file.name} [dim]→[/dim] {out_path}"
                )
                _record_result(file, out_path, "ok")
                success += 1
            progress.advance(task)

        _run_conversions(route, files, output_dir, settings.get().jobs, on_result)
    ui.console.print()
    ui.record_conversion(len(files), success)
    return len(files), success


def convert_groups(groups: dict[str, list[Path]]) -> None:
    """Uzantıya göre gruplanmış dosyaları sırayla dönüştürüp özet basar."""
    history.start_batch()
    total_files = total_success = 0
    for ext, files in groups.items():
        ui.print_group_header(ext, len(files))
        n, s = convert_group(ext, files)
        total_files += n
        total_success += s
    if not settings.get().dry_run:
        ui.print_summary_panel(total_files, total_success)
        history.commit_batch()
        _flush_log()


def interactive_single_file(path: Path) -> None:
    """Tek dosya için etkileşimli format seçici + dönüşüm (run_interactive ve --pick)."""
    ext = path.suffix.lower()
    routes = routes_for(ext)
    bridged = bridged_routes_for(ext)
    if not routes and not bridged:
        supported = ", ".join(all_source_extensions()) or t("unit.none")
        ui.print_error(t("cli.no_support", ext=path.suffix, supported=supported))
        return

    route = ui.select_route(routes + bridged)
    if route is None:
        ui.console.print(f"[dim]{t('cli.cancelled')}[/dim]")
        return
    if settings.get().dry_run:
        _dry_run_group(route, [path], None)
        return
    if not ensure_route_ready(route):
        return

    ui.prompt_route_options(route)
    try:
        history.start_batch()
        with ui.console.status(
            f"[bold {ui.ACCENT}]{t('cli.converting', name=path.name)}[/bold {ui.ACCENT}]",
            spinner="dots12",
        ):
            output_path = convert_one(path, route)
        if output_path is None:
            ui.console.print(f"[dim]{t('conflict.skipped')}[/dim]")
        else:
            ui.print_success_panel(output_path)
            ui.record_conversion(1, 1)
            history.commit_batch()
            _flush_log()
    except Exception as exc:
        ui.print_error(str(exc))
        ui.record_conversion(1, 0)


def preview_select_convert(files: list[Path]) -> None:
    """Çoklu dosyada önce önizleme galerisinden seçtirir, sonra dönüştürür."""
    if len(files) >= 2:
        selected = preview.select_files(files)
        if not selected:
            ui.console.print(f"[dim]{t('preview.none')}[/dim]")
            return
        files = selected
    convert_groups(group_by_extension(files))


def run_interactive() -> None:
    ui.print_banner()

    while True:
        paths = ui.prompt_for_paths()
        if paths is None:
            break

        existing = [p for p in paths if p.exists()]
        for p in (p for p in paths if not p.exists()):
            ui.print_error(t("cli.notfound_skipped", p=p))
        if not existing:
            continue

        ui.console.print()

        if len(existing) == 1 and existing[0].is_dir():
            groups = find_convertible_files(existing[0])
            if not groups:
                ui.print_error(t("cli.no_convertible", p=existing[0]))
            else:
                preview_select_convert([f for files in groups.values() for f in files])

        elif any(p.is_dir() for p in existing):
            ui.print_error(t("cli.mixed"))

        elif len(existing) == 1:
            interactive_single_file(existing[0])

        else:
            for p in (p for p in existing if not routes_for(p.suffix.lower())):
                ui.print_error(t("cli.no_support_skipped", ext=p.suffix, p=p))

            convertible = [p for p in existing if routes_for(p.suffix.lower())]
            if convertible:
                preview_select_convert(convertible)

        if not ui.prompt_continue():
            break


def resolve_route(source_ext: str, target: str | None):
    routes = routes_for(source_ext)
    if not routes:
        supported = ", ".join(all_source_extensions()) or t("unit.none")
        print(f"{t('error.prefix')}: {t('cli.no_support', ext=source_ext, supported=supported)}")
        sys.exit(1)

    if target:
        target_ext = "." + target.lstrip(".").lower()
        matching = [r for r in routes if r.target_ext == target_ext]
        if matching:
            return matching[0]
        # Doğrudan rota yoksa ara format üzerinden köprü kurmayı dene.
        chain = find_chain(source_ext, target_ext)
        if chain:
            path = " → ".join([source_ext] + [r.target_ext for r in chain])
            print(t("cli.chained", chain=path))
            return make_composite(chain)
        options = ", ".join(r.target_ext for r in routes)
        print(t("cli.target_unsupported", src=source_ext, dst=target_ext, options=options))
        sys.exit(1)

    if len(routes) == 1:
        return routes[0]

    options = ", ".join(r.target_ext.lstrip(".") for r in routes)
    print(t("cli.multi_target", src=source_ext, options=options))
    sys.exit(1)


def _matrix_counts(matrix: list[dict]) -> tuple[int, int]:
    """Matristen (rota sayısı, farklı format sayısı) döner."""
    route_count = sum(len(row["targets"]) for row in matrix)
    exts = {row["source"] for row in matrix}
    exts |= {tgt["target"] for row in matrix for tgt in row["targets"]}
    return route_count, len(exts)


def _print_matrix_md(matrix: list[dict], route_count: int, format_count: int) -> None:
    order: list[str] = []
    groups: dict[str, list[dict]] = {}
    for row in matrix:
        if row["group"] not in groups:
            order.append(row["group"])
        groups.setdefault(row["group"], []).append(row)

    lines = [f"## Supported conversions ({route_count} routes · {format_count} formats)", ""]
    has_external = False
    for group in order:
        lines += [f"### {group.capitalize()}", "", "| Source | Targets |", "|--------|---------|"]
        for row in groups[group]:
            targets = []
            for tgt in row["targets"]:
                name = tgt["target"].lstrip(".")
                if tgt["requires"]:
                    name += "\\*"
                    has_external = True
                targets.append(f"`{name}`")
            lines.append(f"| `{row['source'].lstrip('.')}` | {', '.join(targets)} |")
        lines.append("")
    if has_external:
        lines.append("\\* requires an external tool (ffmpeg)")
    print("\n".join(lines))


def print_matrix(fmt: str) -> None:
    """Desteklenen dönüşüm matrisini table / json / md biçiminde yazar."""
    matrix = conversion_matrix()
    if fmt == "table":
        ui._cmd_converts()
        return

    route_count, format_count = _matrix_counts(matrix)
    if fmt == "json":
        print(json.dumps(
            {"routes": route_count, "formats": format_count, "conversions": matrix},
            ensure_ascii=False, indent=2,
        ))
    else:  # md
        _print_matrix_md(matrix, route_count, format_count)


def _cli_undo() -> None:
    """--undo: son batch'in çıktılarını (onay alarak) siler."""
    batch = history.last_batch()
    existing = [o for o in batch[1] if o.is_file()] if batch else []
    if not existing:
        print(t("undo.none"))
        return
    print(t("undo.about", n=len(existing)))
    for out in existing:
        print(f"  ✗ {out}")
    answer = input(t("undo.confirm") + " ").strip().lower()
    from katana.i18n import YES_ANSWERS
    if answer not in YES_ANSWERS:
        print(t("cli.cancelled"))
        return
    deleted, missing = history.undo_last()
    print(t("undo.done", n=len(deleted)))
    if missing:
        print(t("undo.missing", n=len(missing)))


def _cli_convert_dir(input_dir: Path, args) -> None:
    """CLI: klasördeki dosyaları uzantı gruplarıyla dönüştürür (dry-run destekli)."""
    groups = find_convertible_files(input_dir) if args.recursive else {
        ext: [f for f in input_dir.iterdir() if f.is_file() and f.suffix.lower() == ext]
        for ext in all_source_extensions()
        if any(f.is_file() and f.suffix.lower() == ext for f in input_dir.iterdir())
    }
    if not groups:
        print(t("cli.no_convertible", p=input_dir))
        sys.exit(0)

    dry = settings.get().dry_run
    total_files = total_success = total_skipped = total_failed = 0
    for ext, files in groups.items():
        route = resolve_route(ext, args.to)
        if dry:
            for i, file in enumerate(files):
                planned = plan_output(file, route, args.output, i)
                if planned is None:
                    print(f"○ {file}  ({t('dryrun.skip')})")
                else:
                    note = f"  ({t('dryrun.overwrite')})" if planned.exists() else ""
                    print(f"→ {file} -> {planned}{note}")
            continue
        if not ensure_route_ready(route):
            total_files += len(files)
            continue

        counts = {"ok": 0, "skipped": 0, "error": 0}

        def on_result(file: Path, out_path: Path | None, exc: Exception | None) -> None:
            if exc is not None:
                print(f"✗ {file}: {exc}")
                counts["error"] += 1
                _record_result(file, None, "error", str(exc))
            elif out_path is None:
                print(f"○ {file}: {t('conflict.skipped')}")
                counts["skipped"] += 1
                _record_result(file, None, "skipped")
            else:
                print(f"✓ {file} -> {out_path}")
                counts["ok"] += 1
                _record_result(file, out_path, "ok")

        _run_conversions(route, files, args.output, settings.get().jobs, on_result)
        total_files += len(files)
        total_success += counts["ok"]
        total_skipped += counts["skipped"]
        total_failed += counts["error"]

    if dry:
        print("\n" + t("dryrun.title"))
        return
    print("\n" + t("summary.text", total=total_files, success=total_success))
    if total_skipped:
        print(t("summary.skipped", n=total_skipped))
    if total_failed:
        print(t("summary.failed", n=total_failed))


def _cli_convert_file(input_file: Path, args) -> None:
    """CLI: tek dosyayı dönüştürür. Açık -o verilmişse o yol kullanılır."""
    route = resolve_route(input_file.suffix.lower(), args.to)
    if settings.get().dry_run:
        explicit = args.output if (args.output and not args.output.is_dir()) else None
        planned = plan_output(input_file, route, args.output if not explicit else None, 0, explicit)
        if planned is None:
            print(f"○ {input_file}  ({t('dryrun.skip')})")
        else:
            note = f"  ({t('dryrun.overwrite')})" if planned.exists() else ""
            print(f"→ {input_file} -> {planned}{note}")
        print("\n" + t("dryrun.title"))
        return
    if not ensure_route_ready(route):
        sys.exit(1)
    explicit = args.output if (args.output and not args.output.is_dir()) else None
    output_dir = args.output if (args.output and args.output.is_dir()) else None
    try:
        out_path = convert_one(input_file, route, output_dir, explicit=explicit)
        if out_path is None:
            print(t("conflict.skipped"))
            _record_result(input_file, None, "skipped")
        else:
            print(f"✓ {input_file} -> {out_path}")
            _record_result(input_file, out_path, "ok")
    except Exception as exc:
        print(f"{t('error.prefix')}: {exc}")
        _record_result(input_file, None, "error", str(exc))
        _flush_log()
        sys.exit(1)


def _apply_option_flags(args) -> None:
    """Kalite/görsel/av ince ayar bayraklarını converters.options'a yazar."""
    mapping = {
        "jpeg_quality": args.quality,
        "resize": args.resize,
        "watermark": args.watermark,
        "video_height": args.video_height,
        "audio_bitrate": args.audio_bitrate,
        "trim_start": args.trim_start,
        "trim_end": args.trim_end,
    }
    for key, value in mapping.items():
        if value is not None:
            options.set_option(key, value)


def _cli_archive_extract(args) -> None:
    """--extract: arşiv girdiyi (zip/tar) -o klasörüne (yoksa yanına) açar."""
    if not archive.is_archive(args.input):
        print(f"{t('error.prefix')}: {t('arch.not_archive', p=args.input)}")
        sys.exit(1)
    dst_dir = args.output if args.output else args.input.parent / args.input.stem
    files = archive.extract(args.input, dst_dir)
    print(t("arch.extracted", n=len(files), dst=dst_dir))


def _cli_pdf_op(args) -> None:
    """PDF araç bayraklarını (--merge/--pages/--compress/--rotate) yürütür."""
    if args.merge:
        if not args.input.is_dir():
            print(f"{t('error.prefix')}: {t('pdf.need_pdf', p=args.input)}")
            sys.exit(1)
        pdfs = sorted(f for f in args.input.iterdir() if f.suffix.lower() == ".pdf")
        if not pdfs:
            print(t("pdf.no_pdfs", p=args.input))
            sys.exit(0)
        dst = args.output or (args.input / "merged.pdf")
        n = pdf_tools.merge(pdfs, dst)
        print(t("pdf.merged", n=n, dst=dst))
        return

    if args.input.suffix.lower() != ".pdf":
        print(f"{t('error.prefix')}: {t('pdf.need_pdf', p=args.input)}")
        sys.exit(1)
    dst = args.output or args.input.with_stem(args.input.stem + "_out")
    if args.pages:
        n = pdf_tools.select_pages(args.input, dst, args.pages)
        print(t("pdf.merged", n=n, dst=dst))
    elif args.compress:
        pdf_tools.compress(args.input, dst)
        print(t("pdf.done", dst=dst))
    elif args.rotate is not None:
        pdf_tools.rotate(args.input, dst, args.rotate)
        print(t("pdf.done", dst=dst))


def _cli_pipe(args) -> None:
    """stdin → stdout/dosya boru hattı; durum mesajları stdout'u bozmasın diye stderr'e gider."""
    if not args.from_ext:
        print(f"{t('error.prefix')}: {t('pipe.need_from')}", file=sys.stderr)
        sys.exit(1)
    src_ext = "." + args.from_ext.lstrip(".").lower()
    route = resolve_route(src_ext, args.to)
    data = sys.stdin.buffer.read()
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / ("in" + src_ext)
        src.write_bytes(data)
        out = Path(td) / ("out" + route.target_ext)
        route.convert(src, out)
        result = out.read_bytes()

    to_stdout = args.output is None or str(args.output) == "-"
    if to_stdout:
        sys.stdout.buffer.write(result)
        sys.stdout.buffer.flush()
        print(t("pipe.done", src=src_ext.lstrip("."), dst="stdout"), file=sys.stderr)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(result)
        print(t("pipe.done", src=src_ext.lstrip("."), dst=args.output), file=sys.stderr)


def _apply_profile(args) -> None:
    """Profil değerlerini yalnızca kullanıcı açıkça vermediği alanlara uygular."""
    if not args.profile:
        return
    data = config.load_profile(args.profile)
    if data is None:
        available = ", ".join(config.profiles()) or t("unit.none")
        print(t("profile.notfound", name=args.profile, available=available))
        sys.exit(1)
    for key in ("to", "on_conflict", "name"):
        if getattr(args, key) is None and key in data:
            setattr(args, key, data[key])
    if not args.recursive and data.get("recursive"):
        args.recursive = True
    if args.jobs is None and "jobs" in data:
        args.jobs = data["jobs"]
    # Dönüşüm kalite ayarları (varsa) options'a taşınır.
    for opt in ("jpeg_quality", "video_height"):
        if opt in data:
            options.set_option(opt, data[opt])
    print(t("profile.loaded", name=args.profile))


def _save_profile_from_args(args) -> None:
    """--save-profile: verilen argümanları profil olarak kaydedip çıkar."""
    data = {
        "to": args.to,
        "on_conflict": args.on_conflict,
        "name": args.name,
        "recursive": args.recursive or None,
        "jobs": args.jobs,
        "jpeg_quality": args.quality,
        "video_height": args.video_height,
    }
    config.save_profile(args.save_profile, data)
    print(t("profile.saved", name=args.save_profile))


def run_cli(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description=t("cli.args.desc"))
    parser.add_argument("input", type=Path, nargs="?", default=None, help=t("cli.args.input"))
    parser.add_argument("-o", "--output", type=Path, default=None, help=t("cli.args.output"))
    parser.add_argument("-t", "--to", type=str, default=None, help=t("cli.args.to"))
    parser.add_argument("-f", "--from", type=str, default=None, dest="from_ext", help=t("cli.args.from"))
    parser.add_argument("-r", "--recursive", action="store_true", help=t("cli.args.recursive"))
    parser.add_argument("--list-formats", action="store_true", help=t("cli.args.list"))
    parser.add_argument("--format", choices=("table", "json", "md"), default="table",
                        help=t("cli.args.format"))
    parser.add_argument("--on-conflict", choices=naming.CONFLICT_POLICIES, default=None,
                        dest="on_conflict", help=t("cli.args.on_conflict"))
    parser.add_argument("--name", type=str, default=None, help=t("cli.args.name"))
    parser.add_argument("--dry-run", action="store_true", dest="dry_run", help=t("cli.args.dry_run"))
    parser.add_argument("--log", type=Path, default=None, help=t("cli.args.log"))
    parser.add_argument("--undo", action="store_true", help=t("cli.args.undo"))
    parser.add_argument("--pick", type=Path, default=None, help=t("cli.args.pick"))
    parser.add_argument("--install-context-menu", action="store_true", dest="install_menu",
                        help=t("cli.args.install_menu"))
    parser.add_argument("--uninstall-context-menu", action="store_true", dest="uninstall_menu",
                        help=t("cli.args.uninstall_menu"))
    parser.add_argument("--completion", choices=("bash", "zsh", "powershell"), default=None,
                        help=t("cli.args.completion"))
    parser.add_argument("-j", "--jobs", type=int, default=None, help=t("cli.args.jobs"))
    parser.add_argument("--watch", type=Path, default=None, help=t("cli.args.watch"))
    parser.add_argument("--profile", type=str, default=None, help=t("cli.args.profile"))
    parser.add_argument("--save-profile", type=str, default=None, dest="save_profile",
                        help=t("cli.args.save_profile"))
    # Görsel / av ince ayar
    parser.add_argument("--quality", type=int, default=None, help=t("cli.args.quality"))
    # argparse yardım metnini %-formatlar; literal % kaçırılmalı.
    parser.add_argument("--resize", type=str, default=None, help=t("cli.args.resize").replace("%", "%%"))
    parser.add_argument("--watermark", type=str, default=None, help=t("cli.args.watermark"))
    parser.add_argument("--video-height", type=int, default=None, dest="video_height",
                        help=t("cli.args.video_height"))
    parser.add_argument("--audio-bitrate", type=str, default=None, dest="audio_bitrate",
                        help=t("cli.args.audio_bitrate"))
    parser.add_argument("--trim-start", type=str, default=None, dest="trim_start",
                        help=t("cli.args.trim_start"))
    parser.add_argument("--trim-end", type=str, default=None, dest="trim_end",
                        help=t("cli.args.trim_end"))
    # Arşiv & PDF araçları
    parser.add_argument("--zip-output", type=Path, default=None, dest="zip_output",
                        help=t("cli.args.zip_output"))
    parser.add_argument("--extract", action="store_true", help=t("cli.args.extract"))
    parser.add_argument("--merge", action="store_true", help=t("cli.args.merge"))
    parser.add_argument("--pages", type=str, default=None, help=t("cli.args.pages"))
    parser.add_argument("--compress", action="store_true", help=t("cli.args.compress"))
    parser.add_argument("--rotate", type=int, default=None, help=t("cli.args.rotate"))
    args = parser.parse_args(argv)

    if args.undo:
        _cli_undo()
        return

    if args.install_menu or args.uninstall_menu:
        from katana.integrations import windows_menu
        if args.install_menu:
            ok = windows_menu.install()
            print(t("menu.installed") if ok else t("menu.failed"))
        else:
            ok = windows_menu.uninstall()
            print(t("menu.uninstalled") if ok else t("menu.failed"))
        return

    if args.pick is not None:
        if not args.pick.exists():
            print(f"{t('error.prefix')}: {t('cli.notfound', p=args.pick)}")
            sys.exit(1)
        ui.print_banner()
        interactive_single_file(args.pick)
        ui.console.input()  # sağ-tık menüsünde konsol hemen kapanmasın
        return

    if args.completion:
        from katana.integrations import completion
        print(completion.script_for(args.completion))
        return

    if args.list_formats:
        print_matrix(args.format)
        return

    if args.save_profile:
        _save_profile_from_args(args)
        return

    _apply_profile(args)

    settings.configure(
        on_conflict=args.on_conflict,
        name_template=args.name,
        dry_run=args.dry_run,
        log_path=args.log,
        jobs=args.jobs,
    )
    _apply_option_flags(args)

    # stdin/stdout boru hattı: girdi '-' ise.
    if args.input is not None and str(args.input) == "-":
        _cli_pipe(args)
        return

    if args.watch is not None:
        if not args.watch.is_dir():
            print(f"{t('error.prefix')}: {t('watch.not_dir', p=args.watch)}")
            sys.exit(1)
        if not args.to:
            print(f"{t('error.prefix')}: {t('watch.need_to')}")
            sys.exit(1)
        watch_mod.watch(args.watch, args.to)
        return

    if args.input is None:
        parser.error(t("cli.args.input"))

    if not args.input.exists():
        print(f"{t('error.prefix')}: {t('cli.notfound', p=args.input)}")
        sys.exit(1)

    # Özel işlem modları (normal dönüşümü kısa devre eder).
    if args.extract:
        _cli_archive_extract(args)
        return
    if args.merge or args.pages or args.compress or args.rotate is not None:
        _cli_pdf_op(args)
        return

    history.start_batch()
    if args.input.is_dir():
        _cli_convert_dir(args.input, args)
    else:
        _cli_convert_file(args.input, args)

    if not settings.get().dry_run:
        history.commit_batch()
        _flush_log()
        if args.zip_output is not None:
            outputs = [Path(r["target"]) for r in _results if r["status"] == "ok" and r["target"]]
            n = archive.bundle(outputs, args.zip_output)
            print(t("arch.bundled", n=n, dst=args.zip_output))


def main() -> None:
    if len(sys.argv) == 1:
        run_interactive()
    else:
        run_cli(sys.argv[1:])


if __name__ == "__main__":
    main()
