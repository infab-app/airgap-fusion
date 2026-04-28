import json
from dataclasses import dataclass
from pathlib import Path

from lib.audit_logger import GENESIS_HASH, _compute_entry_hash


@dataclass
class VerifyResult:
    valid: bool
    entries_checked: int
    entries_total: int
    legacy_entries_skipped: int
    first_break_at: int | None
    error: str | None
    chain_start_hash: str | None


def _verify_entry(entry, line_num, expected_prev, expected_seq, chain_started):
    if "entry_hash" not in entry or "prev_hash" not in entry:
        return None, expected_prev, expected_seq, chain_started, True, None

    start_hash = None
    if not chain_started:
        expected_prev = entry["prev_hash"]
        start_hash = entry["prev_hash"]
        if "seq" in entry:
            expected_seq = entry["seq"]
        chain_started = True

    if entry["prev_hash"] != expected_prev:
        error = (
            f"Chain broken at line {line_num}: "
            f"expected prev_hash {expected_prev[:16]}..., "
            f"got {entry['prev_hash'][:16]}..."
        )
        return error, expected_prev, expected_seq, chain_started, False, start_hash

    if "seq" in entry and expected_seq is not None:
        if entry["seq"] != expected_seq:
            error = (
                f"Sequence gap at line {line_num}: expected seq {expected_seq}, got {entry['seq']}"
            )
            return error, expected_prev, expected_seq, chain_started, False, start_hash

    stored_hash = entry.pop("entry_hash")
    recomputed = _compute_entry_hash(entry)
    entry["entry_hash"] = stored_hash

    if recomputed != stored_hash:
        error = f"Entry hash mismatch at line {line_num}: entry may have been modified"
        return error, expected_prev, expected_seq, chain_started, False, start_hash

    next_seq = expected_seq + 1 if expected_seq is not None and "seq" in entry else expected_seq
    return None, stored_hash, next_seq, chain_started, False, start_hash


def verify_log(log_path: Path) -> VerifyResult:
    if not log_path.exists():
        return VerifyResult(False, 0, 0, 0, None, "Log file does not exist", None)

    entries_total = 0
    entries_checked = 0
    legacy_skipped = 0
    expected_prev = GENESIS_HASH
    expected_seq = None
    chain_started = False
    chain_start_hash = None

    try:
        with open(log_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                entries_total += 1

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    return VerifyResult(
                        False,
                        entries_checked,
                        entries_total,
                        legacy_skipped,
                        line_num,
                        f"Invalid JSON at line {line_num}",
                        chain_start_hash,
                    )

                error, expected_prev, expected_seq, chain_started, is_legacy, start_hash = (
                    _verify_entry(entry, line_num, expected_prev, expected_seq, chain_started)
                )
                if start_hash is not None:
                    chain_start_hash = start_hash
                if is_legacy:
                    legacy_skipped += 1
                    continue
                if error:
                    return VerifyResult(
                        False,
                        entries_checked,
                        entries_total,
                        legacy_skipped,
                        line_num,
                        error,
                        chain_start_hash,
                    )
                entries_checked += 1

    except OSError as e:
        return VerifyResult(
            False, entries_checked, entries_total, legacy_skipped, None, str(e), chain_start_hash
        )

    return VerifyResult(
        True, entries_checked, entries_total, legacy_skipped, None, None, chain_start_hash
    )
