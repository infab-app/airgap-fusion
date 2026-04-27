import datetime
import traceback

import adsk.core

from commands.start_session import get_enforcer, get_interceptor
from lib.audit_logger import AuditLogger
from lib.persistence import SessionPersistence
from lib.session_manager import SessionManager, SessionState, is_default_document
from lib.ui_components import update_button_visibility

_handlers = []


def _get_open_tracked_doc_names(app, session):
    result = []
    for doc_name in session.substantive_tracked_documents():
        for i in range(app.documents.count):
            doc = app.documents.item(i)
            if doc.name == doc_name:
                result.append(doc_name)
                break
    return result


def _format_session_duration(start_iso):
    if not start_iso:
        return ""
    try:
        start = datetime.datetime.fromisoformat(start_iso)
        delta = datetime.datetime.now() - start
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f" Duration: {hours}h {minutes}m {seconds}s."
    except (ValueError, TypeError):
        return ""


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
                    f"exported locally. Ending the session without exporting may "
                    f"result in data loss.</b>",
                    3,
                    True,
                )

            app = adsk.core.Application.get()
            open_doc_names = _get_open_tracked_doc_names(app, session)

            if open_doc_names:
                inputs.addTextBoxCommandInput(
                    "openDocsWarning",
                    "WARNING",
                    f'<b style="color:red">{len(open_doc_names)} tracked document(s) '
                    f"are still open. This is expected in the Manufacture workspace. "
                    f"Ensure all work has been exported before proceeding.</b>",
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

            from lib.settings import Settings

            if Settings.instance().auto_clear_cache:
                inputs.addTextBoxCommandInput(
                    "autoClearInfo",
                    "",
                    "AirGap will attempt to automatically clear Fusion's local cache "
                    "after performing a final autosave. Some files may not be "
                    "deletable while Fusion is running.",
                    2,
                    True,
                )

            execute_handler = StopSessionExecuteHandler()
            cmd.execute.add(execute_handler)
            _handlers.append(execute_handler)

            validate_handler = StopSessionValidateHandler()
            cmd.validateInputs.add(validate_handler)
            _handlers.append(validate_handler)

        except Exception:
            try:
                AuditLogger.instance().log("INTERNAL_ERROR", traceback.format_exc(), "ERROR")
            except Exception:
                pass
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                "An unexpected error occurred.\nCheck the audit log for details.",
                "AirGap - Error",
            )


class StopSessionValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            inputs = args.inputs
            confirm_export = inputs.itemById("confirmExport")
            confirm_cache = inputs.itemById("confirmCache")
            args.areInputsValid = confirm_export.value and confirm_cache.value
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

            from lib.settings import Settings

            auto_clear = Settings.instance().auto_clear_cache
            clear_result = None

            if auto_clear:
                try:
                    from lib.autosave_manager import AutosaveManager

                    autosave_mgr = AutosaveManager.instance()
                    if autosave_mgr.is_active:
                        logger.log(
                            "CACHE_CLEAR_AUTOSAVE",
                            "Performing final autosave before cache clear",
                        )
                        autosave_mgr.perform_autosave()
                except Exception:
                    logger.log(
                        "CACHE_CLEAR_AUTOSAVE_FAILED",
                        f"Final autosave before cache clear failed: {traceback.format_exc()}",
                        "WARNING",
                    )

                from pathlib import Path

                from lib.export_manager import LocalExportManager

                for i in range(app.documents.count):
                    try:
                        doc = app.documents.item(i)
                        if not doc or is_default_document(doc.name):
                            continue
                        doc_name = doc.name
                        if doc_name not in session.tracked_documents:
                            continue
                        if doc_name in session.exported_documents:
                            continue
                        doc.activate()
                        safe = "".join(
                            c if c.isalnum() or c in "-_ " else "_" for c in doc_name
                        )
                        export_dir = Path(session.export_directory) / safe
                        export_dir.mkdir(parents=True, exist_ok=True)
                        has_xrefs = LocalExportManager.has_external_references()
                        ext = ".f3z" if has_xrefs else ".f3d"
                        filepath = str(export_dir / f"{safe}{ext}")
                        ok = LocalExportManager.export_fusion_archive(filepath)
                        if ok:
                            session.mark_exported(doc_name)
                            logger.log(
                                "CACHE_CLEAR_EXPORT",
                                f"Final export before cache clear: {filepath}",
                            )
                        else:
                            logger.log(
                                "CACHE_CLEAR_EXPORT_FAILED",
                                f"Final export failed for {doc_name}",
                                "WARNING",
                            )
                    except Exception:
                        logger.log(
                            "CACHE_CLEAR_EXPORT_FAILED",
                            f"Final export before cache clear failed for document: "
                            f"{traceback.format_exc()}",
                            "WARNING",
                        )

            if not session.transition_to(SessionState.DEACTIVATING):
                ui.messageBox("Cannot stop session: invalid state transition.", "AirGap - Error")
                return

            substantive_unexported = session.substantive_unexported_documents()
            if substantive_unexported:
                logger.log(
                    "SESSION_END_WITH_UNEXPORTED",
                    f"Session ended with unexported docs: {sorted(substantive_unexported)}",
                    "WARNING",
                )

            open_doc_names = _get_open_tracked_doc_names(app, session)
            if open_doc_names:
                logger.log(
                    "SESSION_END_WITH_OPEN_DOCS",
                    f"Session ended with open docs: {sorted(open_doc_names)}",
                    "WARNING",
                )

            duration_str = _format_session_duration(session.session_start_time)

            if substantive_unexported or open_doc_names:
                logger.log(
                    "SESSION_END",
                    f"AirGap session ended with warnings (user acknowledged).{duration_str}",
                )
            else:
                logger.log("SESSION_END", f"AirGap session ended cleanly.{duration_str}")

            if auto_clear:
                try:
                    from lib.cache_clearer import clear_fusion_cache

                    logger.log("CACHE_CLEAR_START", "Automatic cache clear initiated")
                    clear_result = clear_fusion_cache()
                    detail = clear_result.summary()
                    if clear_result.errors:
                        detail += f" | Errors: {clear_result.errors}"
                    logger.log(
                        "CACHE_CLEAR_COMPLETE",
                        detail,
                        "WARNING" if clear_result.files_failed > 0 else "INFO",
                    )
                except Exception:
                    logger.log(
                        "CACHE_CLEAR_ERROR",
                        f"Cache clear failed: {traceback.format_exc()}",
                        "ERROR",
                    )

            try:
                from lib.autosave_manager import AutosaveManager

                AutosaveManager.instance().deactivate()
            except Exception:
                pass

            get_enforcer().deactivate()
            get_interceptor().deactivate()

            session.transition_to(SessionState.UNPROTECTED)
            session.reset()
            SessionPersistence.clear_state()
            logger.end_session_log()

            update_button_visibility(SessionState.UNPROTECTED)

            cache_msg = ""
            if auto_clear and clear_result is not None:
                if clear_result.success:
                    cache_msg = (
                        f"\n\nCache cleared successfully. "
                        f"{clear_result.files_deleted} items removed."
                    )
                elif clear_result.partial or clear_result.files_failed > 0:
                    failed_f3ds = []
                    for err in clear_result.errors:
                        path_part = err.split(":")[0].strip()
                        if path_part.endswith(".f3d"):
                            name = Path(path_part).name
                            display = name.rsplit(".", 2)[0] if "." in name else name
                            if display not in failed_f3ds:
                                failed_f3ds.append(display)
                    cache_msg = (
                        f"\n\nCache partially cleared: {clear_result.files_deleted} items "
                        f"removed, {clear_result.files_failed} items could not be deleted "
                        f"(likely locked by Fusion)."
                    )
                    if failed_f3ds:
                        cache_msg += (
                            f"\n\nCached designs that could not be removed:"
                            f"\n- " + "\n- ".join(failed_f3ds)
                        )
                    cache_msg += (
                        "\n\nConsider clearing manually after closing Fusion."
                    )
                else:
                    cache_msg = (
                        "\n\nCache clear failed. Please clear the cache manually "
                        "before going online. Refer to the compliance guide."
                    )
            elif auto_clear:
                cache_msg = (
                    "\n\nCache clear encountered an error. Please clear the cache "
                    "manually before going online. Refer to the compliance guide."
                )

            ui.messageBox(
                "AIRGAP SESSION ENDED\n\n"
                "Offline enforcement and save blocking have been deactivated.\n\n"
                "IMPORTANT: Fusion is still in offline mode. You must "
                "manually go online when you are confident no export-controlled data "
                "remains in Fusion's local cache.\n\n"
                "Refer to the compliance guide for cache clearing "
                f"procedures.{cache_msg}",
                "AirGap - Session Ended",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                adsk.core.MessageBoxIconTypes.InformationIconType,
            )
        except Exception:
            try:
                AuditLogger.instance().log("INTERNAL_ERROR", traceback.format_exc(), "ERROR")
            except Exception:
                pass
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                "An unexpected error occurred while stopping session.\nCheck the audit log for details.",
                "AirGap - Error",
            )
