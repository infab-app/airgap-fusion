# Contributing to AirGap

Thanks for your interest in contributing to AirGap. This guide covers how to set up your environment, follow our code standards, and submit changes.

## Getting Started

1. Fork the repository and clone your fork
2. Create a branch from `main` using the appropriate prefix:
   ```
   git checkout main
   git pull origin main
   git checkout -b feature/your-branch-name
   ```
3. Copy the add-in into Fusion's add-ins directory for testing (see [README](../README.md#installation))

## Branch Naming

All branches should be created from `main` and use one of these prefixes:

| Prefix | Use for | Example |
|--------|---------|---------|
| `feature/` | New functionality | `feature/export-pdf-format` |
| `bugfix/` | Fixing a bug | `bugfix/offline-monitor-crash` |
| `enhancement/` | Improving existing functionality | `enhancement/settings-dialog` |
| `repo/` | CI, docs, tooling, repo maintenance | `repo/update-documentation` |

## Pull Request Guidelines

- **All PRs target `main`**
- Describe what your change does and why
- Reference any related issues
- Keep PRs focused on a single concern
- Ensure all CI checks pass before requesting review

## Development Environment

AirGap runs inside Fusion's embedded Python runtime. There are no external pip dependencies, only the standard library and the Fusion SDK (`adsk.core`, `adsk.fusion`, `adsk.cam`).

### Linting and Formatting

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. Configuration is in `ruff.toml` at the project root.

**Install Ruff:**
```
pip install ruff
```

**Before committing, run both checks:**
```
ruff check .
ruff format .
```

`ruff check .` catches lint errors. `ruff format .` auto-formats all files. Running both ensures your PR will pass CI.

**Auto-fix lint issues:**
```
ruff check --fix .
```

**If `ruff` is not found in your PATH**, you can run it as a Python module instead:
```
python -m ruff check .
python -m ruff format .
```
This is common on macOS when `pip install` places binaries in a directory not on your shell's PATH.

### VS Code Setup

If you use VS Code, install the [Ruff extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff). It reads `ruff.toml` automatically and provides inline lint warnings and format-on-save.

## Project Structure

The repository separates the add-in from development tooling. The `AirGap/` folder is the complete Fusion add-in that users copy into their Add-Ins directory. All add-in code, resources, and configuration must live inside `AirGap/` so that users can install it by dragging a single folder.

```
airgap-fusion/
├── AirGap/                  # Add-in folder (this is what users install)
│   ├── AirGap.py            # Entry point (run/stop hooks for Fusion)
│   ├── config.py            # Constants, paths, command IDs
│   ├── lib/                 # Core modules
│   │   ├── session_manager.py
│   │   ├── offline_enforcer.py
│   │   ├── save_interceptor.py
│   │   ├── export_manager.py
│   │   ├── audit_logger.py
│   │   ├── log_verifier.py
│   │   ├── ui_components.py
│   │   ├── persistence.py
│   │   ├── settings.py
│   │   ├── github_client.py
│   │   └── updater.py
│   ├── commands/            # UI command handlers
│   │   ├── start_session.py
│   │   ├── stop_session.py
│   │   ├── export_local.py
│   │   ├── check_update.py
│   │   ├── verify_log.py
│   │   ├── view_log.py
│   │   └── settings.py
│   └── resources/           # Toolbar icons
├── tests/                   # Unit tests (run outside Fusion)
├── docs/                    # Documentation (not included in the add-in)
├── .github/workflows/       # CI and release workflows
└── ruff.toml                # Linter configuration
```

Files outside of `AirGap/` (docs, CI config, linter config) are for development only and are not part of the add-in.

## Versioning

The version is tracked in two files that must always match:

- `AirGap/config.py` — `VERSION = "x.y.z"`
- `AirGap/AirGap.manifest` — `"version": "x.y.z"`

**Do not manually edit version numbers.** Versioning is handled automatically by CI workflows. See [RELEASE_STRATEGY.md](RELEASE_STRATEGY.md) for details.

The PR Checks workflow validates that both files contain the same version on every pull request.

## Code Style

- **Python 3.10+** — Use modern type annotations (`set[str]`, `str | None`)
- **Line length** — 100 characters max
- **Imports** — Sorted by Ruff's isort rules. `adsk` is grouped as third-party
- **No comments unless the "why" is non-obvious** — Let clear naming do the work
- **Fusion SDK pattern** — Some files import `adsk.fusion` or `adsk.cam` without direct reference. This is required by the Fusion runtime to register submodule APIs. These imports are intentional and suppressed in the linter config

## CI Checks

Every pull request to `main` runs these GitHub Actions:

| Workflow | What it checks |
|----------|---------------|
| **Tests** | Unit tests pass on Python 3.10, 3.12, and 3.14 |
| **Syntax Check** | All `.py` files compile on Python 3.12 |
| **Lint** | Ruff lint rules and formatting |
| **CodeQL** | Security analysis for common vulnerability patterns |
| **PR Checks** | JSON validity, version consistency, no `.pyc` files |

All checks must pass before a PR can be merged.

## Testing

### Automated Unit Tests

AirGap includes a test suite for core logic modules that runs outside of Fusion. Tests use only `unittest` (standard library, no dependencies) and require **Python 3.10+** or higher.

**Run all tests:**
```
python3 -m unittest
```

**Run with verbose output:**
```
python3 -m unittest discover -v
```

**Run a specific test file:**
```
python3 -m unittest tests.test_session_manager
```

Tests cover: state machine transitions, integrity checksums, path validation, settings persistence, session persistence, version comparison, and audit log hash chain verification. See [UNIT-TESTS.md](UNIT-TESTS.md) for full details on test structure and coverage.

All tests must pass before a PR can be merged. The `Tests` CI workflow runs automatically on every pull request.

### Manual Testing in Fusion

Modules that interact directly with the Fusion API (save interceptor, offline enforcer, export manager, command handlers) cannot be unit tested outside the runtime. For changes to these modules, manually test in Fusion before submitting a PR:

1. Load the modified add-in in Fusion
2. Start and stop an AirGap session
3. Verify your change works as expected
4. Check the audit log for any unexpected entries
5. Confirm existing functionality is not broken

## Reporting Issues

Open a GitHub issue with:

- What you expected to happen
- What actually happened
- Fusion version and OS
- Relevant audit log entries (if applicable)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
