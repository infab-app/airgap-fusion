import datetime
import json
import platform
from pathlib import Path

import adsk.core

import config


class AuditLogger:
    _instance = None

    def __init__(self):
        self._log_dir = Path(config.AUDIT_LOG_DIR)
        self._current_log_file = None
        self._session_id = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start_session_log(self, session_id: str):
        self._session_id = session_id
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            self._log_dir = Path(config.AUDIT_LOG_DIR)
            self._log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"airgap_{timestamp}_{session_id}.jsonl"
        self._current_log_file = self._log_dir / filename

    def end_session_log(self):
        self._current_log_file = None
        self._session_id = None

    def log(self, event_type: str, detail: str, severity: str = "INFO"):
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "session_id": self._session_id or "no_session",
            "event_type": event_type,
            "detail": detail,
            "severity": severity,
            "user": self._get_user(),
            "machine": platform.node(),
        }

        log_file = self._current_log_file
        if log_file is None:
            try:
                self._log_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                self._log_dir = Path(config.AUDIT_LOG_DIR)
                self._log_dir.mkdir(parents=True, exist_ok=True)
            log_file = self._log_dir / "airgap_unsessioned.jsonl"

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def get_current_log_path(self):
        return self._current_log_file

    def get_log_dir(self):
        return self._log_dir

    def set_log_dir(self, path: str):
        if path.strip():
            self._log_dir = Path(path)
        else:
            self._log_dir = Path(config.AUDIT_LOG_DIR)

    @staticmethod
    def _get_user():
        try:
            app = adsk.core.Application.get()
            return app.userName or "unknown"
        except Exception:
            return "unknown"
