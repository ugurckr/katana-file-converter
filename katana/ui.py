"""Terminal arayüzü: banner, paneller, prompt'lar ve seçim menüleri."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

import questionary
from pyfiglet import Figlet
from questionary import Style as QuestionaryStyle
from rich import box
from rich.console import Console, Group, RenderableType
from rich.measure import Measurement
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from katana import i18n, themes
from katana.core import history
from katana.converters import GROUP_ORDER, ConversionRoute, all_routes, conversion_matrix
from katana.converters import options as convert_options
from katana.converters.tooling import FFMPEG, find_tool, installer_name
from katana.i18n import t

console = Console()

# ─── Tema ────────────────────────────────────────────────────────────────────

def apply_theme() -> None:
    """Aktif temanın (themes.py) renklerini stil sabitlerine uygular."""
    global ACCENT, ACCENT_SOFT, BORDER, KANJI_GRADIENT, BANNER_GRADIENT, MENU_STYLE
    theme = themes.current_theme()
    ACCENT = theme.accent
    ACCENT_SOFT = theme.accent_soft
    BORDER = theme.border
    KANJI_GRADIENT = list(theme.gradient)
    BANNER_GRADIENT = KANJI_GRADIENT
    MENU_STYLE = QuestionaryStyle([
        ("qmark", f"fg:{ACCENT} bold"),
        ("question", "bold"),
        ("pointer", f"fg:{ACCENT} bold"),
        ("highlighted", f"fg:{ACCENT} bold"),
        ("selected", f"fg:{ACCENT} bold"),
        ("instruction", "fg:#808080"),
    ])


apply_theme()

APP_NAME = "Katana File Converter"
APP_VERSION = "v1.0.0"
KANJI_LOGO = "愛"

# ─── Geliştirici bilgileri ('credit' ekranı) ─────────────────────────────────
AUTHOR_NAME = "Uğur Çakar"
AUTHOR_GITHUB = "github.com/ugurckr"
COPYRIGHT = "© 2026 Uğur Çakar"

# Oturum sayacı ('stats') ve son çıktı yolu ('open').
SESSION_STATS = {"files": 0, "success": 0}
_last_output: Path | None = None


def record_conversion(total: int, success: int) -> None:
    SESSION_STATS["files"] += total
    SESSION_STATS["success"] += success


def record_output(path: Path) -> None:
    global _last_output
    _last_output = path


def _open_in_explorer(path: Path) -> None:
    """Dosya yöneticisinde çıktıyı gösterir (varsa dosya seçili olarak)."""
    if sys.platform == "win32":
        # Liste argümanla subprocess '/select,...' ifadesini komple tırnaklıyor
        # ve Explorer bunu çözemeyip Belgeler'i açıyor; string form şart.
        path = path.resolve()
        if path.is_file():
            subprocess.Popen(f'explorer /select,"{path}"')
        else:
            folder = path if path.is_dir() else path.parent
            subprocess.Popen(f'explorer "{folder}"')
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)] if path.exists() else ["open", str(path.parent)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent if path.is_file() or not path.exists() else path)])


def open_last_output() -> None:
    """Son dönüşümün çıktı klasörünü açar."""
    if _last_output is None:
        console.print(f"[dim]{t('open.none')}[/dim]")
        return
    _open_in_explorer(_last_output)
    folder = _last_output.parent if not _last_output.is_dir() else _last_output
    console.print(f"[bold green]✓[/bold green] {t('open.opened', p=folder)}")


_GROUP_ICONS = {"image": "🖼", "document": "📄", "data": "🗂",
                "spreadsheet": "📊", "video": "🎬", "audio": "🎵", "other": "📦"}

# Kategori→uzantı eşlemesi tek kaynaktan (base.GROUP_ORDER) türetilir; ikonlar burada eklenir.
_ICON_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    (_GROUP_ICONS[key], exts) for key, exts in GROUP_ORDER
]

_GROUP_KEYS = {icon: f"group.{key}" for key, icon in _GROUP_ICONS.items()}

# Banner ve help ekranında listelenen komutlar.
_COMMAND_HELP = (
    ("converts", "cmd.converts"),
    ("tools", "cmd.tools"),
    ("credit", "cmd.credit"),
    ("stats", "cmd.stats"),
    ("undo", "cmd.undo"),
    ("open", "cmd.open"),
    ("language", "cmd.language"),
    ("theme", "cmd.theme"),
    ("help", "cmd.help"),
    ("clear", "cmd.clear"),
    ("q", "cmd.q"),
)


def format_icon(ext: str) -> str:
    for icon, exts in _ICON_GROUPS:
        if ext in exts:
            return icon
    return "📦"


def _group_name(icon: str) -> str:
    return t(_GROUP_KEYS.get(icon, "group.other"))


def _group_index(ext: str) -> int:
    for i, (_icon, exts) in enumerate(_ICON_GROUPS):
        if ext in exts:
            return i
    return len(_ICON_GROUPS)


# ─── Renk geçişi yardımcıları ────────────────────────────────────────────────

def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _gradient_palette(stops: list[str], steps: int) -> list[str]:
    """`stops` renkleri arasında `steps` adımlık düzgün geçiş üretir."""
    rgb_stops = [_hex_to_rgb(s) for s in stops]
    segments = len(rgb_stops) - 1
    palette = []
    for i in range(steps):
        t_pos = i / max(steps - 1, 1) * segments
        seg = min(int(t_pos), segments - 1)
        frac = t_pos - seg
        r0, g0, b0 = rgb_stops[seg]
        r1, g1, b1 = rgb_stops[seg + 1]
        r = round(r0 + (r1 - r0) * frac)
        g = round(g0 + (g1 - g0) * frac)
        b = round(b0 + (b1 - b0) * frac)
        palette.append(f"#{r:02x}{g:02x}{b:02x}")
    return palette


def _gradient_figlet(text: str, font: str, stops: list[str]) -> Text:
    """Figlet metnini sol üstten sağ alta çapraz bir renk geçişiyle boyar."""
    lines = Figlet(font=font).renderText(text).rstrip("\n").split("\n")
    width = max(len(line) for line in lines)
    slant = 3  # her satır aşağı indikçe gradyan bu kadar karakter kayar
    palette = _gradient_palette(stops, width + slant * (len(lines) - 1))

    banner = Text(justify="center")
    for row, line in enumerate(lines):
        for col, ch in enumerate(line):
            banner.append(ch, style=f"bold {palette[col + slant * row]}" if ch.strip() else "")
        if row != len(lines) - 1:
            banner.append("\n")
    return banner


def _gradient_text(text: str, stops: list[str], style_suffix: str = "bold") -> Text:
    """Tek satırlık metni karakter karakter gradyanla boyar."""
    palette = _gradient_palette(stops, max(len(text), 1))
    result = Text()
    for i, ch in enumerate(text):
        result.append(ch, style=f"{style_suffix} {palette[i]}" if ch.strip() else "")
    return result


# ─── 愛 logosu (braille nokta sanatı) ────────────────────────────────────────

# Braille hücresindeki 2x4 noktanın (dx, dy) -> bit eşlemesi (U+2800 tabanı).
_DOT_BITS = ((0, 0, 1), (0, 1, 2), (0, 2, 4), (1, 0, 8), (1, 1, 16), (1, 2, 32), (0, 3, 64), (1, 3, 128))

_WIN_CJK_FONTS = ("YuGothB.ttc", "msgothic.ttc", "meiryob.ttc", "meiryo.ttc", "msmincho.ttc", "simsun.ttc")
_MAC_CJK_FONTS = ("PingFang.ttc", "Hiragino Sans GB.ttc", "ヒラギノ角ゴシック W3.ttc", "Apple Symbols.ttf")


def _cjk_font_candidates() -> list[Path]:
    """Platforma göre kanji glifi içerebilecek font yollarını sıralar."""
    import glob

    if sys.platform == "win32":
        fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        return [fonts_dir / name for name in _WIN_CJK_FONTS]

    if sys.platform == "darwin":
        dirs = ("/System/Library/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts")
        return [Path(d) / name for d in dirs for name in _MAC_CJK_FONTS]

    # Linux ve diğerleri: bilinen font dizinlerinde Noto CJK'yı rekürsif ara.
    dirs = ("/usr/share/fonts", "/usr/local/share/fonts",
            str(Path.home() / ".fonts"), str(Path.home() / ".local/share/fonts"))
    patterns = ("NotoSansCJK*.ttc", "NotoSerifCJK*.ttc", "NotoSansCJK*.otf",
                "*CJK*.ttc", "*CJK*.otf")
    found: list[Path] = []
    for directory in dirs:
        for pattern in patterns:
            found += [Path(p) for p in glob.glob(os.path.join(directory, "**", pattern), recursive=True)]
    return found


def _find_cjk_font(size: int):
    """İlk yüklenebilen CJK fontunu döner; hiçbiri yoksa None."""
    from PIL import ImageFont

    for path in _cjk_font_candidates():
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return None


def _kanji_dot_art(char: str, size: int = 56, threshold: int = 110) -> list[str] | None:
    """Kanjiyi sistem CJK fontuyla bitmap'e çizip braille noktalarına çevirir.
    Uygun font yoksa None döner (figlet banner'a düşülür)."""
    from PIL import Image, ImageDraw

    font = _find_cjk_font(size)
    if font is None:
        return None

    canvas = size * 2
    img = Image.new("L", (canvas, canvas), 0)
    ImageDraw.Draw(img).text((canvas // 2, canvas // 2), char, fill=255, font=font, anchor="mm")
    bbox = img.getbbox()
    if bbox is None:
        return None
    img = img.crop(bbox)

    # Yatay kütle merkezine göre ortala: sınırlayıcı kutu ortalaması, sağa uzanan
    # ince strokları da sayarak yoğun kütleyi (愛'nin gövdesi) hafifçe sola kaydırıp
    # figürü "kayık" gösteriyordu. Boş kalan tarafa dolgu ekleyip kütleyi ortalarız.
    px = img.load()
    width, height = img.size
    col_mass = [sum(px[x, y] for y in range(height)) for x in range(width)]
    total = sum(col_mass)
    if total:
        cx = sum(x * m for x, m in enumerate(col_mass)) / total
        pad = int(round(abs((width - 1 - cx) - cx)))
        if pad:
            canvas = Image.new("L", (width + pad, height), 0)
            canvas.paste(img, (pad if cx < (width - 1) / 2 else 0, 0))
            img = canvas
            px = img.load()
            width, height = img.size

    lines = []
    for y0 in range(0, height, 4):
        line = ""
        for x0 in range(0, width, 2):
            bits = 0
            for dx, dy, bit in _DOT_BITS:
                x, y = x0 + dx, y0 + dy
                if x < width and y < height and px[x, y] > threshold:
                    bits |= bit
            line += chr(0x2800 + bits)
        lines.append(line)
    return lines


_kanji_art_cache: list[str] | None = None
_kanji_art_rendered = False


def _kanji_art() -> list[str] | None:
    """Logo bir kez render edilir, sonrası önbellekten döner."""
    global _kanji_art_cache, _kanji_art_rendered
    if not _kanji_art_rendered:
        _kanji_art_cache = _kanji_dot_art(KANJI_LOGO)
        _kanji_art_rendered = True
    return _kanji_art_cache


# ─── Banner ──────────────────────────────────────────────────────────────────

def _key_value_grid(rows: list[tuple[str, str]]) -> Table:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style=ACCENT_SOFT, no_wrap=True)
    grid.add_column(overflow="fold")
    for key, value in rows:
        grid.add_row(f"{key}:", value)
    return grid


def _banner_left_column(dots: list[str]) -> Group:
    """Gradyanla boyanmış kanji logosu + altında künye satırları."""
    palette = _gradient_palette(KANJI_GRADIENT, len(dots))
    logo = Text(justify="center")
    for i, line in enumerate(dots):
        logo.append(line, style=f"bold {palette[i]}")
        if i != len(dots) - 1:
            logo.append("\n")

    routes = all_routes()
    sources = {r.source_ext for r in routes}
    caption = Text(t("banner.stats_line", routes=len(routes), formats=len(sources)),
                   style="dim", justify="center")

    return Group(logo, Text(), caption)


def _banner_right_column() -> Group:
    """Komut listesi ve desteklenen format özeti."""
    commands = _key_value_grid([(name, t(key)) for name, key in _COMMAND_HELP])

    sources = {r.source_ext for r in all_routes()}
    format_rows = []
    for icon, exts in _ICON_GROUPS:
        names = [e.lstrip(".") for e in exts if e in sources]
        if not names:
            continue
        shown = ", ".join(names[:5]) + (", …" if len(names) > 5 else "")
        format_rows.append((_group_name(icon).lower(), shown))

    return Group(
        Text(t("banner.commands"), style=f"bold {ACCENT}"),
        commands,
        Text(),
        Text(t("banner.formats"), style=f"bold {ACCENT}"),
        _key_value_grid(format_rows),
    )


def _fallback_banner_content() -> Text:
    """CJK fontu bulunamayan sistemler için figlet tabanlı banner içeriği."""
    content = Text(justify="center")
    content.append(_gradient_figlet("KATANA", font="ansi_shadow", stops=BANNER_GRADIENT))
    content.append("\n\n")
    content.append("─" * 10 + "  ", style="dim")
    content.append(_gradient_text("F I L E   C O N V E R T E R", BANNER_GRADIENT))
    content.append("  " + "─" * 10, style="dim")
    content.append("\n")
    for i, (name, _key) in enumerate(_COMMAND_HELP):
        if i:
            content.append("  ·  ", style="dim")
        content.append(name, style=f"bold {ACCENT}")
    return content


def _banner_content() -> tuple[RenderableType, tuple[int, int]]:
    """Logo üretilebiliyorsa iki sütunlu düzen, yoksa figlet banner."""
    dots = _kanji_art()
    if dots is None:
        return _fallback_banner_content(), (1, 6)

    layout = Table.grid(padding=(0, 5))
    layout.add_column(vertical="middle")
    layout.add_column(vertical="middle")
    layout.add_row(_banner_left_column(dots), _banner_right_column())
    return layout, (1, 4)


_frame_width_cache: dict[tuple[int, str], int] = {}


def frame_width() -> int:
    """Banner ve giriş panelinin ortak dış genişliği. Metinler dile göre
    değiştiği için önbellek (genişlik, dil) çiftiyle tutulur."""
    key = (console.width, i18n.current_language())
    if key not in _frame_width_cache:
        content, padding = _banner_content()
        natural = Measurement.get(console, console.options, content).maximum
        _frame_width_cache[key] = min(natural + padding[1] * 2 + 2, console.width)
    return _frame_width_cache[key]


def print_banner() -> None:
    content, padding = _banner_content()
    console.print()
    console.print(
        Panel(
            content,
            title=f"[bold {ACCENT}] {APP_NAME} {APP_VERSION} [/bold {ACCENT}]",
            subtitle=f"[dim]{t('banner.subtitle')}[/dim]",
            box=box.ROUNDED,
            border_style=BORDER,
            padding=padding,
            width=frame_width(),
        )
    )
    console.print()


# ─── Komut ekranları ('help', 'converts', 'tools'...) ───────────────────────

def _cmd_converts() -> None:
    """Desteklenen tüm dönüşümleri kategoriye göre gruplu bir tabloda gösterir."""
    matrix = conversion_matrix()
    total = sum(len(row["targets"]) for row in matrix)

    table = Table(
        title=f"[bold]{t('converts.title')}[/bold] [dim]({total} {t('unit.routes')})[/dim]",
        box=box.ROUNDED,
        border_style=BORDER,
        header_style="bold",
        padding=(0, 2),
    )
    table.add_column(t("converts.col.type"), style="bold")
    table.add_column(t("converts.col.source"), style="bold white")
    table.add_column(t("converts.col.targets"))

    has_external = False
    prev_group = None
    for row in matrix:
        ext = row["source"]
        icon = format_icon(ext)
        group = f"{icon} {_group_name(icon)}"
        if prev_group is not None and group != prev_group:
            table.add_section()
        targets = []
        for tgt in row["targets"]:
            name = tgt["target"].lstrip(".")
            if tgt["requires"]:
                name += "*"
                has_external = True
            targets.append(f"[{ACCENT}]{name}[/{ACCENT}]")
        table.add_row(group if group != prev_group else "", ext, "[dim] · [/dim]".join(targets))
        prev_group = group

    console.print(table)
    if has_external:
        console.print(f"[dim]{t('converts.footnote')}[/dim]")


def _cmd_tools() -> None:
    """Harici araçların (ffmpeg) kurulum durumunu gösterir."""
    table = Table(
        title=f"[bold]{t('tools.title')}[/bold]",
        box=box.ROUNDED,
        border_style=BORDER,
        header_style="bold",
        padding=(0, 2),
    )
    table.add_column(t("tools.col.tool"), style="bold white")
    table.add_column(t("tools.col.status"))
    table.add_column(t("tools.col.location"), overflow="fold")

    for tool in (FFMPEG,):
        path = find_tool(tool)
        if path:
            table.add_row(
                tool.friendly_name,
                f"[bold green]{t('tools.installed')}[/bold green]",
                f"[dim]{path}[/dim]",
            )
        else:
            table.add_row(
                tool.friendly_name,
                f"[bold red]{t('tools.missing')}[/bold red]",
                f"[dim]winget install --id {tool.winget_id}[/dim]",
            )

    # OCR opsiyonel bir ek — kuruluysa yeşil, değilse gri bilgi satırı.
    from katana.converters.ocr import ocr_available
    if ocr_available():
        table.add_row("Tesseract (OCR)", f"[bold green]{t('tools.installed')}[/bold green]", "")
    else:
        table.add_row("Tesseract (OCR)", f"[dim]{t('tools.optional')}[/dim]",
                      "[dim]winget install --id UB-Mannheim.TesseractOCR[/dim]")

    console.print(table)
    console.print(f"[dim]{t('tools.note')}[/dim]")


def _cmd_credit() -> None:
    """Geliştirici bilgilerini gösterir."""
    heading = Text()
    heading.append(_gradient_text("K A T A N A", BANNER_GRADIENT))
    heading.append("  File Converter", style="bold white")

    # Text() sarmalı: Rich, köşeli parantezli ham string'i markup sanabiliyor.
    info = Table.grid(padding=(0, 3))
    info.add_column(style=f"bold {ACCENT_SOFT}", no_wrap=True)
    info.add_column()
    info.add_row(t("credit.name"), Text(AUTHOR_NAME))
    info.add_row("GitHub", Text(AUTHOR_GITHUB) if AUTHOR_GITHUB else Text("—", style="dim"))
    info.add_row(t("credit.version"), Text(APP_VERSION))

    console.print(
        Panel(
            Group(heading, Text(), info, Text(), Text(COPYRIGHT, style="dim")),
            title=f"[bold]{t('credit.title')}[/bold]",
            title_align="left",
            box=box.ROUNDED,
            border_style=BORDER,
            expand=False,
            padding=(1, 4),
        )
    )


def _cmd_stats() -> None:
    """Bu oturumdaki dönüştürme sayılarını gösterir."""
    files, success = SESSION_STATS["files"], SESSION_STATS["success"]
    if files == 0:
        body = f"[dim]{t('stats.empty')}[/dim]"
    else:
        body = (
            f"[bold]{t('stats.converted')}[/bold] [bold green]{success}[/bold green][dim]/{files}[/dim]\n\n"
            f"{_ratio_bar(success, files)}  [dim]{_percent(round(success / files * 100))}[/dim]"
        )
    console.print(
        Panel(
            body,
            title=f"[bold]{t('stats.title')}[/bold]",
            title_align="left",
            box=box.ROUNDED,
            border_style=BORDER,
            expand=False,
            padding=(1, 3),
        )
    )


def confirm(message: str) -> bool:
    """Evet/hayır sorar (Enter = evet). i18n.YES_ANSWERS'a göre karar verir."""
    answer = console.input(f"[bold {ACCENT}]{message}[/bold {ACCENT}] ").strip().lower()
    return answer in i18n.YES_ANSWERS


def _cmd_undo() -> None:
    """Son dönüştürme grubunun çıktı dosyalarını (onay alarak) siler."""
    batch = history.last_batch()
    if batch is None:
        console.print(f"[dim]{t('undo.none')}[/dim]")
        return
    _, outputs = batch
    existing = [o for o in outputs if o.is_file()]
    if not existing:
        console.print(f"[dim]{t('undo.none')}[/dim]")
        return

    console.print(f"[bold]{t('undo.about', n=len(existing))}[/bold]")
    for out in existing[:12]:
        console.print(f"  [red]✗[/red] [dim]{out}[/dim]")
    if len(existing) > 12:
        console.print(f"  [dim]… (+{len(existing) - 12})[/dim]")

    if not confirm(t("undo.confirm")):
        console.print(f"[dim]{t('cli.cancelled')}[/dim]")
        return
    deleted, missing = history.undo_last()
    console.print(f"[bold green]✓[/bold green] {t('undo.done', n=len(deleted))}")
    if missing:
        console.print(f"[dim]{t('undo.missing', n=len(missing))}[/dim]")


def _cmd_language() -> None:
    """Arayüz dilini ok tuşlarıyla seçtirir; seçim kalıcı olarak kaydedilir."""
    current = i18n.current_language()
    choices = [
        questionary.Choice(title=f"{'●' if code == current else '○'}  {name}", value=code)
        for code, name in i18n.LANGUAGES.items()
    ]
    code = questionary.select(
        t("language.prompt"),
        choices=choices,
        default=current,
        style=MENU_STYLE,
        qmark="➜",
        pointer="❯",
        instruction=t("select.instruction"),
    ).ask()
    if code is None or code == current:
        return

    i18n.set_language(code)
    _cmd_clear()
    console.print(f"[bold green]✓[/bold green] {t('language.changed', name=i18n.LANGUAGES[code])}")


def _cmd_theme() -> None:
    """Renk temasını ok tuşlarıyla seçtirir; seçim kalıcı olarak kaydedilir."""
    current = themes.current_theme_id()

    # Her temanın adı ve degrade şeridi kendi renkleriyle önizlenir.
    preview = Table.grid(padding=(0, 3))
    preview.add_column(no_wrap=True)
    preview.add_column(no_wrap=True)
    for theme_id, theme in themes.THEMES.items():
        stops = list(theme.gradient)
        mark = Text("● " if theme_id == current else "○ ", style=theme.accent)
        name = _gradient_text(theme.name, stops)
        preview.add_row(mark + name, _gradient_text("█" * 24, stops))
    console.print(
        Panel(
            preview,
            title=f"[bold]{t('theme.title')}[/bold]",
            title_align="left",
            box=box.ROUNDED,
            border_style=BORDER,
            expand=False,
            padding=(1, 3),
        )
    )

    choices = [
        questionary.Choice(
            title=f"{'●' if theme_id == current else '○'}  {theme.name}",
            value=theme_id,
        )
        for theme_id, theme in themes.THEMES.items()
    ]
    theme_id = questionary.select(
        t("theme.prompt"),
        choices=choices,
        default=current,
        style=MENU_STYLE,
        qmark="➜",
        pointer="❯",
        instruction=t("select.instruction"),
    ).ask()
    if theme_id is None or theme_id == current:
        return

    themes.set_theme(theme_id)
    apply_theme()
    _cmd_clear()
    console.print(f"[bold green]✓[/bold green] {t('theme.changed', name=themes.THEMES[theme_id].name)}")


def _cmd_clear() -> None:
    """Ekranı temizleyip banner'ı yeniden çizer."""
    console.clear()
    print_banner()


def _cmd_help() -> None:
    """Komutları ve temel kullanımı özetler."""
    table = Table.grid(padding=(0, 3))
    table.add_column(style=f"bold {ACCENT_SOFT}", no_wrap=True)
    table.add_column()
    for name, key in _COMMAND_HELP:
        table.add_row(name, t(key))

    usage = Text()
    usage.append(f"{t('help.usage')}\n", style=f"bold {ACCENT}")
    for tip in ("help.tip1", "help.tip2"):
        usage.append(f"• {t(tip)}\n", style="dim")
    usage.append(f"• {t('help.tip3')}", style="dim")
    usage.append("katana file.png --to ico", style=ACCENT)

    console.print(
        Panel(
            Group(table, Text(), usage),
            title=f"[bold]{t('help.title')}[/bold]",
            title_align="left",
            box=box.ROUNDED,
            border_style=BORDER,
            expand=False,
            padding=(1, 3),
        )
    )


COMMANDS = {
    "help": _cmd_help,
    "converts": _cmd_converts,
    "tools": _cmd_tools,
    "credit": _cmd_credit,
    "stats": _cmd_stats,
    "undo": _cmd_undo,
    "open": open_last_output,
    "language": _cmd_language,
    "theme": _cmd_theme,
    "clear": _cmd_clear,
}


# ─── Prompt'lar ──────────────────────────────────────────────────────────────

def _strip_quotes(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def prompt_for_paths() -> list[Path] | None:
    """Dosya/klasör yolları ister; komut yazılırsa ekranını gösterip tekrar
    sorar. Boş giriş veya 'q' çıkış demektir (None)."""
    console.print(
        Panel(
            f"[bold {ACCENT}]{t('prompt.title')}[/bold {ACCENT}]\n"
            f"[dim]   {t('prompt.hint1')}[/dim]\n"
            f"[dim]    {t('prompt.hint2')}[/dim]\n"
            f"[dim]   {t('prompt.hint3', help=f'[{ACCENT}]help[/{ACCENT}][dim]')}[/dim]",
            box=box.ROUNDED,
            border_style=BORDER,
            padding=(1, 3),
            width=frame_width(),
        )
    )
    while True:
        raw = console.input(f"[bold {ACCENT}]➜  [/bold {ACCENT}]").strip()
        if not raw or raw.lower() in ("q", "quit", "exit"):
            return None

        command = COMMANDS.get(raw.lower())
        if command:
            console.print()
            command()
            console.print()
            continue

        tokens = shlex.split(raw, posix=False)
        return [Path(_strip_quotes(token)) for token in tokens if token.strip()]


def prompt_continue() -> bool:
    """Devam edilsin mi? Enter = devam, 'o' = çıktı klasörünü aç, 'q' = çık."""
    while True:
        answer = console.input(f"\n[dim]{t('continue.prompt')}[/dim] ").strip().lower()
        if answer == "o":
            open_last_output()
            continue
        return answer not in ("q", "quit", "exit")


def prompt_install_tool(tool) -> bool:
    """Eksik harici aracın kurulup kurulmayacağını sorar (Enter = evet)."""
    console.print(
        Panel(
            f"[bold {ACCENT}]{t('install.notfound', tool=tool.friendly_name)}[/bold {ACCENT}]\n"
            f"[dim]{t('install.required', installer=installer_name(tool))}[/dim]",
            box=box.ROUNDED,
            border_style=BORDER,
            expand=False,
            padding=(1, 3),
        )
    )
    answer = console.input(f"[bold {ACCENT}]{t('install.ask')}[/bold {ACCENT}]").strip().lower()
    return answer in i18n.YES_ANSWERS


def batch_progress():
    """Toplu dönüştürme için dosya adı + sayaç + süre gösteren progress bar."""
    return Progress(
        SpinnerColumn(spinner_name="dots12", style=ACCENT),
        TextColumn(f"[bold {ACCENT}]{{task.fields[filename]}}[/bold {ACCENT}]"),
        BarColumn(
            bar_width=30,
            style="grey35",
            complete_style=ACCENT,
            finished_style="green",
            pulse_style=ACCENT,
        ),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def _remembered_target(source_ext: str) -> str | None:
    return i18n._load_config().get("last_targets", {}).get(source_ext)


def _remember_target(source_ext: str, target_ext: str) -> None:
    last_targets = i18n._load_config().get("last_targets", {})
    last_targets[source_ext] = target_ext
    i18n._save_config(last_targets=last_targets)


def select_route(routes: list[ConversionRoute]) -> ConversionRoute | None:
    """Hedef format seçtirir; tek seçenek varsa direkt döner, iptalde None.
    Bu uzantı için önceki seçim varsa menüde önceden işaretli gelir."""
    if len(routes) == 1:
        return routes[0]

    direct = [r for r in routes if not r.via]
    bridged = [r for r in routes if r.via]

    remembered = _remembered_target(routes[0].source_ext)
    # Hatırlanan hedef için önce doğrudan, yoksa köprü rotasını varsayılan seç.
    default_route = (next((r for r in direct if r.target_ext == remembered), None)
                     or next((r for r in bridged if r.target_ext == remembered), None))

    def _choice(route: ConversionRoute) -> questionary.Choice:
        title = (f"{format_icon(route.target_ext)}  {route.target_ext.lstrip('.').upper():<6} — "
                 f"{i18n.translate_label(route.label)}")
        if route is default_route:
            title += f"  {t('select.last_used')}"
        if route.via:
            inter = ", ".join(v.lstrip(".") for v in route.via)
            title += f"  [{t('select.via', inter=inter)}]"
        return questionary.Choice(title=title, value=route)

    choices: list = [_choice(r) for r in direct]
    if bridged:
        choices.append(questionary.Separator(f"  ── {t('select.bridge_header')} ──"))
        choices += [_choice(r) for r in bridged]

    route = questionary.select(
        t("select.question"),
        choices=choices,
        default=default_route,
        style=MENU_STYLE,
        qmark="➜",
        pointer="❯",
        instruction=t("select.instruction"),
    ).ask()

    if route is not None and route.target_ext != remembered:
        _remember_target(route.source_ext, route.target_ext)
    return route


_VIDEO_SOURCE_EXTS = (".mov", ".mkv", ".webm", ".avi")


def prompt_route_options(route: ConversionRoute) -> None:
    """Rotanın ayarlanabilir parametresi varsa (JPEG kalitesi, çözünürlük)
    sorar; Enter varsayılanı seçer."""
    if route.target_ext in (".jpg", ".jpeg") and route.source_ext != ".svg":
        choices = [
            questionary.Choice(title=f"95 — {t('options.jpeg.high')}", value=95),
            questionary.Choice(title=f"85 — {t('options.jpeg.balanced')}", value=85),
            questionary.Choice(title=f"75 — {t('options.jpeg.small')}", value=75),
        ]
        quality = questionary.select(
            t("options.jpeg.question"),
            choices=choices,
            default=95,
            style=MENU_STYLE,
            qmark="➜",
            pointer="❯",
            instruction=t("select.instruction"),
        ).ask()
        convert_options.set_option("jpeg_quality", quality if quality is not None else 95)

    elif route.target_ext == ".mp4" and route.source_ext in _VIDEO_SOURCE_EXTS:
        choices = [
            questionary.Choice(title=t("options.video.original"), value=0),
            questionary.Choice(title="1080p", value=1080),
            questionary.Choice(title="720p", value=720),
            questionary.Choice(title="480p", value=480),
        ]
        height = questionary.select(
            t("options.video.question"),
            choices=choices,
            default=0,
            style=MENU_STYLE,
            qmark="➜",
            pointer="❯",
            instruction=t("select.instruction"),
        ).ask()
        convert_options.set_option("video_height", height or None)


# ─── Sonuç çıktıları ─────────────────────────────────────────────────────────

def print_error(message: str) -> None:
    console.print(f"[bold red]✗  {t('error.prefix')}:[/bold red] {message}\n")


def print_group_header(ext: str, count: int) -> None:
    """Her uzantı grubunun başına ince bir ayraç basar."""
    console.print(
        Rule(
            f"{format_icon(ext)}  [bold {ACCENT}]{ext}[/bold {ACCENT}]"
            f" [dim]·[/dim] [bold]{count}[/bold] {t('unit.files')}",
            style="dim",
            align="left",
        )
    )


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


def print_success_panel(output_path: Path) -> None:
    size = f"  [dim]({_human_size(output_path.stat().st_size)})[/dim]" if output_path.exists() else ""
    console.print(
        Panel(
            f"[bold green]{t('success.converted')}[/bold green]\n\n"
            f"[bold white]{output_path}[/bold white]{size}",
            box=box.ROUNDED,
            border_style="green",
            expand=False,
            padding=(1, 3),
        )
    )


def _ratio_bar(success: int, total: int, width: int = 20) -> str:
    """Özet paneli için '████████░░' tarzı mini bir oran çubuğu üretir."""
    filled = round(success / total * width) if total else width
    return f"[green]{'█' * filled}[/green][grey35]{'░' * (width - filled)}[/grey35]"


def _percent(value: int) -> str:
    """Yüzde işaretinin yeri dile göre değişir: Türkçede %70, diğerlerinde 70%."""
    return f"%{value}" if i18n.current_language() == "tr" else f"{value}%"


def print_summary_panel(total: int, success: int) -> None:
    if total == 0 or success == total:
        border, icon = "green", "✓"
    elif success == 0:
        border, icon = "red", "✗"
    else:
        border, icon = "yellow", "⚠"

    percent = _percent(round(success / total * 100) if total else 0)
    text = t("summary.text", total=total, success=f"[bold {border}]{success}[/bold {border}]")
    console.print(
        Panel(
            f"[bold]{icon}  {text}[/bold]\n\n"
            f"{_ratio_bar(success, total)}  [dim]{percent}[/dim]",
            title=f"[bold]{t('summary.title')}[/bold]",
            title_align="left",
            box=box.ROUNDED,
            border_style=border,
            expand=False,
            padding=(1, 3),
        )
    )
