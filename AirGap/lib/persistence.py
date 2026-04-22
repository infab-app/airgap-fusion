import datetime
import json
import os
from pathlib import Path

import AirGap.config as config
from AirGap.lib.session_manager import ITARSessionManager, SessionState


class SessionPersistence:
    @staticmethod
    def save_state(session: ITARSessionManager):
        state_data = {
            "state": session.state.value,
            "session_id": session.session_id,
            "tracked_documents": list(session.tracked_documents),
            "exported_documents": list(session.exported_documents),
            "export_directory": session.export_directory,
            "timestamp": datetime.datetime.now().isoformat(),
            "pid": os.getpid(),
        }
        state_file = Path(config.SESSION_STATE_FILE)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = state_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)
        tmp_file.replace(state_file)

    @staticmethod
    def load_state() -> dict | None:
        state_file = Path(config.SESSION_STATE_FILE)
        if not state_file.exists():
            return None
        try:
            with open(state_file, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def clear_state():
        state_file = Path(config.SESSION_STATE_FILE)
        if state_file.exists():
            try:
                state_file.unlink()
            except OSError:
                pass

    @staticmethod
    def restore_session(session: ITARSessionManager, state_data: dict):
        session._state = SessionState.PROTECTED
        session._session_id = state_data.get("session_id", "")
        session._tracked_documents = set(state_data.get("tracked_documents", []))
        session._exported_documents = set(state_data.get("exported_documents", []))
        session._export_directory = state_data.get("export_directory", "")
