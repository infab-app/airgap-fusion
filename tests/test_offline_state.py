import datetime
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import config
from lib.integrity import wrap_with_checksum
from lib.offline_state import OfflineState


class TestOfflineState(unittest.TestCase):
    def setUp(self):
        OfflineState._instance = None
        self._tmp_dir = tempfile.mkdtemp()
        self._state_file = Path(self._tmp_dir) / "offline_state.json"
        self._orig = config.OFFLINE_STATE_FILE
        config.OFFLINE_STATE_FILE = self._state_file

    def tearDown(self):
        config.OFFLINE_STATE_FILE = self._orig
        OfflineState._instance = None
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_singleton(self):
        a = OfflineState.instance()
        b = OfflineState.instance()
        self.assertIs(a, b)

    def test_initial_state_has_no_online_time(self):
        state = OfflineState.instance()
        self.assertIsNone(state.last_online_time)

    def test_days_remaining_none_when_no_observation(self):
        state = OfflineState.instance()
        self.assertIsNone(state.days_remaining())

    def test_record_online_observation(self):
        state = OfflineState.instance()
        state.record_online_observation()
        self.assertIsNotNone(state.last_online_time)
        datetime.datetime.fromisoformat(state.last_online_time)

    def test_days_remaining_calculation(self):
        state = OfflineState.instance()
        two_days_ago = datetime.datetime.now() - datetime.timedelta(days=2)
        state._last_online_time = two_days_ago.isoformat()
        remaining = state.days_remaining()
        self.assertIsNotNone(remaining)
        self.assertAlmostEqual(remaining, 12.0, delta=0.1)

    def test_days_remaining_overdue(self):
        state = OfflineState.instance()
        twenty_days_ago = datetime.datetime.now() - datetime.timedelta(days=20)
        state._last_online_time = twenty_days_ago.isoformat()
        remaining = state.days_remaining()
        self.assertIsNotNone(remaining)
        self.assertLess(remaining, 0)

    def test_persistence_round_trip(self):
        state = OfflineState.instance()
        state.record_online_observation()
        saved_time = state.last_online_time

        OfflineState._instance = None
        state2 = OfflineState.instance()
        self.assertEqual(state2.last_online_time, saved_time)

    def test_tampered_file_ignored(self):
        data = {"last_online_time": "2025-01-01T00:00:00"}
        envelope = wrap_with_checksum(data)
        envelope["payload"]["last_online_time"] = "2025-12-31T23:59:59"
        with open(self._state_file, "w", encoding="utf-8") as f:
            json.dump(envelope, f)

        state = OfflineState.instance()
        self.assertIsNone(state.last_online_time)

    def test_legacy_file_without_envelope(self):
        raw = {"last_online_time": "2025-06-15T10:30:00"}
        with open(self._state_file, "w", encoding="utf-8") as f:
            json.dump(raw, f)

        state = OfflineState.instance()
        self.assertEqual(state.last_online_time, "2025-06-15T10:30:00")

    def test_corrupted_json_ignored(self):
        with open(self._state_file, "w", encoding="utf-8") as f:
            f.write("{not valid json")

        state = OfflineState.instance()
        self.assertIsNone(state.last_online_time)

    def test_save_creates_file(self):
        state = OfflineState.instance()
        self.assertFalse(self._state_file.exists())
        state.record_online_observation()
        self.assertTrue(self._state_file.exists())


if __name__ == "__main__":
    unittest.main()
