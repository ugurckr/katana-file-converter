"""Sürüklenip bırakılan dosyaların terminal önizlemesi ve seçimi.

Görsel önizleme iki katmanlıdır:
  * Sixel — terminal destekliyorsa (otomatik algılanır) gerçek, yüksek çözünürlüklü
    satır-içi görüntü.
  * Yarım-blok — her truecolor terminalde çalışan `▀` tabanlı renkli küçük resim
    (Sixel yoksa güvenli geri-dönüş).
PDF ilk sayfa, metin ilk satırlar, ses/video süre/çözünürlük (ffprobe) de gösterilir.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import questionary
from PIL import Image, ImageFilter
from rich.cells import cell_len, set_cell_size
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from katana import ui
from katana.i18n import t

# PIL ile açılıp küçük resmi çıkarılabilen raster görseller.
_RASTER = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".gif", ".heic", ".ico", ".icns"}
# İlk satırları gösterilebilecek metin/veri dosyaları.
_TEXTLIKE = {".txt", ".csv", ".json", ".yaml", ".yml", ".toml", ".xml", ".md", ".html", ".sql", ".svg"}
# ffprobe ile süre/çözünürlük okunabilen ses/video dosyaları.
_MEDIA = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".mp3", ".wav", ".m4a", ".flac", ".ogg"}

_THUMB_COLS = 30       # yarım-blok küçük resim genişliği (karakter)
_MAX_THUMB_ROWS = 15
# Sixel çerçeveli ızgara geometrisi (hücre cinsinden)
_IMG_COLS = 30         # kart içindeki görüntü alanı genişliği
_IMG_ROWS = 14         # kart içindeki görüntü alanı yüksekliği
_CARD_W = _IMG_COLS + 4  # │ + boşluk + IMG + boşluk + │
_CARD_H = _IMG_ROWS + 3  # üst çizgi + görüntü + ad + alt çizgi
_COL_GAP = 2
_ROW_GAP = 1
_MAX_CARDS = 24


# ─── Ortak yardımcılar ───────────────────────────────────────────────────────

def _human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"


def _file_size(path: Path) -> str:
    try:
        return _human_size(path.stat().st_size)
    except OSError:
        return "?"


def _raster_image(path: Path) -> Image.Image | None:
    try:
        im = Image.open(path)
        im.load()
        return im.convert("RGB")
    except Exception:
        return None


def _pdf_first_page(path: Path) -> tuple[Image.Image | None, int]:
    """PDF ilk sayfasını PIL görseli + sayfa sayısı olarak döner."""
    import io

    import fitz

    try:
        doc = fitz.open(path)
    except Exception:
        return None, 0
    try:
        if doc.page_count == 0:
            return None, 0
        pix = doc[0].get_pixmap()
        return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"), doc.page_count
    except Exception:
        return None, 0
    finally:
        doc.close()


def _text_preview(path: Path, max_lines: int = 6, width: int = _THUMB_COLS) -> Text | None:
    """Metin/veri dosyasının ilk satırlarını soluk renkte döner."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = [next(f, None) for _ in range(max_lines)]
    except OSError:
        return None
    body = Text()
    shown = 0
    for line in lines:
        if line is None:
            break
        clean = line.rstrip("\n").replace("\t", "  ")
        if len(clean) > width:
            clean = clean[: width - 1] + "…"
        body.append(clean + "\n", style="dim")
        shown += 1
    return body if shown else None


def _ffprobe() -> str | None:
    """Sistemde ffprobe yolunu bulur (ffmpeg'in yanında da arar)."""
    found = shutil.which("ffprobe")
    if found:
        return found
    from katana.converters.tooling import FFMPEG, find_tool
    ffmpeg = find_tool(FFMPEG)
    if ffmpeg:
        candidate = Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix)
        if candidate.exists():
            return str(candidate)
    return None


