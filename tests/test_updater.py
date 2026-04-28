"""Tests for lib/updater.py — version parsing and comparison."""

import unittest

import conftest  # noqa: F401

from lib.updater import is_newer, parse_version


class TestParseVersion(unittest.TestCase):
    def test_simple_version(self):
        parts, pre = parse_version("1.0.7")
        self.assertEqual(parts, (1, 0, 7))
        self.assertEqual(pre, "")

    def test_v_prefix(self):
        parts, pre = parse_version("v1.0.7")
        self.assertEqual(parts, (1, 0, 7))
        self.assertEqual(pre, "")

    def test_prerelease(self):
        parts, pre = parse_version("1.1.0-beta.1")
        self.assertEqual(parts, (1, 1, 0))
        self.assertEqual(pre, "beta.1")

    def test_rc_prerelease(self):
        parts, pre = parse_version("2.0.0-rc.1")
        self.assertEqual(parts, (2, 0, 0))
        self.assertEqual(pre, "rc.1")

    def test_two_part_version(self):
        parts, _pre = parse_version("1.0")
        self.assertEqual(parts, (1, 0))

    def test_prerelease_with_v(self):
        parts, pre = parse_version("v1.0.0-alpha")
        self.assertEqual(parts, (1, 0, 0))
        self.assertEqual(pre, "alpha")


class TestIsNewer(unittest.TestCase):
    def test_higher_major(self):
        self.assertTrue(is_newer("2.0.0", "1.0.7"))

    def test_higher_minor(self):
        self.assertTrue(is_newer("1.1.0", "1.0.7"))

    def test_higher_patch(self):
        self.assertTrue(is_newer("1.0.8", "1.0.7"))

    def test_same_version(self):
        self.assertFalse(is_newer("1.0.7", "1.0.7"))

    def test_lower_version(self):
        self.assertFalse(is_newer("1.0.6", "1.0.7"))

    def test_release_newer_than_prerelease(self):
        self.assertTrue(is_newer("1.0.7", "1.0.7-beta.1"))

    def test_prerelease_not_newer_than_release(self):
        self.assertFalse(is_newer("1.0.7-beta.1", "1.0.7"))

    def test_higher_prerelease(self):
        self.assertTrue(is_newer("1.0.7-beta.2", "1.0.7-beta.1"))

    def test_rc_newer_than_beta(self):
        self.assertTrue(is_newer("1.0.7-rc.1", "1.0.7-beta.1"))

    def test_v_prefix_ignored(self):
        self.assertTrue(is_newer("v1.1.0", "v1.0.7"))

    def test_both_prerelease_same(self):
        self.assertFalse(is_newer("1.0.0-beta.1", "1.0.0-beta.1"))

    def test_higher_major_with_prerelease(self):
        self.assertTrue(is_newer("2.0.0-alpha", "1.9.9"))


if __name__ == "__main__":
    unittest.main()
