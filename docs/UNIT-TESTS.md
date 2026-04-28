# Unit Tests

AirGap includes an automated test suite that validates core logic without requiring the Fusion runtime. Tests run with Python's built-in `unittest` module and have zero external dependencies.

## Requirements

- **Python 3.10+** (the codebase uses PEP 604 union syntax: `X | None`)

## Running Tests

From the project root:

```
python -m unittest
```

With verbose output:

```
python -m unittest discover -v
```

Run a specific test file:

```
python -m unittest tests.test_integrity
```

Run a specific test case:

```
python -m unittest tests.test_session_manager.TestStateTransitions
```

## Test Structure

```
tests/
├── __init__.py              # Package init — mocks adsk module, sets up sys.path
├── test_integrity.py        # Checksum envelope operations
├── test_session_manager.py  # State machine and document tracking
├── test_path_validation.py  # Path security checks
├── test_settings.py         # Settings defaults, validation, persistence
├── test_persistence.py      # Session state save/load/clear
├── test_updater.py          # Version parsing and comparison
└── test_audit_logger.py     # Audit log hash chain and verification
```

## How the Fusion SDK Mock Works

`tests/__init__.py` injects a `MagicMock` for the `adsk` module into `sys.modules` before any AirGap code is imported. This allows all modules to `import adsk.core` without error. The mock also configures `Application.get().userName` to return a real string so that JSON serialization in the audit logger works correctly.

## What Each Test File Covers

### `test_integrity.py`

Tests the SHA-256 checksum envelope system used for tamper detection on all persistent state files.

- `compute_checksum` — determinism, key-order independence, hex format
- `verify_checksum` — valid/invalid/tampered scenarios
- `file_checksum` — file hashing
- `wrap_with_checksum` / `unwrap_and_verify` — envelope creation and validation
- `is_envelope` — envelope format detection

### `test_session_manager.py`

Tests the session state machine that governs all enforcement behavior.

- **State transitions** — every valid transition succeeds, every invalid transition is rejected
- **`is_protected`** — correct for each state (ACTIVATING, PROTECTED, DEACTIVATING are protected; UNPROTECTED, RECOVERING are not)
- **Document tracking** — track, mark exported, unexported sets, default document filtering
- **Session lifecycle** — start_session, reset, property setters

### `test_path_validation.py`

Tests the path security layer that prevents directory traversal and symlink attacks.

- `validate_safe_path` — rejects `..`, rejects symlinks, respects `allowed_parent`
- `validate_filename` — rejects path separators and `..`
- `secure_mkdir` — creates directories with `0o700` permissions
- `secure_file_permissions` — sets files to `0o600`

### `test_settings.py`

Tests user settings management including persistence and validation.

- **Defaults** — all settings start with documented default values
- **Validation** — interval clamping (1–60), max versions clamping (1–20), channel restriction, path validation on directory setters
- **Persistence** — save/load round-trip, checksum envelope handling, tampered envelope rejection, legacy format migration

### `test_persistence.py`

Tests session state persistence used for crash recovery.

- **Round-trip** — save state and reload matches
- **Tamper rejection** — modified payload fails checksum verification
- **Legacy format** — pre-checksum state files are accepted once
- **Clear/restore** — file deletion and direct state restoration

### `test_updater.py`

Tests version parsing and semantic version comparison for the self-update system.

- `parse_version` — handles `v` prefix, prerelease suffixes, two-part versions
- `is_newer` — major/minor/patch comparison, prerelease ordering (beta < rc < release), same-version detection

### `test_audit_logger.py`

Tests the tamper-evident hash chain in the audit log system.

- **Hash chain** — first entry links to genesis, subsequent entries chain correctly, sequence numbers increment
- **Entry verification** — stored hash matches recomputed hash
- **Log verifier** — detects tampered entries, deleted entries, reordered entries, sequence gaps
- **Backward compatibility** — legacy entries (pre-chain) are skipped gracefully
- **Edge cases** — empty files, invalid JSON, nonexistent files

## What Is NOT Tested

The following modules depend heavily on the Fusion runtime API and are not covered by automated tests:

- **`save_interceptor.py`** — Document event handlers (`documentSaving`, `documentOpened`, etc.)
- **`offline_enforcer.py`** — `app.isOffLine` enforcement and event handler registration
- **`export_manager.py`** — Fusion's `exportManager.execute()` calls
- **`autosave_manager.py`** — Background export thread with Fusion document access
- **`commands/`** — UI command handlers that interact with Fusion dialogs

These should be manually tested in Fusion before merging any changes to them.

## CI Integration

Tests run automatically on every pull request and push to `main` via the `Tests` GitHub Actions workflow (`.github/workflows/tests.yml`). The test matrix covers Python 3.10, 3.12, and 3.14.

## Writing New Tests

1. Add a new file in `tests/` named `test_<module>.py`
2. Import from `lib.*` or `config` directly — `tests/__init__.py` handles the path setup
3. Use `unittest.TestCase` — no external test frameworks needed
4. For modules that use singletons, reset `ClassName._instance = None` in `setUp`/`tearDown`
5. For file operations, use `tempfile.mkdtemp()` and clean up in `tearDown`
6. Run `ruff check tests/` before committing
