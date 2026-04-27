import os
import sys
import threading
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
        target = dest / item.name
        if item.is_dir():
            if overwrite and target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
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

        staging_path = Path(pending["staging_path"])
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

from commands.start_session import get_enforcer, get_interceptor
from lib import ui_components
from lib.audit_logger import AuditLogger
from lib.persistence import SessionPersistence
from lib.session_manager import SessionManager, SessionState
from lib.settings import Settings

_app = None
_ui = None
_auto_start_event = None
_auto_start_handlers = []
_crash_recovery_event = None
_crash_recovery_handlers = []
_update_check_event = None
_update_check_handlers = []

CUSTOM_EVENT_AUTO_START = "AirGap_AutoStart"
CUSTOM_EVENT_CRASH_RECOVERY = "AirGap_CrashRecoveryComplete"
CUSTOM_EVENT_UPDATE_CHECK = "AirGap_UpdateCheck"


def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        if _update_applied:
            import config as cfg

            _ui.messageBox(
                f"AirGap has been updated to version {cfg.VERSION}.\n\n"
                "See the release notes on GitHub for details.",
                "AirGap - Updated",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                adsk.core.MessageBoxIconTypes.InformationIconType,
            )

        _settings = Settings.instance()
        if _settings.log_directory:
            AuditLogger.instance().set_log_dir(_settings.log_directory)

        restored = _handle_crash_recovery(_app, _ui)

        ui_components.create_ui(_app)

        if restored:
            ui_components.update_button_visibility(SessionState.RECOVERING)
            _schedule_crash_recovery_completion(_app)
        else:
            _schedule_auto_start(_app)
            _schedule_update_check(_app)

    except Exception:
        if _ui:
            _ui.messageBox(f"AirGap failed to start:\n{traceback.format_exc()}")


def stop(context):
    global _auto_start_event, _crash_recovery_event, _update_check_event
    try:
        session = SessionManager.instance()
        if session.is_protected or session.state == SessionState.RECOVERING:
            SessionPersistence.save_state(session)
            AuditLogger.instance().log(
                "ADDIN_STOPPING",
                "AirGap add-in stopping while session active; state persisted",
                "WARNING",
            )

        enforcer = get_enforcer()
        if enforcer.is_active:
            enforcer.deactivate()

        get_interceptor().deactivate()

        if _app:
            for event_id in (
                CUSTOM_EVENT_AUTO_START,
                CUSTOM_EVENT_CRASH_RECOVERY,
                CUSTOM_EVENT_UPDATE_CHECK,
            ):
                try:
                    _app.unregisterCustomEvent(event_id)
                except Exception:
                    pass
            ui_components.destroy_ui(_app)

        _auto_start_handlers.clear()
        _auto_start_event = None
        _crash_recovery_handlers.clear()
        _crash_recovery_event = None
        _update_check_handlers.clear()
        _update_check_event = None

    except Exception:
        if _ui:
            _ui.messageBox(f"AirGap error during shutdown:\n{traceback.format_exc()}")


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _handle_crash_recovery(app: adsk.core.Application, ui: adsk.core.UserInterface) -> bool:
    saved_state = SessionPersistence.load_state()
    if not saved_state:
        return False
    if saved_state.get("state") not in (
        SessionState.PROTECTED.value,
        SessionState.ACTIVATING.value,
        SessionState.RECOVERING.value,
    ):
        SessionPersistence.clear_state()
        return False

    saved_pid = saved_state.get("pid")
    if saved_pid is not None and _is_pid_alive(saved_pid):
        SessionPersistence.clear_state()
        return False

    logger = AuditLogger.instance()
    logger.log(
        "CRASH_RECOVERY",
        f"Detected unclean shutdown. Previous state: {saved_state.get('state')}",
        "WARNING",
    )

    app.isOffLine = True

    tracked_count = len(saved_state.get("tracked_documents", []))
    exported_count = len(saved_state.get("exported_documents", []))

    result = ui.messageBox(
        "AirGap detected an unclean shutdown while an AirGap session "
        "was active.\n\n"
        f"Previous session had {tracked_count} tracked document(s), "
        f"{exported_count} exported.\n\n"
        "Fusion has been placed in offline mode as a precaution.\n\n"
        "Would you like to restore the AirGap session?",
        "AirGap - Crash Recovery",
        adsk.core.MessageBoxButtonTypes.YesNoButtonType,
        adsk.core.MessageBoxIconTypes.WarningIconType,
    )

    if result == adsk.core.DialogResults.DialogYes:
        session = SessionManager.instance()
        SessionPersistence.restore_session(session, saved_state)

        session_id = saved_state.get("session_id", "recovered")
        logger.start_session_log(f"{session_id}_recovered")
        logger.log(
            "CRASH_RECOVERY",
            "Session restored by user; offline enforcement deferred until Fusion is ready",
        )
        return True

    else:
        SessionPersistence.clear_state()
        logger.log("CRASH_RECOVERY", "User declined session restore")
        ui.messageBox(
            "Session not restored. AirGap will try to enable offline mode "
            "as a precaution, but this is not enforced; Fusion may enter "
            "prevent offline mode from being enabled.\n\n"
            "If offline, you may go online when you are confident "
            "no export-controlled data is present.",
            "AirGap",
            adsk.core.MessageBoxButtonTypes.OKButtonType,
            adsk.core.MessageBoxIconTypes.InformationIconType,
        )
        return False


