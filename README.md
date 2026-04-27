# AirGap for Autodesk Fusion

**An open-source Autodesk Fusion add-in by [Infab Softworks](https://infab.app)** that adds application-level safeguards for working with export-controlled design data. AirGap locks Fusion into offline mode, blocks cloud saves, and provides local-only file export, giving teams an additional layer of protection when using Fusion 360 in export controlled workflows.

> **Disclaimer:** AirGap is designed to operate within an existing ITAR-compliant environment. It is not a substitute for compliant network architecture, access controls, or a formal compliance program. Autodesk Fusion 360 is not ITAR-compliant per Autodesk's own documentation. Consult your compliance officers before relying on this or any tool for export-controlled work.

## How It Works

AirGap manages a session lifecycle with four states:

```
UNPROTECTED → ACTIVATING → PROTECTED → DEACTIVATING → UNPROTECTED
```

1. **Start Session** — Forces Fusion into offline mode, begins monitoring
2. **Work in Protected Mode** — Cloud saves are blocked, all opened documents are tracked
3. **Export Locally** — Save .f3d, STEP, STL, IGES files to local or network-attached storage
4. **End Session** — Verifies all documents were exported and closed before allowing deactivation

### Key Features

- **Offline Enforcement** — Programmatically sets `app.isOffLine = True` and monitors via event handlers and a polling thread. If someone toggles Fusion back online, AirGap immediately re-enforces offline mode.
- **Cloud Save Blocking** — Intercepts save operations via the `documentSaving` event and cancels them with a warning directing the user to export locally.
- **Local Export** — Supports F3D (Fusion Archive), STEP, STL, IGES, and SAT.
- **Audit Logging** — Append-only JSONL logs record every session event (start, stop, exports, blocked saves, violations) for compliance auditing.
- **Crash Recovery** — Session state is persisted to disk. If Fusion crashes during a session, AirGap forces offline mode on restart and offers to restore the session.
- **Cross-Platform** — Single Python codebase for Windows and macOS.
- **Auto-Update** - Optionally check for updates automatically on Fusion startup, notifying you of any new updates and can update itself after user confirmation

## Installation

The `AirGap` folder in this repository is the complete add-in. Copy just this folder into Fusion 360's add-ins directory.

**Option 1: Download from GitHub Releases (recommended)**

1. Go to the [latest release](https://github.com/infab-app/airgap-fusion/releases/latest)
2. Download `AirGap-v{version}.zip`
3. Extract the zip — you'll get an `AirGap/` folder
4. Drag-and-drop or copy the `AirGap` folder into Fusion 360's add-ins directory:
   - **Windows:** `%AppData%\Autodesk\Autodesk Fusion 360\API\AddIns\`
   - **macOS:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`

**Option 2: Download the repository as a ZIP**

1. Click **Code → Download ZIP** on the repository page
2. Extract the zip and copy only the `AirGap` folder into the add-ins directory above

**Option 3: Clone with git**

**Windows:**
```
git clone https://github.com/infab-app/airgap-fusion.git
xcopy /E airgap-fusion\AirGap "%AppData%\Autodesk\Autodesk Fusion 360\API\AddIns\AirGap\"
```

**macOS:**
```
git clone https://github.com/infab-app/airgap-fusion.git
cp -R airgap-fusion/AirGap ~/Library/Application\ Support/Autodesk/Autodesk\ Fusion\ 360/API/AddIns/AirGap
```

> **Important:** For options 2 and 3, copy only the `AirGap` folder, not the entire repository. The other files (docs, CI config, linter config) are for development and are not needed by the add-in.

### Updating

AirGap can check for updates from within Fusion 360. Click **Check for Updates** in the AirGap toolbar tab to see if a newer version is available. You can also enable automatic update checks on startup in AirGap Settings.

To update manually, delete the existing `AirGap` folder from your Fusion 360 add-ins directory and replace it with the `AirGap` folder from the [latest release](https://github.com/infab-app/airgap-fusion/releases/latest). Your settings and audit logs are stored separately (`~/.airgap/`) and will not be affected.

The resulting directory in your Add-Ins folder should look like:
```
AirGap/
├── AirGap.py
├── AirGap.manifest
├── config.py
├── lib/
├── commands/
├── resources/
└── ...
```

Then in Fusion 360:
1. Open **Tools → Add-Ins** (or press `Shift+S`)
2. Go to the **Add-Ins** tab
3. Click the green **+** icon and navigate to the `AirGap` folder (or it may appear automatically)
4. Check **Run on Startup** (recommended)
5. Click **Run**

## Usage

Once running, AirGap adds an **AirGap** tab to the toolbar in both the Design and Manufacture workspaces.

### Starting an AirGap Session

1. Click **Start AirGap Session**
2. Set the export directory (local path or NAS mount)
3. Confirm the ITAR acknowledgment checkbox
4. Click **OK** — Fusion goes offline and cloud saves are blocked

### Exporting Files

1. Click **Export Locally**
2. Select formats: F3D, STEP, STL, IGES
3. Choose the target component
4. Click **OK** — Files are saved to your local export directory

### Ending an AirGap Session

1. Export all tracked documents
2. Close all tracked documents in Fusion
3. Click **Stop AirGap Session**
4. Confirm both acknowledgment checkboxes
5. Click **OK** — Enforcement is deactivated

### Enabling Auto-updates

1. Click **AirGap Settings**
2. Enable the **Check for updates when Fusion starts** toggle
3. Click **OK**
4. Settings should now be saved and AirGap will check for updates every time Fusion starts

Fusion remains in offline mode after the session ends. You must manually go online after confirming no ITAR data remains in Fusion's local cache.

## Repository Structure

```
airgap-fusion/
├── AirGap/                    # Add-in folder (copy this into Fusion 360)
│   ├── AirGap.py              # Entry point
│   ├── AirGap.manifest        # Add-in metadata
│   ├── config.py              # Constants and paths
│   ├── lib/
│   │   ├── session_manager.py # State machine
│   │   ├── offline_enforcer.py# Offline mode control and monitoring
│   │   ├── save_interceptor.py# Cloud save blocking
│   │   ├── export_manager.py  # Local file export
│   │   ├── audit_logger.py    # JSONL compliance logging
│   │   ├── ui_components.py   # Toolbar and button setup
│   │   ├── persistence.py     # Crash recovery state
│   │   ├── settings.py        # User settings management
│   │   ├── github_client.py   # GitHub Releases API client
│   │   └── updater.py         # Self-update orchestration
│   ├── commands/
│   │   ├── start_session.py   # Start AirGap session command
│   │   ├── stop_session.py    # Stop session command
│   │   ├── export_local.py    # Export dialog command
│   │   ├── check_update.py    # Check for updates command
│   │   ├── view_log.py        # Open audit log
│   │   └── settings.py        # Settings dialog command
│   └── resources/             # Toolbar icons (16x16 and 32x32 PNG)
├── docs/                      # Documentation
│   ├── ITAR_COMPLIANCE_GUIDE.md
│   ├── CONTRIBUTING.md
│   └── RELEASE_STRATEGY.md
├── .github/workflows/         # CI workflows
└── ruff.toml                  # Linter configuration
```

## Audit Logs

Logs are stored as JSONL files at:
- **Windows:** `%APPDATA%\.airgap\logs\`
- **macOS:** `~/.airgap/logs/`

Each line is a JSON object with timestamp, session ID, event type, detail, severity, user, and machine name. See [ITAR Compliance Guide](docs/ITAR_COMPLIANCE_GUIDE.md) for the full event type reference.

## Important Limitations

- **Not a standalone ITAR solution.** AirGap adds application-level safeguards but is not a substitute for compliant network architecture, access controls, or organizational policies. Fusion 360's local cache may retain design data that syncs when going back online. See the [ITAR Compliance Guide](docs/ITAR_COMPLIANCE_GUIDE.md) for cache clearing procedures.
- **14-day license window.** Fusion requires internet access for license validation every 14 days. Plan ITAR work within this window, then clear the cache before reconnecting.
- **Session-level tracking.** All documents opened during a session are treated as ITAR-controlled. There is no per-file classification.

## Contributing

AirGap is open-source software maintained by [Infab Softworks](https://infab.app). Contributions are welcome — see [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](LICENSE) for details.

---

Built and maintained by **[Infab Softworks](https://infab.app)**
