import enum
from typing import Optional, Set


class SessionState(enum.Enum):
    UNPROTECTED = 'UNPROTECTED'
    ACTIVATING = 'ACTIVATING'
    PROTECTED = 'PROTECTED'
    DEACTIVATING = 'DEACTIVATING'


_VALID_TRANSITIONS = {
    SessionState.UNPROTECTED: [SessionState.ACTIVATING],
    SessionState.ACTIVATING: [SessionState.PROTECTED, SessionState.UNPROTECTED],
    SessionState.PROTECTED: [SessionState.DEACTIVATING],
    SessionState.DEACTIVATING: [SessionState.PROTECTED, SessionState.UNPROTECTED],
}


class ITARSessionManager:
    _instance: Optional['ITARSessionManager'] = None

    def __init__(self):
        self._state: SessionState = SessionState.UNPROTECTED
        self._tracked_documents: Set[str] = set()
        self._exported_documents: Set[str] = set()
        self._session_start_time: Optional[str] = None
        self._export_directory: str = ''
        self._session_id: str = ''

    @classmethod
    def instance(cls) -> 'ITARSessionManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def is_protected(self) -> bool:
        return self._state in (SessionState.PROTECTED, SessionState.ACTIVATING)

    @property
    def export_directory(self) -> str:
        return self._export_directory

    @export_directory.setter
    def export_directory(self, value: str):
        self._export_directory = value

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def tracked_documents(self) -> Set[str]:
        return self._tracked_documents.copy()

    @property
    def exported_documents(self) -> Set[str]:
        return self._exported_documents.copy()

    def transition_to(self, new_state: SessionState) -> bool:
        allowed = _VALID_TRANSITIONS.get(self._state, [])
        if new_state not in allowed:
            return False
        self._state = new_state
        return True

    def track_document(self, doc_name: str):
        self._tracked_documents.add(doc_name)

    def mark_exported(self, doc_name: str):
        self._exported_documents.add(doc_name)

    def unexported_documents(self) -> Set[str]:
        return self._tracked_documents - self._exported_documents

    def start_session(self, session_id: str, export_dir: str, start_time: str):
        self._session_id = session_id
        self._export_directory = export_dir
        self._session_start_time = start_time

    def reset(self):
        self._tracked_documents.clear()
        self._exported_documents.clear()
        self._session_start_time = None
        self._export_directory = ''
        self._session_id = ''
        self._state = SessionState.UNPROTECTED
