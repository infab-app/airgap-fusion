"""Tests for lib/path_validation.py — path security checks."""

import os
import stat
import tempfile
import unittest
from pathlib import Path

from lib.path_validation import (
    secure_file_permissions,
    secure_mkdir,
    validate_filename,
    validate_safe_path,
)


class TestValidateSafePath(unittest.TestCase):
    def test_valid_absolute_path(self):
        with tempfile.TemporaryDirectory() as td:
            result = validate_safe_path(td)
            self.assertIsNotNone(result)
            self.assertEqual(result, Path(td).resolve())

    def test_rejects_dotdot(self):
        self.assertIsNone(validate_safe_path("/tmp/../etc"))

    def test_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "real"
            target.mkdir()
            link = Path(td) / "link"
            link.symlink_to(target)
            self.assertIsNone(validate_safe_path(str(link)))

    def test_nonexistent_path_resolves(self):
        result = validate_safe_path("/tmp/nonexistent_test_path_xyz")
        self.assertIsNotNone(result)

    def test_allowed_parent_valid(self):
        with tempfile.TemporaryDirectory() as td:
            child = Path(td) / "sub"
            child.mkdir()
            result = validate_safe_path(str(child), allowed_parent=Path(td))
            self.assertIsNotNone(result)

    def test_allowed_parent_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = validate_safe_path("/tmp", allowed_parent=Path(td))
            self.assertIsNone(result)

    def test_empty_string_resolves_to_cwd(self):
        result = validate_safe_path("")
        self.assertIsNotNone(result)
        self.assertEqual(result, Path("").resolve())


class TestValidateFilename(unittest.TestCase):
    def test_valid_filename(self):
        self.assertTrue(validate_filename("design_v1.f3d"))

    def test_empty(self):
        self.assertFalse(validate_filename(""))

    def test_forward_slash(self):
        self.assertFalse(validate_filename("path/file.txt"))

    def test_backslash(self):
        self.assertFalse(validate_filename("path\\file.txt"))

    def test_dotdot(self):
        self.assertFalse(validate_filename(".."))
        self.assertFalse(validate_filename("../file"))

    def test_simple_dot(self):
        self.assertTrue(validate_filename("file.txt"))
        self.assertTrue(validate_filename(".hidden"))


class TestSecureMkdir(unittest.TestCase):
    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "new_dir"
            secure_mkdir(target)
            self.assertTrue(target.exists())
            self.assertTrue(target.is_dir())

    @unittest.skipIf(os.name == "nt", "Unix permissions only")
    def test_permissions_700(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "secure"
            secure_mkdir(target)
            mode = target.stat().st_mode & 0o777
            self.assertEqual(mode, 0o700)

    def test_existing_directory_ok(self):
        with tempfile.TemporaryDirectory() as td:
            secure_mkdir(Path(td))


class TestSecureFilePermissions(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "Unix permissions only")
    def test_sets_600(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = Path(f.name)
        try:
            os.chmod(path, 0o644)
            secure_file_permissions(path)
            mode = path.stat().st_mode & 0o777
            self.assertEqual(mode, stat.S_IRUSR | stat.S_IWUSR)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