def _media_info(path: Path) -> str | None:
    """ffprobe ile süre ve (varsa) video yüksekliğini "3:42 · 1080p" olarak döner."""
    exe = _ffprobe()
    if not exe:
        return None
    try:
        result = subprocess.run(
            [exe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None

    parts = []
    duration = data.get("format", {}).get("duration")
    if duration:
        try:
            total = int(float(duration))
            parts.append(f"{total // 60}:{total % 60:02d}")
        except ValueError:
            pass
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and stream.get("height"):
            parts.append(f"{stream['height']}p")
            break
    return " · ".join(parts) or None


def _info_line(path: Path) -> str:
    """Dosyanın metadata özeti (boyut + türüne özel bilgi)."""
    ext = path.suffix.lower()
    size = _file_size(path)
    if ext in _RASTER:
        im = _raster_image(path)
        if im is not None:
            return f"{im.width}×{im.height} · {size}"
    elif ext == ".pdf":
        _, pages = _pdf_first_page(path)
        if pages:
            return f"{pages} {t('unit.pages')} · {size}"
    elif ext in _MEDIA:
        media = _media_info(path)
        if media:
            return f"{media} · {size}"
    return size


def _placeholder(icon: str, ext: str) -> Text:
    """Küçük resmi olmayan dosyalar için ikon + uzantı yer tutucusu."""
    body = Text(justify="center")
    body.append("\n")
    body.append(icon + "\n\n", style="bold")
    body.append(ext.lstrip(".").upper() or "?", style="dim")
    body.append("\n")
    return body


# ─── Yarım-blok küçük resim (her truecolor terminalde) ───────────────────────

def _image_thumbnail(im: Image.Image, cols: int = _THUMB_COLS) -> Text:
    """Görseli yarım-blok (▀) karakterlerle renkli küçük resme çevirir: her
    hücre üstte ön, altta arka renk taşır → hücre başına 2 dikey piksel."""
    im = im.convert("RGB")
    w, h = im.size
    rows = max(1, round(cols * (h / w) * 0.5))
    tw = cols
    if rows > _MAX_THUMB_ROWS:  # çok uzun görseli kutuya sığdır, en/boy koru
        rows = _MAX_THUMB_ROWS
        tw = max(1, round(rows * 2 * (w / h)))
    # LANCZOS keskin küçültme sağlar; hafif unsharp maske küçük resmi netleştirir.
    small = im.resize((tw, rows * 2), Image.LANCZOS)
    small = small.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=0))
    px = small.load()

    pad = cols - tw
    left = " " * (pad // 2)
    right = " " * (pad - pad // 2)
    art = Text()
    for y in range(0, rows * 2, 2):
        art.append(left)
        for x in range(tw):
            r, g, b = px[x, y]
            r2, g2, b2 = px[x, y + 1]
            art.append("▀", style=f"#{r:02x}{g:02x}{b:02x} on #{r2:02x}{g2:02x}{b2:02x}")
        art.append(right)
        if y < rows * 2 - 2:
            art.append("\n")
    return art


def _card(index: int, path: Path) -> Panel:
    """Yarım-blok galeri için tek dosya kartı (başlık + önizleme + metadata)."""
    ext = path.suffix.lower()
    icon = ui.format_icon(ext)
    info = _file_size(path)

    body: Text | None = None
    if ext in _RASTER:
        im = _raster_image(path)
        if im is not None:
            body = _image_thumbnail(im)
            info = f"{im.width}×{im.height} · {info}"
    elif ext == ".pdf":
        im, pages = _pdf_first_page(path)
        if im is not None:
            body = _image_thumbnail(im)
        if pages:
            info = f"{pages} {t('unit.pages')} · {info}"
    elif ext in _TEXTLIKE:
        body = _text_preview(path)
    elif ext in _MEDIA:
        media = _media_info(path)
        if media:
            info = f"{media} · {info}"

    if body is None:
        body = _placeholder(icon, ext)

    name = path.name
    if len(name) > _THUMB_COLS:
        name = name[: _THUMB_COLS - 1] + "…"

    return Panel(
        Group(body, Text(name, overflow="ellipsis", no_wrap=True)),
        title=f"[bold {ui.ACCENT}]{index}[/bold {ui.ACCENT}] {icon}",
        title_align="left",
        subtitle=f"[dim]{info}[/dim]",
        border_style=ui.BORDER,
        padding=(0, 1),
        width=_THUMB_COLS + 4,
    )


def _halfblock_gallery(files: list[Path]) -> None:
    cards = []
    for i, path in enumerate(files[:_MAX_CARDS], 1):
        try:
            cards.append(_card(i, path))
        except Exception:
            cards.append(Panel(Text(path.name, overflow="ellipsis"),
                               title=f"{i}", border_style=ui.BORDER, width=_THUMB_COLS + 4))
    ui.console.print(Columns(cards, padding=(1, 2), expand=False))


# ─── Sixel (terminal destekliyorsa) ──────────────────────────────────────────

_sixel_cache: bool | None = None


def _term_query(query: str, end: str, timeout: float = 0.25) -> str:
    """Terminale bir sorgu dizisi yazıp `end` karakteriyle biten yanıtı okur."""
    if sys.platform == "win32":
        return _term_query_windows(query, end, timeout)

    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        sys.stdout.write(query)
        sys.stdout.flush()
        resp = ""
        while True:
            ready, _, _ = select.select([fd], [], [], timeout)
            if not ready:
                break
            ch = sys.stdin.read(1)
            resp += ch
            if ch == end:
                break
        return resp
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _term_query_windows(query: str, end: str, timeout: float) -> str:
    """Windows'ta VT giriş/çıkışını geçici açıp terminal yanıtını okur."""
    import ctypes
    import msvcrt
    import time

    kernel32 = ctypes.windll.kernel32
    h_out = kernel32.GetStdHandle(-11)
    h_in = kernel32.GetStdHandle(-10)
    old_out = ctypes.c_uint()
    old_in = ctypes.c_uint()
    if not kernel32.GetConsoleMode(h_out, ctypes.byref(old_out)):
        return ""
    if not kernel32.GetConsoleMode(h_in, ctypes.byref(old_in)):
        return ""

    enable_vt_output = 0x0004
    enable_vt_input = 0x0200
    try:
        kernel32.SetConsoleMode(h_out, old_out.value | enable_vt_output)
        kernel32.SetConsoleMode(h_in, enable_vt_input)  # satır/echo kapalı, ham VT
        sys.stdout.write(query)
        sys.stdout.flush()
        deadline = time.monotonic() + timeout
        resp = ""
        while time.monotonic() < deadline:
            if msvcrt.kbhit():
                resp += msvcrt.getwch()
                if resp.endswith(end):
                    break
            else:
                time.sleep(0.005)
        return resp
    finally:
        kernel32.SetConsoleMode(h_out, old_out.value)
        kernel32.SetConsoleMode(h_in, old_in.value)


def _detect_sixel() -> bool:
    """DA1 (ESC[c) yanıtındaki '4' özniteliği Sixel desteği demektir."""
    if not (sys.stdout.isatty() and sys.stdin.isatty()):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        resp = _term_query("\033[c", "c")
    except Exception:
        return False
    if "[?" not in resp or "c" not in resp:
        return False
    body = resp.split("[?", 1)[1].split("c", 1)[0]
    attrs = body.replace(";", " ").split()
    return "4" in attrs[1:]  # ilk değer cihaz sınıfı, gerisi yetenekler


_cell_cache: tuple[int, int] | None = None


def _cell_pixel_size() -> tuple[int, int]:
    """Bir karakter hücresinin (genişlik, yükseklik) pikselini döner. ESC[16t ile
    sorar; alınamazsa (10, 20) varsayar. KATANA_CELL=GxY ile elle ayarlanabilir."""
    global _cell_cache
    if _cell_cache is not None:
        return _cell_cache
    env = os.environ.get("KATANA_CELL", "").lower()
    if "x" in env:
        try:
            w, h = env.split("x")
            _cell_cache = (int(w), int(h))
            return _cell_cache
        except ValueError:
            pass
    cw = ch = None
    try:
        resp = _term_query("\033[16t", "t")
        body = resp.split("[", 1)[1].rstrip("t") if "[" in resp else ""
        parts = body.split(";")
        if len(parts) >= 3 and parts[0] == "6":
            ch = int(parts[1])
            cw = int(parts[2])
    except Exception:
        pass
    _cell_cache = (cw or 10, ch or 20)
    return _cell_cache


def supports_sixel() -> bool:
    """Sixel desteğini (bir kez) belirler. KATANA_SIXEL ile elle geçersiz kılınabilir."""
    global _sixel_cache
    if _sixel_cache is not None:
        return _sixel_cache
    override = os.environ.get("KATANA_SIXEL")
    if override is not None:
        _sixel_cache = override.strip().lower() not in ("", "0", "false", "no")
    else:
        _sixel_cache = _detect_sixel()
    return _sixel_cache


def _sixel_band(row: bytearray) -> str:
    """Bir renk bandını sixel baytlarına (63+bit) çevirir, RLE ile sıkıştırır."""
    out = []
    i, n = 0, len(row)
    while i < n:
        value = row[i]
        j = i + 1
        while j < n and row[j] == value:
            j += 1
        run = j - i
        ch = chr(63 + value)
        out.append(f"!{run}{ch}" if run >= 4 else ch * run)
        i = j
    return "".join(out)


def _sixel_encode(im: Image.Image, max_colors: int = 128) -> str:
    """PIL görselini Sixel (DCS ... ST) dizesine kodlar (saf Python)."""
    pal = im.convert("RGB").quantize(colors=max_colors, method=Image.MEDIANCUT)
    w, h = pal.size
    palette = pal.getpalette()
    data = list(pal.getdata())

    parts = ["\033Pq", f'"1;1;{w};{h}']
    for idx in sorted(set(data)):
        r = round(palette[idx * 3] / 255 * 100)
        g = round(palette[idx * 3 + 1] / 255 * 100)
        b = round(palette[idx * 3 + 2] / 255 * 100)
        parts.append(f"#{idx};2;{r};{g};{b}")

    for y0 in range(0, h, 6):
        rows = min(6, h - y0)
        bands: dict[int, bytearray] = {}
        for i in range(rows):
            base = (y0 + i) * w
            bit = 1 << i
            for x in range(w):
                color = data[base + x]
                band = bands.get(color)
                if band is None:
                    band = bytearray(w)
                    bands[color] = band
                band[x] |= bit
        parts.append("$".join(f"#{color}{_sixel_band(band)}" for color, band in sorted(bands.items())))
        parts.append("-")
    parts.append("\033\\")
    return "".join(parts)


def _fit_box(im: Image.Image, box: tuple[int, int]) -> Image.Image:
    """Görseli (bw, bh) piksel kutusuna en/boy koruyarak sığdırır."""
    im = im.convert("RGB")
    w, h = im.size
    bw, bh = box
    scale = min(bw / w, bh / h)
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    resized = im.resize(size, Image.LANCZOS)
    if scale < 1:
        resized = resized.filter(ImageFilter.UnsharpMask(radius=1.0, percent=90, threshold=0))
    return resized


def _ellipsize(text: str, width: int) -> str:
    if cell_len(text) <= width:
        return text
    return set_cell_size(text, max(1, width - 1)) + "…"


def _center(text: str, width: int) -> str:
    length = cell_len(text)
    if length >= width:
        return set_cell_size(text, width)
    pad = width - length
    return " " * (pad // 2) + text + " " * (pad - pad // 2)


def _hborder(left: str, right: str, label: str, label_style: str) -> Text:
    """Kart üst/alt çizgisi: köşeler + ortada etiket, tam _CARD_W hücre."""
    line = Text()
    line.append(left, style=ui.BORDER)
    line.append("─", style=ui.BORDER)
    used = 2 + cell_len(label)
    if label:
        line.append(label, style=label_style)
    fill = _CARD_W - used - 1
    if fill > 0:
        line.append("─" * fill, style=ui.BORDER)
    line.append(right, style=ui.BORDER)
    return line


def _content_line(inner: str, style: str = "") -> Text:
    """Kart içerik satırı: │ + boşluk + inner(_IMG_COLS) + boşluk + │."""
    line = Text()
    line.append("│ ", style=ui.BORDER)
    line.append(set_cell_size(inner, _IMG_COLS), style=style)
    line.append(" │", style=ui.BORDER)
    return line


def _grid_card(index: int, path: Path) -> tuple[list[Text], Image.Image | None]:
    """Kartın satırlarını ve (görsel/pdf ise) üstüne bindirilecek PIL görselini döner."""
    ext = path.suffix.lower()
    icon = ui.format_icon(ext)
    info = _ellipsize(_info_line(path), _CARD_W - 6)

    image = None
    if ext in _RASTER:
        image = _raster_image(path)
    elif ext == ".pdf":
        image, _pages = _pdf_first_page(path)

    lines = [_hborder("╭", "╮", f" {index} {icon} ", f"bold {ui.ACCENT}")]
    if image is not None:
        lines += [_content_line(" " * _IMG_COLS) for _ in range(_IMG_ROWS)]  # sixel bindirilecek
    elif ext in _TEXTLIKE:
        preview = _text_preview(path, max_lines=_IMG_ROWS, width=_IMG_COLS)
        rows = preview.plain.split("\n") if preview else []
        lines += [_content_line(rows[i] if i < len(rows) else "", style="dim") for i in range(_IMG_ROWS)]
    else:
        mid = _IMG_ROWS // 2
        for i in range(_IMG_ROWS):
            if i == mid - 1:
                lines.append(_content_line(_center(icon, _IMG_COLS)))
            elif i == mid:
                lines.append(_content_line(_center(ext.lstrip(".").upper() or "?", _IMG_COLS), style="dim"))
            else:
                lines.append(_content_line(" " * _IMG_COLS))

    lines.append(_content_line(_ellipsize(path.name, _IMG_COLS)))
    lines.append(_hborder("╰", "╯", f" {info} ", "dim"))
    return lines, image


def _sixel_grid(files: list[Path]) -> None:
    """Çerçeveli kartları yan yana yazıp görüntü alanlarına Sixel bindirir."""
    shown = files[:_MAX_CARDS]
    cols = max(1, (ui.console.width + _COL_GAP) // (_CARD_W + _COL_GAP))
    cards = [_grid_card(i, path) for i, path in enumerate(shown, 1)]
    rows = (len(cards) + cols - 1) // cols
    total_lines = rows * _CARD_H + (rows - 1) * _ROW_GAP

    overlays: list[tuple[Image.Image, int, int]] = []
    for r in range(rows):
        row_cards = cards[r * cols:(r + 1) * cols]
        for k in range(_CARD_H):
            line = Text()
            for ci, (clines, _img) in enumerate(row_cards):
                if ci:
                    line.append(" " * _COL_GAP)
                line.append_text(clines[k])
            ui.console.print(line)
        if r < rows - 1:
            for _ in range(_ROW_GAP):
                ui.console.print()
        for ci, (_clines, img) in enumerate(row_cards):
            if img is None:
                continue
            img_top = r * (_CARD_H + _ROW_GAP) + 1
            overlays.append((img, total_lines - img_top, ci * (_CARD_W + _COL_GAP) + 2))

    if not overlays:
        return
    cell_w, cell_h = _cell_pixel_size()
    box = (_IMG_COLS * cell_w, _IMG_ROWS * cell_h)
    ui.console.file.flush()
    chunks = []
    for img, up, left in overlays:
        try:
            sixel = _sixel_encode(_fit_box(img, box))
        except Exception:
            continue
        seq = "\0337" + f"\033[{up}A" + "\r"
        if left:
            seq += f"\033[{left}C"
        chunks.append(seq + sixel + "\0338")
    ui.console.file.write("".join(chunks))
    ui.console.file.flush()


# ─── Galeri + seçim ──────────────────────────────────────────────────────────

def preview_gallery(files: list[Path]) -> None:
    """Dosyaları önizler: Sixel destekleniyorsa satır-içi görüntü, yoksa yarım-blok."""
    if supports_sixel():
        _sixel_grid(files)
    else:
        _halfblock_gallery(files)
    if len(files) > _MAX_CARDS:
        ui.console.print(f"[dim]… +{len(files) - _MAX_CARDS}[/dim]")


def select_files(files: list[Path]) -> list[Path] | None:
    """Galeriyi gösterir ve kullanıcının dönüştüreceği dosyaları seçtirir.
    Hepsi öntanımlı işaretlidir. İptal/boş seçimde None döner."""
    ui.console.print()
    preview_gallery(files)
    ui.console.print()

    choices = [
        questionary.Choice(title=f"{i} · {path.name}", value=path, checked=True)
        for i, path in enumerate(files, 1)
    ]
    selected = questionary.checkbox(
        t("preview.select"),
        choices=choices,
        style=ui.MENU_STYLE,
        qmark="➜",
        instruction=t("preview.instruction"),
    ).ask()
    return selected or None
