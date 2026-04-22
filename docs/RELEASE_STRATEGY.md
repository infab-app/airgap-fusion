# Release Strategy

AirGap uses a two-channel release model with automated beta releases and manual stable releases.

## Branch Structure

```
main        ← stable releases (v1.0.0, v1.1.0, v2.0.0)
develop     ← beta releases (v1.0.1-beta.1, v1.0.1-beta.2, ...)
feature/*   ← branch from develop, PR back to develop
bugfix/*    ← branch from develop, PR back to develop
enhancement/*
repo/*
```

- `main` always reflects the latest stable release.
- `develop` is the integration branch where all work lands before promotion to stable.
- Both branches are protected. Direct pushes are not allowed; all changes go through pull requests.

## Version Format

Versions follow [Semantic Versioning](https://semver.org/):

- **Stable:** `MAJOR.MINOR.PATCH` (e.g., `1.1.0`)
- **Beta:** `MAJOR.MINOR.PATCH-beta.N` (e.g., `1.1.0-beta.1`)

The version is stored in two files that must always match:

- `AirGap/config.py` — `VERSION = "x.y.z"`
- `AirGap/AirGap.manifest` — `"version": "x.y.z"`

## Beta Releases (Automatic)

Beta releases are created automatically when a pull request is merged into `develop`.

**Workflow:** `auto-release-beta.yml`

**What happens on merge to `develop`:**

1. CI checks run (lint, syntax, format)
2. The current version is read from `config.py`
3. The patch beta version is incremented:
   - `1.0.0` → `1.0.1-beta.1`
   - `1.0.1-beta.1` → `1.0.1-beta.2`
   - `1.0.1-beta.2` → `1.0.1-beta.3`
4. Both version files are updated and committed
5. A git tag is created (e.g., `v1.0.1-beta.3`)
6. A GitHub Pre-Release is published with:
   - `AirGap-v{version}.zip` — the packaged add-in
   - `SHA256SUMS` — checksum file for integrity verification

No manual action is required. Every merged PR produces a new beta release.

## Stable Releases (Manual)

Stable releases are created by manually running the **Release** workflow.

**Workflow:** `release.yml` (triggered via workflow_dispatch)

**Steps to create a stable release:**

1. Ensure `develop` contains all the changes you want to release
2. Open a pull request from `develop` to `main` and merge it
3. Go to **Actions → Release → Run workflow**
4. Enter the desired version number (e.g., `1.1.0`, `2.0.0`)
   - Must be plain semver with no pre-release suffix
   - You control the version — use your judgment on major, minor, or patch
5. The workflow:
   - Updates both version files on `main`
   - Commits and pushes the version change
   - Creates a git tag (e.g., `v1.1.0`)
   - Packages the add-in and generates checksums
   - Publishes a GitHub Release (marked as Latest)

## Hotfixes

For critical bugs in a stable release that cannot wait for the normal beta cycle:

1. Branch from `main`: `git checkout -b bugfix/critical-fix main`
2. Fix the issue
3. Open a PR targeting `main`
4. After merge, run the **Release** workflow with a patch bump (e.g., `1.0.1` → `1.0.2`)
5. Cherry-pick or merge the fix into `develop` to keep branches in sync

## Release Artifacts

Every release (beta and stable) publishes:

| Artifact | Description |
|----------|-------------|
| `AirGap-v{version}.zip` | The complete add-in folder, ready to extract and install |
| `SHA256SUMS` | SHA-256 checksum for verifying download integrity |

The zip contains the `AirGap/` directory. Users extract it and copy to their Fusion 360 Add-Ins directory.

## Self-Update Mechanism

AirGap includes a built-in update checker that queries GitHub Releases:

- **Manual check:** Users click "Check for Updates" in the AirGap toolbar
- **Automatic check:** Opt-in setting to check on Fusion startup (off by default)
- **Update channel:** Users choose between "Stable" and "Beta" in settings

When an update is found, the user can download and stage it. The update is applied the next time Fusion 360 restarts. Updates are never checked or downloaded during an active AirGap session.

## CI Workflows Summary

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `lint.yml` | Pull request | Ruff lint and format checks |
| `syntax-check.yml` | Pull request | Python compilation check |
| `pr-checks.yml` | Pull request | JSON validation, version consistency, no .pyc files |
| `codeql.yml` | Pull request, push, weekly | Security analysis |
| `auto-release-beta.yml` | PR merged to `develop` | Auto-bump beta version and publish pre-release |
| `release.yml` | Manual (workflow_dispatch) | Bump to specified version and publish stable release |
