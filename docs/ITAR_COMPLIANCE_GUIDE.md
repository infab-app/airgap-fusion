# AirGap ITAR Compliance Guide

## Disclaimer

AirGap is a **best-effort compliance workflow tool**, not an ITAR certification or guarantee. Autodesk Fusion 360 is NOT ITAR-compliant per Autodesk's own documentation. This plugin enforces offline mode and blocks cloud saves to minimize the risk of ITAR-controlled data reaching Autodesk servers, but it cannot eliminate all risk.

Organizations handling ITAR-controlled data should consult with their compliance officers and legal counsel before relying on this tool as part of their ITAR compliance program.

---

## How AirGap Works

1. **Forces Offline Mode** — Programmatically sets Fusion 360 to offline mode before any ITAR work begins. Monitors and re-enforces if toggled.
2. **Blocks Cloud Saves** — Intercepts all save operations and cancels them. Users must use "Export Locally" instead.
3. **Local-Only Export** — Provides export to .f3d, STEP, STL, IGES, and SAT formats directly to local or network-attached storage.
4. **Audit Logging** — Records all session events in append-only JSONL log files for compliance auditing. Each entry is linked via a SHA-256 hash chain for tamper detection.
5. **Crash Recovery** — If Fusion crashes during an ITAR session, AirGap forces offline mode on restart and offers to restore the session.

---

## Fusion 360 Local Cache — Critical Information

Even with AirGap active, Fusion 360 maintains a local cache of design data. When Fusion goes back online, cached data MAY sync to Autodesk's cloud servers.

### Cache Locations

Fusion 360 stores cached data under user-specific directories (alphanumeric hashes) within its application support folder:

**Windows:**
```
%LocalAppData%\Autodesk\Autodesk Fusion 360\<user_hash>\
```

**macOS:**
```
~/Library/Application Support/Autodesk/Autodesk Fusion 360/<user_hash>/
```
For Mac App Store installations:
```
~/Library/Containers/com.autodesk.mas.fusion360/Data/Library/Application Support/Autodesk/<user_hash>/
```

Within each user directory, the cache contains:
- `W.login/` — Contains cached design files (`.f3d`, `.f3z`), structural metadata, and upload queues
- `NsCloudBrowserCache*.dat` — Cloud browser cache (Data Panel file/project listings)
- `OfflineCache.xml` — Offline mode state metadata (licensing, entitlements, timebomb)

### What AirGap Clears vs. Preserves

AirGap performs **targeted** cache clearing — only removing data that contains actual design content while preserving the metadata Fusion requires to remain in offline mode:

| Item | Action | Reason |
|------|--------|--------|
| `.f3d` / `.f3z` files in `W.login` | **Deleted** | Contain actual 3D geometry, dimensions, and manufacturing data |
| `CacheCommandQueue*.xml` in `W.login` | **Reset to empty** | Prevents queued design uploads from syncing when going online |
| `NsCloudBrowserCache*.dat` | **Preserved** | Contains only Data Panel directory listings (project names, folder structure) — no design geometry. Fusion cannot enter offline mode without this file |
| `OfflineCache.xml` | **Preserved** | Contains licensing/entitlement state and offline timebomb. Fusion cannot remain offline without this file |
| `W.login` structural files (`M2/index.xml`, directory structure) | **Preserved** | Cache infrastructure Fusion needs to function offline |

### Automatic Cache Clearing

AirGap can automatically clear Fusion's local cache when ending an ITAR session. Enable this via **Settings > Auto-clear Fusion cache when ending sessions**. When enabled, AirGap will:

1. Perform a final autosave of any active work
2. Export all tracked unexported documents as `.f3d`/`.f3z` files to the session export directory
3. Delete cached design files (`.f3d`, `.f3z`) from `W.login` and reset any pending upload queues

AirGap automatically discovers all user directories within the Fusion cache base. Some files may not be deletable while Fusion is still running. AirGap will report which items succeeded and which failed. For any items that could not be deleted, follow the manual procedure below.

### Manual Cache Clearing Procedure

After ending an ITAR session and before allowing Fusion to go online:

1. **Close Fusion 360 completely** (not just minimize)
2. Navigate to the cache directories listed above
3. Delete `.f3d` and `.f3z` files from the `W.login` folder in each user directory
4. Do **not** delete `OfflineCache.xml`, `NsCloudBrowserCache*.dat`, or structural files in `W.login` — Fusion needs these to remain in offline mode
5. Restart Fusion 360
6. Only then should you allow Fusion to go online

