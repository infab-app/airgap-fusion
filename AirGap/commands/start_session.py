import datetime
import traceback
import uuid

import adsk.core

from lib.audit_logger import AuditLogger
from lib.offline_enforcer import OfflineEnforcer
from lib.persistence import SessionPersistence
from lib.save_interceptor import SaveInterceptor
from lib.session_manager import SessionManager, SessionState, is_default_document
from lib.settings import Settings
from lib.ui_components import update_button_visibility

_enforcer = OfflineEnforcer()
_interceptor = SaveInterceptor()
_handlers = []


def get_enforcer():
    return _enforcer


def get_interceptor():
    return _interceptor


class StartSessionCommand(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            inputs = cmd.commandInputs

            inputs.addStringValueInput(
                "exportDir", "Export Directory", Settings.instance().default_export_directory
            )

            inputs.addBoolValueInput("browseDir", "Browse...", False, "", False)

            inputs.addBoolValueInput(
                "confirmItar",
                "I understand all documents opened during "
                "this session will be treated as export-controlled",
                True,
                "",
                False,
            )

            execute_handler = StartSessionExecuteHandler()
            cmd.execute.add(execute_handler)
            _handlers.append(execute_handler)

            validate_handler = StartSessionValidateHandler()
            cmd.validateInputs.add(validate_handler)
            _handlers.append(validate_handler)

            input_changed_handler = StartSessionInputChangedHandler()
            cmd.inputChanged.add(input_changed_handler)
            _handlers.append(input_changed_handler)

        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                f"Error creating start session dialog:\n{traceback.format_exc()}"
            )


class StartSessionInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            changed_input = args.input
            if changed_input.id != "browseDir":
                return

            app = adsk.core.Application.get()
            ui = app.userInterface
            folder_dlg = ui.createFolderDialog()
            folder_dlg.title = "Select Export Directory"
            result = folder_dlg.showDialog()
            if result == adsk.core.DialogResults.DialogOK:
                inputs = args.inputs
                dir_input = inputs.itemById("exportDir")
                dir_input.value = folder_dlg.folder
        except Exception:
            pass


class StartSessionValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            inputs = args.inputs
            confirm_input = inputs.itemById("confirmItar")
            dir_input = inputs.itemById("exportDir")

            is_valid = True
            if not confirm_input.value:
                is_valid = False
            if not dir_input.value.strip():
                is_valid = False

            args.areInputsValid = is_valid
        except Exception:
            args.areInputsValid = False


class StartSessionExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            inputs = args.command.commandInputs
            export_dir = inputs.itemById("exportDir").value.strip()

            from pathlib import Path

            export_path = Path(export_dir)
            export_path.mkdir(parents=True, exist_ok=True)

            session = SessionManager.instance()
            logger = AuditLogger.instance()

            if not session.transition_to(SessionState.ACTIVATING):
                ui.messageBox(
                    "Cannot start AirGap session: invalid state transition.", "AirGap - Error"
                )
                return

            session_id = uuid.uuid4().hex[:12]
            start_time = datetime.datetime.now().isoformat()
            session.start_session(session_id, export_dir, start_time)
            logger.start_session_log(session_id)
            logger.log("SESSION_START", f"AirGap session initiated. Export dir: {export_dir}")

            if not _enforcer.activate(app):
                logger.log("SESSION_ABORT", "Could not enable offline mode", "CRITICAL")
                session.transition_to(SessionState.UNPROTECTED)
                session.reset()
                logger.end_session_log()
                ui.messageBox(
                    "FAILED TO START AIRGAP SESSION\n\n"
                    "Could not enable offline mode. Fusion may not support "
                    "programmatic offline control in this version.\n\n"
                    "Please manually enable offline mode and try again.",
                    "AirGap - Error",
                    adsk.core.MessageBoxButtonTypes.OKButtonType,
                    adsk.core.MessageBoxIconTypes.CriticalIconType,
                )
                return

            _interceptor.activate(app)

            if not session.transition_to(SessionState.PROTECTED):
                _enforcer.deactivate()
                _interceptor.deactivate()
                session.reset()
                logger.end_session_log()
                ui.messageBox("Failed to transition to PROTECTED state.", "AirGap - Error")
                return

            SessionPersistence.save_state(session)
            update_button_visibility(SessionState.PROTECTED)

            settings = Settings.instance()
            autosave_info = ""
            if settings.autosave_enabled:
                from lib.autosave_manager import AutosaveManager

                autosave_dir = settings.autosave_directory or export_dir
                AutosaveManager.instance().activate(
                    app,
                    session_id,
                    autosave_dir,
                    settings.autosave_interval_minutes * 60,
                    settings.autosave_max_versions,
                )
                autosave_info = f"- Autosave: every {settings.autosave_interval_minutes}m\n"

            if app.activeDocument:
                doc_name = app.activeDocument.name
                if not is_default_document(doc_name):
                    session.track_document(doc_name)
                    logger.log("DOC_OPENED", f"Active document tracked: {doc_name}")

            ui.messageBox(
                "AIRGAP SESSION ACTIVE\n\n"
                f"Session ID: {session_id}\n"
                f"Export Directory: {export_dir}\n\n"
                "- Fusion is now OFFLINE\n"
                "- Cloud saves are BLOCKED\n"
                '- Use "Export Locally" to save files\n'
                f"{autosave_info}\n"
                "All documents opened during this session will be tracked.",
                "AirGap - Session Started",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                adsk.core.MessageBoxIconTypes.InformationIconType,
            )
        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(f"Error starting session:\n{traceback.format_exc()}")
