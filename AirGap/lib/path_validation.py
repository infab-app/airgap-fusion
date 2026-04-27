import os
import stat
from pathlib import Path


def validate_safe_path(path_str: str, allowed_parent: Path | None = None) -> Path | None:
    try:
        raw = Path(path_str)
        if ".." in raw.parts:
            return None
        if raw.exists() and raw.is_symlink():
            return None
        p = raw.resolve()
        if allowed_parent is not None and not p.is_relative_to(allowed_parent.resolve()):
            return None
        return p
    except (OSError, ValueError):
        return None


def validate_filename(name: str) -> bool:
    if not name:
        return False
    if "/" in name or "\\" in name:
        return False
    return ".." not in name


def secure_mkdir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(path, stat.S_IRWXU)


def secure_file_permissions(path: Path):
    if os.name != "nt":
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