**WARNING:** Clearing the cache will remove ALL locally cached designs, not just ITAR-controlled ones. Ensure all work is exported before clearing.

### Cache Clearing Scope and Limitations

AirGap's cache clearing targets design files (`.f3d`, `.f3z`) within `W.login` in each user directory. The following are **intentionally preserved** to maintain offline mode:

- **`NsCloudBrowserCache*.dat`** — Contains Data Panel listings (project names, file names, folder hierarchy) and **embedded design thumbnail images** (base64-encoded PNGs). Fusion requires this file to enter offline mode; without it, Fusion displays an error and forces an online connection. **Important:** These thumbnails are visual previews of designs and may be considered controlled data. However, they pose no upload risk — the browser cache is populated by downloading from Autodesk's servers, and there is no mechanism that uploads this cache back. The risk is limited to data at rest on the local machine. AirGap cannot selectively strip thumbnails from this file without breaking offline mode due to its proprietary binary format. Organizations where thumbnail data at rest is a concern should use full-disk encryption on ITAR workstations.
- **`OfflineCache.xml`** — Contains licensing, entitlement, and offline timebomb data. Required for Fusion to validate its offline state on startup.
- **`W.login` structural files** — Cache index, directory structure, and avatar files. Required for Fusion's cache subsystem to function.

The following locations are **not** covered by AirGap's automatic clearing and may retain residual data:

- **OS temp directories** (`%TEMP%` on Windows, `/tmp` on macOS) — may contain Fusion working files
- **OS-level caches** — filesystem caches, virtual memory swap files, and hibernation files
- **Fusion telemetry queue** — usage analytics data that may be queued for transmission (see Limitations below)
- **Design thumbnails in browser cache** — embedded in `NsCloudBrowserCache*.dat` (see above); cannot be cleared without breaking offline mode

For maximum data residue reduction, organizations should consider full-disk encryption on ITAR workstations and OS-level secure deletion tools as complementary measures.

---

## Recommended Air-Gapped Workstation Setup

For maximum ITAR compliance:

### Network Isolation
- Use a dedicated workstation with **no internet connection** for ITAR work
- If network access is required for NAS, use a private network segment with no internet gateway
- Consider OS-level firewall rules to block Autodesk server IPs as an additional layer

### Fusion 360 Licensing
- Fusion 360 requires an internet connection every **14 days** for license validation
- Plan your workflow to accommodate this: perform all ITAR work within a 14-day window, then clear the cache and reconnect for license renewal
- Consider requesting offline licensing from Autodesk for dedicated ITAR workstations

### Workstation Policy
- Designate specific machines as "ITAR workstations"
- Install AirGap with `runOnStartup: true`
- Document which machines are approved for ITAR work
- Maintain a log of when machines go online/offline

---

## Organizational Policy Template

Consider implementing the following policies:

### Before Starting ITAR Work
- [ ] Verify you are on an approved ITAR workstation
- [ ] Start an AirGap ITAR session
- [ ] Verify the AirGap session shows PROTECTED status
- [ ] Confirm export directory is on approved local/NAS storage

### During ITAR Work
- [ ] Never attempt to go online while working on ITAR data
- [ ] Use "Export Locally" for all file saves
- [ ] Do not share designs via Fusion 360 collaboration features
- [ ] Do not use cloud-dependent features (rendering, simulation, generative design)

### After ITAR Work
- [ ] Export all designs to approved local storage
- [ ] Close all ITAR documents in Fusion 360
- [ ] End the AirGap ITAR session
- [ ] Clear Fusion 360's local cache (see procedure above)
- [ ] Verify cache is cleared before allowing online access
- [ ] Review the audit log for any violations

### Audit Requirements
- [ ] Retain AirGap audit logs for the required retention period
- [ ] Review audit logs periodically for OFFLINE_VIOLATION and SAVE_BLOCKED events
- [ ] Investigate any CRITICAL severity events immediately
- [ ] Maintain records of which designs were worked on and when

---

## What Data Fusion 360 Sends to Autodesk Servers

When online, Fusion 360 transmits:

