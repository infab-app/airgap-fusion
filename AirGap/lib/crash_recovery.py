import os
import threading
import traceback

import adsk.core

import config
from lib import ui_components
from lib.audit_logger import AuditLogger
from lib.persistence import SessionPersistence
from lib.session_manager import SessionManager, SessionState
from lib.startup_common import fire_event_after_ready

_crash_recovery_event = None
_crash_recovery_handlers = []


def handle_crash_recovery(app, ui):
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


def schedule_crash_recovery_completion(app):
    global _crash_recovery_event

    _crash_recovery_event = app.registerCustomEvent(config.CUSTOM_EVENT_CRASH_RECOVERY)
    handler = _CrashRecoveryCompleteHandler()
    _crash_recovery_event.add(handler)
    _crash_recovery_handlers.append(handler)

    thread = threading.Thread(
        target=fire_event_after_ready, args=(app, config.CUSTOM_EVENT_CRASH_RECOVERY)
    )
    thread.daemon = True
    thread.start()


def cleanup():
    global _crash_recovery_event
    _crash_recovery_handlers.clear()
    _crash_recovery_event = None


def _is_pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class _CrashRecoveryCompleteHandler(adsk.core.CustomEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            from commands.start_session import get_enforcer, get_interceptor

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

            try:
                from lib.autosave_manager import activate_if_enabled

                activate_if_enabled(app, session.session_id, session.export_directory)
            except Exception:
                pass
        except Exception:
            try:
                app = adsk.core.Application.get()
                app.userInterface.messageBox(
                    f"AirGap crash recovery error:\n{traceback.format_exc()}",
                    "AirGap - Error",
                )
            except Exception:
                pass
