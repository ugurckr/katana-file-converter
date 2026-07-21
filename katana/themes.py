"""Renk temaları ('theme' komutu). Seçim ~/.katana/config.json'da saklanır;
yeni tema için THEMES'e bir girdi eklemek yeterli."""

from dataclasses import dataclass

from katana import i18n


@dataclass(frozen=True)
class Theme:
    name: str
    accent: str                    # başlıklar ve vurgular
    accent_soft: str               # ikincil vurgular
    border: str                    # panel çerçeveleri
    gradient: tuple[str, str, str] # banner/logo degradesi


THEMES: dict[str, Theme] = {
    "katana": Theme(
        name="Katana",
        accent="#ff9d00",
        accent_soft="#c77f3f",
        border="#b45309",
        gradient=("#ff3d3d", "#ff6b35", "#ff9d00"),
    ),
    "sakura": Theme(
        name="Sakura",
        accent="#ff6eb4",
        accent_soft="#c77298",
        border="#b83b78",
        gradient=("#e83d84", "#ff6eb4", "#ffa3d1"),
    ),
    "umi": Theme(
        name="Umi",
        accent="#22d3ee",
        accent_soft="#5c9dc7",
        border="#0369a1",
        gradient=("#2563eb", "#0ea5e9", "#22d3ee"),
    ),
    "matcha": Theme(
        name="Matcha",
        accent="#22c55e",
        accent_soft="#6aa84f",
        border="#15803d",
        gradient=("#059669", "#22c55e", "#a3e635"),
    ),
    "murasaki": Theme(
        name="Murasaki",
        accent="#a855f7",
        accent_soft="#9678c0",
        border="#7e22ce",
        gradient=("#7c3aed", "#a855f7", "#e879f9"),
    ),
    "kohaku": Theme(
        name="Kōhaku",
        accent="#ef4444",
        accent_soft="#cf7d7d",
        border="#991b1b",
        gradient=("#dc2626", "#f87171", "#ffe4e6"),
    ),
    "sumi": Theme(
        name="Sumi",
        accent="#d4d4d8",
        accent_soft="#8b8b93",
        border="#71717a",
        gradient=("#52525b", "#a1a1aa", "#f4f4f5"),
    ),
    "kin": Theme(
        name="Kin",
        accent="#eab308",
        accent_soft="#b08d4a",
        border="#a16207",
        gradient=("#b45309", "#eab308", "#fde68a"),
    ),
    "neon": Theme(
        name="Neon",
        accent="#00e5ff",
        accent_soft="#b06bcf",
        border="#c026d3",
        gradient=("#ff00aa", "#a855f7", "#00e5ff"),
    ),
    "yoru": Theme(
        name="Yoru",
        accent="#818cf8",
        accent_soft="#7b86b8",
        border="#4338ca",
        gradient=("#4338ca", "#6366f1", "#93c5fd"),
    ),
}

DEFAULT_THEME = "katana"

_theme_id: str = i18n._load_config().get("theme") or DEFAULT_THEME
if _theme_id not in THEMES:
    _theme_id = DEFAULT_THEME


def current_theme_id() -> str:
    return _theme_id


def current_theme() -> Theme:
    return THEMES[_theme_id]


def set_theme(theme_id: str) -> None:
    """Temayı değiştirir ve seçimi config dosyasına kalıcı olarak yazar."""
    global _theme_id
    if theme_id not in THEMES:
        raise ValueError(f"Desteklenmeyen tema: {theme_id}")
    _theme_id = theme_id
    i18n._save_config(theme=theme_id)
