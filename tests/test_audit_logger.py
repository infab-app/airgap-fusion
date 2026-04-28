"""Tests for lib/audit_logger.py and lib/log_verifier.py — hash chain integrity."""

import json
import tempfile
import unittest
from pathlib import Path

import config
from lib.audit_logger import GENESIS_HASH, AuditLogger, _compute_entry_hash, _read_last_entry_meta
from lib.log_verifier import verify_log


class TestComputeEntryHash(unittest.TestCase):
    def test_deterministic(self):
        entry = {"event": "test", "value": 1}
        self.assertEqual(_compute_entry_hash(entry), _compute_entry_hash(entry))

    def test_different_entries(self):
        a = {"event": "test", "value": 1}
        b = {"event": "test", "value": 2}
        self.assertNotEqual(_compute_entry_hash(a), _compute_entry_hash(b))


class TestReadLastEntryMeta(unittest.TestCase):
    def test_nonexistent_file(self):
        h, seq = _read_last_entry_meta(Path("/nonexistent"))
        self.assertEqual(h, GENESIS_HASH)
        self.assertEqual(seq, 0)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = Path(f.name)
        try:
            h, _seq = _read_last_entry_meta(path)
            self.assertEqual(h, GENESIS_HASH)
        finally:
            path.unlink()

    def test_valid_last_entry(self):
        entry = {"event": "test", "seq": 5, "prev_hash": "abc"}
        entry["entry_hash"] = _compute_entry_hash(entry)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(entry) + "\n")
            path = Path(f.name)
        try:
            h, seq = _read_last_entry_meta(path)
            self.assertEqual(h, entry["entry_hash"])
            self.assertEqual(seq, 5)
        finally:
            path.unlink()

    def test_tampered_entry_returns_genesis(self):
        entry = {"event": "test", "seq": 3, "prev_hash": "abc"}
        entry["entry_hash"] = "bogus_hash_value"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(entry) + "\n")
            path = Path(f.name)
        try:
            h, seq = _read_last_entry_meta(path)
            self.assertEqual(h, GENESIS_HASH)
            self.assertEqual(seq, 0)
        finally:
            path.unlink()


class TestAuditLoggerHashChain(unittest.TestCase):
    def setUp(self):
        AuditLogger._instance = None
        self._tmp_dir = tempfile.mkdtemp()
        self._orig_log_dir = config.AUDIT_LOG_DIR
        config.AUDIT_LOG_DIR = Path(self._tmp_dir)

    def tearDown(self):
        config.AUDIT_LOG_DIR = self._orig_log_dir
        AuditLogger._instance = None
        import shutil

        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_first_entry_has_genesis_prev(self):
        logger = AuditLogger()
        logger._log_dir = Path(self._tmp_dir)
        logger.log("TEST", "first entry")

        log_file = Path(self._tmp_dir) / "airgap_unsessioned.jsonl"
        with open(log_file) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["prev_hash"], GENESIS_HASH)
        self.assertIn("entry_hash", entry)
        self.assertEqual(entry["seq"], 0)

    def test_chain_links(self):
        logger = AuditLogger()
        logger._log_dir = Path(self._tmp_dir)
        logger.log("TEST", "first")
        logger.log("TEST", "second")
        logger.log("TEST", "third")

        log_file = Path(self._tmp_dir) / "airgap_unsessioned.jsonl"
        entries = []
        with open(log_file) as f:
            for line in f:
                entries.append(json.loads(line))

        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["prev_hash"], GENESIS_HASH)
        self.assertEqual(entries[1]["prev_hash"], entries[0]["entry_hash"])
        self.assertEqual(entries[2]["prev_hash"], entries[1]["entry_hash"])
        self.assertEqual(entries[0]["seq"], 0)
        self.assertEqual(entries[1]["seq"], 1)
        self.assertEqual(entries[2]["seq"], 2)

    def test_entry_hash_verifiable(self):
        logger = AuditLogger()
        logger._log_dir = Path(self._tmp_dir)
        logger.log("TEST", "entry")

        log_file = Path(self._tmp_dir) / "airgap_unsessioned.jsonl"
        with open(log_file) as f:
            entry = json.loads(f.readline())

        stored_hash = entry.pop("entry_hash")
        self.assertEqual(_compute_entry_hash(entry), stored_hash)