def _schedule_auto_start(app: adsk.core.Application):
    global _auto_start_event

    session = SessionManager.instance()
    if session.is_protected:
        return

    settings = Settings.reload()
    if not settings.auto_offline_on_startup:
        return

    _auto_start_event = app.registerCustomEvent(CUSTOM_EVENT_AUTO_START)
    handler = _AutoStartHandler()
    _auto_start_event.add(handler)
    _auto_start_handlers.append(handler)

    thread = threading.Thread(target=_fire_event_after_ready, args=(app, CUSTOM_EVENT_AUTO_START))
    thread.daemon = True
    thread.start()


def _wait_until_ready(app: adsk.core.Application) -> bool:
    import time

    import config as cfg

    deadline = time.monotonic() + cfg.AUTO_START_READY_TIMEOUT
    while time.monotonic() < deadline:
        try:
            if hasattr(app, "isStartupComplete") and app.isStartupComplete:
                return True
            if app.activeViewport is not None:
                return True
        except Exception:
            pass
        time.sleep(cfg.AUTO_START_READY_POLL)
    return False


def _fire_event_after_ready(app: adsk.core.Application, event_id: str):
    import time

    import config as cfg

    ready = _wait_until_ready(app)

    if not ready:
        try:
            AuditLogger.instance().log(
                "STARTUP_WARN",
                f"Fusion readiness not confirmed after {cfg.AUTO_START_READY_TIMEOUT}s; proceeding anyway",
                "WARNING",
            )
        except Exception:
            pass

    time.sleep(cfg.AUTO_START_POST_READY_DELAY)

    try:
        app.fireCustomEvent(event_id, "")
    except Exception:
        pass


def _schedule_crash_recovery_completion(app: adsk.core.Application):
    global _crash_recovery_event

    _crash_recovery_event = app.registerCustomEvent(CUSTOM_EVENT_CRASH_RECOVERY)
    handler = _CrashRecoveryCompleteHandler()
    _crash_recovery_event.add(handler)
    _crash_recovery_handlers.append(handler)

    thread = threading.Thread(
        target=_fire_event_after_ready, args=(app, CUSTOM_EVENT_CRASH_RECOVERY)
    )
    thread.daemon = True
    thread.start()


