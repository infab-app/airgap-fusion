import os
import sys
from pathlib import Path

ADDIN_NAME = "AirGap"
COMPANY_NAME = "Infab"
VERSION = "1.0.6"

ADDIN_DIR = Path(os.path.dirname(os.path.realpath(__file__)))

# Command IDs
CMD_START_SESSION = "airgap_start_session"
CMD_STOP_SESSION = "airgap_stop_session"
CMD_EXPORT_LOCAL = "airgap_export_local"
CMD_VIEW_LOG = "airgap_view_log"
CMD_SETTINGS = "airgap_settings"
CMD_CHECK_UPDATE = "airgap_check_update"

# Toolbar IDs
TOOLBAR_TAB_ID = "AirGapTab"
TOOLBAR_PANEL_ID = "AirGapPanel"

# Custom event for offline polling fallback
CUSTOM_EVENT_OFFLINE_CHECK = "AirGap_OfflineCheck"

# Polling interval for offline mode verification (seconds)
OFFLINE_CHECK_INTERVAL = 5

# Auto-start readiness timing
AUTO_START_READY_TIMEOUT = 60
AUTO_START_READY_POLL = 2
AUTO_START_POST_READY_DELAY = 3

# Allowed export formats
ALLOWED_EXPORT_FORMATS = ["f3d", "f3z", "step", "stl", "igs", "sat"]

# Platform-dependent paths
if sys.platform == "win32":
    _BASE_DIR = Path(os.environ.get("APPDATA", Path.home())) / ".airgap"
else:
    _BASE_DIR = Path.home() / ".airgap"

DEFAULT_EXPORT_DIR = Path.home() / "AirGap_Exports"
AUDIT_LOG_DIR = _BASE_DIR / "logs"
SESSION_STATE_FILE = _BASE_DIR / "session_state.json"
SETTINGS_FILE = _BASE_DIR / "settings.json"

# Update system
CUSTOM_EVENT_UPDATE_CHECK = "AirGap_UpdateCheck"
GITHUB_OWNER = "infab-app"
GITHUB_REPO = "airgap-fusion"
GITHUB_API_BASE = "https://api.github.com"
UPDATE_CHECK_TIMEOUT = 15
UPDATE_STAGING_DIR = _BASE_DIR / "update_staging"
UPDATE_PENDING_FILE = _BASE_DIR / "update_pending.json"
UPDATE_BACKUP_DIR = _BASE_DIR / "update_backup"

# Icon resource paths (relative to ADDIN_DIR)
ICON_AIRGAP_ON = str(ADDIN_DIR / "resources" / "airgap_on")
ICON_AIRGAP_OFF = str(ADDIN_DIR / "resources" / "airgap_off")
ICON_EXPORT = str(ADDIN_DIR / "resources" / "export")

# Workspaces to add toolbar to
TARGET_WORKSPACES = ["FusionSolidEnvironment", "CAMEnvironment"]
