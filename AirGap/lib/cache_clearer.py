import fnmatch
import os
from pathlib import Path

import config
from lib.audit_logger import AuditLogger


class CacheClearResult:
    def __init__(self):
        self.dirs_attempted: list[str] = []
        self.dirs_cleared: list[str] = []
        self.files_deleted: int = 0
        self.files_failed: int = 0
        self.errors: list[str] = []

    @property
    def success(self) -> bool:
        return self.files_failed == 0 and len(self.errors) == 0

    @property
    def partial(self) -> bool:
        return self.files_deleted > 0 and self.files_failed > 0

    def summary(self) -> str:
        status = "success" if self.success else ("partial" if self.partial else "failed")
        return (
            f"Cache clear {status}: "
            f"{self.files_deleted} items deleted, "
            f"{self.files_failed} items failed, "
            f"{len(self.dirs_attempted)} dirs attempted"
        )


def _discover_user_dirs(base: Path) -> list[Path]:
    """Find user-hash directories inside a Fusion cache base."""
    user_dirs = []
    try:
        for entry in os.scandir(base):
            if not entry.is_dir(follow_symlinks=False):
                continue
            if entry.name.startswith("."):
                continue
            name = entry.name
            if len(name) >= 8 and name.isalnum() and name.isupper():
                user_dirs.append(Path(entry.path))
    except OSError:
        pass
    return user_dirs


def _delete_sensitive_files_recursive(
    directory: Path, patterns: list[str], result: CacheClearResult, logger: "AuditLogger"
):
    """Recursively walk a directory and delete only files matching sensitive patterns."""
    if not directory.exists():
        return
    if directory.is_symlink():
        result.errors.append(f"Skipped symlink: {directory}")
        logger.log(
            "CACHE_CLEAR_SKIP",
            f"Directory is a symlink, skipped: {directory}",
            "WARNING",
        )
        return

    result.dirs_attempted.append(str(directory))

    try:
        for dirpath, _dirnames, filenames in os.walk(directory, topdown=True, followlinks=False):
            dp = Path(dirpath)
            for name in filenames:
                if not any(fnmatch.fnmatch(name, pat) for pat in patterns):
                    continue
                fp = dp / name
                if fp.is_symlink():
                    result.errors.append(f"Skipped symlink: {fp}")
                    continue
                try:
                    fp.unlink()
                    result.files_deleted += 1
                except OSError as e:
                    result.files_failed += 1
                    result.errors.append(f"{fp}: {e}")
    except OSError as e:
        result.errors.append(f"Cannot walk {directory}: {e}")
        logger.log(
            "CACHE_CLEAR_ERROR",
            f"Cannot walk directory {directory}: {e}",
            "ERROR",
        )


_EMPTY_CACHE_QUEUE = (
    '<?xml version="1.0" encoding="UTF-16" standalone="no" ?>\n<CacheCommandUrns/>\n'
).encode("utf-16")


def _reset_upload_queue(wlogin_dir: Path, result: CacheClearResult, logger: "AuditLogger"):
    """Reset CacheCommandQueue XML files to empty, preventing queued uploads."""
    if not wlogin_dir.exists():
        return
    try:
        for entry in os.scandir(wlogin_dir):
            if not entry.is_file(follow_symlinks=False):
                continue
            if not fnmatch.fnmatch(entry.name, "CacheCommandQueue*.xml"):
                continue
            entry_path = Path(entry.path)
            if entry_path.is_symlink():
                result.errors.append(f"Skipped symlink: {entry_path}")
                continue
            try:
                entry_path.write_bytes(_EMPTY_CACHE_QUEUE)
                result.files_deleted += 1
            except OSError as e:
                result.files_failed += 1
                result.errors.append(f"{entry_path}: {e}")
    except OSError as e:
        result.errors.append(f"Cannot scan {wlogin_dir}: {e}")
        logger.log(
            "CACHE_CLEAR_ERROR",
            f"Cannot scan for upload queues in {wlogin_dir}: {e}",
            "ERROR",
        )


def clear_fusion_cache() -> CacheClearResult:
    result = CacheClearResult()
    logger = AuditLogger.instance()

    for base in config.FUSION_CACHE_BASES:
        if not base.exists():
            continue

        user_dirs = _discover_user_dirs(base)
        if not user_dirs:
            continue

        for user_dir in user_dirs:
            for subdir_name in config.FUSION_CACHE_SUBDIRS:
                subdir = user_dir / subdir_name
                _delete_sensitive_files_recursive(
                    subdir,
                    config.FUSION_CACHE_SENSITIVE_PATTERNS,
                    result,
                    logger,
                )
                _reset_upload_queue(subdir, result, logger)

    return result
