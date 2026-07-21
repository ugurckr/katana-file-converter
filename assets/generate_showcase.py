"""README görsellerini üretir:
  * showcase.gif — her renk temasının banner'ını sırayla gösteren animasyon
  * demo.gif     — bir toplu dönüşüm akışı (giriş → menü → ilerleme → özet)

Boru hattı:  Rich (ekran → SVG)  →  resvg (SVG → PNG)  →  Pillow (PNG'ler → GIF)

Neden resvg?  Rich'in ürettiği SVG, kırpma yolları (clip-path) ve web fontu içerir;
saf-Python rasterleştiriciler (svglib, cairosvg) bunu düzgün çizemez. resvg tam
uyumlu, tek dosyalık bir rasterleştiricidir. Braille sanatı için de tek genişlikli
(monospace) bir font gerekir — Fira Code otomatik indirilir.

Gereksinimler (ilk çalıştırmada `.showcase-cache/` içine otomatik indirilir):
  * resvg  — https://github.com/linebender/resvg
  * Fira Code TTF  — https://github.com/tonsky/FiraCode

Çalıştırma (repo kökünden):
  python assets/generate_showcase.py
"""

import io
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image
from rich import box
from rich.console import Console
from rich.panel import Panel

# Repo kökünü import yoluna ekle (katana paketi için)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from katana import i18n, themes, ui  # noqa: E402

# Görselleri İngilizce üret (kullanıcının kayıtlı dil tercihini config'e yazmadan geçici olarak).
i18n._lang = "en"

CACHE = ROOT / "assets" / ".showcase-cache"
FONTS = CACHE / "fonts"
WIDTH = 1100          # GIF genişliği (px)

RESVG_URL = "https://github.com/linebender/resvg/releases/download/v0.47.0/resvg-win64.zip"
FIRACODE_URL = "https://github.com/tonsky/FiraCode/releases/download/6.2/Fira_Code_v6.2.zip"

# Temaların showcase'te görünme sırası (renk geçişleri hoş dursun diye elle düzenlenmiş)
THEME_ORDER = ["katana", "sakura", "kohaku", "kin", "matcha", "umi", "yoru", "murasaki", "neon", "sumi"]


# ── Ortak altyapı ────────────────────────────────────────────────────────────
def ensure_tools() -> Path:
    """resvg ve Fira Code'u indirir (yoksa) ve resvg.exe yolunu döner."""
    CACHE.mkdir(parents=True, exist_ok=True)
    FONTS.mkdir(parents=True, exist_ok=True)
    resvg = CACHE / "resvg.exe"

    if not resvg.exists():
        print("resvg indiriliyor…")
        data = urllib.request.urlopen(RESVG_URL).read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extract("resvg.exe", CACHE)

    if not (FONTS / "FiraCode-Regular.ttf").exists():
        print("Fira Code indiriliyor…")
        data = urllib.request.urlopen(FIRACODE_URL).read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in ("ttf/FiraCode-Regular.ttf", "ttf/FiraCode-Bold.ttf"):
                (FONTS / Path(member).name).write_bytes(z.read(member))

    return resvg


def rasterize(resvg: Path, svg_path: Path, png_path: Path) -> None:
    subprocess.run(
        [str(resvg), "--use-fonts-dir", str(FONTS), "--font-family", "Fira Code",
         "--width", str(WIDTH), str(svg_path), str(png_path)],
        check=True, capture_output=True,
    )


