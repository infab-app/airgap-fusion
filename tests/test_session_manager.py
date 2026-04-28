"""Tests for lib/session_manager.py — state machine and document tracking."""

import unittest

import conftest  # noqa: F401

from lib.session_manager import SessionManager, SessionState, is_default_document


class TestIsDefaultDocument(unittest.TestCase):
    def test_untitled(self):
        self.assertTrue(is_default_document("Untitled"))

    def test_untitled_with_number(self):
        self.assertTrue(is_default_document("Untitled1"))
        self.assertTrue(is_default_document("Untitled42"))

    def test_case_insensitive(self):
        self.assertTrue(is_default_document("untitled"))
        self.assertTrue(is_default_document("UNTITLED"))
        self.assertTrue(is_default_document("UNTITLED3"))

    def test_named_document(self):
        self.assertFalse(is_default_document("My Design"))
        self.assertFalse(is_default_document("Part_v1"))

    def test_untitled_with_suffix(self):
        self.assertFalse(is_default_document("Untitled Design"))
        self.assertFalse(is_default_document("Untitled_1"))


class TestSessionState(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(SessionState.UNPROTECTED.value, "UNPROTECTED")
        self.assertEqual(SessionState.PROTECTED.value, "PROTECTED")
        self.assertEqual(SessionState.ACTIVATING.value, "ACTIVATING")
        self.assertEqual(SessionState.DEACTIVATING.value, "DEACTIVATING")
        self.assertEqual(SessionState.RECOVERING.value, "RECOVERING")


class TestSessionManager(unittest.TestCase):
    def setUp(self):
        SessionManager._instance = None
        self.sm = SessionManager.instance()

    def tearDown(self):
        SessionManager._instance = None

    def test_singleton(self):
        self.assertIs(SessionManager.instance(), self.sm)

    def test_initial_state(self):
        self.assertEqual(self.sm.state, SessionState.UNPROTECTED)
        self.assertFalse(self.sm.is_protected)
        self.assertEqual(self.sm.tracked_documents, set())
        self.assertEqual(self.sm.exported_documents, set())
        self.assertEqual(self.sm.session_id, "")
        self.assertEqual(self.sm.export_directory, "")
        self.assertIsNone(self.sm.session_start_time)


class TestStateTransitions(unittest.TestCase):
    def setUp(self):
        SessionManager._instance = None
        self.sm = SessionManager.instance()

    def tearDown(self):
        SessionManager._instance = None

    def test_unprotected_to_activating(self):
        self.assertTrue(self.sm.transition_to(SessionState.ACTIVATING))
        self.assertEqual(self.sm.state, SessionState.ACTIVATING)

    def test_unprotected_to_recovering(self):
        self.assertTrue(self.sm.transition_to(SessionState.RECOVERING))
        self.assertEqual(self.sm.state, SessionState.RECOVERING)

    def test_unprotected_to_protected_invalid(self):
        self.assertFalse(self.sm.transition_to(SessionState.PROTECTED))
        self.assertEqual(self.sm.state, SessionState.UNPROTECTED)

    def test_activating_to_protected(self):
        self.sm.transition_to(SessionState.ACTIVATING)
        self.assertTrue(self.sm.transition_to(SessionState.PROTECTED))
        self.assertEqual(self.sm.state, SessionState.PROTECTED)

    def test_activating_to_unprotected(self):
        self.sm.transition_to(SessionState.ACTIVATING)
        self.assertTrue(self.sm.transition_to(SessionState.UNPROTECTED))

    def test_protected_to_deactivating(self):
        self.sm.transition_to(SessionState.ACTIVATING)
        self.sm.transition_to(SessionState.PROTECTED)
        self.assertTrue(self.sm.transition_to(SessionState.DEACTIVATING))

    def test_protected_to_unprotected_invalid(self):
        self.sm.transition_to(SessionState.ACTIVATING)
        self.sm.transition_to(SessionState.PROTECTED)
        self.assertFalse(self.sm.transition_to(SessionState.UNPROTECTED))

    def test_deactivating_to_unprotected(self):
        self.sm.transition_to(SessionState.ACTIVATING)
        self.sm.transition_to(SessionState.PROTECTED)
        self.sm.transition_to(SessionState.DEACTIVATING)
        self.assertTrue(self.sm.transition_to(SessionState.UNPROTECTED))

    def test_deactivating_to_protected(self):
        self.sm.transition_to(SessionState.ACTIVATING)
        self.sm.transition_to(SessionState.PROTECTED)
        self.sm.transition_to(SessionState.DEACTIVATING)
        self.assertTrue(self.sm.transition_to(SessionState.PROTECTED))

    def test_recovering_to_protected(self):
        self.sm.transition_to(SessionState.RECOVERING)
        self.assertTrue(self.sm.transition_to(SessionState.PROTECTED))

    def test_recovering_to_unprotected(self):
        self.sm.transition_to(SessionState.RECOVERING)
        self.assertTrue(self.sm.transition_to(SessionState.UNPROTECTED))


class TestIsProtected(unittest.TestCase):
    def setUp(self):
        SessionManager._instance = None
        self.sm = SessionManager.instance()

    def tearDown(self):
        SessionManager._instance = None

    def test_unprotected(self):
        self.assertFalse(self.sm.is_protected)

    def test_activating_is_protected(self):
        self.sm.transition_to(SessionState.ACTIVATING)
        self.assertTrue(self.sm.is_protected)

    def test_protected(self):
        self.sm.transition_to(SessionState.ACTIVATING)
        self.sm.transition_to(SessionState.PROTECTED)
        self.assertTrue(self.sm.is_protected)

    def test_deactivating_is_protected(self):
        self.sm.transition_to(SessionState.ACTIVATING)
        self.sm.transition_to(SessionState.PROTECTED)
        self.sm.transition_to(SessionState.DEACTIVATING)
        self.assertTrue(self.sm.is_protected)

    def test_recovering_not_protected(self):
        self.sm.transition_to(SessionState.RECOVERING)
        self.assertFalse(self.sm.is_protected)


class TestDocumentTracking(unittest.TestCase):
    def setUp(self):
        SessionManager._instance = None
        self.sm = SessionManager.instance()

    def tearDown(self):
        SessionManager._instance = None

    def test_track_document(self):
        self.sm.track_document("Design A")
        self.assertIn("Design A", self.sm.tracked_documents)

    def test_track_duplicate(self):
        self.sm.track_document("Design A")
        self.sm.track_document("Design A")
        self.assertEqual(len(self.sm.tracked_documents), 1)

    def test_mark_exported(self):
        self.sm.track_document("Design A")
        self.sm.mark_exported("Design A")
        self.assertIn("Design A", self.sm.exported_documents)

    def test_unexported_documents(self):
        self.sm.track_document("Design A")
        self.sm.track_document("Design B")
        self.sm.mark_exported("Design A")
        self.assertEqual(self.sm.unexported_documents(), {"Design B"})

    def test_substantive_unexported_filters_untitled(self):
        self.sm.track_document("Untitled")
        self.sm.track_document("Untitled1")
        self.sm.track_document("Real Design")
        self.assertEqual(self.sm.substantive_unexported_documents(), {"Real Design"})

    def test_substantive_tracked_documents(self):
        self.sm.track_document("Untitled")
        self.sm.track_document("My Part")
        self.assertEqual(self.sm.substantive_tracked_documents(), {"My Part"})

    def test_tracked_returns_copy(self):
        self.sm.track_document("A")
        docs = self.sm.tracked_documents
        docs.add("B")
        self.assertNotIn("B", self.sm.tracked_documents)


class TestSessionLifecycle(unittest.TestCase):
    def setUp(self):
        SessionManager._instance = None
        self.sm = SessionManager.instance()

    def tearDown(self):
        SessionManager._instance = None

    def test_start_session(self):
        self.sm.start_session("abc123", "/export/path", "2025-01-01T00:00:00")
        self.assertEqual(self.sm.session_id, "abc123")
        self.assertEqual(self.sm.export_directory, "/export/path")
        self.assertEqual(self.sm.session_start_time, "2025-01-01T00:00:00")

    def test_reset(self):
        self.sm.start_session("abc123", "/export", "2025-01-01T00:00:00")
        self.sm.track_document("Doc")
        self.sm.mark_exported("Doc")
        self.sm.transition_to(SessionState.ACTIVATING)
        self.sm.reset()
        self.assertEqual(self.sm.state, SessionState.UNPROTECTED)
        self.assertEqual(self.sm.tracked_documents, set())
        self.assertEqual(self.sm.exported_documents, set())
        self.assertEqual(self.sm.session_id, "")
        self.assertEqual(self.sm.export_directory, "")

    def test_export_directory_setter(self):
        self.sm.export_directory = "/new/path"
        self.assertEqual(self.sm.export_directory, "/new/path")


if __name__ == "__main__":
    unittest.main()
