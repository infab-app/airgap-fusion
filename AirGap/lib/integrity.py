import hashlib
import json
from pathlib import Path


def compute_checksum(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verify_checksum(data: dict, expected_hex: str) -> bool:
    return compute_checksum(data) == expected_hex


def file_checksum(filepath: Path) -> str:
    return hashlib.sha256(filepath.read_bytes()).hexdigest()


def verify_file(filepath: Path, expected_hex: str) -> bool:
    if not filepath.exists():
        return False
    return file_checksum(filepath) == expected_hex


def wrap_with_checksum(data: dict) -> dict:
    return {
        "version": 1,
        "payload": data,
        "checksum": compute_checksum(data),
    }


def unwrap_and_verify(envelope: dict) -> dict | None:
    if "version" not in envelope or "payload" not in envelope or "checksum" not in envelope:
        return None
    if not verify_checksum(envelope["payload"], envelope["checksum"]):
        return None
    return envelope["payload"]


def is_envelope(data: dict) -> bool:
    return "version" in data and "payload" in data and "checksum" in data