class TestVerifyLog(unittest.TestCase):
    def setUp(self):
        AuditLogger._instance = None
        self._tmp_dir = tempfile.mkdtemp()
        self._orig_log_dir = config.AUDIT_LOG_DIR
        config.AUDIT_LOG_DIR = Path(self._tmp_dir)

    def tearDown(self):
        config.AUDIT_LOG_DIR = self._orig_log_dir
        AuditLogger._instance = None
        import shutil

        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _write_log(self, count=5):
        logger = AuditLogger()
        logger._log_dir = Path(self._tmp_dir)
        for i in range(count):
            logger.log("TEST", f"entry {i}")
        return Path(self._tmp_dir) / "airgap_unsessioned.jsonl"

    def test_valid_log(self):
        log_file = self._write_log(5)
        result = verify_log(log_file)
        self.assertTrue(result.valid)
        self.assertEqual(result.entries_checked, 5)
        self.assertEqual(result.entries_total, 5)
        self.assertEqual(result.legacy_entries_skipped, 0)
        self.assertIsNone(result.first_break_at)
        self.assertIsNone(result.error)

    def test_nonexistent_file(self):
        result = verify_log(Path("/nonexistent"))
        self.assertFalse(result.valid)
        self.assertEqual(result.error, "Log file does not exist")

    def test_empty_file(self):
        log_file = Path(self._tmp_dir) / "empty.jsonl"
        log_file.touch()
        result = verify_log(log_file)
        self.assertTrue(result.valid)
        self.assertEqual(result.entries_checked, 0)

    def test_detects_tampered_entry(self):
        log_file = self._write_log(3)
        lines = log_file.read_text().strip().split("\n")
        entry = json.loads(lines[1])
        entry["detail"] = "TAMPERED"
        lines[1] = json.dumps(entry)
        log_file.write_text("\n".join(lines) + "\n")

        result = verify_log(log_file)
        self.assertFalse(result.valid)
        self.assertEqual(result.first_break_at, 2)
        self.assertIn("hash mismatch", result.error)

    def test_detects_deleted_entry(self):
        log_file = self._write_log(5)
        lines = log_file.read_text().strip().split("\n")
        del lines[2]
        log_file.write_text("\n".join(lines) + "\n")

        result = verify_log(log_file)
        self.assertFalse(result.valid)
        self.assertIn("Chain broken", result.error)

    def test_detects_reordered_entries(self):
        log_file = self._write_log(4)
        lines = log_file.read_text().strip().split("\n")
        lines[1], lines[2] = lines[2], lines[1]
        log_file.write_text("\n".join(lines) + "\n")

        result = verify_log(log_file)
        self.assertFalse(result.valid)

    def test_legacy_entries_skipped(self):
        log_file = Path(self._tmp_dir) / "mixed.jsonl"
        legacy_entry = {"timestamp": "2024-01-01", "event_type": "OLD", "detail": "legacy"}
        with open(log_file, "w") as f:
            f.write(json.dumps(legacy_entry) + "\n")

        logger = AuditLogger()
        logger._log_dir = Path(self._tmp_dir)
        logger._current_log_file = log_file
        logger.log("TEST", "chained entry")

        result = verify_log(log_file)
        self.assertTrue(result.valid)
        self.assertEqual(result.legacy_entries_skipped, 1)
        self.assertEqual(result.entries_checked, 1)

    def test_invalid_json_detected(self):
        log_file = Path(self._tmp_dir) / "bad.jsonl"
        log_file.write_text('{"valid": true}\nnot json at all\n')
        result = verify_log(log_file)
        self.assertFalse(result.valid)
        self.assertIn("Invalid JSON", result.error)

    def test_sequence_gap_detected(self):
        log_file = self._write_log(3)
        lines = log_file.read_text().strip().split("\n")
        entry = json.loads(lines[2])
        entry.pop("entry_hash")
        entry["seq"] = 99
        entry["entry_hash"] = _compute_entry_hash(entry)
        lines[2] = json.dumps(entry)
        log_file.write_text("\n".join(lines) + "\n")

        result = verify_log(log_file)
        self.assertFalse(result.valid)
        self.assertIn("Sequence gap", result.error)


if __name__ == "__main__":
    unittest.main()