| Data Type | When Sent | ITAR Risk |
|-----------|-----------|-----------|
| Design files | On save (auto-save and manual) | HIGH |
| Render data | When using cloud rendering | HIGH |
| Simulation data | When using cloud simulation | HIGH |
| Generative design | When using generative features | HIGH |
| Collaboration metadata | When sharing or commenting | MEDIUM |
| Application telemetry | Continuously when online | LOW |
| License validation | Every 14 days | NONE |

AirGap blocks the HIGH and MEDIUM risk transmissions by enforcing offline mode and blocking saves.

---

## Audit Log Format

AirGap writes JSONL (one JSON object per line) log files at:
- **Windows:** `%APPDATA%\.airgap\logs\`
- **macOS:** `~/.airgap/logs/`

Each entry contains:
```json
{
    "timestamp": "2026-04-21T14:30:00.123456",
    "session_id": "abc123def456",
    "event_type": "SAVE_BLOCKED",
    "detail": "Cloud save blocked for: Housing_Assembly",
    "severity": "WARNING",
    "user": "blake.nazario",
    "machine": "WORKSTATION-01",
    "seq": 5,
    "prev_hash": "a1b2c3...",
    "entry_hash": "d4e5f6..."
}
```

The `seq`, `prev_hash`, and `entry_hash` fields form a hash chain. Each entry's hash is computed over its contents (including the previous entry's hash), creating a tamper-evident chain. Use the **Verify Audit Log** button in the AirGap toolbar to check a log file's integrity. Legacy entries written before hash chain support will be skipped during verification.

### Event Types Reference

| Event Type | Severity | Description |
|-----------|----------|-------------|
| SESSION_START | INFO | ITAR session activated |
| SESSION_END | INFO | ITAR session ended cleanly |
| OFFLINE_SET | INFO | Offline mode activated |
| OFFLINE_VIOLATION | CRITICAL | Online transition detected and blocked |
| SAVE_BLOCKED | WARNING | Cloud save attempt canceled |
| DOC_OPENED | INFO | Document opened during session |
| DOC_CREATED | INFO | New document created during session |
| DOC_CLOSED | INFO | Document closed during session |
| EXPORT_F3D | INFO | Fusion Archive (.f3d) exported |
| EXPORT_F3Z | INFO | Fusion Archive (.f3z) with external references exported |
| EXPORT_STEP | INFO | STEP file exported |
| EXPORT_STL | INFO | STL file exported |
| EXPORT_IGES | INFO | IGES file exported |
| EXPORT_ERROR | ERROR | Export operation failed |
| DEACTIVATION_BLOCKED | WARNING | Session end blocked (unexported docs) |
| CACHE_CLEAR_START | INFO | Automatic cache clear initiated |
| CACHE_CLEAR_COMPLETE | INFO/WARNING | Cache clear finished (WARNING if partial) |
| CACHE_CLEAR_SKIP | WARNING | Symlink encountered and skipped during cache clear |
| CACHE_CLEAR_ERROR | ERROR | Cache clear operation failed |
| CACHE_CLEAR_LARGE_DIR | WARNING | Cache directory contains >10,000 entries |
| CRASH_RECOVERY | WARNING | Session restored after crash |
| ADDIN_STOPPING | WARNING | Add-in stopping with active session |
| LOG_VERIFIED | INFO | Audit log integrity check passed |
| LOG_VERIFY_FAILED | WARNING | Audit log integrity check failed |

---

## Limitations

1. **Not a complete ITAR solution** — AirGap cannot guarantee zero data leakage from Fusion 360's internal processes.
2. **Local cache persistence** — Fusion's cache may retain design data even after documents are closed. Manual cache clearing is required.
3. **14-day license limit** — Fusion requires periodic internet access for licensing. This creates a window where data could sync if cache is not cleared.
4. **No file-level ITAR tagging** — AirGap treats ALL documents during a session as ITAR-controlled. There is no per-file classification.
5. **Application telemetry** — Fusion may send usage telemetry even in offline mode (though design data is not included). Telemetry data may also be queued for transmission while offline and sent when the machine next goes online, regardless of whether the cache has been cleared. Cache clearing does not affect queued telemetry.
6. **Audit log integrity is not cryptographically secure** — The hash chain detects accidental corruption and casual tampering (e.g., someone editing a log file without understanding the chain structure). However, AirGap is an uncompiled Python plugin — anyone with access to the machine can read the source code, understand the hashing scheme, and rewrite a log with a valid chain. The integrity check is not a defense against a knowledgeable actor with local access.
