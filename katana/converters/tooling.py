"""Harici araç (ffmpeg) tespiti ve winget ile kurulumu."""

import glob as glob_module
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExternalTool:
    command: str
    friendly_name: str
    winget_id: str
    manual_url: str
    # macOS Homebrew formül adı ve Linux paket adı (platforma göre kurulum için).
    brew_id: str = ""
    linux_package: str = ""
    # winget bazı paketleri PATH'e eklemiyor; tipik kurulum yerleri buradan taranır.
    fallback_globs: tuple[str, ...] = field(default_factory=tuple)


FFMPEG = ExternalTool(
    command="ffmpeg",
    friendly_name="ffmpeg",
    winget_id="Gyan.FFmpeg",
    manual_url="https://ffmpeg.org/download.html",
    brew_id="ffmpeg",
    linux_package="ffmpeg",
    fallback_globs=(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\**\ffmpeg.exe",
        r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe",
    ),
)

# Linux paket yöneticileri: (komut adı, kurulum komut şablonu). İlk bulunan kullanılır.
_LINUX_MANAGERS: tuple[tuple[str, str], ...] = (
    ("apt", "sudo apt install -y {pkg}"),
    ("dnf", "sudo dnf install -y {pkg}"),
    ("pacman", "sudo pacman -S --noconfirm {pkg}"),
    ("zypper", "sudo zypper install -y {pkg}"),
)


def _linux_manager() -> tuple[str, str] | None:
    """Sistemdeki ilk bilinen paket yöneticisini (ad, şablon) döner."""
    for name, template in _LINUX_MANAGERS:
        if shutil.which(name):
            return name, template
    return None
class MissingToolError(Exception):
    """Bir dönüştürme için gereken harici araç sistemde bulunamadı."""

    def __init__(self, tool: ExternalTool):
        self.tool = tool
        super().__init__(f"{tool.friendly_name} sistemde bulunamadı.")


def _search_fallback_paths(tool: ExternalTool) -> str | None:
    """PATH'te olmayan aracı bilinen kurulum konumlarında arar (yalnızca Windows)."""
    if sys.platform != "win32":
        return None
    for pattern in tool.fallback_globs:
        expanded = os.path.expandvars(pattern)
        matches = glob_module.glob(expanded, recursive=True)
        if matches:
            return matches[0]
    return None


def find_tool(tool: ExternalTool) -> str | None:
    path = shutil.which(tool.command) or shutil.which(f"{tool.command}.exe")
    if path:
        return path

    found = _search_fallback_paths(tool)
    if found:
        # Bu process'in PATH'ine ekle ki subprocess çağrıları da bulabilsin.
        os.environ["PATH"] = os.path.dirname(found) + os.pathsep + os.environ.get("PATH", "")
        return found
    return None


def require_tool(tool: ExternalTool) -> str:
    path = find_tool(tool)
    if not path:
        raise MissingToolError(tool)
    return path


def _refresh_path_from_registry() -> None:
    """winget kurulumu sonrası PATH'i yeniden başlatmadan yansıtmayı dener."""
    if sys.platform != "win32":
        return
    import winreg

    def read_path(root, subkey: str) -> str:
        try:
            with winreg.OpenKey(root, subkey) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
                return value
        except OSError:
            return ""

    machine_path = read_path(
        winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    )
    user_path = read_path(winreg.HKEY_CURRENT_USER, r"Environment")
    combined = ";".join(p for p in (machine_path, user_path) if p)
    if combined:
        os.environ["PATH"] = combined + ";" + os.environ.get("PATH", "")


def auto_installable(tool: ExternalTool) -> bool:
    """Araç bu platformda otomatik (parolasız) kurulabiliyor mu? Windows'ta
    winget, macOS'ta brew varsa True; Linux'ta daima False (sudo istemez)."""
    if sys.platform == "win32":
        return shutil.which("winget") is not None
    if sys.platform == "darwin":
        return bool(tool.brew_id) and shutil.which("brew") is not None
    return False


def installer_name(tool: ExternalTool) -> str:
    """Bu platformdaki paket yöneticisinin adı (mesajlarda kullanılır)."""
    if sys.platform == "win32":
        return "winget"
    if sys.platform == "darwin":
        return "brew"
    manager = _linux_manager()
    return manager[0] if manager else ""


def install_command(tool: ExternalTool) -> str | None:
    """Aracı kurmak için gösterilecek komut; yoksa None. Linux'ta ilgili paket
    yöneticisinin sudo'lu komutu döner (kullanıcı elle çalıştırır)."""
    if sys.platform == "win32":
        return f"winget install --id {tool.winget_id} -e" if shutil.which("winget") else None
    if sys.platform == "darwin":
        return f"brew install {tool.brew_id}" if tool.brew_id and shutil.which("brew") else None
    manager = _linux_manager()
    if manager and tool.linux_package:
        return manager[1].format(pkg=tool.linux_package)
    return None


def _install_winget(tool: ExternalTool) -> bool:
    winget = shutil.which("winget")
    if not winget:
        return False
    subprocess.run(
        [
            winget, "install", "--id", tool.winget_id, "-e",
            "--accept-source-agreements", "--accept-package-agreements",
        ],
        check=False,
    )
    _refresh_path_from_registry()
    return find_tool(tool) is not None


def _install_brew(tool: ExternalTool) -> bool:
    brew = shutil.which("brew")
    if not brew or not tool.brew_id:
        return False
    subprocess.run([brew, "install", tool.brew_id], check=False)
    return find_tool(tool) is not None


def install_tool(tool: ExternalTool) -> bool:
    """Otomatik kurulabilen platformlarda kurar (Windows→winget, macOS→brew).
    Linux'ta hiçbir şey çalıştırmaz (bkz. install_command) ve False döner."""
    if sys.platform == "win32":
        return _install_winget(tool)
    if sys.platform == "darwin":
        return _install_brew(tool)
    return False
