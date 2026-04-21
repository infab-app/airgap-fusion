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
