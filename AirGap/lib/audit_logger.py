import datetime
import json
import platform
import threading
from pathlib import Path

import adsk.core

import config
from lib.integrity import compute_checksum
from lib.path_validation import secure_file_permissions, secure_mkdir, validate_safe_path

GENESIS_HASH = "genesis"


def _compute_entry_hash(entry: dict) -> str:
    return compute_checksum(entry)


def _read_last_entry_meta(log_file: Path) -> tuple[str, int]:
    """Return (entry_hash, seq) from the last entry, verifying integrity."""
    try:
        if not log_file.exists() or log_file.stat().st_size == 0:
            return GENESIS_HASH, 0
        with open(log_file, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 4096))
            chunk = f.read()
        lines = chunk.strip().split(b"\n")
        if not lines:
            return GENESIS_HASH, 0
        entry = json.loads(lines[-1])
        stored_hash = entry.get("entry_hash")
        if not stored_hash:
            return GENESIS_HASH, 0
        verify_entry = dict(entry)
        verify_entry.pop("entry_hash")
        if _compute_entry_hash(verify_entry) != stored_hash:
            return GENESIS_HASH, 0
        return stored_hash, entry.get("seq", 0)
    except (OSError, json.JSONDecodeError, ValueError):
        return GENESIS_HASH, 0


class AuditLogger:
    _instance = None

    def __init__(self):
        self._log_dir = Path(config.AUDIT_LOG_DIR)
        self._current_log_file = None
        self._session_id = None
        self._prev_hash = GENESIS_HASH
        self._seq = 0
        self._dropped_entries = 0
        self._lock = threading.Lock()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start_session_log(self, session_id: str):
        self._session_id = session_id
        try:
            secure_mkdir(self._log_dir)
        except OSError:
            self._log_dir = Path(config.AUDIT_LOG_DIR)
            secure_mkdir(self._log_dir)

        prev_log = self._current_log_file
        if prev_log and prev_log.exists():
            self._prev_hash, self._seq = _read_last_entry_meta(prev_log)
        elif self._prev_hash == GENESIS_HASH:
            unsessioned = self._log_dir / "airgap_unsessioned.jsonl"
            if unsessioned.exists():
                self._prev_hash, self._seq = _read_last_entry_meta(unsessioned)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"airgap_{timestamp}_{session_id}.jsonl"
        self._current_log_file = self._log_dir / filename

    def end_session_log(self):
        self._current_log_file = None
        self._session_id = None

    def log(self, event_type: str, detail: str, severity: str = "INFO"):
        with self._lock:
            entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "session_id": self._session_id or "no_session",
                "event_type": event_type,
                "detail": detail,
                "severity": severity,
                "user": self._get_user(),
                "machine": platform.node(),
                "seq": self._seq,
                "prev_hash": self._prev_hash,
            }
            entry["entry_hash"] = _compute_entry_hash(entry)
            self._prev_hash = entry["entry_hash"]
            self._seq += 1

            log_file = self._current_log_file
            if log_file is None:
                try:
                    secure_mkdir(self._log_dir)
                except OSError:
                    self._log_dir = Path(config.AUDIT_LOG_DIR)
                    secure_mkdir(self._log_dir)
                log_file = self._log_dir / "airgap_unsessioned.jsonl"

            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
                secure_file_permissions(log_file)
            except OSError:
                self._dropped_entries += 1

    def get_current_log_path(self):
        return self._current_log_file

    def get_log_dir(self):
        return self._log_dir

    def set_log_dir(self, path: str):
        if path.strip():
            validated = validate_safe_path(path.strip())
            if validated:
                self._log_dir = validated
                return
        self._log_dir = Path(config.AUDIT_LOG_DIR)

    def get_dropped_count(self):
        return self._dropped_entries

    @staticmethod
    def _get_user():
        try:
            app = adsk.core.Application.get()
            return app.userName or "unknown"
        except Exception:
            return "unknown"