class _CrashRecoveryCompleteHandler(adsk.core.CustomEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            session = SessionManager.instance()
            logger = AuditLogger.instance()

            if session.state != SessionState.RECOVERING:
                return

            enforcer = get_enforcer()
            if enforcer.is_active:
                return

            if not enforcer.activate(app, retries=5):
                logger.log(
                    "SESSION_ABORT",
                    "Crash recovery failed: could not enable offline mode",
                    "CRITICAL",
                )
                session.transition_to(SessionState.UNPROTECTED)
                session.reset()
                SessionPersistence.clear_state()
                logger.end_session_log()
                ui_components.update_button_visibility(SessionState.UNPROTECTED)
                ui.messageBox(
                    "AIRGAP CRASH RECOVERY FAILED\n\n"
                    "Could not enable offline mode. The previous session "
                    "has NOT been restored.\n\n"
                    "Please start a new AirGap session manually.",
                    "AirGap - Error",
                    adsk.core.MessageBoxButtonTypes.OKButtonType,
                    adsk.core.MessageBoxIconTypes.CriticalIconType,
                )
                return

            get_interceptor().activate(app)
            session.transition_to(SessionState.PROTECTED)
            ui_components.update_button_visibility(SessionState.PROTECTED)
            SessionPersistence.save_state(session)
            logger.log("CRASH_RECOVERY", "Offline enforcement activated after Fusion startup")
        except Exception:
            try:
                app = adsk.core.Application.get()
                app.userInterface.messageBox(
                    f"AirGap crash recovery error:\n{traceback.format_exc()}",
                    "AirGap - Error",
                )
            except Exception:
                pass


def _activate_session(app, session, session_id, export_dir, start_time):
    """Activate an AirGap session. Returns (True, None) on success or (False, error_msg)."""
    if not session.transition_to(SessionState.ACTIVATING):
        return False, "AirGap auto-start failed: invalid session state."

    logger = AuditLogger.instance()
    session.start_session(session_id, export_dir, start_time)
    logger.start_session_log(session_id)
    logger.log("SESSION_AUTO_START", f"AirGap session auto-started. Export dir: {export_dir}")

    enforcer = get_enforcer()
    if not enforcer.activate(app, retries=5):
        logger.log("SESSION_ABORT", "Auto-start failed: could not enable offline mode", "CRITICAL")
        session.transition_to(SessionState.UNPROTECTED)
        session.reset()
        logger.end_session_log()
        return False, (
            "AirGap auto-start failed: could not enable offline mode.\n\n"
            "Please start the AirGap session manually."
        )

    get_interceptor().activate(app)

    if not session.transition_to(SessionState.PROTECTED):
        enforcer.deactivate()
        get_interceptor().deactivate()
        session.reset()
        logger.end_session_log()
        return False, None

    SessionPersistence.save_state(session)
    ui_components.update_button_visibility(SessionState.PROTECTED)
    return True, None


class _AutoStartHandler(adsk.core.CustomEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            session = SessionManager.instance()

            if session.is_protected:
                return

            settings = Settings.instance()

            app.isOffLine = True
            AuditLogger.instance().log(
                "AUTO_OFFLINE", "Offline mode enforced on startup per settings"
            )

            if not settings.auto_start_session:
                return

            import datetime
            import uuid
            from pathlib import Path

            session_id = uuid.uuid4().hex[:12]
            start_time = datetime.datetime.now().isoformat()
            export_dir = settings.default_export_directory

            Path(export_dir).mkdir(parents=True, exist_ok=True)

            success, error_msg = _activate_session(app, session, session_id, export_dir, start_time)
            if not success:
                if error_msg:
                    ui.messageBox(
                        error_msg,
                        "AirGap - Error",
                        adsk.core.MessageBoxButtonTypes.OKButtonType,
                        adsk.core.MessageBoxIconTypes.CriticalIconType,
                    )
                return

            ui.messageBox(
                "AIRGAP SESSION AUTO-STARTED\n\n"
                f"Session ID: {session_id}\n"
                f"Export Directory: {export_dir}\n\n"
                "Fusion is offline and cloud saves are blocked.\n\n"
                "This session was started automatically per your AirGap settings.",
                "AirGap - Auto Session",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                adsk.core.MessageBoxIconTypes.InformationIconType,
            )
        except Exception:
            try:
                app = adsk.core.Application.get()
                app.userInterface.messageBox(
                    f"AirGap auto-start error:\n{traceback.format_exc()}", "AirGap - Error"
                )
            except Exception:
                pass


def _schedule_update_check(app: adsk.core.Application):
    global _update_check_event

    if _update_applied:
        return

    settings = Settings.reload()
    if not settings.auto_check_updates:
        return

    session = SessionManager.instance()
    if session.is_protected:
        return

    _update_check_event = app.registerCustomEvent(CUSTOM_EVENT_UPDATE_CHECK)
    handler = _UpdateCheckHandler()
    _update_check_event.add(handler)
    _update_check_handlers.append(handler)

    thread = threading.Thread(target=_check_update_after_ready, args=(app, settings.update_channel))
    thread.daemon = True
    thread.start()


def _check_update_after_ready(app: adsk.core.Application, channel: str):
    import json
    import time

    import config as cfg

    _wait_until_ready(app)
    time.sleep(cfg.AUTO_START_POST_READY_DELAY)

    try:
        from lib.updater import check_for_update

        result = check_for_update(channel)
        if result.update_available and not result.error:
            payload = json.dumps(
                {"version": result.latest_version, "prerelease": result.is_prerelease}
            )
            app.fireCustomEvent(CUSTOM_EVENT_UPDATE_CHECK, payload)
    except Exception:
        pass


class _UpdateCheckHandler(adsk.core.CustomEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            import json

            app = adsk.core.Application.get()
            ui = app.userInterface

            payload = json.loads(args.additionalInfo) if args.additionalInfo else {}
            version = payload.get("version", "")
            prerelease = payload.get("prerelease", False)

            label = f"{version} (beta)" if prerelease else version

            ui.messageBox(
                f"A new version of AirGap is available: {label}\n\n"
                'Use "Check for Updates" in the AirGap toolbar to download it.',
                "AirGap - Update Available",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                adsk.core.MessageBoxIconTypes.InformationIconType,
            )
        except Exception:
            pass
