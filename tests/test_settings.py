"""Tests for lib/settings.py — settings defaults, validation, persistence."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import conftest  # noqa: F401

import config
from lib.integrity import wrap_with_checksum
from lib.settings import Settings


class TestSettingsDefaults(unittest.TestCase):
    def setUp(self):
        Settings._instance = None
        self._tmp_dir = tempfile.mkdtemp()
        self._settings_file = Path(self._tmp_dir) / "settings.json"
        self._orig_file = config.SETTINGS_FILE
        config.SETTINGS_FILE = self._settings_file

    def tearDown(self):
        config.SETTINGS_FILE = self._orig_file
        Settings._instance = None
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_default_values(self):
        s = Settings.instance()
        self.assertFalse(s.auto_offline_on_startup)
        self.assertFalse(s.auto_start_session)
        self.assertEqual(s.update_channel, "stable")
        self.assertFalse(s.auto_check_updates)
        self.assertTrue(s.autosave_enabled)
        self.assertEqual(s.autosave_interval_minutes, 10)
        self.assertEqual(s.autosave_max_versions, 3)
        self.assertFalse(s.auto_clear_cache)


class TestSettingsValidation(unittest.TestCase):
    def setUp(self):
        Settings._instance = None
        self._tmp_dir = tempfile.mkdtemp()
        self._settings_file = Path(self._tmp_dir) / "settings.json"
        self._orig_file = config.SETTINGS_FILE
        config.SETTINGS_FILE = self._settings_file

    def tearDown(self):
        config.SETTINGS_FILE = self._orig_file
        Settings._instance = None
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_autosave_interval_clamped_low(self):
        s = Settings.instance()
        s.autosave_interval_minutes = 0
        self.assertEqual(s.autosave_interval_minutes, 1)

    def test_autosave_interval_clamped_high(self):
        s = Settings.instance()
        s.autosave_interval_minutes = 999
        self.assertEqual(s.autosave_interval_minutes, 60)

    def test_autosave_max_versions_clamped_low(self):
        s = Settings.instance()
        s.autosave_max_versions = 0
        self.assertEqual(s.autosave_max_versions, 1)

    def test_autosave_max_versions_clamped_high(self):
        s = Settings.instance()
        s.autosave_max_versions = 100
        self.assertEqual(s.autosave_max_versions, 20)

    def test_update_channel_rejects_invalid(self):
        s = Settings.instance()
        s.update_channel = "nightly"
        self.assertEqual(s.update_channel, "stable")

    def test_update_channel_accepts_beta(self):
        s = Settings.instance()
        s.update_channel = "beta"
        self.assertEqual(s.update_channel, "beta")

    def test_export_directory_rejects_dotdot(self):
        s = Settings.instance()
        original = s.default_export_directory
        s.default_export_directory = "/tmp/../etc"
        self.assertEqual(s.default_export_directory, original)


class TestSettingsPersistence(unittest.TestCase):
    def setUp(self):
        Settings._instance = None
        self._tmp_dir = tempfile.mkdtemp()
        self._settings_file = Path(self._tmp_dir) / "settings.json"
        self._orig_file = config.SETTINGS_FILE
        config.SETTINGS_FILE = self._settings_file

    def tearDown(self):
        config.SETTINGS_FILE = self._orig_file
        Settings._instance = None
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_save_and_reload(self):
        s = Settings.instance()
        s.auto_check_updates = True
        s.autosave_interval_minutes = 5
        s.save()

        Settings._instance = None
        s2 = Settings.instance()
        self.assertTrue(s2.auto_check_updates)
        self.assertEqual(s2.autosave_interval_minutes, 5)

    def test_load_with_checksum_envelope(self):
        data = {"auto_check_updates": True, "autosave_interval_minutes": 15, "version": 1}
        envelope = wrap_with_checksum(data)
        with open(self._settings_file, "w") as f:
            json.dump(envelope, f)

        s = Settings.instance()
        self.assertTrue(s.auto_check_updates)
        self.assertEqual(s.autosave_interval_minutes, 15)

    def test_load_rejects_tampered_envelope(self):
        data = {"auto_check_updates": True, "version": 1}
        envelope = wrap_with_checksum(data)
        envelope["payload"]["auto_check_updates"] = False
        with open(self._settings_file, "w") as f:
            json.dump(envelope, f)

        s = Settings.instance()
        self.assertFalse(s.auto_check_updates)

    def test_load_legacy_format(self):
        data = {"auto_check_updates": True, "autosave_interval_minutes": 7}
        with open(self._settings_file, "w") as f:
            json.dump(data, f)

        s = Settings.instance()
        self.assertTrue(s.auto_check_updates)
        self.assertEqual(s.autosave_interval_minutes, 7)


if __name__ == "__main__":
    unittest.main()
