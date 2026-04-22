import json
from pathlib import Path
from typing import Optional

import config

_DEFAULTS = {
    "auto_offline_on_startup": False,
    "auto_start_session": False,
    "default_export_directory": str(config.DEFAULT_EXPORT_DIR),
    "version": 1,
}


class Settings:
    _instance: Optional["Settings"] = None

    def __init__(self):
        self._data: dict = dict(_DEFAULTS)
        self._load()

    @classmethod
    def instance(cls) -> "Settings":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reload(cls) -> "Settings":
        cls._instance = cls()
        return cls._instance

    def _load(self):
        settings_file = Path(config.SETTINGS_FILE)
        if not settings_file.exists():
            return
        try:
            with open(settings_file, encoding="utf-8") as f:
                stored = json.load(f)
            for key in _DEFAULTS:
                if key in stored:
                    self._data[key] = stored[key]
        except (json.JSONDecodeError, OSError):
            pass

    def save(self):
        settings_file = Path(config.SETTINGS_FILE)
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = settings_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        tmp_file.replace(settings_file)

    @property
    def auto_offline_on_startup(self) -> bool:
        return bool(self._data.get("auto_offline_on_startup", False))

    @auto_offline_on_startup.setter
    def auto_offline_on_startup(self, value: bool):
        self._data["auto_offline_on_startup"] = value

    @property
    def auto_start_session(self) -> bool:
        return bool(self._data.get("auto_start_session", False))

    @auto_start_session.setter
    def auto_start_session(self, value: bool):
        self._data["auto_start_session"] = value

    @property
    def default_export_directory(self) -> str:
        return self._data.get("default_export_directory", str(config.DEFAULT_EXPORT_DIR))

    @default_export_directory.setter
    def default_export_directory(self, value: str):
        self._data["default_export_directory"] = value
