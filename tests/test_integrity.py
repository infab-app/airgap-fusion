"""Tests for lib/integrity.py — checksum envelope operations."""

import tempfile
import unittest
from pathlib import Path

from lib.integrity import (
    compute_checksum,
    file_checksum,
    is_envelope,
    unwrap_and_verify,
    verify_checksum,
    verify_file,
    wrap_with_checksum,
)


class TestComputeChecksum(unittest.TestCase):
    def test_deterministic(self):
        data = {"key": "value", "num": 42}
        self.assertEqual(compute_checksum(data), compute_checksum(data))

    def test_key_order_independent(self):
        a = {"z": 1, "a": 2}
        b = {"a": 2, "z": 1}
        self.assertEqual(compute_checksum(a), compute_checksum(b))

    def test_different_data_different_hash(self):
        a = {"key": "value1"}
        b = {"key": "value2"}
        self.assertNotEqual(compute_checksum(a), compute_checksum(b))

    def test_returns_hex_string(self):
        result = compute_checksum({"test": True})
        self.assertEqual(len(result), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_empty_dict(self):
        result = compute_checksum({})
        self.assertEqual(len(result), 64)


class TestVerifyChecksum(unittest.TestCase):
    def test_valid(self):
        data = {"hello": "world"}
        checksum = compute_checksum(data)
        self.assertTrue(verify_checksum(data, checksum))

    def test_invalid(self):
        data = {"hello": "world"}
        self.assertFalse(verify_checksum(data, "0" * 64))

    def test_tampered_data(self):
        data = {"hello": "world"}
        checksum = compute_checksum(data)
        data["hello"] = "tampered"
        self.assertFalse(verify_checksum(data, checksum))


class TestFileChecksum(unittest.TestCase):
    def test_file_hash(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test content")
            path = Path(f.name)
        try:
            result = file_checksum(path)
            self.assertEqual(len(result), 64)
            self.assertEqual(result, file_checksum(path))
        finally:
            path.unlink()

    def test_different_content_different_hash(self):
        with tempfile.NamedTemporaryFile(delete=False) as f1:
            f1.write(b"content A")
            path1 = Path(f1.name)
        with tempfile.NamedTemporaryFile(delete=False) as f2:
            f2.write(b"content B")
            path2 = Path(f2.name)
        try:
            self.assertNotEqual(file_checksum(path1), file_checksum(path2))
        finally:
            path1.unlink()
            path2.unlink()


class TestVerifyFile(unittest.TestCase):
    def test_valid_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"verify me")
            path = Path(f.name)
        try:
            expected = file_checksum(path)
            self.assertTrue(verify_file(path, expected))
        finally:
            path.unlink()

    def test_nonexistent_file(self):
        self.assertFalse(verify_file(Path("/nonexistent"), "abc"))

    def test_wrong_checksum(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"data")
            path = Path(f.name)
        try:
            self.assertFalse(verify_file(path, "0" * 64))
        finally:
            path.unlink()


class TestWrapWithChecksum(unittest.TestCase):
    def test_envelope_structure(self):
        data = {"foo": "bar"}
        envelope = wrap_with_checksum(data)
        self.assertIn("version", envelope)
        self.assertIn("payload", envelope)
        self.assertIn("checksum", envelope)
        self.assertEqual(envelope["version"], 1)
        self.assertEqual(envelope["payload"], data)

    def test_checksum_matches_payload(self):
        data = {"foo": "bar"}
        envelope = wrap_with_checksum(data)
        self.assertTrue(verify_checksum(envelope["payload"], envelope["checksum"]))


class TestUnwrapAndVerify(unittest.TestCase):
    def test_valid_envelope(self):
        data = {"key": "value"}
        envelope = wrap_with_checksum(data)
        result = unwrap_and_verify(envelope)
        self.assertEqual(result, data)

    def test_tampered_payload(self):
        envelope = wrap_with_checksum({"key": "value"})
        envelope["payload"]["key"] = "tampered"
        self.assertIsNone(unwrap_and_verify(envelope))

    def test_tampered_checksum(self):
        envelope = wrap_with_checksum({"key": "value"})
        envelope["checksum"] = "0" * 64
        self.assertIsNone(unwrap_and_verify(envelope))

    def test_missing_fields(self):
        self.assertIsNone(unwrap_and_verify({"version": 1, "payload": {}}))
        self.assertIsNone(unwrap_and_verify({"version": 1, "checksum": "abc"}))
        self.assertIsNone(unwrap_and_verify({"payload": {}, "checksum": "abc"}))


class TestIsEnvelope(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(is_envelope({"version": 1, "payload": {}, "checksum": "abc"}))

    def test_missing_version(self):
        self.assertFalse(is_envelope({"payload": {}, "checksum": "abc"}))

    def test_plain_dict(self):
        self.assertFalse(is_envelope({"key": "value"}))


if __name__ == "__main__":
    unittest.main()
