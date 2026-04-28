"""Save interceptor with handler hardening.

Fusion drops document event handlers on workspace context switches (e.g. Design
to Manufacture). A background monitor thread periodically verifies that handlers
are still registered and reattaches any that were silently removed.
"""

import json
import re
import threading
from pathlib import Path

import adsk.core

import config
from lib.audit_logger import AuditLogger
from lib.session_manager import SessionManager


def _try_local_export(doc_name, session):
    # Attempt auto-export on blocked save; returns (success, path).
    try:
        from lib.export_manager import LocalExportManager

        export_dir_root = session.export_directory
        if not export_dir_root:
            return False, ""

        clean_name = re.sub(r"( v\d+)+$", "", doc_name).strip() or doc_name
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in clean_name)
        export_dir = Path(export_dir_root) / safe
        export_dir.mkdir(parents=True, exist_ok=True)

        has_xrefs = LocalExportManager.has_external_references()
        ext = ".f3z" if has_xrefs else ".f3d"
        export_path = str(export_dir / f"{safe}{ext}")

        if LocalExportManager.export_fusion_archive(export_path):
            return True, export_path
    except Exception:
        pass
    return False, ""


def _show_save_blocked_message(doc_name, exported, export_path):
    app = adsk.core.Application.get()
    if exported:
        app.userInterface.messageBox(
            f"CLOUD SAVE BLOCKED\n\n"
            f"Document: {doc_name}\n\n"
            f"Cloud saves are blocked during AirGap sessions.\n"
            f"Your work has been exported locally to:\n{export_path}",
            "AirGap - Save Blocked",
            adsk.core.MessageBoxButtonTypes.OKButtonType,
            adsk.core.MessageBoxIconTypes.InformationIconType,
        )
    else:
        app.userInterface.messageBox(
            f"CLOUD SAVE BLOCKED\n\n"
            f"Document: {doc_name}\n\n"
            f"Cloud saves are blocked during AirGap sessions.\n"
            f'Use the AirGap "Export Locally" button to save '
            f"files to your local or NAS storage.",
            "AirGap - Save Blocked",
            adsk.core.MessageBoxButtonTypes.OKButtonType,
            adsk.core.MessageBoxIconTypes.CriticalIconType,
        )


class DocumentSavingHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            event_args = adsk.core.DocumentEventArgs.cast(args)
        except Exception:
            try:
                AuditLogger.instance().log(
                    "SAVE_BLOCK_ERROR", "Could not cast save event args", "CRITICAL"
                )
            except Exception:
                pass
            return

        if event_args is None:
            try:
                AuditLogger.instance().log(
                    "SAVE_BLOCK_ERROR", "Save event args cast returned None", "CRITICAL"
                )
            except Exception:
                pass
            return

        event_args.isSaveCanceled = True

        try:
            session = SessionManager.instance()
            if not session.is_protected:
                event_args.isSaveCanceled = False
                return

            doc_name = event_args.document.name if event_args.document else "Unknown"
            AuditLogger.instance().log(
                "SAVE_BLOCKED", f"Cloud save blocked for: {doc_name}", "WARNING"
            )

            exported, export_path = _try_local_export(doc_name, session)
            _show_save_blocked_message(doc_name, exported, export_path)
        except Exception:
            try:
                AuditLogger.instance().log(
                    "SAVE_BLOCK_ERROR",
                    "Save blocked but handler error during notification",
                    "ERROR",
                )
            except Exception:
                pass


class DocumentOpenedHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            event_args = adsk.core.DocumentEventArgs.cast(args)
            session = SessionManager.instance()
            if not session.is_protected:
                return
            if event_args.document:
                doc_name = event_args.document.name
                session.track_document(doc_name)
                AuditLogger.instance().log("DOC_OPENED", f"Document tracked: {doc_name}")
        except Exception:
            pass


class DocumentCreatedHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            event_args = adsk.core.DocumentEventArgs.cast(args)
            session = SessionManager.instance()
            if not session.is_protected:
                return
            if event_args.document:
                doc_name = event_args.document.name
                session.track_document(doc_name)
                AuditLogger.instance().log("DOC_CREATED", f"New document tracked: {doc_name}")
        except Exception:
            pass


class DocumentClosedHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            event_args = adsk.core.DocumentEventArgs.cast(args)
            session = SessionManager.instance()
            if not session.is_protected:
                return
            doc_name = event_args.document.name if event_args.document else "Unknown"
            AuditLogger.instance().log("DOC_CLOSED", f"Document closed: {doc_name}")
        except Exception:
            pass


class HandlerMonitorThread(threading.Thread):
    def __init__(self, stop_event: threading.Event, app: adsk.core.Application):
        super().__init__()
        self.daemon = True
        self._stop_event = stop_event
        self._app = app

    def run(self):
        while not self._stop_event.wait(config.HANDLER_CHECK_INTERVAL):
            session = SessionManager.instance()
            if not session.is_protected:
                continue
            try:
                self._app.fireCustomEvent(
                    config.CUSTOM_EVENT_HANDLER_CHECK, json.dumps({"check": True})
                )
            except Exception:
                try:
                    AuditLogger.instance().log(
                        "HANDLER_MONITOR_ERROR",
                        "Failed to fire handler check event",
                        "ERROR",
                    )
                except Exception:
                    pass
        try:
            AuditLogger.instance().log(
                "HANDLER_MONITOR_STOPPED",
                "Handler monitor thread exited",
                "WARNING",
            )
        except Exception:
            pass


class HandlerCheckCustomHandler(adsk.core.CustomEventHandler):
    def __init__(self, interceptor: "SaveInterceptor"):
        super().__init__()
        self._interceptor = interceptor

    def notify(self, args):
        try:
            session = SessionManager.instance()
            if not session.is_protected:
                return
            self._interceptor._verify_and_reattach()
        except Exception:
            try:
                AuditLogger.instance().log(
                    "HANDLER_CHECK_ERROR",
                    "Handler integrity check failed",
                    "ERROR",
                )
            except Exception:
                pass


class SaveInterceptor:
    def __init__(self):
        self._app = None
        self._handlers = []
        self._monitor_thread = None
        self._stop_event = None
        self._custom_event = None
        self._check_handler = None

    def activate(self, app: adsk.core.Application):
        self._app = app

        for event, handler_cls in (
            (app.documentSaving, DocumentSavingHandler),
            (app.documentOpened, DocumentOpenedHandler),
            (app.documentCreated, DocumentCreatedHandler),
            (app.documentClosed, DocumentClosedHandler),
        ):
            handler = handler_cls()
            event.add(handler)
            self._handlers.append((event, handler))

        self._custom_event = app.registerCustomEvent(config.CUSTOM_EVENT_HANDLER_CHECK)
        self._check_handler = HandlerCheckCustomHandler(self)
        self._custom_event.add(self._check_handler)

        self._stop_event = threading.Event()
        self._monitor_thread = HandlerMonitorThread(self._stop_event, app)
        self._monitor_thread.start()

    def deactivate(self):
        if self._stop_event:
            self._stop_event.set()
            if self._monitor_thread:
                self._monitor_thread.join(timeout=2)
            self._stop_event = None
            self._monitor_thread = None

        if not self._app:
            return

        try:
            if self._custom_event and self._check_handler:
                self._custom_event.remove(self._check_handler)
            self._app.unregisterCustomEvent(config.CUSTOM_EVENT_HANDLER_CHECK)
        except Exception:
            pass

        self._custom_event = None
        self._check_handler = None

        for event, handler in self._handlers:
            try:
                event.remove(handler)
            except Exception:
                pass
        self._handlers.clear()

    def _try_replace_handler(self, index, event, handler_cls):
        # Create a fresh handler instance after the original failed to re-register.
        new_handler = handler_cls()
        try:
            event.add(new_handler)
            self._handlers[index] = (event, new_handler)
            return handler_cls.__name__
        except Exception:
            return None

    def _verify_and_reattach(self):
        if not self._app:
            return

        reattached = []
        for i, (event, handler) in enumerate(self._handlers):
            try:
                event.remove(handler)
                event.add(handler)
            except Exception:
                name = self._try_replace_handler(i, event, handler.__class__)
                if name:
                    reattached.append(name)
                else:
                    AuditLogger.instance().log(
                        "HANDLER_LOST",
                        f"Failed to reattach handler: {handler.__class__.__name__}",
                        "CRITICAL",
                    )

        if reattached:
            AuditLogger.instance().log(
                "HANDLER_REATTACHED",
                f"Re-registered dropped handlers: {', '.join(reattached)}",
                "WARNING",
            )
