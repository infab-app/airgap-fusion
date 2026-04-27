import datetime
import json
import os
import uuid
from pathlib import Path

import config
from lib.integrity import is_envelope, unwrap_and_verify, wrap_with_checksum
from lib.path_validation import secure_file_permissions, secure_mkdir
from lib.session_manager import SessionManager, SessionState


class SessionPersistence:
    @staticmethod
    def save_state(session: SessionManager):
        state_data = {
            "state": session.state.value,
            "session_id": session.session_id,
            "tracked_documents": list(session.tracked_documents),
            "exported_documents": list(session.exported_documents),
            "export_directory": session.export_directory,
            "timestamp": datetime.datetime.now().isoformat(),
            "pid": os.getpid(),
        }
        envelope = wrap_with_checksum(state_data)
        state_file = Path(config.SESSION_STATE_FILE)
        secure_mkdir(state_file.parent)
        tmp_file = state_file.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2)
        tmp_file.replace(state_file)
        secure_file_permissions(state_file)

    @staticmethod
    def load_state() -> dict | None:
        state_file = Path(config.SESSION_STATE_FILE)
        if not state_file.exists():
            return None
        try:
            with open(state_file, encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

        if is_envelope(raw):
            payload = unwrap_and_verify(raw)
            if payload is None:
                try:
                    from lib.audit_logger import AuditLogger

                    AuditLogger.instance().log(
                        "INTEGRITY_VIOLATION",
                        "Session state file failed checksum verification; file rejected",
                        "CRITICAL",
                    )
                except Exception:
                    pass
                return None
            return payload

        # Legacy format (pre-checksum): accept once, will be upgraded on next save
        try:
            from lib.audit_logger import AuditLogger

            AuditLogger.instance().log(
                "INTEGRITY_MIGRATION",
                "Session state file lacks checksum; treating as legacy format",
                "WARNING",
            )
        except Exception:
            pass
        return raw

    @staticmethod
    def clear_state():
        state_file = Path(config.SESSION_STATE_FILE)
        if state_file.exists():
            try:
                state_file.unlink()
            except OSError:
                pass

    @staticmethod
    def restore_session(session: SessionManager, state_data: dict):
        session._state = SessionState.RECOVERING
        session._session_id = state_data.get("session_id", "")
        session._tracked_documents = set(state_data.get("tracked_documents", []))
        session._exported_documents = set(state_data.get("exported_documents", []))
        session._export_directory = state_data.get("export_directory", "")
