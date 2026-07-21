"""~/.katana/config.json okuma/yazma ve profil (kayıtlı argüman seti) yönetimi."""

import json

from katana.i18n import CONFIG_PATH


def load() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(**updates) -> None:
    config = load()
    config.update(updates)
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def profiles() -> dict:
    return load().get("profiles", {})


def load_profile(name: str) -> dict | None:
    return profiles().get(name)


def save_profile(name: str, data: dict) -> None:
    current = profiles()
    current[name] = {k: v for k, v in data.items() if v is not None}
    save(profiles=current)


def delete_profile(name: str) -> bool:
    current = profiles()
    if name not in current:
        return False
    del current[name]
    save(profiles=current)
    return True
