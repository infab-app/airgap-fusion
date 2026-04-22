# Contributing to AirGap

Thanks for your interest in contributing to AirGap. This guide covers how to set up your environment, follow our code standards, and submit changes.

## Getting Started

1. Fork the repository and clone your fork
2. Create a feature branch from `main`:
   ```
   git checkout -b feature/your-feature-name
   ```
3. Copy the add-in into Fusion 360's add-ins directory for testing (see [README](../README.md#installation))

## Development Environment

AirGap runs inside Fusion 360's embedded Python runtime. There are no external pip dependencies, only the standard library and the Fusion 360 SDK (`adsk.core`, `adsk.fusion`, `adsk.cam`).

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
python3 -m ruff check .
python3 -m ruff format .
```
This is common on macOS when `pip install` places binaries in a directory not on your shell's PATH.

### VS Code Setup

If you use VS Code, install the [Ruff extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff). It reads `ruff.toml` automatically and provides inline lint warnings and format-on-save.

## Project Structure

The repository separates the add-in from development tooling. The `AirGap/` folder is the complete Fusion 360 add-in that users copy into their Add-Ins directory. All add-in code, resources, and configuration must live inside `AirGap/` so that users can install it by dragging a single folder.

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
│   │   ├── ui_components.py
│   │   ├── persistence.py
│   │   └── settings.py
│   ├── commands/            # UI command handlers
│   │   ├── start_session.py
│   │   ├── stop_session.py
│   │   ├── export_local.py
│   │   ├── view_log.py
│   │   └── settings.py
│   └── resources/           # Toolbar icons
├── docs/                    # Documentation (not included in the add-in)
├── .github/workflows/       # CI workflows
└── ruff.toml                # Linter configuration
```

Files outside of `AirGap/` (docs, CI config, linter config) are for development only and are not part of the add-in.

## Code Style

- **Python 3.10+** — Use modern type annotations (`set[str]`, `str | None`)
- **Line length** — 100 characters max
- **Imports** — Sorted by Ruff's isort rules. `adsk` is grouped as third-party
- **No comments unless the "why" is non-obvious** — Let clear naming do the work
- **Fusion SDK pattern** — Some files import `adsk.fusion` or `adsk.cam` without direct reference. This is required by the Fusion runtime to register submodule APIs. These imports are intentional and suppressed in the linter config

## CI Checks

Every push and pull request runs these GitHub Actions:

| Workflow | What it checks |
|----------|---------------|
| **Syntax Check** | All `.py` files compile on Python 3.12 |
| **Lint** | Ruff lint rules and formatting |
| **CodeQL** | Security analysis for common vulnerability patterns |
| **PR Checks** | JSON validity, version consistency, no `.pyc` files |

All checks must pass before a PR can be merged.

## Testing

AirGap runs inside Fusion 360's runtime, so automated unit testing is limited. Please manually test your changes in Fusion 360 before submitting a PR:

1. Load the modified add-in in Fusion 360
2. Start and stop an ITAR session
3. Verify your change works as expected
4. Check the audit log for any unexpected entries
5. Confirm existing functionality is not broken

## Submitting a Pull Request

1. Ensure `ruff check .` and `ruff format --check .` both pass with no errors
2. Test your changes in Fusion 360
3. Push your branch and open a PR against `main`
4. Describe what your change does and why
5. Reference any related issues

## Reporting Issues

Open a GitHub issue with:

- What you expected to happen
- What actually happened
- Fusion 360 version and OS
- Relevant audit log entries (if applicable)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
