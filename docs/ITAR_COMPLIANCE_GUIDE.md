# AirGap ITAR Compliance Guide

## Disclaimer

AirGap is a **best-effort compliance workflow tool**, not an ITAR certification or guarantee. Autodesk Fusion 360 is NOT ITAR-compliant per Autodesk's own documentation. This plugin enforces offline mode and blocks cloud saves to minimize the risk of ITAR-controlled data reaching Autodesk servers, but it cannot eliminate all risk.

Organizations handling ITAR-controlled data should consult with their compliance officers and legal counsel before relying on this tool as part of their ITAR compliance program.

---

## How AirGap Works

1. **Forces Offline Mode** — Programmatically sets Fusion 360 to offline mode before any ITAR work begins. Monitors and re-enforces if toggled.
2. **Blocks Cloud Saves** — Intercepts all save operations and cancels them. Users must use "Export Locally" instead.
3. **Local-Only Export** — Provides export to .f3d, STEP, STL, IGES, and SAT formats directly to local or network-attached storage.
4. **Audit Logging** — Records all session events in append-only JSONL log files for compliance auditing.
5. **Crash Recovery** — If Fusion crashes during an ITAR session, AirGap forces offline mode on restart and offers to restore the session.

---

## Fusion 360 Local Cache — Critical Information

Even with AirGap active, Fusion 360 maintains a local cache of design data. When Fusion goes back online, cached data MAY sync to Autodesk's cloud servers.

### Cache Locations

**Windows:**
```
%LocalAppData%\Autodesk\Autodesk Fusion 360\
```
Specifically:
- `W.Login\` — Contains cached design files
- `DataCache\` — General data cache

**macOS:**
```
~/Library/Application Support/Autodesk/Autodesk Fusion 360/
```
For Mac App Store installations:
```
~/Library/Containers/com.autodesk.mas.fusion360/Data/Library/Application Support/Autodesk/
```

### Cache Clearing Procedure

After ending an ITAR session and before allowing Fusion to go online:

1. **Close Fusion 360 completely** (not just minimize)
2. Navigate to the cache directories listed above
3. Delete the contents of the `W.Login` and `DataCache` folders
4. Restart Fusion 360
5. Only then should you allow Fusion to go online

**WARNING:** Clearing the cache will remove ALL locally cached designs, not just ITAR-controlled ones. Ensure all work is exported before clearing.

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
    "machine": "WORKSTATION-01"
}
```

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
| CRASH_RECOVERY | WARNING | Session restored after crash |
| ADDIN_STOPPING | WARNING | Add-in stopping with active session |

---

## Limitations

1. **Not a complete ITAR solution** — AirGap cannot guarantee zero data leakage from Fusion 360's internal processes.
2. **Local cache persistence** — Fusion's cache may retain design data even after documents are closed. Manual cache clearing is required.
3. **14-day license limit** — Fusion requires periodic internet access for licensing. This creates a window where data could sync if cache is not cleared.
4. **No file-level ITAR tagging** — AirGap treats ALL documents during a session as ITAR-controlled. There is no per-file classification.
5. **Application telemetry** — Fusion may send usage telemetry even in offline mode (though design data is not included).
