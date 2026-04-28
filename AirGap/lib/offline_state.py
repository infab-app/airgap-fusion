import datetime
import json
import uuid
from pathlib import Path
from typing import Optional

import config
from lib.integrity import is_envelope, unwrap_and_verify, wrap_with_checksum
from lib.path_validation import secure_file_permissions, secure_mkdir


class OfflineState:
    _instance: Optional["OfflineState"] = None

    def __init__(self):
        self._last_online_time: str | None = None
        self._load()

    @classmethod
    def instance(cls) -> "OfflineState":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def last_online_time(self) -> str | None:
        return self._last_online_time

    def record_online_observation(self):
        self._last_online_time = datetime.datetime.now().isoformat()
        self._save()

    def days_remaining(self) -> float | None:
        if not self._last_online_time:
            return None
        try:
            last_online = datetime.datetime.fromisoformat(self._last_online_time)
            elapsed = datetime.datetime.now() - last_online
            return config.FUSION_OFFLINE_LICENSE_DAYS - elapsed.total_seconds() / 86400
        except (ValueError, TypeError):
            return None

    def _load(self):
        state_file = Path(config.OFFLINE_STATE_FILE)
        if not state_file.exists():
            return
        try:
            with open(state_file, encoding="utf-8") as f:
                raw = json.load(f)
            if is_envelope(raw):
                payload = unwrap_and_verify(raw)
                if payload is None:
                    return
            else:
                payload = raw
            self._last_online_time = payload.get("last_online_time")
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self):
        state_file = Path(config.OFFLINE_STATE_FILE)
        secure_mkdir(state_file.parent)
        data = {"last_online_time": self._last_online_time}
        envelope = wrap_with_checksum(data)
        tmp_file = state_file.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2)
        tmp_file.replace(state_file)
        secure_file_permissions(state_file)
