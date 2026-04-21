import os
import sys
import traceback

import adsk.core
import adsk.fusion
import adsk.cam

_addin_path = os.path.dirname(os.path.abspath(__file__))
if _addin_path not in sys.path:
    sys.path.insert(0, _addin_path)

from lib.session_manager import ITARSessionManager, SessionState
from lib.audit_logger import AuditLogger
from lib.persistence import SessionPersistence
from lib.settings import Settings
from lib import ui_components
from commands.start_session import get_enforcer, get_interceptor

_app = None
_ui = None


def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        _handle_crash_recovery(_app, _ui)

        ui_components.create_ui(_app)

        _apply_auto_start_settings(_app, _ui)

    except Exception:
        if _ui:
            _ui.messageBox(f'AirGap failed to start:\n{traceback.format_exc()}')


def stop(context):
    try:
        session = ITARSessionManager.instance()
        if session.is_protected:
            SessionPersistence.save_state(session)
            AuditLogger.instance().log(
                'ADDIN_STOPPING',
                'AirGap add-in stopping while session active; state persisted',
                'WARNING'
            )

        enforcer = get_enforcer()
        if enforcer.is_active:
            enforcer.deactivate()

        get_interceptor().deactivate()

        if _app:
            ui_components.destroy_ui(_app)

    except Exception:
        if _ui:
            _ui.messageBox(f'AirGap error during shutdown:\n{traceback.format_exc()}')


def _handle_crash_recovery(app: adsk.core.Application, ui: adsk.core.UserInterface):
    saved_state = SessionPersistence.load_state()
    if not saved_state:
        return
    if saved_state.get('state') not in ('PROTECTED', 'ACTIVATING'):
        SessionPersistence.clear_state()
        return

    logger = AuditLogger.instance()
    logger.log(
        'CRASH_RECOVERY',
        f'Detected unclean shutdown. Previous state: {saved_state.get("state")}',
        'WARNING'
    )

    app.isOffLine = True

    tracked_count = len(saved_state.get('tracked_documents', []))
    exported_count = len(saved_state.get('exported_documents', []))

    result = ui.messageBox(
        'AirGap detected an unclean shutdown while an ITAR session '
        'was active.\n\n'
        f'Previous session had {tracked_count} tracked document(s), '
        f'{exported_count} exported.\n\n'
        'Fusion has been placed in offline mode as a precaution.\n\n'
        'Would you like to restore the ITAR session?',
        'AirGap - Crash Recovery',
        adsk.core.MessageBoxButtonTypes.YesNoButtonType,
        adsk.core.MessageBoxIconTypes.WarningIconType
    )

    if result == adsk.core.DialogResults.DialogYes:
        session = ITARSessionManager.instance()
        SessionPersistence.restore_session(session, saved_state)

        enforcer = get_enforcer()
        enforcer.activate(app)
        get_interceptor().activate(app)

        session_id = saved_state.get('session_id', 'recovered')
        logger.start_session_log(f'{session_id}_recovered')
        logger.log('CRASH_RECOVERY', 'Session restored by user')

    else:
        SessionPersistence.clear_state()
        ui.messageBox(
            'Session not restored. Fusion remains offline.\n\n'
            'You may manually go online when you are confident '
            'no ITAR data is present.',
            'AirGap',
            adsk.core.MessageBoxButtonTypes.OKButtonType,
            adsk.core.MessageBoxIconTypes.InformationIconType
        )


def _apply_auto_start_settings(app: adsk.core.Application, ui: adsk.core.UserInterface):
    session = ITARSessionManager.instance()
    if session.is_protected:
        return

    settings = Settings.instance()

    if settings.auto_offline_on_startup:
        app.isOffLine = True
        AuditLogger.instance().log(
            'AUTO_OFFLINE',
            'Offline mode enforced on startup per settings'
        )

    if settings.auto_start_session and settings.auto_offline_on_startup:
        import datetime
        import uuid
        from pathlib import Path

        session_id = uuid.uuid4().hex[:12]
        start_time = datetime.datetime.now().isoformat()
        export_dir = settings.default_export_directory

        Path(export_dir).mkdir(parents=True, exist_ok=True)

        if not session.transition_to(SessionState.ACTIVATING):
            return

        logger = AuditLogger.instance()
        session.start_session(session_id, export_dir, start_time)
        logger.start_session_log(session_id)
        logger.log('SESSION_AUTO_START',
                    f'ITAR session auto-started. Export dir: {export_dir}')

        enforcer = get_enforcer()
        if not enforcer.activate(app):
            logger.log('SESSION_ABORT',
                        'Auto-start failed: could not enable offline mode',
                        'CRITICAL')
            session.transition_to(SessionState.UNPROTECTED)
            session.reset()
            logger.end_session_log()
            return

        get_interceptor().activate(app)

        if not session.transition_to(SessionState.PROTECTED):
            enforcer.deactivate()
            get_interceptor().deactivate()
            session.reset()
            logger.end_session_log()
            return

        SessionPersistence.save_state(session)
        ui_components.update_button_visibility(SessionState.PROTECTED)

        ui.messageBox(
            'ITAR SESSION AUTO-STARTED\n\n'
            f'Session ID: {session_id}\n'
            f'Export Directory: {export_dir}\n\n'
            'Fusion is offline and cloud saves are blocked.\n\n'
            'This session was started automatically per your AirGap settings.',
            'AirGap - Auto Session',
            adsk.core.MessageBoxButtonTypes.OKButtonType,
            adsk.core.MessageBoxIconTypes.InformationIconType
        )
