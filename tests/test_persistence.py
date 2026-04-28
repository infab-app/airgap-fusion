"""Tests for lib/persistence.py — session state save/load/clear."""

import json
import tempfile
import unittest
from pathlib import Path

import config
from lib.persistence import SessionPersistence
from lib.session_manager import SessionManager, SessionState


class TestSessionPersistence(unittest.TestCase):
    def setUp(self):
        SessionManager._instance = None
        self._tmp_dir = tempfile.mkdtemp()
        self._state_file = Path(self._tmp_dir) / "session_state.json"
        self._orig = config.SESSION_STATE_FILE
        config.SESSION_STATE_FILE = self._state_file

    def tearDown(self):
        config.SESSION_STATE_FILE = self._orig
        SessionManager._instance = None
        import shutil

        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_save_creates_file(self):
        sm = SessionManager.instance()
        sm.start_session("test123", "/export", "2025-01-01T00:00:00")
        sm.transition_to(SessionState.ACTIVATING)
        sm.transition_to(SessionState.PROTECTED)
        SessionPersistence.save_state(sm)
        self.assertTrue(self._state_file.exists())

    def test_save_load_roundtrip(self):
        sm = SessionManager.instance()
        sm.start_session("test123", "/export", "2025-01-01T00:00:00")
        sm.transition_to(SessionState.ACTIVATING)
        sm.transition_to(SessionState.PROTECTED)
        sm.track_document("Design A")
        sm.mark_exported("Design A")
        sm.track_document("Design B")
        SessionPersistence.save_state(sm)

        state = SessionPersistence.load_state()
        self.assertIsNotNone(state)
        self.assertEqual(state["session_id"], "test123")
        self.assertEqual(state["export_directory"], "/export")
        self.assertEqual(state["state"], "PROTECTED")
        self.assertIn("Design A", state["tracked_documents"])
        self.assertIn("Design B", state["tracked_documents"])
        self.assertIn("Design A", state["exported_documents"])
        self.assertNotIn("Design B", state["exported_documents"])

    def test_load_nonexistent_returns_none(self):
        self.assertIsNone(SessionPersistence.load_state())

    def test_load_rejects_tampered(self):
        sm = SessionManager.instance()
        sm.start_session("test123", "/export", "2025-01-01T00:00:00")
        sm.transition_to(SessionState.ACTIVATING)
        SessionPersistence.save_state(sm)

        with open(self._state_file) as f:
            data = json.load(f)
        data["payload"]["session_id"] = "TAMPERED"
        with open(self._state_file, "w") as f:
            json.dump(data, f)

        self.assertIsNone(SessionPersistence.load_state())

    def test_load_legacy_format(self):
        legacy = {
            "state": "PROTECTED",
            "session_id": "legacy123",
            "tracked_documents": ["Doc A"],
            "exported_documents": [],
            "export_directory": "/old/path",
            "timestamp": "2024-06-01T12:00:00",
            "pid": 9999,
        }
        with open(self._state_file, "w") as f:
            json.dump(legacy, f)

        state = SessionPersistence.load_state()
        self.assertIsNotNone(state)
        self.assertEqual(state["session_id"], "legacy123")

    def test_clear_state(self):
        sm = SessionManager.instance()
        sm.start_session("test", "/e", "2025-01-01T00:00:00")
        sm.transition_to(SessionState.ACTIVATING)
        SessionPersistence.save_state(sm)
        self.assertTrue(self._state_file.exists())

        SessionPersistence.clear_state()
        self.assertFalse(self._state_file.exists())

    def test_clear_nonexistent_ok(self):
        SessionPersistence.clear_state()

    def test_restore_session(self):
        state_data = {
            "session_id": "restored123",
            "tracked_documents": ["A", "B"],
            "exported_documents": ["A"],
            "export_directory": "/restored",
        }
        sm = SessionManager.instance()
        SessionPersistence.restore_session(sm, state_data)

        self.assertEqual(sm.state, SessionState.RECOVERING)
        self.assertEqual(sm.session_id, "restored123")
        self.assertEqual(sm.tracked_documents, {"A", "B"})
        self.assertEqual(sm.exported_documents, {"A"})
        self.assertEqual(sm.export_directory, "/restored")


if __name__ == "__main__":
    unittest.main()
