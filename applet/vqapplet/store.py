# Nastavení instancí appletu (instances.json) a globální konfigurace.
import json
import os
import threading

from . import texts

DEFAULT_CONFIG = os.path.expanduser("~/.config/vaultquick-desktop/config.json")
DEFAULT_INSTANCES = os.path.expanduser("~/.config/vaultquick-desktop/instances.json")


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load_config(path=DEFAULT_CONFIG):
    cfg = _read(path)
    vault = cfg.get("vault")
    if not isinstance(vault, str) or not vault.strip():
        vault = "~/MujVault"
    cfg["vault"] = os.path.expanduser(vault)  # `~` v config.json jako ve vqd
    return cfg


def with_defaults(raw):
    v = dict(raw)
    project = v.get("project")
    v["project"] = project
    v.setdefault("label", project if project else texts.ALL)
    v.setdefault("noDate", "all" if project else "inProgress")
    v.setdefault("days", 7)
    v.setdefault("fontSize", 11)
    v.setdefault("overdueExpanded", False)
    v.setdefault("noDateExpanded", True)
    return v


class Instances:
    def __init__(self, path=DEFAULT_INSTANCES):
        self.path = path
        self._lock = threading.Lock()
        self._data = _read(path)

    def get(self, key):
        with self._lock:
            return with_defaults(self._data.get(key, {}))

    def set(self, key, value):
        with self._lock:
            self._data[key] = dict(value)
            self._save()

    def keys(self):
        with self._lock:
            return set(self._data)

    def prune(self, live_keys):
        with self._lock:
            self._data = {k: v for k, v in self._data.items() if k in live_keys}
            self._save()

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
