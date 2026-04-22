import traceback

import adsk.core

from AirGap.commands.start_session import get_enforcer, get_interceptor
from AirGap.lib.audit_logger import AuditLogger
from AirGap.lib.persistence import SessionPersistence
from AirGap.lib.session_manager import SessionManager, SessionState
from AirGap.lib.ui_components import update_button_visibility

_handlers = []


class StopSessionCommand(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            inputs = cmd.commandInputs
            session = SessionManager.instance()

            tracked = session.tracked_documents
            exported = session.exported_documents
            unexported = session.substantive_unexported_documents()

            status_lines = []
            for doc_name in sorted(tracked):
                mark = "[EXPORTED]" if doc_name in exported else "[NOT EXPORTED]"
                status_lines.append(f"  {mark} {doc_name}")

            if not status_lines:
                status_text = "  (No documents were tracked during this session)"
            else:
                status_text = "\n".join(status_lines)

            inputs.addTextBoxCommandInput(
                "docStatus", "Tracked Documents", status_text, len(status_lines) + 2, True
            )

            if unexported:
                inputs.addTextBoxCommandInput(
                    "warning",
                    "WARNING",
                    f'<b style="color:red">{len(unexported)} document(s) have NOT been '
                    f"exported locally. You must export all documents before ending "
                    f"the AirGap session.</b>",
                    3,
                    True,
                )

            inputs.addBoolValueInput(
                "confirmExport",
                "I confirm all export-controlled data has been exported and no protected documents remain open",
                True,
                "",
                False,
            )

            inputs.addBoolValueInput(
                "confirmCache",
                "I understand I should clear Fusion's local cache per organizational policy",
                True,
                "",
                False,
            )

            execute_handler = StopSessionExecuteHandler()
            cmd.execute.add(execute_handler)
            _handlers.append(execute_handler)

            validate_handler = StopSessionValidateHandler()
            cmd.validateInputs.add(validate_handler)
            _handlers.append(validate_handler)

        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                f"Error creating stop session dialog:\n{traceback.format_exc()}"
            )


class StopSessionValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            inputs = args.inputs
            session = SessionManager.instance()

            confirm_export = inputs.itemById("confirmExport")
            confirm_cache = inputs.itemById("confirmCache")

            is_valid = True

            if not confirm_export.value:
                is_valid = False
            if not confirm_cache.value:
                is_valid = False

            if session.substantive_unexported_documents():
                is_valid = False

            app = adsk.core.Application.get()
            for doc_name in session.substantive_tracked_documents():
                for i in range(app.documents.count):
                    doc = app.documents.item(i)
                    if doc.name == doc_name:
                        is_valid = False
                        break

            args.areInputsValid = is_valid
        except Exception:
            args.areInputsValid = False


class StopSessionExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            session = SessionManager.instance()
            logger = AuditLogger.instance()

            if not session.transition_to(SessionState.DEACTIVATING):
                ui.messageBox("Cannot stop session: invalid state transition.", "AirGap - Error")
                return

            substantive_unexported = session.substantive_unexported_documents()
            if substantive_unexported:
                logger.log(
                    "DEACTIVATION_BLOCKED",
                    f"Attempted deactivation with unexported docs: {substantive_unexported}",
                    "WARNING",
                )
                session.transition_to(SessionState.PROTECTED)
                ui.messageBox(
                    "Cannot end session: unexported documents remain.\n\n"
                    "Please export all tracked documents first.",
                    "AirGap - Session Active",
                    adsk.core.MessageBoxButtonTypes.OKButtonType,
                    adsk.core.MessageBoxIconTypes.WarningIconType,
                )
                return

            logger.log("SESSION_END", "AirGap session ended cleanly")

            get_enforcer().deactivate()
            get_interceptor().deactivate()

            session.transition_to(SessionState.UNPROTECTED)
            session.reset()
            SessionPersistence.clear_state()
            logger.end_session_log()

            update_button_visibility(SessionState.UNPROTECTED)

            ui.messageBox(
                "AIRGAP SESSION ENDED\n\n"
                "Offline enforcement and save blocking have been deactivated.\n\n"
                "IMPORTANT: Fusion is still in offline mode. You must "
                "manually go online when you are confident no export-controlled data "
                "remains in Fusion's local cache.\n\n"
                "Refer to the compliance guide for cache clearing "
                "procedures.",
                "AirGap - Session Ended",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                adsk.core.MessageBoxIconTypes.InformationIconType,
            )
        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(f"Error stopping session:\n{traceback.format_exc()}")
