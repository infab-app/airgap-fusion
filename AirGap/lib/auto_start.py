import threading
import traceback

import adsk.core

import config
from lib import ui_components
from lib.audit_logger import AuditLogger
from lib.persistence import SessionPersistence
from lib.session_manager import SessionManager, SessionState
from lib.settings import Settings
from lib.startup_common import fire_event_after_ready

_auto_start_event = None
_auto_start_handlers = []


def schedule_auto_start(app):
    global _auto_start_event

    session = SessionManager.instance()
    if session.is_protected:
        return

    settings = Settings.reload()
    if not settings.auto_offline_on_startup:
        return

    _auto_start_event = app.registerCustomEvent(config.CUSTOM_EVENT_AUTO_START)
    handler = _AutoStartHandler()
    _auto_start_event.add(handler)
    _auto_start_handlers.append(handler)

    thread = threading.Thread(
        target=fire_event_after_ready, args=(app, config.CUSTOM_EVENT_AUTO_START)
    )
    thread.daemon = True
    thread.start()


def cleanup():
    global _auto_start_event
    _auto_start_handlers.clear()
    _auto_start_event = None


def _activate_session(app, session, session_id, export_dir, start_time):
    from commands.start_session import get_enforcer, get_interceptor

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

    try:
        from lib.timer_display import TimerDisplay

        TimerDisplay.instance().activate(app)
    except Exception:
        pass

    try:
        from lib.autosave_manager import activate_if_enabled

        activate_if_enabled(app, session_id, export_dir)
    except Exception:
        pass

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

            if not app.isOffLine:
                from lib.offline_state import OfflineState

                OfflineState.instance().record_online_observation()

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
                AuditLogger.instance().log("INTERNAL_ERROR", traceback.format_exc(), "ERROR")
            except Exception:
                pass
            try:
                app = adsk.core.Application.get()
                app.userInterface.messageBox(
                    "An unexpected error occurred during auto-start.\nCheck the audit log for details.",
                    "AirGap - Error",
                )
            except Exception:
                pass
