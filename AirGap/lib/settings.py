import json
from pathlib import Path
from typing import Optional

import config
from lib.integrity import is_envelope, unwrap_and_verify, wrap_with_checksum
from lib.path_validation import secure_file_permissions, secure_mkdir, validate_safe_path

_DEFAULTS = {
    "auto_offline_on_startup": False,
    "auto_start_session": False,
    "default_export_directory": str(config.DEFAULT_EXPORT_DIR),
    "update_channel": "stable",
    "auto_check_updates": False,
    "log_directory": "",
    "autosave_enabled": True,
    "autosave_interval_minutes": 10,
    "autosave_max_versions": 3,
    "autosave_directory": "",
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
                raw = json.load(f)
            if is_envelope(raw):
                stored = unwrap_and_verify(raw)
                if stored is None:
                    return
            else:
                stored = raw
            for key in _DEFAULTS:
                if key in stored:
                    self._data[key] = stored[key]
        except (json.JSONDecodeError, OSError):
            pass

    def save(self):
        settings_file = Path(config.SETTINGS_FILE)
        secure_mkdir(settings_file.parent)
        envelope = wrap_with_checksum(self._data)
        tmp_file = settings_file.with_suffix(f".tmp.{__import__('uuid').uuid4().hex[:8]}")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2)
        tmp_file.replace(settings_file)
        secure_file_permissions(settings_file)

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
        if value and validate_safe_path(value) is None:
            return
        self._data["default_export_directory"] = value

    @property
    def log_directory(self) -> str:
        return self._data.get("log_directory", "")

    @log_directory.setter
    def log_directory(self, value: str):
        if value and validate_safe_path(value) is None:
            return
        self._data["log_directory"] = value

    @property
    def update_channel(self) -> str:
        return self._data.get("update_channel", "stable")

    @update_channel.setter
    def update_channel(self, value: str):
        if value in ("stable", "beta"):
            self._data["update_channel"] = value

    @property
    def auto_check_updates(self) -> bool:
        return bool(self._data.get("auto_check_updates", False))

    @auto_check_updates.setter
    def auto_check_updates(self, value: bool):
        self._data["auto_check_updates"] = value

    @property
    def autosave_enabled(self) -> bool:
        return bool(self._data.get("autosave_enabled", True))

    @autosave_enabled.setter
    def autosave_enabled(self, value: bool):
        self._data["autosave_enabled"] = value

    @property
    def autosave_interval_minutes(self) -> int:
        return max(1, min(60, int(self._data.get("autosave_interval_minutes", 10))))

    @autosave_interval_minutes.setter
    def autosave_interval_minutes(self, value: int):
        self._data["autosave_interval_minutes"] = max(1, min(60, int(value)))

    @property
    def autosave_max_versions(self) -> int:
        return max(1, min(20, int(self._data.get("autosave_max_versions", 3))))

    @autosave_max_versions.setter
    def autosave_max_versions(self, value: int):
        self._data["autosave_max_versions"] = max(1, min(20, int(value)))

    @property
    def autosave_directory(self) -> str:
        return self._data.get("autosave_directory", "")

    @autosave_directory.setter
    def autosave_directory(self, value: str):
        if value and validate_safe_path(value) is None:
            return
        self._data["autosave_directory"] = value
