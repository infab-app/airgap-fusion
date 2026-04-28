import os
import sys
import traceback

import adsk.cam
import adsk.core
import adsk.fusion

_addin_path = os.path.dirname(os.path.abspath(__file__))
if _addin_path not in sys.path:
    sys.path.insert(0, _addin_path)


def _copy_dir_contents(src, dest, *, overwrite=False, skip_dotfiles=False):
    import shutil

    for item in src.iterdir():
        if skip_dotfiles and item.name.startswith("."):
            continue
        if item.is_symlink():
            continue
        target = dest / item.name
        if item.is_dir():
            if overwrite and target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target, symlinks=False)
        else:
            shutil.copy2(item, target)


def _apply_pending_update():
    import json
    import shutil
    from pathlib import Path

    if sys.platform == "win32":
        base_dir = Path(os.environ.get("APPDATA", Path.home())) / ".airgap"
    else:
        base_dir = Path.home() / ".airgap"

    pending_file = base_dir / "update_pending.json"
    if not pending_file.exists():
        return False

    try:
        with open(pending_file, encoding="utf-8") as f:
            pending = json.load(f)

        from lib.integrity import is_envelope, unwrap_and_verify

        if is_envelope(pending):
            payload = unwrap_and_verify(pending)
            if payload is None:
                pending_file.unlink(missing_ok=True)
                return False
            pending = payload
        else:
            pending_file.unlink(missing_ok=True)
            return False

        staging_path = Path(pending["staging_path"])
        staging_base = base_dir / "update_staging"
        resolved_staging = staging_path.resolve()
        if not resolved_staging.is_relative_to(staging_base.resolve()):
            pending_file.unlink(missing_ok=True)
            return False
        if staging_path.is_symlink():
            pending_file.unlink(missing_ok=True)
            return False
        if not staging_path.exists():
            pending_file.unlink(missing_ok=True)
            return False

        addin_dir = Path(_addin_path)
        backup_dir = base_dir / "update_backup"

        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)

        _copy_dir_contents(addin_dir, backup_dir, skip_dotfiles=True)

        try:
            _copy_dir_contents(staging_path, addin_dir, overwrite=True)
        except Exception:
            _copy_dir_contents(backup_dir, addin_dir, overwrite=True)
            pending_file.unlink(missing_ok=True)
            return False

        shutil.rmtree(backup_dir, ignore_errors=True)
        staging_parent = staging_path.parent
        if staging_parent.name == "extracted":
            shutil.rmtree(staging_parent.parent, ignore_errors=True)
        else:
            shutil.rmtree(staging_parent, ignore_errors=True)
        pending_file.unlink(missing_ok=True)
        return True

    except Exception:
        try:
            pending_file.unlink(missing_ok=True)
        except Exception:
            pass
        return False


_update_applied = _apply_pending_update()

import config
from commands.start_session import get_enforcer, get_interceptor
from lib import ui_components
from lib.audit_logger import AuditLogger
from lib.auto_start import schedule_auto_start
from lib.crash_recovery import (
    cleanup as cleanup_crash_recovery,
)
from lib.crash_recovery import (
    handle_crash_recovery,
    schedule_crash_recovery_completion,
)
from lib.persistence import SessionPersistence
from lib.session_manager import SessionManager, SessionState
from lib.settings import Settings
from lib.update_check import cleanup as cleanup_update_check
from lib.update_check import schedule_update_check

_app = None
_ui = None


def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        if _update_applied:
            _ui.messageBox(
                f"AirGap has been updated to version {config.VERSION}.\n\n"
                "See the release notes on GitHub for details.",
                "AirGap - Updated",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                adsk.core.MessageBoxIconTypes.InformationIconType,
            )

        _settings = Settings.instance()
        if _settings.log_directory:
            AuditLogger.instance().set_log_dir(_settings.log_directory)

        if not _app.isOffLine:
            from lib.offline_state import OfflineState

            OfflineState.instance().record_online_observation()

        restored = handle_crash_recovery(_app, _ui)

        ui_components.create_ui(_app)

        if restored:
            ui_components.update_button_visibility(SessionState.RECOVERING)
            schedule_crash_recovery_completion(_app)
        else:
            schedule_auto_start(_app)
            schedule_update_check(_app, skip_if_just_updated=_update_applied)

    except Exception:
        if _ui:
            _ui.messageBox(f"AirGap failed to start:\n{traceback.format_exc()}")


def stop(context):
    try:
        session = SessionManager.instance()
        if session.is_protected or session.state == SessionState.RECOVERING:
            SessionPersistence.save_state(session)
            AuditLogger.instance().log(
                "ADDIN_STOPPING",
                "AirGap add-in stopping while session active; state persisted",
                "WARNING",
            )

        try:
            from lib.autosave_manager import AutosaveManager

            AutosaveManager.instance().deactivate()
        except Exception:
            pass

        try:
            from lib.timer_display import TimerDisplay

            TimerDisplay.instance().deactivate()
        except Exception:
            pass

        enforcer = get_enforcer()
        if enforcer.is_active:
            enforcer.deactivate()

        get_interceptor().deactivate()

        if _app:
            for event_id in (
                config.CUSTOM_EVENT_AUTO_START,
                config.CUSTOM_EVENT_CRASH_RECOVERY,
                config.CUSTOM_EVENT_UPDATE_CHECK,
                config.CUSTOM_EVENT_AUTOSAVE,
            ):
                try:
                    _app.unregisterCustomEvent(event_id)
                except Exception:
                    pass
            ui_components.destroy_ui(_app)

        from lib.auto_start import cleanup as cleanup_auto_start

        cleanup_auto_start()
        cleanup_crash_recovery()
        cleanup_update_check()

    except Exception:
        try:
            AuditLogger.instance().log("INTERNAL_ERROR", traceback.format_exc(), "ERROR")
        except Exception:
            pass
        if _ui:
            _ui.messageBox(
                "An unexpected error occurred during shutdown.\nCheck the audit log for details.",
                "AirGap - Error",
            )