def save_gif(frames: list[Image.Image], durations, out: Path) -> None:
    """Kareleri ortak boyutlu tuvale hizalayıp animasyonlu GIF olarak kaydeder."""
    w = max(f.width for f in frames)
    h = max(f.height for f in frames)
    bg = frames[0].getpixel((5, h // 2))
    canvas = []
    for f in frames:
        base = Image.new("RGB", (w, h), bg)
        base.paste(f, (0, 0))
        canvas.append(base)
    canvas[0].save(out, save_all=True, append_images=canvas[1:],
                   duration=durations, loop=0, disposal=2, optimize=True)
    size = out.stat().st_size // 1024
    print(f"{out.relative_to(ROOT)} — {len(canvas)} kare, {w}x{h}, {size} KB")


# ── showcase.gif (temalar) ───────────────────────────────────────────────────
def build_showcase(resvg: Path) -> None:
    frames_dir = CACHE / "showcase"
    frames_dir.mkdir(exist_ok=True)
    pngs = []
    for theme_id in THEME_ORDER:
        themes.set_theme(theme_id)
        ui.apply_theme()
        console = Console(record=True, width=88)
        ui.console = console
        ui.print_banner()
        svg_path = frames_dir / f"{theme_id}.svg"
        svg_path.write_text(console.export_svg(title=""), encoding="utf-8")
        png_path = frames_dir / f"{theme_id}.png"
        rasterize(resvg, svg_path, png_path)
        pngs.append(png_path)

    frames = [Image.open(p).convert("RGB") for p in pngs]
    save_gif(frames, 1300, ROOT / "assets" / "showcase.gif")


# ── demo.gif (dönüşüm akışı) ─────────────────────────────────────────────────
DEMO_COLS = 92
DEMO_ROWS = 20  # her kare bu satır sayısına doldurulur (tutarlı GIF boyutu)
MENU = [("ico", "Windows ICO icon"), ("jpg", "JPEG image"),
        ("webp", "WEBP image (web-optimized)"), ("icns", "macOS ICNS icon")]


def _demo_console() -> Console:
    c = Console(record=True, width=DEMO_COLS)
    ui.console = c
    return c


def _pad_export(c: Console) -> str:
    # export_text varsayılan clear=True kayıt tamponunu siler; ölçüm için clear=False şart.
    used = len(c.export_text(clear=False).splitlines())
    for _ in range(max(0, DEMO_ROWS - used)):
        c.print()
    return c.export_svg(title="")


def _f_prompt(c: Console):
    a = ui.ACCENT
    c.print(Panel(
        f"[bold {a}]{i18n.t('prompt.title')}[/bold {a}]\n"
        f"[dim]   {i18n.t('prompt.hint1')}[/dim]\n"
        f"[dim]    {i18n.t('prompt.hint2')}[/dim]\n"
        f"[dim]   {i18n.t('prompt.hint3', help=f'[{a}]help[/{a}][dim]')}[/dim]",
        box=box.ROUNDED, border_style=ui.BORDER, padding=(1, 3), width=ui.frame_width(),
    ))
    c.print(f"[bold {a}]➜  [/bold {a}]./icons")


def _f_menu(c: Console):
    a = ui.ACCENT
    ui.print_group_header(".png", 5)
    c.print()
    c.print(f"[bold {a}]➜[/bold {a}]  Which format do you want?  "
            f"[dim]{i18n.t('select.instruction')}[/dim]")
    for i, (ext, label) in enumerate(MENU):
        icon = ui.format_icon(f".{ext}")
        if i == 0:
            c.print(f"[bold {a}]❯[/bold {a}] {icon}  [bold {a}]{ext.upper():<6} — {label}[/bold {a}]")
        else:
            c.print(f"  {icon}  [white]{ext.upper():<6}[/white] [dim]— {label}[/dim]")


def _f_progress(c: Console, done: int, current: str):
    ui.print_group_header(".png", 5)
    for i in range(1, done + 1):
        c.print(f"  [bold green]✓[/bold green] photo{i}.png [dim]→[/dim] photo{i}.ico")
    prog = ui.batch_progress()
    task = prog.add_task("convert", filename=current, total=5)
    prog.update(task, completed=done)
    c.print(prog.get_renderable())


def _f_summary(c: Console):
    ui.print_group_header(".png", 5)
    for i in range(1, 6):
        c.print(f"  [bold green]✓[/bold green] photo{i}.png [dim]→[/dim] photo{i}.ico")
    c.print()
    ui.print_summary_panel(5, 5)


def build_demo(resvg: Path) -> None:
    themes.set_theme("katana")
    ui.apply_theme()
    frames_dir = CACHE / "demo"
    frames_dir.mkdir(exist_ok=True)

    steps = [
        (_f_prompt, 1800),
        (_f_menu, 1900),
        (lambda c: _f_progress(c, 2, "photo3.png"), 1200),
        (lambda c: _f_progress(c, 4, "photo5.png"), 1200),
        (_f_summary, 2200),
    ]
    pngs, durations = [], []
    for i, (build, dur) in enumerate(steps):
        c = _demo_console()
        build(c)
        svg_path = frames_dir / f"{i}.svg"
        svg_path.write_text(_pad_export(c), encoding="utf-8")
        png_path = frames_dir / f"{i}.png"
        rasterize(resvg, svg_path, png_path)
        pngs.append(png_path)
        durations.append(dur)

    frames = [Image.open(p).convert("RGB") for p in pngs]
    save_gif(frames, durations, ROOT / "assets" / "demo.gif")


def main() -> None:
    resvg = ensure_tools()
    build_showcase(resvg)
    build_demo(resvg)


if __name__ == "__main__":
    main()
