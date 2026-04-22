# Release Strategy

AirGap uses trunk-based development with a two-channel release model: automated beta pre-releases and manual stable releases.

## Branch Model

```
main (active development)
  tags: v1.0.3, v1.0.4-beta.1, v1.0.4-beta.2, v1.1.0
```

- `main` is the only long-lived branch. It contains active development.
- Feature branches (`feature/*`, `bugfix/*`, `enhancement/*`, `repo/*`) are created from `main` and merged back via pull request.
- Stable releases are published as normal version tags (e.g., `v1.1.0`).
- Beta releases are published as pre-release tags with `-beta.N` suffixes (e.g., `v1.1.0-beta.1`).
- Users running production or compliance-sensitive workflows should use stable releases only.

## Version Format

Versions follow [Semantic Versioning](https://semver.org/):

- **Stable:** `MAJOR.MINOR.PATCH` (e.g., `1.1.0`)
- **Beta:** `MAJOR.MINOR.PATCH-beta.N` (e.g., `1.1.0-beta.1`)

The version is stored in two files that must always match:

- `AirGap/config.py` — `VERSION = "x.y.z"`
- `AirGap/AirGap.manifest` — `"version": "x.y.z"`

These files on `main` always reflect the **last stable release**. Beta versions exist only in git tags and release artifacts (the downloaded zip contains the correct beta version).

## Beta Releases (Automatic)

A beta pre-release is created automatically every time a pull request is merged into `main`.

**Workflow:** `auto-release-beta.yml`

**What happens on merge:**

1. CI checks run (lint, syntax, format)
2. The next beta version is computed from existing git tags:
   - If the stable version is `1.0.3`, the next beta is `1.0.4-beta.1`
   - Subsequent merges produce `1.0.4-beta.2`, `1.0.4-beta.3`, etc.
3. Version files are updated in the working directory (not committed)
4. The add-in is packaged as a zip with the beta version baked in
5. A git tag and GitHub Pre-Release are created with:
   - `AirGap-v{version}.zip` — the packaged add-in
   - `SHA256SUMS` — checksum for integrity verification

No manual action is required. Every merged PR produces a new beta release.

## Stable Releases (Manual)

Stable releases are created by manually running the **Release** workflow.

**Workflow:** `release.yml` (triggered via workflow_dispatch)

**Steps to create a stable release:**

1. Go to **Actions → Release → Run workflow**
2. Enter the desired version number (e.g., `1.1.0`, `2.0.0`)
   - Must be plain semver with no pre-release suffix
   - You control the version — use your judgment on major, minor, or patch
3. The workflow:
   - Updates both version files on `main`
   - Commits and pushes the version change
   - Creates a git tag (e.g., `v1.1.0`)
   - Packages the add-in and generates checksums
   - Publishes a GitHub Release (marked as Latest)

## Release Branches (Optional)

For significant releases that need a stabilization period, you can optionally create a temporary release branch:

1. Branch from `main`: `git checkout -b release/1.2`
2. Only bug fixes go into this branch
3. When stable, merge to `main` and run the Release workflow
4. Delete the release branch

This is not required for most releases and should only be used when you need to freeze features while continuing development on `main`.

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
| `auto-release-beta.yml` | PR merged to `main` | Auto-compute beta version and publish pre-release |
| `release.yml` | Manual (workflow_dispatch) | Bump to specified version and publish stable release |
