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


def _safe_rmtree(
    root: Path, result: CacheClearResult, logger: "AuditLogger"
) -> tuple[int, int]:
    """Walk bottom-up and delete, checking every node for symlinks."""
    deleted = 0
    failed = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=False, followlinks=False):
        dp = Path(dirpath)
        for name in filenames:
            fp = dp / name
            if fp.is_symlink():
                result.errors.append(f"Skipped symlink: {fp}")
                logger.log(
                    "CACHE_CLEAR_SKIP",
                    f"Skipped symlink during tree walk: {fp}",
                    "WARNING",
                )
                continue
            try:
                fp.unlink()
                deleted += 1
            except OSError as e:
                failed += 1
                result.errors.append(f"{fp}: {e}")
        for name in dirnames:
            dp_child = dp / name
            if dp_child.is_symlink():
                result.errors.append(f"Skipped symlink: {dp_child}")
                logger.log(
                    "CACHE_CLEAR_SKIP",
                    f"Skipped symlink during tree walk: {dp_child}",
                    "WARNING",
                )
                continue
            try:
                dp_child.rmdir()
                deleted += 1
            except OSError as e:
                failed += 1
                result.errors.append(f"{dp_child}: {e}")
    try:
        root.rmdir()
        deleted += 1
    except OSError as e:
        failed += 1
        result.errors.append(f"{root}: {e}")
    return deleted, failed


def clear_fusion_cache() -> CacheClearResult:
    result = CacheClearResult()
    logger = AuditLogger.instance()

    for base in config.FUSION_CACHE_BASES:
        if not base.exists():
            continue
        for subdir_name in config.FUSION_CACHE_SUBDIRS:
            cache_dir = base / subdir_name
            if not cache_dir.exists():
                continue
            if cache_dir.is_symlink():
                result.errors.append(f"Skipped symlink: {cache_dir}")
                logger.log(
                    "CACHE_CLEAR_SKIP",
                    f"Cache directory is a symlink, skipped: {cache_dir}",
                    "WARNING",
                )
                continue

            result.dirs_attempted.append(str(cache_dir))
            dir_deleted = 0
            dir_failed = 0

            try:
                entries = list(os.scandir(cache_dir))
            except OSError as e:
                result.errors.append(f"Cannot scan {cache_dir}: {e}")
                logger.log(
                    "CACHE_CLEAR_ERROR",
                    f"Cannot scan cache directory {cache_dir}: {e}",
                    "ERROR",
                )
                continue

            if len(entries) > 10000:
                logger.log(
                    "CACHE_CLEAR_LARGE_DIR",
                    f"Large cache directory ({len(entries)} top-level entries): {cache_dir}",
                    "WARNING",
                )

            for entry in entries:
                try:
                    entry_path = Path(entry.path)
                    if entry_path.is_symlink():
                        result.errors.append(f"Skipped symlink: {entry_path}")
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        deleted, failed = _safe_rmtree(entry_path, result, logger)
                        dir_deleted += deleted
                        dir_failed += failed
                    else:
                        entry_path.unlink()
                        dir_deleted += 1
                except OSError as e:
                    dir_failed += 1
                    result.errors.append(f"{entry.path}: {e}")

            result.files_deleted += dir_deleted
            result.files_failed += dir_failed

            if dir_failed == 0:
                result.dirs_cleared.append(str(cache_dir))

    return result
