"""Windows sağ-tık menüsü girdisi (HKCU, yönetici hakkı gerektirmez)."""

import sys

_KEY = r"Software\Classes\*\shell\Katana"
_LABEL = "Katana ile dönüştür"


def _command() -> str:
    # cmd /k: pencere açık kalsın, etkileşimli format seçimi yapılabilsin.
    return f'cmd /k ""{sys.executable}" -m katana --pick "%1""'


def install() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _KEY) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, _LABEL)
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, sys.executable)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _KEY + r"\command") as cmd_key:
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, _command())
        return True
    except OSError:
        return False


def uninstall() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    for sub in (_KEY + r"\command", _KEY):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
        except FileNotFoundError:
            pass
        except OSError:
            return False
    return True
